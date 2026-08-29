# Copyright (c) 2026, Dexciss and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import add_months, flt, formatdate, get_first_day, getdate, nowdate

BUCKETS = [
	("0-30", 0, 30),
	("31-60", 31, 60),
	("61-90", 61, 90),
	("91-120", 91, 120),
	("121-150", 121, 150),
	("151-180", 151, 180),
	("> 181", 181, None),
]

# Sales history covers the fiscal year the report is run in and the four before it.
FY_SPAN = 5

LAKH = 100000

# Buckets counted as long overdue.
LONG_OVERDUE = ("121-150", "151-180", "> 181")


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)

	fiscal_years = get_fiscal_years(filters)
	return get_columns(filters, fiscal_years), get_data(filters, fiscal_years)


LINK_FILTERS = (
	("company", "Company"),
	("customer", "Customer"),
	("customer_group", "Customer Group"),
	("territory", "Territory"),
	("sales_person", "Sales Person"),
)


def validate_filters(filters):
	if not filters.company:
		frappe.throw(_("Please select a Company."))

	if not filters.as_on_date:
		frappe.throw(_("Please select an As On Date."))

	# Prepared Report and API callers bypass the Link field's own lookup, so the
	# references are checked here rather than assumed valid.
	for fieldname, doctype in LINK_FILTERS:
		value = filters.get(fieldname)
		if value and not frappe.db.exists(doctype, value):
			frappe.throw(_("{0} {1} does not exist.").format(_(doctype), frappe.bold(value)))

	# Every age is measured back from this date, so a date still to come would
	# report ages nobody has reached yet.
	if getdate(filters.as_on_date) > getdate(nowdate()):
		frappe.throw(
			_("As On Date {0} is in the future. Balances can only be struck up to {1}.").format(
				formatdate(filters.as_on_date), formatdate(nowdate())
			)
		)

	if not get_current_fiscal_year(filters):
		frappe.throw(
			_("No Fiscal Year covers {0}. Create one before running this report.").format(
				formatdate(filters.as_on_date)
			)
		)

	if filters.os_type and filters.os_type not in ("Dr", "Cr"):
		frappe.throw(_("O/s Type must be either Dr or Cr."))

	if filters.ageing_based_on and filters.ageing_based_on not in ("Posting Date", "Due Date"):
		frappe.throw(_("Ageing Based On must be either Posting Date or Due Date."))


def get_current_fiscal_year(filters):
	rows = frappe.db.sql(
		"""
		select name, year_start_date, year_end_date
		from `tabFiscal Year`
		where %(as_on)s between year_start_date and year_end_date
		order by year_start_date desc
		limit 1
	""",
		{"as_on": filters.as_on_date},
		as_dict=1,
	)
	return rows[0] if rows else None


def get_fiscal_years(filters):
	"""The fiscal years whose sales get a column, oldest first."""
	current = get_current_fiscal_year(filters)
	return frappe.db.sql(
		"""
		select name, year_start_date, year_end_date
		from `tabFiscal Year`
		where year_start_date <= %(start)s
		order by year_start_date desc
		limit %(span)s
	""",
		{"start": current.year_start_date, "span": FY_SPAN},
		as_dict=1,
	)[::-1]


