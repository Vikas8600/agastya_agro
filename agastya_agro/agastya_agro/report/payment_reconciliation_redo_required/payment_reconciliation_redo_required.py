# Copyright (c) 2026, Dexciss and contributors
# For license information, please see license.txt

"""Which customers need a Payment Reconciliation Redo, and why.

Reads the Payment Reconciliation Mismatch rows written by the scan. The scan
does the expensive full-history FIFO work; this report only aggregates, so it
stays fast enough to open on demand.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate


# Detail rows returned before truncating. Summary is unbounded -- it is one row
# per customer, so it stays small however bad the data is.
DETAIL_ROW_LIMIT = 2000


def execute(filters=None):
	filters = frappe._dict(filters or {})

	# Cleared up front so a truncation warning from an earlier run in this worker
	# can never leak onto a later, complete result.
	frappe.flags.mismatch_detail_truncated = False

	if not filters.company:
		return get_columns(filters), []

	if filters.get("view") == "Detail":
		data = get_detail_data(filters)
	else:
		data = get_summary_data(filters)

	return get_columns(filters), data, get_message(filters), get_chart(data, filters)


def get_conditions(filters):
	conditions = ["m.company = %(company)s"]
	values = {"company": filters.company}

	if filters.get("customer"):
		customers = filters.customer
		if isinstance(customers, str):
			customers = [c.strip() for c in customers.split(",") if c.strip()]
		if customers:
			conditions.append("m.customer IN %(customers)s")
			values["customers"] = tuple(customers)

	if filters.get("customer_group"):
		conditions.append(
			"m.customer IN (SELECT name FROM `tabCustomer` WHERE customer_group = %(customer_group)s)"
		)
		values["customer_group"] = filters.customer_group

	if filters.get("mismatch_type"):
		types = filters.mismatch_type
		if isinstance(types, str):
			types = [t.strip() for t in types.split(",") if t.strip()]
		if types:
			conditions.append("m.mismatch_type IN %(mismatch_types)s")
			values["mismatch_types"] = tuple(types)

	if filters.get("upto_date"):
		conditions.append("m.credit_posting_date <= %(upto_date)s")
		values["upto_date"] = filters.upto_date

	if cint(filters.get("backdated_beyond")):
		conditions.append("m.backdated_by_days >= %(backdated_beyond)s")
		values["backdated_beyond"] = cint(filters.backdated_beyond)

	min_amount = flt(filters.get("min_amount"))
	if min_amount:
		conditions.append("ABS(m.difference) >= %(min_amount)s")
		values["min_amount"] = min_amount

	# Build one allowed-status set rather than stacking conditions. Stacking let
	# "Redo Status = Pending" (status = Open) fight "Show Ignored" (status !=
	# Ignored), so ticking Show Ignored on the default filter silently did
	# nothing -- the two clauses could never both be true.
	redo_status = filters.get("redo_status") or "Pending"
	if redo_status == "Pending":
		allowed = ["Open"]
	elif redo_status == "Redo Created":
		allowed = ["Redo Created"]
	else:
		# "All" means all of the live states plus the history of fixed ones.
		allowed = ["Open", "Redo Created", "Resolved"]

	if filters.get("show_ignored"):
		allowed.append("Ignored")

	conditions.append("m.status IN %(statuses)s")
	values["statuses"] = tuple(allowed)

	return " AND ".join(conditions), values


def get_summary_data(filters):
	where, values = get_conditions(filters)

	rows = frappe.db.sql(
		f"""
		SELECT
			m.customer,
			m.customer_name,
			COUNT(*) AS mismatch_count,
			SUM(CASE WHEN m.difference > 0 THEN m.difference ELSE 0 END) AS impacted_amount,
			SUM(CASE WHEN m.mismatch_type = 'Wrong Pairing' THEN 1 ELSE 0 END) AS wrong_pairing,
			SUM(CASE WHEN m.mismatch_type = 'Missing Allocation' THEN 1 ELSE 0 END) AS missing_allocation,
			SUM(CASE WHEN m.mismatch_type = 'Amount Mismatch' THEN 1 ELSE 0 END) AS amount_mismatch,
			SUM(CASE WHEN m.mismatch_type = 'Unallocated Payment' THEN 1 ELSE 0 END) AS unallocated_payment,
			MIN(m.debit_posting_date) AS oldest_affected_date,
			MAX(m.backdated_by_days) AS max_backdated_days,
			MIN(CASE WHEN m.actual_allocated > m.desired_allocated THEN m.debit_posting_date END) AS money_sitting_on,
			MIN(CASE WHEN m.desired_allocated > m.actual_allocated THEN m.debit_posting_date END) AS should_sit_on,
			COUNT(DISTINCT m.suggested_from_date) AS suggested_runs,
			MIN(m.suggested_from_date) AS first_window_from,
			MIN(m.suggested_to_date) AS first_window_to,
			MAX(m.redo) AS last_redo,
			MAX(m.scanned_on) AS scanned_on
		FROM `tabPayment Reconciliation Mismatch` m
		WHERE {where}
		GROUP BY m.customer, m.customer_name
		""",
		values,
		as_dict=True,
	)

	# One lookup for every Redo referenced, rather than one per customer row --
	# on a full company that is thousands of queries saved per refresh.
	redo_names = {row.last_redo for row in rows if row.last_redo}
	redo_status = (
		dict(
			frappe.get_all(
				"Payment Reconciliation Redo",
				filters={"name": ("in", list(redo_names))},
				fields=["name", "status"],
				as_list=True,
			)
		)
		if redo_names
		else {}
	)

	as_on = getdate(filters.get("upto_date") or nowdate())

	for row in rows:
		# Money parked on a newer invoice than it belongs to is exactly what
		# skews the receivable ageing report -- the number the client is
		# actually complaining about.
		row["ageing_shift"] = 0
		if row.money_sitting_on and row.should_sit_on:
			# Money parked on a newer invoice than it belongs to: the distance
			# between the two is how far the ageing is out.
			row["ageing_shift"] = (getdate(row.money_sitting_on) - getdate(row.should_sit_on)).days
		elif row.should_sit_on:
			# Nothing is over-allocated -- the payment was simply never applied.
			# The old invoice is ageing when it should not exist at all, so the
			# distortion is its full age. Without this branch these customers
			# score zero and sort to the bottom, which is backwards: an unapplied
			# payment against a four-year-old bill is the worst case there is.
			row["ageing_shift"] = (as_on - getdate(row.should_sit_on)).days

		row["redo_status"] = redo_status.get(row.last_redo, "Not Raised") if row.last_redo else "Not Raised"
		# Pass the customer's earliest window. Without dates the Redo opens blank
		# and throws "From Date and To Date are required" the moment it is saved.
		row["action"] = _redo_button(row.customer, row.first_window_from, row.first_window_to)

	# Ranked by how badly the ageing is distorted, not by rupees. A customer can
	# have hundreds of mismatched pairs worth lakhs and still age correctly --
	# sorting by amount buries the ones whose reports are actually lying.
	rows.sort(
		key=lambda r: (abs(cint(r.get("ageing_shift"))), flt(r.get("impacted_amount"))),
		reverse=True,
	)

	return rows


def get_detail_data(filters):
	where, values = get_conditions(filters)

	# One over the limit, so we can tell "exactly full" from "there is more".
	limit = DETAIL_ROW_LIMIT + 1

	rows = frappe.db.sql(
		f"""
		SELECT
			m.name,
			m.customer,
			m.customer_name,
			m.mismatch_type,
			m.debit_voucher_type,
			m.debit_voucher,
			m.debit_posting_date,
			m.debit_amount,
			m.backdated_by_days,
			m.credit_voucher_type,
			m.credit_voucher,
			m.credit_posting_date,
			m.credit_amount,
			m.actual_allocated,
			m.desired_allocated,
			m.difference,
			m.suggested_from_date,
			m.suggested_to_date,
			m.redo,
			m.status
		FROM `tabPayment Reconciliation Mismatch` m
		WHERE {where}
		ORDER BY m.customer ASC, m.credit_posting_date ASC, m.debit_posting_date ASC
		LIMIT {limit}
		""",
		values,
		as_dict=True,
	)

	# Detail is for investigating one customer, not for reading a whole company.
	# One back-dated entry cascades into dozens of rows, so an unfiltered company
	# runs to hundreds of thousands -- enough to hang the browser. Truncate, and
	# say so rather than silently showing a partial list as if it were complete.
	frappe.flags.mismatch_detail_truncated = len(rows) > DETAIL_ROW_LIMIT
	rows = rows[:DETAIL_ROW_LIMIT]

	for row in rows:
		row["action"] = _redo_button(row.customer, row.suggested_from_date, row.suggested_to_date)

	return rows


def _redo_button(customer, from_date=None, to_date=None):
	args = frappe.utils.escape_html(frappe.as_json({
		"customer": customer,
		"from_date": str(from_date) if from_date else None,
		"to_date": str(to_date) if to_date else None,
	}))

	return (
		f"<button class='btn btn-xs btn-default' data-redo='{args}'>{_('Create Redo')}</button>"
	)


def get_message(filters):
	"""Banner telling the user how stale these figures are.

	Read from the table rather than the cache -- a cache eviction would
	otherwise claim no scan had ever run on a site that scans nightly, and
	quietly imply the empty report meant "nothing wrong".
	"""
	scanned_on = frappe.db.get_value(
		"Payment Reconciliation Mismatch",
		{"company": filters.company},
		"MAX(scanned_on)",
	)

	if not scanned_on:
		return _("No scan has run yet. Use <b>Refresh Scan</b> to build this list.")

	message = _(
		"Last scanned {0}. These figures are as of that scan, not live &mdash; "
		"entries posted since then are not included."
	).format(frappe.format_value(scanned_on, {"fieldtype": "Datetime"}))

	if frappe.flags.get("mismatch_detail_truncated"):
		message += "<br>" + _(
			"<b>Showing the first {0} rows only.</b> Filter by customer to see a complete list."
		).format(DETAIL_ROW_LIMIT)

	return message


def get_chart(data, filters):
	if filters.get("view") == "Detail" or not data:
		return None

	# Charted by ageing distortion, matching how the table is ranked. Charting
	# rupees instead would headline customers whose ageing is already correct.
	top = [row for row in data if cint(row.get("ageing_shift"))][:10]

	if not top:
		return None

	return {
		"data": {
			"labels": [row.get("customer_name") or row.get("customer") for row in top],
			"datasets": [
				{
					"name": _("Ageing Shift (Days)"),
					"values": [cint(row.get("ageing_shift")) for row in top],
				}
			],
		},
		"type": "bar",
		"colors": ["#e24c4c"],
	}


def get_columns(filters):
	if filters.get("view") == "Detail":
		return [
			{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 110},
			{"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 160},
			{"label": _("Mismatch Type"), "fieldname": "mismatch_type", "fieldtype": "Data", "width": 140},
			{"label": _("Invoice Type"), "fieldname": "debit_voucher_type", "fieldtype": "Data", "width": 110},
			{"label": _("Invoice"), "fieldname": "debit_voucher", "fieldtype": "Dynamic Link", "options": "debit_voucher_type", "width": 150},
			{"label": _("Invoice Date"), "fieldname": "debit_posting_date", "fieldtype": "Date", "width": 100},
			{"label": _("Invoice Amount"), "fieldname": "debit_amount", "fieldtype": "Currency", "width": 120},
			{"label": _("Backdated By (Days)"), "fieldname": "backdated_by_days", "fieldtype": "Int", "width": 100},
			{"label": _("Payment Type"), "fieldname": "credit_voucher_type", "fieldtype": "Data", "width": 110},
			{"label": _("Payment"), "fieldname": "credit_voucher", "fieldtype": "Dynamic Link", "options": "credit_voucher_type", "width": 150},
			{"label": _("Payment Date"), "fieldname": "credit_posting_date", "fieldtype": "Date", "width": 100},
			{"label": _("Payment Amount"), "fieldname": "credit_amount", "fieldtype": "Currency", "width": 120},
			{"label": _("Actual Allocated"), "fieldname": "actual_allocated", "fieldtype": "Currency", "width": 120},
			{"label": _("Desired Allocated"), "fieldname": "desired_allocated", "fieldtype": "Currency", "width": 120},
			{"label": _("Difference"), "fieldname": "difference", "fieldtype": "Currency", "width": 120},
			{"label": _("Suggested From"), "fieldname": "suggested_from_date", "fieldtype": "Date", "width": 110},
			{"label": _("Suggested To"), "fieldname": "suggested_to_date", "fieldtype": "Date", "width": 110},
			{"label": _("Redo"), "fieldname": "redo", "fieldtype": "Link", "options": "Payment Reconciliation Redo", "width": 140},
			{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
			{"label": _("Action"), "fieldname": "action", "fieldtype": "HTML", "width": 110},
		]

	return [
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 110},
		{"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 180},
		{"label": _("Mismatched Pairs"), "fieldname": "mismatch_count", "fieldtype": "Int", "width": 120},
		{"label": _("Impacted Amount"), "fieldname": "impacted_amount", "fieldtype": "Currency", "width": 130},
		{"label": _("Wrong Pairing"), "fieldname": "wrong_pairing", "fieldtype": "Int", "width": 110},
		{"label": _("Missing Allocation"), "fieldname": "missing_allocation", "fieldtype": "Int", "width": 130},
		{"label": _("Amount Mismatch"), "fieldname": "amount_mismatch", "fieldtype": "Int", "width": 130},
		{"label": _("Unallocated Payment"), "fieldname": "unallocated_payment", "fieldtype": "Int", "width": 140},
		{"label": _("Oldest Affected"), "fieldname": "oldest_affected_date", "fieldtype": "Date", "width": 110},
		{"label": _("Max Backdated (Days)"), "fieldname": "max_backdated_days", "fieldtype": "Int", "width": 120},
		{"label": _("Money Sitting On"), "fieldname": "money_sitting_on", "fieldtype": "Date", "width": 120},
		{"label": _("Should Sit On"), "fieldname": "should_sit_on", "fieldtype": "Date", "width": 120},
		{"label": _("Ageing Shift (Days)"), "fieldname": "ageing_shift", "fieldtype": "Int", "width": 130},
		{"label": _("Suggested Redo Runs"), "fieldname": "suggested_runs", "fieldtype": "Int", "width": 130},
		{"label": _("Last Redo"), "fieldname": "last_redo", "fieldtype": "Link", "options": "Payment Reconciliation Redo", "width": 140},
		{"label": _("Redo Status"), "fieldname": "redo_status", "fieldtype": "Data", "width": 120},
		{"label": _("Action"), "fieldname": "action", "fieldtype": "HTML", "width": 110},
	]
