# Copyright (c) 2026, Dexciss and contributors
# For license information, please see license.txt

"""Compares the FIFO allocation a customer *should* have against the one the
Payment Ledger actually holds, and records every difference as a Payment
Reconciliation Mismatch row.

The report reads those rows. Nothing here touches the ledger -- raising the
Payment Reconciliation Redo is a separate, deliberate step.
"""

import traceback

import frappe
from frappe.utils import cint, flt, getdate, now_datetime

from agastya_agro.agastya_agro.reconciliation.desired_allocations import (
	DEFAULT_PRECISION,
	as_pair_map,
	get_actual_allocations,
	get_desired_allocations,
)


# Differences smaller than this are rounding dust from multi-currency and
# partial allocations, not something a user should be asked to act on.
MIN_DIFFERENCE = 0.01

WRONG_PAIRING = "Wrong Pairing"
MISSING_ALLOCATION = "Missing Allocation"
AMOUNT_MISMATCH = "Amount Mismatch"
UNALLOCATED_PAYMENT = "Unallocated Payment"


def diff_allocations(desired_pairs, actual_pairs, min_difference=MIN_DIFFERENCE):
	"""Diff two {(credit_voucher, debit_voucher): amount} maps.

	Pure function -- no database, no document writes -- so the classification
	rules can be tested directly.
	"""
	mismatches = []

	credits_seen_in_actual = {credit for credit, _debit in actual_pairs}

	for key in sorted(set(desired_pairs) | set(actual_pairs)):
		credit_voucher, debit_voucher = key
		desired = flt(desired_pairs.get(key, 0), DEFAULT_PRECISION)
		actual = flt(actual_pairs.get(key, 0), DEFAULT_PRECISION)
		difference = flt(desired - actual, DEFAULT_PRECISION)

		if abs(difference) < min_difference:
			continue

		if actual and not desired:
			mismatch_type = WRONG_PAIRING
		elif desired and not actual:
			# A payment absent from the ledger entirely is lying loose, which
			# reads very differently to an allocation that merely sits on the
			# wrong invoice.
			mismatch_type = (
				MISSING_ALLOCATION
				if credit_voucher in credits_seen_in_actual
				else UNALLOCATED_PAYMENT
			)
		else:
			mismatch_type = AMOUNT_MISMATCH

		mismatches.append(
			{
				"credit_voucher": credit_voucher,
				"debit_voucher": debit_voucher,
				"desired_allocated": desired,
				"actual_allocated": actual,
				"difference": difference,
				"mismatch_type": mismatch_type,
				# Every mismatch touching one payment is one move of money.
				"pair_group": credit_voucher,
			}
		)

	return mismatches


def chunk_date_windows(dates, max_days):
	"""Split dates into windows of at most `max_days`, oldest first.

	Payment Reconciliation Redo refuses a span wider than `redo_max_days`, but
	mismatches routinely reach back years -- so the report has to suggest several
	runs rather than one impossible one.
	"""
	dates = sorted({getdate(d) for d in dates if d})
	if not dates:
		return []

	max_days = cint(max_days) or 62
	windows = []
	start = dates[0]
	end = start

	for date in dates:
		# max_days counts inclusively, matching the Redo validation.
		if (date - start).days + 1 > max_days:
			windows.append((start, end))
			start = date
		end = date

	windows.append((start, end))
	return windows