def get_data(filters, fiscal_years):
	customers = get_customers(filters)
	if not customers:
		# An empty grid reads as "nothing is outstanding", which is a very
		# different thing from "no customer answers these filters".
		frappe.throw(
			_("No customer matches the selected filters ({0}).").format(describe_filters(filters))
		)

	codes = list(customers)
	sales = get_fiscal_year_sales(filters, codes, fiscal_years)
	balances = get_balances(filters, codes)
	billed = get_billed_by_bucket(filters, codes)
	collected = get_collections(filters, codes)

	data = []
	for code in codes:
		customer = customers[code]
		balance = balances.get(code) or frappe._dict()
		closing = flt(balance.closing)
		opening = flt(balance.opening)

		row = {
			"customer": code,
			"customer_name": customer.customer_name,
			"place": customer.city,
			"sales_person": customer.sales_person,
			"sales_team": customer.sales_team,
			"sales_team_head": customer.sales_team_head,
			"opening": opening,
			"debit": flt(balance.debit),
			"credit": flt(balance.credit),
			"closing": closing,
			"os_type": "Dr" if closing >= 0 else "Cr",
			# A credit opening is not an old balance to chase, so it reads as nil.
			"old_balance": opening if opening > 0 else 0,
			"actual_collection": flt(collected.get(code)),
			"current_month_target": 0,
			"next_month_target": 0,
			"next_month_abs_target": 0,
		}

		for fy in fiscal_years:
			row[fy_fieldname(fy.name)] = flt(sales.get((code, fy.name))) / LAKH

		allocation = allocate_outstanding(billed.get(code) or {}, closing)
		for label, _start, _end in BUCKETS:
			row[bucket_fieldname(label)] = allocation[label]

		row["long_overdue"] = sum(allocation[label] for label in LONG_OVERDUE)

		if filters.os_type and row["os_type"] != filters.os_type:
			continue

		if filters.hide_nil_rows and not closing and not row["long_overdue"]:
			if not any(row.get(fy_fieldname(fy.name)) for fy in fiscal_years):
				continue

		data.append(row)

	return data


def is_narrowed(filters):
	"""Whether a filter has cut the customer list down to a subset worth naming."""
	return any(filters.get(fieldname) for fieldname, _doctype in LINK_FILTERS[1:])


def customer_condition(filters, column):
	"""Restrict a query to the customers on hand, but only when that pays off.

	Naming every customer turns an index range scan into one lookup per code,
	which on the ledger costs far more than reading the range once. Rows for
	customers outside the list are simply never looked up by the caller.
	"""
	if is_narrowed(filters):
		return "and {column} in %(customers)s".format(column=column)

	return ""


def describe_filters(filters):
	"""The optional filters actually in play, for use in an error message."""
	described = []
	for fieldname, _doctype in LINK_FILTERS:
		if fieldname == "company":
			continue
		if filters.get(fieldname):
			described.append("{0}: {1}".format(_(frappe.unscrub(fieldname)), filters.get(fieldname)))

	return ", ".join(described) or _("Company: {0}").format(filters.company)


def allocate_outstanding(billed, outstanding):
	"""Spread the closing balance across ageing buckets, newest first.

	Receipts are taken to clear the oldest invoices, so whatever is still
	outstanding belongs to the most recent billing. Each bucket absorbs at most
	what was billed into it; anything left over once every bucket is full is
	older than the invoices on hand and falls into the last bucket.
	"""
	allocation = {label: 0.0 for label, _s, _e in BUCKETS}
	if not outstanding:
		return allocation

	# A customer in credit is carrying an advance rather than a debt. It shows
	# against the newest bucket where there is billing to set it against, and
	# nowhere at all for a customer who has never been billed.
	if outstanding < 0:
		if billed:
			allocation[BUCKETS[0][0]] = outstanding
		return allocation

	remaining = outstanding
	for label, _start, _end in BUCKETS[:-1]:
		available = flt(billed.get(label))
		take = available if remaining > available else remaining
		allocation[label] = take
		remaining -= take
		if remaining <= 0:
			break

	last = BUCKETS[-1][0]
	spread = sum(allocation.values())
	if outstanding > spread:
		allocation[last] = outstanding - spread

	return allocation


