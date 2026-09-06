# Copyright (c) 2026, Dexciss and contributors
# For license information, please see license.txt

"""Ledger entries that are not trade movement, and so are kept out of summaries.

Two kinds of voucher post an equal debit and credit against the same party. They
move no balance at all and only inflate the debit and credit columns of a party
summary: the credit and debit notes the payment reconciliation tool writes on
its own, and a cheque that bounced, which the accounts team marks on the receipt
and on the journal that reverses it.

General Ledger already drops the first kind under "Ignore System Generated
Credit / Debit Notes". This module lets the party summaries stay in step with
it, and adds the bounced cheque to the same treatment.

Nothing here is ever allowed to move a balance. Callers strike opening and
closing from the full ledger and use these figures only to reduce what the
movement columns show, so a cheque flagged on one leg and not the other can at
worst make debit and credit stop tying to closing, in plain sight, rather than
quietly restate the balance.
"""

import frappe
from frappe.utils import flt

# Correlated against an alias of `tabGL Entry` named gle. The voucher type is
# tested before either lookup, so an entry that is neither a journal nor a
# payment never reaches one.
EXCLUDED_VOUCHER = """
	gle.voucher_type = 'Journal Entry' and exists (
		select 1 from `tabJournal Entry` je
		where je.name = gle.voucher_no
			and (
				(je.is_system_generated = 1 and je.voucher_type in ('Credit Note', 'Debit Note'))
				or ifnull(je.custom_is_bounced_cheque, 0) = 1
			)
	)
	or gle.voucher_type = 'Payment Entry' and exists (
		select 1 from `tabPayment Entry` pe
		where pe.name = gle.voucher_no
			and ifnull(pe.custom_is_bounced_cheque, 0) = 1
	)
"""


def get_excluded_movement(
	company, from_date, to_date, party_type="Customer", parties=None, accounts=None
):
	"""Debit and credit these vouchers posted per party over the period.

	Driven from the journals and payments rather than from the ledger: the
	excluded vouchers number in the thousands where the ledger numbers in the
	millions, so starting on the small side and reaching the entries through
	`voucher_type` and `voucher_no` costs a few thousand lookups instead of a
	second pass over the period.
	"""
	values = {
		"company": company,
		"from_date": from_date,
		"to_date": to_date,
		"party_type": party_type,
		"parties": parties,
		"accounts": accounts,
	}

	conditions = ""
	if parties:
		conditions += " and gle.party in %(parties)s"
	if accounts:
		conditions += " and gle.account in %(accounts)s"

	movement = {}
	for row in frappe.db.sql(
		"""
		select gle.party, sum(gle.debit) as debit, sum(gle.credit) as credit
		from `tabGL Entry` gle
		where gle.is_cancelled = 0
			and gle.party_type = %(party_type)s
			and gle.party != ''
			and gle.company = %(company)s
			and gle.posting_date between %(from_date)s and %(to_date)s
			and gle.is_opening = 'No'
			and ({excluded})
			{conditions}
		group by gle.party
	""".format(excluded=EXCLUDED_VOUCHER, conditions=conditions),
		values,
		as_dict=1,
	):
		movement[row.party] = frappe._dict(debit=flt(row.debit), credit=flt(row.credit))

	return movement