def _voucher_meta(vouchers, customer, company):
	"""Posting date, amount and entry date for a set of vouchers, in one hit.

	`creation` minus `posting_date` is how far back-dated an invoice was, which
	is the single most useful column on the report -- it explains *why* the
	allocation went wrong.

	Restricted to this customer's own party rows. A Journal Entry can carry
	several parties, and the income/tax legs of an invoice carry none, so
	summing without the party filter would report somebody else's figure.
	"""
	if not vouchers:
		return {}

	rows = frappe.db.sql(
		"""
		SELECT
			gle.voucher_type,
			gle.voucher_no,
			MIN(gle.posting_date) AS posting_date,
			SUM(gle.debit) AS debit,
			SUM(gle.credit) AS credit
		FROM `tabGL Entry` gle
		WHERE gle.voucher_no IN %(vouchers)s
			AND gle.company = %(company)s
			AND gle.party_type = 'Customer'
			AND gle.party = %(party)s
			AND gle.is_cancelled = 0
		GROUP BY gle.voucher_type, gle.voucher_no
		""",
		{"vouchers": tuple(vouchers), "company": company, "party": customer},
		as_dict=True,
	)

	entered_on = _entered_on({(row.voucher_type, row.voucher_no) for row in rows})

	meta = {}
	for row in rows:
		created = entered_on.get(row.voucher_no)
		backdated = 0
		if row.posting_date and created:
			backdated = max(0, (getdate(created) - getdate(row.posting_date)).days)

		meta[row.voucher_no] = {
			"voucher_type": row.voucher_type,
			"voucher_no": row.voucher_no,
			"posting_date": row.posting_date,
			"amount": flt(row.debit) or flt(row.credit),
			"backdated_by_days": backdated,
		}

	return meta


def receivable_account_for(customer, company, party_type="Customer"):
	"""The receivable account this customer's balances actually sit in.

	Taken from the customer's own ledger rather than the single account on Auto
	Payment Reconciliation. Agastya runs three receivable accounts and the
	configured one covers a handful of customers, so copying it onto every Redo
	would point almost all of them at an account holding none of their entries --
	the reconciliation would then find nothing and the "fix" would silently do
	nothing at all.

	Where a customer spans more than one account, the busiest wins.
	"""
	row = frappe.db.sql(
		"""
		SELECT account
		FROM `tabPayment Ledger Entry`
		WHERE company = %(company)s
			AND party_type = %(party_type)s
			AND party = %(party)s
			AND delinked = 0
			AND account IS NOT NULL
			AND account != ''
		GROUP BY account
		ORDER BY COUNT(*) DESC
		LIMIT 1
		""",
		{"company": company, "party_type": party_type, "party": customer},
		as_dict=True,
	)

	return row[0].account if row else None


def _entered_on(typed_vouchers):
	"""When each voucher document was actually created, keyed by voucher name.

	Read from the source document, NOT from GL Entry. Reposting a voucher
	rewrites its GL rows with a fresh creation timestamp, so measuring against GL
	reports the date of the last repost instead of the date the entry was made --
	which turns an invoice booked 55 days late into one that looks 579 days late.
	"""
	by_type = {}
	for voucher_type, voucher_no in typed_vouchers:
		if voucher_type:
			by_type.setdefault(voucher_type, []).append(voucher_no)

	created = {}
	for voucher_type, names in by_type.items():
		if not frappe.db.table_exists(voucher_type):
			continue
		for row in frappe.get_all(
			voucher_type,
			filters={"name": ("in", names)},
			fields=["name", "creation"],
		):
			created[row.name] = row.creation

	return created