def get_customers(filters):
	conditions = ["c.disabled = 0"]
	values = {}

	if filters.customer:
		conditions.append("c.name = %(customer)s")
		values["customer"] = filters.customer

	if filters.customer_group:
		conditions.append("c.customer_group = %(customer_group)s")
		values["customer_group"] = filters.customer_group

	if filters.territory:
		conditions.append("c.territory = %(territory)s")
		values["territory"] = filters.territory

	customers = {}
	for row in frappe.db.sql(
		"""
		select c.name, c.customer_name, c.city
		from `tabCustomer` c
		where {conditions}
		order by c.name
	""".format(conditions=" and ".join(conditions)),
		values,
		as_dict=1,
	):
		row.sales_person = ""
		row.sales_team = ""
		row.sales_team_head = ""
		customers[row.name] = row

	attach_sales_team(customers, filters)
	return customers


def attach_sales_team(customers, filters):
	"""Sales person, their team, and the team's own parent.

	The team is read from the Sales Team row rather than walked from the Sales
	Person tree, so a customer keeps the team it was assigned under even after
	the tree is reorganised. The head is the team's parent in the tree.
	"""
	if not customers:
		return

	team_rows = frappe.db.sql(
		"""
		select st.parent, st.sales_person, st.parent_sales_person
		from `tabSales Team` st
		where st.parenttype = 'Customer' and st.parent in %(customers)s
		order by st.idx
	""",
		{"customers": list(customers)},
		as_dict=1,
	)

	grouped = {}
	for row in team_rows:
		grouped.setdefault(row.parent, []).append(row)

	heads = get_team_heads({r.parent_sales_person for r in team_rows if r.parent_sales_person})

	selected = None
	if filters.sales_person:
		selected = get_sales_person_descendants(filters.sales_person)

	for code, rows in grouped.items():
		customer = customers[code]
		customer.sales_person = ", ".join(sorted({r.sales_person for r in rows if r.sales_person}))
		customer.sales_team = ", ".join(sorted({r.parent_sales_person for r in rows if r.parent_sales_person}))
		customer.sales_team_head = ", ".join(
			sorted({heads[r.parent_sales_person] for r in rows if heads.get(r.parent_sales_person)})
		)

	if selected is not None:
		for code in list(customers):
			rows = grouped.get(code) or []
			if not any(r.sales_person in selected for r in rows):
				del customers[code]


def get_team_heads(teams):
	if not teams:
		return {}

	return {
		row.name: row.parent_sales_person
		for row in frappe.db.sql(
			"""
			select name, parent_sales_person
			from `tabSales Person`
			where name in %(teams)s
		""",
			{"teams": list(teams)},
			as_dict=1,
		)
	}


def get_sales_person_descendants(sales_person):
	"""Every sales person at or under the selected node."""
	bounds = frappe.db.get_value("Sales Person", sales_person, ["lft", "rgt"], as_dict=1)
	if not bounds:
		return {sales_person}

	return set(
		frappe.db.sql_list(
			"""
		select name from `tabSales Person` where lft >= %(lft)s and rgt <= %(rgt)s
	""",
			{"lft": bounds.lft, "rgt": bounds.rgt},
		)
	)


def get_fiscal_year_sales(filters, customers, fiscal_years):
	"""Billed value per customer per fiscal year, credit notes left out.

	The year each invoice belongs to is decided in the select rather than by
	joining Fiscal Year, which has no index to join a date range on and would
	otherwise re-read the invoices once per year.
	"""
	if not fiscal_years:
		return {}

	values = {
		"company": filters.company,
		"as_on": filters.as_on_date,
		"start": fiscal_years[0].year_start_date,
		"customers": customers,
	}

	# Oldest year first, so each case only needs to name its own closing date.
	cases = []
	for index, fy in enumerate(fiscal_years):
		values["fy_end_{0}".format(index)] = fy.year_end_date
		values["fy_name_{0}".format(index)] = fy.name
		cases.append(
			"when si.posting_date <= %(fy_end_{0})s then %(fy_name_{0})s".format(index)
		)

	sales = {}
	for row in frappe.db.sql(
		"""
		select si.customer, case {cases} end as fiscal_year, sum(si.rounded_total) as amount
		from `tabSales Invoice` si
		where si.docstatus = 1
			and si.is_return = 0
			and si.company = %(company)s
			and si.posting_date between %(start)s and %(as_on)s
			{customer_condition}
		group by si.customer, fiscal_year
	""".format(
			cases=" ".join(cases),
			customer_condition=customer_condition(filters, "si.customer"),
		),
		values,
		as_dict=1,
	):
		sales[(row.customer, row.fiscal_year)] = flt(row.amount)

	return sales


