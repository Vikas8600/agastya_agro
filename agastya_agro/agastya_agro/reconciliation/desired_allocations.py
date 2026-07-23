# Copyright (c) 2026, Dexciss and contributors
# For license information, please see license.txt

"""FIFO allocation engine.

Answers one question: given a customer's GL entries, which payment *should* be
allocated against which invoice, if allocation were done strictly oldest-first?

This is deliberately blind to what is actually reconciled in `tabPayment Ledger
Entry`. Comparing this output against the real allocations is what tells us a
customer needs a Payment Reconciliation Redo -- a back-dated invoice entered
after the fact shifts every downstream allocation, and nothing in stock ERPNext
notices.

The allocation order replicates
`desired_payment_reconciliation.build_invoice_centric_report` exactly:

  1. a positive opening balance consumes credits first
  2. a negative opening balance (advance) is consumed by invoices first
  3. receivables oldest-first, each drawing from the credit queue oldest-first

Any change to the order here changes the report too -- keep them in step, and
run test_desired_allocations.py, which asserts they agree.
"""

import frappe
from frappe.utils import flt

from agastya_agro.agastya_agro.report.desired_payment_reconciliation.desired_payment_reconciliation import (
	get_credit_entries,
	get_opening_balance,
	get_receivables,
)


# Allocations below this are rounding dust, not a reconciliation error.
DEFAULT_PRECISION = 2

# Sentinel used where an allocation has no real voucher on one side. Opening
# balance is an aggregate of everything before f_date, not a document, so it can
# never be handed to Unreconcile Payment.
OPENING = "__opening__"


def get_ledger_entries(customer, company, party_type="Customer", precision=DEFAULT_PRECISION):
	"""Every voucher on the customer's receivable sub-ledger, split into what they
	owe and what they have paid.

	Read from Payment Ledger Entry rather than GL Entry. The GL route needs each
	voucher type's effect on the receivable to be hand-modelled, and it missed
	two whole classes: credit notes (Sales Invoice rows on the credit side, worth
	hundreds of crores here) and customer refunds. Anything settled by a credit
	note therefore looked unpaid, and the customer was reported as mis-allocated
	when nothing was wrong.

	PLE is what ERPNext's own Payment Reconciliation works from, and it models
	every voucher type uniformly:

	  * a voucher's self row (voucher_no = against_voucher_no) is the document's
	    own effect -- positive for a receivable, negative for unapplied credit
	  * every other row is an allocation against some receivable

	So a voucher with a positive self row is something owed, and anything whose
	rows net negative is money received. Reversals net themselves out for free,
	which is why the totals are summed rather than counted.

	Returns (receivables, credits), each oldest-first.
	"""
	rows = frappe.db.sql(
		"""
		SELECT
			voucher_type,
			voucher_no,
			MIN(posting_date) AS posting_date,
			SUM(CASE WHEN voucher_no = against_voucher_no THEN amount ELSE 0 END) AS self_amount,
			SUM(amount) AS net_amount,
			MIN(creation) AS created_on
		FROM `tabPayment Ledger Entry`
		WHERE company = %(company)s
			AND party_type = %(party_type)s
			AND party = %(party)s
			AND delinked = 0
		GROUP BY voucher_type, voucher_no
		ORDER BY MIN(posting_date), MIN(creation)
		""",
		{"company": company, "party_type": party_type, "party": customer},
		as_dict=True,
	)

	receivables = []
	credits = []

	for row in rows:
		self_amount = flt(row.self_amount, precision)
		net_amount = flt(row.net_amount, precision)

		if self_amount > 0:
			# Something owed. The self row carries the original amount; the net is
			# what is still open after allocations.
			receivables.append(
				{
					"name": row.voucher_no,
					"voucher_type": row.voucher_type,
					"date": row.posting_date,
					"amount": self_amount,
				}
			)
		elif net_amount < 0:
			# Money received -- a payment, a credit journal, or a credit note.
			credits.append(
				{
					"name": row.voucher_no,
					"voucher_type": row.voucher_type,
					"date": row.posting_date,
					"amount": flt(-net_amount, precision),
				}
			)

	return receivables, credits