def scan_customer(customer, company, redo_max_days=62, scanned_on=None, mismatch_from=None):
	"""Scan one customer and sync their mismatch rows. Returns rows written.

	`mismatch_from` limits what is reported to allocations whose *payment* falls
	on or after that date. Re-reconciling years of history is a job nobody wants,
	so the business draws a line and only corrects what is recent enough to be
	worth disturbing. FIFO still reads the customer's full history -- the desired
	allocation stays correct -- the cut-off only decides what is worth acting on.
	"""
	scanned_on = scanned_on or now_datetime()

	desired = as_pair_map(get_desired_allocations(customer, company))
	actual, actual_meta = get_actual_allocations(customer, company)

	mismatches = diff_allocations(desired, actual)

	# Every existing row for this customer in one hit. Looking each one up
	# individually turns a scan into a full table scan per mismatch, which is
	# unusable once this table holds a few hundred thousand rows.
	existing = {
		(row.credit_voucher, row.debit_voucher): row
		for row in frappe.get_all(
			"Payment Reconciliation Mismatch",
			filters={"company": company, "customer": customer},
			fields=["name", "credit_voucher", "debit_voucher", "status"],
		)
	}

	if not mismatches:
		# Customer is clean now -- close anything still standing against them.
		_close_resolved(existing, set(), scanned_on)
		return 0

	vouchers = set()
	for row in mismatches:
		vouchers.add(row["credit_voucher"])
		vouchers.add(row["debit_voucher"])
	meta = _voucher_meta(vouchers, customer, company)

	if mismatch_from:
		# Keep only what is recent enough to be worth correcting, judged on the
		# payment date -- that is what a Redo actually unreconciles, so anything
		# older would drag old settled history back open.
		cutoff = getdate(mismatch_from)
		mismatches = [
			row
			for row in mismatches
			if meta.get(row["credit_voucher"], {}).get("posting_date")
			and getdate(meta[row["credit_voucher"]]["posting_date"]) >= cutoff
		]

		if not mismatches:
			_drop_rows(existing.values(), keep_keys=set())
			return 0

	receivable_account = receivable_account_for(customer, company)

	# One suggested window per payment date cluster, sized to survive the Redo
	# validation.
	credit_dates = [
		meta.get(row["credit_voucher"], {}).get("posting_date") for row in mismatches
	]
	windows = chunk_date_windows(credit_dates, redo_max_days)

	def window_for(date):
		if not date:
			return None, None
		date = getdate(date)
		for start, end in windows:
			if start <= date <= end:
				return start, end
		return date, date

	keep_keys = set()

	for row in mismatches:
		credit_meta = meta.get(row["credit_voucher"], {})
		debit_meta = meta.get(row["debit_voucher"], {})
		pair_meta = actual_meta.get((row["credit_voucher"], row["debit_voucher"]), {})

		from_date, to_date = window_for(credit_meta.get("posting_date"))

		values = {
			"company": company,
			"customer": customer,
			"mismatch_type": row["mismatch_type"],
			"pair_group": row["pair_group"],
			"debit_voucher_type": debit_meta.get("voucher_type")
			or pair_meta.get("debit_voucher_type"),
			"debit_voucher": row["debit_voucher"],
			"debit_posting_date": debit_meta.get("posting_date"),
			"debit_amount": debit_meta.get("amount"),
			"backdated_by_days": debit_meta.get("backdated_by_days") or 0,
			"credit_voucher_type": credit_meta.get("voucher_type")
			or pair_meta.get("credit_voucher_type"),
			"credit_voucher": row["credit_voucher"],
			"credit_posting_date": credit_meta.get("posting_date"),
			"credit_amount": credit_meta.get("amount"),
			"actual_allocated": row["actual_allocated"],
			"desired_allocated": row["desired_allocated"],
			"difference": row["difference"],
			"suggested_from_date": from_date,
			"suggested_to_date": to_date,
			"receivable_account": receivable_account,
			"scanned_on": scanned_on,
		}

		key = (row["credit_voucher"], row["debit_voucher"])
		keep_keys.add(key)

		match = existing.get(key)
		if not match:
			frappe.get_doc(
				dict(doctype="Payment Reconciliation Mismatch", status="Open", **values)
			).insert(ignore_permissions=True)
			continue

		# Ignored stays ignored -- a human ruled on it and a re-scan must not
		# overrule that. Everything else follows the ledger.
		if match.status == "Ignored":
			values.pop("mismatch_type", None)
		elif match.status == "Resolved":
			# It was fixed and has gone wrong again (a Redo undone, or new
			# back-dated data recreating the same pairing). Without this the row
			# stays Resolved and the problem never reappears on the report.
			values["status"] = "Open"

		frappe.db.set_value(
			"Payment Reconciliation Mismatch", match.name, values, update_modified=True
		)

	if mismatch_from:
		# Rows that fell outside the window are not "resolved" -- nobody fixed
		# them, they are simply not being tracked any more. Marking them Resolved
		# would claim work that never happened, so they are removed instead.
		_drop_rows(existing.values(), keep_keys)
	else:
		_close_resolved(existing, keep_keys, scanned_on)

	return len(mismatches)


def _drop_rows(rows, keep_keys):
	"""Delete mismatch rows that are no longer in scope."""
	stale = [
		row.name
		for row in rows
		if (row.credit_voucher, row.debit_voucher) not in keep_keys
	]

	if not stale:
		return

	frappe.db.sql(
		"""DELETE FROM `tabPayment Reconciliation Mismatch` WHERE name IN %(names)s""",
		{"names": tuple(stale)},
	)