def get_balances(filters, customers):
	"""Opening, movement and closing, struck from the start of the fiscal year.

	Split the way Trial Balance for Party splits it: one plain sum over the
	history before the year, another over the year to date. Reading the ledger
	twice this way beats one pass carrying a case expression per column, because
	the second half spans months rather than years. Closing is then arithmetic
	rather than a third trip over the whole ledger.
	"""
	fy = get_current_fiscal_year(filters)
	condition = customer_condition(filters, "gle.party")

	query = """
		select gle.party, sum(gle.debit) as debit, sum(gle.credit) as credit
		from `tabGL Entry` gle
		where gle.is_cancelled = 0
			and gle.party_type = 'Customer'
			and gle.party != ''
			and gle.company = %(company)s
			and {period}
			{customer_condition}
		group by gle.party
	"""

	values = {
		"company": filters.company,
		"fy_start": fy.year_start_date,
		"as_on": filters.as_on_date,
		"customers": customers,
	}

	balances = {}
	for row in frappe.db.sql(
		query.format(
			period=(
				"(gle.posting_date < %(fy_start)s"
				" or (gle.is_opening = 'Yes' and gle.posting_date <= %(as_on)s))"
			),
			customer_condition=condition,
		),
		values,
		as_dict=1,
	):
		balances[row.party] = frappe._dict(
			opening=flt(row.debit) - flt(row.credit), debit=0.0, credit=0.0
		)

	for row in frappe.db.sql(
		query.format(
			period=(
				"gle.posting_date between %(fy_start)s and %(as_on)s"
				" and gle.is_opening = 'No'"
			),
			customer_condition=condition,
		),
		values,
		as_dict=1,
	):
		balance = balances.setdefault(row.party, frappe._dict(opening=0.0, debit=0.0, credit=0.0))
		balance.debit = flt(row.debit)
		balance.credit = flt(row.credit)

	for balance in balances.values():
		balance.closing = balance.opening + balance.debit - balance.credit

	return balances


def get_billed_by_bucket(filters, customers):
	"""Invoiced value per customer per ageing bucket, credit notes left out.

	Age runs from the as-on date back to the invoice, so the buckets describe how
	long ago the customer was billed, or how long the invoice has been due when
	ageing on the due date. Invoices carrying no due date age from their posting
	date either way.
	"""
	aged_on = "ifnull(si.due_date, si.posting_date)" \
		if filters.ageing_based_on == "Due Date" else "si.posting_date"

	# The cases are tested in order, so each one only needs its upper bound. That
	# also lands an invoice that is not yet due in the youngest bucket instead of
	# dropping it out of the ageing altogether.
	cases = []
	for label, _start, end in BUCKETS:
		if end is None:
			cases.append("else '{label}'".format(label=label))
		else:
			cases.append("when age <= {end} then '{label}'".format(end=end, label=label))

	billed = {}
	for row in frappe.db.sql(
		"""
		select customer, case {cases} end as bucket, sum(amount) as amount
		from (
			select si.customer,
				datediff(%(as_on)s, {aged_on}) as age,
				si.rounded_total as amount
			from `tabSales Invoice` si
			where si.docstatus = 1
				and si.is_return = 0
				and si.company = %(company)s
				and si.posting_date <= %(as_on)s
				{customer_condition}
		) aged
		group by customer, bucket
	""".format(
			cases=" ".join(cases),
			aged_on=aged_on,
			customer_condition=customer_condition(filters, "si.customer"),
		),
		{"company": filters.company, "as_on": filters.as_on_date, "customers": customers},
		as_dict=1,
	):
		if row.bucket:
			billed.setdefault(row.customer, {})[row.bucket] = flt(row.amount)

	return billed