def get_desired_allocations(customer, company, f_date=None, t_date=None, precision=DEFAULT_PRECISION):
	"""FIFO allocation plan for one customer.

	Called with no dates (the mismatch scan does this) it walks the customer's
	full history, so the opening balance is zero and every allocation is a real
	voucher pair. Called with a window (the report does this) it can also emit
	rows against OPENING, which are informational only.

	Returns a list of dicts: credit/debit voucher type, name, posting date and
	amount, plus the allocated amount.
	"""
	if f_date or t_date:
		# Windowed mode is only used by the display report, which is GL-based.
		opening_balance = flt(get_opening_balance(customer, company, f_date), precision)
		receivables = get_receivables(customer, company, f_date, t_date)
		credits = get_credit_entries(customer, company, f_date, t_date)
	else:
		# Full history -- the mode the mismatch scan uses. Read from the payment
		# ledger so credit notes and refunds are included, and so both sides of
		# the comparison come from the same ledger.
		opening_balance = 0
		receivables, credits = get_ledger_entries(customer, company, precision=precision)

	credit_queue = [
		{
			"name": row["name"],
			"date": row["date"],
			"voucher_type": row["voucher_type"],
			"amount": flt(row["amount"], precision),
			"remaining": flt(row["amount"], precision),
		}
		for row in credits
	]

	allocations = []
	credit_idx = 0

	def consume_credits(debit, remaining):
		"""Draw `remaining` off the credit queue, oldest credit first."""
		nonlocal credit_idx

		while remaining > 0 and credit_idx < len(credit_queue):
			credit = credit_queue[credit_idx]

			if credit["remaining"] <= 0:
				credit_idx += 1
				continue

			allocated = flt(min(remaining, credit["remaining"]), precision)
			if allocated <= 0:
				credit_idx += 1
				continue

			remaining = flt(remaining - allocated, precision)
			credit["remaining"] = flt(credit["remaining"] - allocated, precision)

			allocations.append(
				{
					"credit_voucher_type": credit["voucher_type"],
					"credit_voucher": credit["name"],
					"credit_date": credit["date"],
					"credit_amount": credit["amount"],
					"debit_voucher_type": debit["voucher_type"],
					"debit_voucher": debit["name"],
					"debit_date": debit["date"],
					"debit_amount": debit["amount"],
					"allocated": allocated,
				}
			)

			if credit["remaining"] <= 0:
				credit_idx += 1

		return remaining

	# 1. A positive opening balance is the oldest receivable there is.
	if opening_balance > 0:
		consume_credits(
			{
				"voucher_type": "Opening",
				"name": OPENING,
				"date": f_date,
				"amount": opening_balance,
			},
			opening_balance,
		)

	# 2. A negative opening balance is unapplied credit carried in.
	opening_credit_remaining = flt(abs(opening_balance), precision) if opening_balance < 0 else 0

	# 3. Receivables oldest-first.
	for receivable in receivables:
		debit = {
			"voucher_type": receivable["voucher_type"],
			"name": receivable["name"],
			"date": receivable["date"],
			"amount": flt(receivable["amount"], precision),
		}
		remaining = debit["amount"]

		if opening_credit_remaining > 0 and remaining > 0:
			allocated = flt(min(remaining, opening_credit_remaining), precision)
			remaining = flt(remaining - allocated, precision)
			opening_credit_remaining = flt(opening_credit_remaining - allocated, precision)

			allocations.append(
				{
					"credit_voucher_type": "Opening",
					"credit_voucher": OPENING,
					"credit_date": f_date,
					"credit_amount": flt(abs(opening_balance), precision),
					"debit_voucher_type": debit["voucher_type"],
					"debit_voucher": debit["name"],
					"debit_date": debit["date"],
					"debit_amount": debit["amount"],
					"allocated": allocated,
				}
			)

		consume_credits(debit, remaining)

	return allocations


def as_pair_map(allocations, skip_opening=True):
	"""Collapse an allocation list into {(credit_voucher, debit_voucher): amount}.

	This is the shape the mismatch scan diffs against the real Payment Ledger
	Entry rows. Opening-balance rows are dropped by default: they are an
	aggregate, so there is no voucher to unreconcile and no honest comparison to
	make against the ledger.
	"""
	pairs = {}

	for row in allocations:
		if skip_opening and OPENING in (row["credit_voucher"], row["debit_voucher"]):
			continue

		key = (row["credit_voucher"], row["debit_voucher"])
		pairs[key] = flt(pairs.get(key, 0) + row["allocated"], DEFAULT_PRECISION)

	return pairs


def get_actual_allocations(customer, company, party_type="Customer", precision=DEFAULT_PRECISION):
	"""What is really reconciled today, straight off the Payment Ledger.

	Mirrors the query Payment Reconciliation Redo uses to decide what to
	unreconcile, minus the date window -- the scan always looks at full history,
	because a back-dated entry can invalidate an allocation of any age.

	`voucher_no != against_voucher_no` drops the self-referencing rows the ledger
	writes for the invoice's own debit.
	"""
	rows = frappe.db.sql(
		"""
		SELECT
			voucher_type,
			voucher_no,
			against_voucher_type,
			against_voucher_no,
			SUM(ABS(amount)) AS allocated_amount
		FROM `tabPayment Ledger Entry`
		WHERE company = %(company)s
			AND party_type = %(party_type)s
			AND party = %(party)s
			AND delinked = 0
			AND against_voucher_no IS NOT NULL
			AND against_voucher_no != ''
			AND voucher_no != against_voucher_no
		GROUP BY voucher_type, voucher_no, against_voucher_type, against_voucher_no
		""",
		{"company": company, "party_type": party_type, "party": customer},
		as_dict=True,
	)

	pairs = {}
	meta = {}

	for row in rows:
		key = (row.voucher_no, row.against_voucher_no)
		pairs[key] = flt(pairs.get(key, 0) + flt(row.allocated_amount), precision)
		meta[key] = {
			"credit_voucher_type": row.voucher_type,
			"debit_voucher_type": row.against_voucher_type,
		}

	return pairs, meta