def _close_resolved(existing, keep_keys, scanned_on):
	"""Mark rows that no longer mismatch as Resolved.

	Kept rather than deleted: 'this was wrong in June and a Redo fixed it' is
	exactly the evidence the client asked for when they said they wanted
	trustworthy reports.

	Works off the rows already fetched for the upsert, so closing costs no extra
	read.
	"""
	stale = [
		row.name
		for key, row in existing.items()
		if key not in keep_keys and row.status in ("Open", "Redo Created")
	]

	if not stale:
		return

	frappe.db.sql(
		"""
		UPDATE `tabPayment Reconciliation Mismatch`
		SET status = 'Resolved', difference = 0, scanned_on = %(scanned_on)s, modified = %(scanned_on)s
		WHERE name IN %(names)s
		""",
		{"scanned_on": scanned_on, "names": tuple(stale)},
	)


def get_customers_with_ledger_activity(company, from_date=None, changed_since=None):
	"""Customers worth scanning.

	Both filters narrow WHO gets scanned, never how much history is read for
	them. That distinction matters: FIFO is a running allocation, so reading a
	customer's ledger from a cut-off date would leave the engine blind to what
	was already outstanding, and every payment that clears an older invoice would
	be reported as a wrong allocation. Each customer selected here is still
	diffed against their complete history.

	`from_date`     -- ignore customers with no posting activity since then.
	`changed_since` -- ignore customers whose ledger has not been touched since
	                   the last scan. This is the one that makes a nightly run
	                   cheap; on a settled ledger most customers change never.
	"""
	conditions = [
		"ple.company = %(company)s",
		"ple.party_type = 'Customer'",
		"ple.delinked = 0",
		"ple.party IS NOT NULL",
		"ple.party != ''",
	]
	values = {"company": company}

	if from_date:
		conditions.append("ple.posting_date >= %(from_date)s")
		values["from_date"] = from_date

	if changed_since:
		conditions.append("ple.modified >= %(changed_since)s")
		values["changed_since"] = changed_since

	rows = frappe.db.sql(
		f"""
		SELECT DISTINCT ple.party
		FROM `tabPayment Ledger Entry` ple
		WHERE {" AND ".join(conditions)}
		""",
		values,
		as_dict=True,
	)

	return [row.party for row in rows]


def scan_reconciliation_mismatches(company=None, customers=None, full=False):
	"""Entry point for the scheduler and the report's Refresh Scan button.

	Scope, in order of precedence:
	  - an explicit `customers` list scans exactly those
	  - `full=True` scans everyone due, ignoring the incremental watermark
	  - otherwise the settings decide (Scan Customers Active From + Incremental)

	One customer per commit, failures logged and stepped over -- a single bad
	party must not cost the whole run, which is the same shape
	process_auto_reconciliation already uses.
	"""
	config = frappe.get_single("Auto Payment Reconciliation")
	company = company or config.company

	if not company:
		frappe.throw("Set a Company on Auto Payment Reconciliation first")

	redo_max_days = cint(config.redo_max_days) or 62
	mismatch_from = config.scan_from_date

	if isinstance(customers, str):
		customers = frappe.parse_json(customers)

	explicit = bool(customers)
	scanned_on = now_datetime()

	if not customers:
		# An explicit customer list always wins -- "re-scan these two" must scan
		# them whether or not their ledger moved.
		changed_since = None
		if cint(config.incremental_scan) and not full:
			changed_since = config.last_scan_completed_on

		customers = get_customers_with_ledger_activity(
			company,
			from_date=config.scan_from_date,
			changed_since=changed_since,
		)

		# Anything that errored last time is owed a retry. Its ledger may not have
		# changed since, so an incremental pass would otherwise never look at it
		# again.
		customers = list(dict.fromkeys(list(customers) + _pending_retry(config)))

	scanned = 0
	found = 0
	failed = []

	for customer in customers:
		try:
			found += scan_customer(
				customer, company, redo_max_days, scanned_on, mismatch_from=mismatch_from
			)
			scanned += 1
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			failed.append(customer)
			frappe.log_error(
				title=f"Reconciliation mismatch scan failed for {customer}",
				message=traceback.format_exc(),
			)

	# Only a sweep of everyone due may move the watermark. Advancing it after a
	# two-customer spot check would make the next incremental run skip everything
	# that changed in between.
	#
	# Failures do not hold the watermark back -- one permanently broken customer
	# would otherwise force a full scan every night forever. They are carried in
	# the retry list instead, so they are still picked up next run.
	if not explicit:
		frappe.db.set_single_value(
			"Auto Payment Reconciliation",
			{
				"last_scan_completed_on": scanned_on,
				"pending_retry": frappe.as_json(failed) if failed else None,
			},
		)
		frappe.db.commit()

	return {"customers": scanned, "mismatches": found, "failed": len(failed)}