def get_collections(filters, customers):
	"""Receipts banked so far in the month the report is struck in."""
	collected = {}
	for row in frappe.db.sql(
		"""
		select pe.party, sum(pe.paid_amount) as amount
		from `tabPayment Entry` pe
		where pe.docstatus = 1
			and pe.payment_type = 'Receive'
			and pe.party_type = 'Customer'
			and pe.company = %(company)s
			and pe.posting_date between %(month_start)s and %(as_on)s
			{customer_condition}
		group by pe.party
	""".format(customer_condition=customer_condition(filters, "pe.party")),
		{
			"company": filters.company,
			"month_start": get_first_day(filters.as_on_date),
			"as_on": filters.as_on_date,
			"customers": customers,
		},
		as_dict=1,
	):
		collected[row.party] = flt(row.amount)

	return collected


def fy_fieldname(name):
	return "fy_{0}".format(name.replace("-", "_").replace(" ", "_").lower())


def bucket_fieldname(label):
	return "bucket_{0}".format(label.replace("> ", "over_").replace("-", "_"))


def get_columns(filters, fiscal_years):
	as_on = getdate(filters.as_on_date)
	this_month = as_on.strftime("%b")
	next_month = getdate(add_months(as_on, 1)).strftime("%b")

	columns = [
		{"label": _("Code"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 110},
		{"label": _("Name Of The Party"), "fieldname": "customer_name", "fieldtype": "Data", "width": 240},
		{"label": _("Place"), "fieldname": "place", "fieldtype": "Data", "width": 130},
		{"label": _("Sales Person"), "fieldname": "sales_person", "fieldtype": "Data", "width": 160},
		{"label": _("Sales Team"), "fieldname": "sales_team", "fieldtype": "Data", "width": 160},
		{"label": _("Sales Team Head"), "fieldname": "sales_team_head", "fieldtype": "Data", "width": 160},
	]

	for fy in fiscal_years:
		columns.append({
			"label": _("FY {0} Sales").format(fy.name),
			"fieldname": fy_fieldname(fy.name),
			"fieldtype": "Float",
			"precision": 2,
			"width": 110,
		})

	columns += [
		{"label": _("Opening"), "fieldname": "opening", "fieldtype": "Currency", "width": 120},
		{"label": _("Debit"), "fieldname": "debit", "fieldtype": "Currency", "width": 120},
		{"label": _("Credit"), "fieldname": "credit", "fieldtype": "Currency", "width": 120},
		{"label": _("Closing"), "fieldname": "closing", "fieldtype": "Currency", "width": 120},
		{"label": _("O/s Type"), "fieldname": "os_type", "fieldtype": "Data", "width": 80},
		{"label": _("Old Balance"), "fieldname": "old_balance", "fieldtype": "Currency", "width": 120},
	]

	for label, _start, _end in BUCKETS:
		columns.append({
			"label": _(label),
			"fieldname": bucket_fieldname(label),
			"fieldtype": "Currency",
			"width": 110,
		})

	columns += [
		{"label": _("> 121 Outstanding"), "fieldname": "long_overdue", "fieldtype": "Currency", "width": 130},
		{
			"label": _("{0}.Coll.Tgt").format(this_month),
			"fieldname": "current_month_target",
			"fieldtype": "Currency",
			"width": 120,
		},
		{
			"label": _("Actual Received Collection"),
			"fieldname": "actual_collection",
			"fieldtype": "Currency",
			"width": 160,
		},
		{
			"label": _("{0}.Coll.Tgt").format(next_month),
			"fieldname": "next_month_target",
			"fieldtype": "Currency",
			"width": 120,
		},
		{
			"label": _("{0}.ABS.Tgt").format(next_month),
			"fieldname": "next_month_abs_target",
			"fieldtype": "Currency",
			"width": 120,
		},
	]

	return columns
