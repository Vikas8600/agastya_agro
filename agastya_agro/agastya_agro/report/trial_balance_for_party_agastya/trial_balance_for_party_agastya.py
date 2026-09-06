# Copyright (c) 2026, Dexciss and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

from erpnext.accounts.report.general_ledger.general_ledger import get_accounts_with_children
from erpnext.accounts.report.trial_balance_for_party.trial_balance_for_party import (
	execute as standard_trial_balance,
)
from erpnext.accounts.utils import get_currency_precision

from agastya_agro.ledger_exclusions import get_excluded_movement


def execute(filters=None):
	"""Trial Balance for Party with the entries that are not trade movement taken out.

	The reconciliation tool's own credit and debit notes, and cheques that
	bounced, post an equal debit and credit against the party. They leave the
	balance alone and only inflate the two movement columns, which is why
	General Ledger offers to drop them. This does the same, party by party.

	Everything else is the standard report, called as it stands, so the two can
	be run side by side and the difference read off. Only Debit and Credit are
	touched: Opening and Closing are left exactly as the standard report struck
	them, so this still ties to the ledger even where a bounced cheque has been
	flagged on the receipt and not on the journal that reverses it.
	"""
	filters = frappe._dict(filters or {})
	columns, data = standard_trial_balance(filters)
	if not data:
		return columns, data

	parties = filters.get("party")
	if parties and not isinstance(parties, (list, tuple)):
		parties = [parties]

	movement = get_excluded_movement(
		company=filters.company,
		from_date=filters.from_date,
		to_date=filters.to_date,
		party_type=filters.party_type,
		parties=parties,
		accounts=get_accounts_with_children(filters.account) if filters.get("account") else None,
	)
	if not movement:
		return columns, data

	precision = get_currency_precision()
	excluded = frappe._dict(debit=0.0, credit=0.0)

	for row in data:
		adjustment = movement.get(row.get("party"))
		if not adjustment:
			continue

		row["debit"] = flt(flt(row.get("debit")) - adjustment.debit, precision)
		row["credit"] = flt(flt(row.get("credit")) - adjustment.credit, precision)
		excluded.debit += adjustment.debit
		excluded.credit += adjustment.credit

	# The standard report totals only the rows it kept, so the totals come down
	# by what was taken off those rows rather than by the whole excluded set.
	totals = data[-1]
	if totals.get("party") == "'{0}'".format(_("Totals")):
		totals["debit"] = flt(flt(totals.get("debit")) - excluded.debit, precision)
		totals["credit"] = flt(flt(totals.get("credit")) - excluded.credit, precision)

	return columns, data