def _pending_retry(config):
	"""Customers that errored on the previous run and are owed another attempt."""
	if not config.get("pending_retry"):
		return []

	try:
		return frappe.parse_json(config.pending_retry) or []
	except Exception:
		return []


@frappe.whitelist()
def create_redos(company=None, customers=None):
	"""Raise one Payment Reconciliation Redo per customer per suggested window.

	Deliberately left as drafts. The scan is new, and nothing should unreconcile
	a live ledger until somebody has looked at what it proposes -- submitting is
	the user's decision, not this function's.
	"""
	frappe.only_for(("Accounts Manager", "System Manager"))

	config = frappe.get_single("Auto Payment Reconciliation")
	company = company or config.company

	if isinstance(customers, str):
		customers = frappe.parse_json(customers)
	if not customers:
		return {"created": [], "skipped": []}

	created = []
	skipped = []

	for customer in customers:
		rows = frappe.get_all(
			"Payment Reconciliation Mismatch",
			filters={
				"company": company,
				"customer": customer,
				"status": "Open",
			},
			fields=["name", "suggested_from_date", "suggested_to_date", "receivable_account"],
		)

		if not rows:
			skipped.append(customer)
			continue

		# The account recorded against the customer's own entries, not the single
		# default on the settings -- that one matches almost nobody, and a Redo
		# pointed at the wrong account reconciles nothing while reporting success.
		account = next((row.receivable_account for row in rows if row.receivable_account), None)
		account = account or receivable_account_for(customer, company) or config.receivable_payable_account

		windows = {}
		for row in rows:
			if not (row.suggested_from_date and row.suggested_to_date):
				continue
			windows.setdefault((row.suggested_from_date, row.suggested_to_date), []).append(row.name)

		for (from_date, to_date), mismatch_names in sorted(windows.items()):
			try:
				redo = frappe.get_doc(
					{
						"doctype": "Payment Reconciliation Redo",
						"company": company,
						"party_type": "Customer",
						"party": customer,
						"from_date": from_date,
						"to_date": to_date,
						"receivable_payable_account": account,
						"cost_center": config.cost_center,
						"bank_cash_account": config.bank_cash_account,
					}
				)
				redo.insert(ignore_permissions=True)

				for name in mismatch_names:
					frappe.db.set_value(
						"Payment Reconciliation Mismatch",
						name,
						{"redo": redo.name, "status": "Redo Created"},
						update_modified=True,
					)

				created.append(redo.name)
				frappe.db.commit()
			except Exception:
				frappe.db.rollback()
				frappe.log_error(
					title=f"Could not create Redo for {customer} {from_date} to {to_date}",
					message=traceback.format_exc(),
				)
				skipped.append(customer)

	return {"created": created, "skipped": skipped}


@frappe.whitelist()
def enqueue_scan(company=None, customers=None, full=False):
	"""Queued from the report. Long queue -- a full-history scan is not quick."""
	frappe.only_for(("Accounts Manager", "System Manager"))

	frappe.enqueue(
		scan_reconciliation_mismatches,
		queue="long",
		timeout=7200,
		full=cint(full),
		company=company,
		customers=customers,
	)

	return "Queued"
