# Opening voucher detail for Desired Payment Reconciliation report
# Uses Accounts Receivable report logic via Payment Ledger Entry

import frappe
from frappe.utils import flt, add_days


def get_opening_vouchers_detail(customer, company, f_date):
	"""
	Get voucher-wise outstanding breakdown as of f_date.
	Uses AR report with report_date = f_date - 1 (so posting_date <= f_date-1 = posting_date < f_date).
	Returns HTML string with <br> separated voucher lines.
	"""
	if not f_date:
		return ""

	from erpnext.accounts.report.accounts_receivable.accounts_receivable import execute

	ar_filters = frappe._dict({
		"company": company,
		"report_date": add_days(f_date, -1),
		"party_type": "Customer",
		"party": [customer],
		"ageing_based_on": "Posting Date",
		"range1": 30, "range2": 60, "range3": 90, "range4": 120,
	})

	try:
		columns, data, *rest = execute(ar_filters)
	except Exception:
		return ""

	if not data:
		return ""

	lines = []
	for row in data:
		# AR report returns frappe._dict, not plain dict
		vno = row.get("voucher_no") if hasattr(row, "get") else getattr(row, "voucher_no", None)
		if not vno:
			continue
		vtype = row.get("voucher_type") if hasattr(row, "get") else getattr(row, "voucher_type", "")
		outstanding = flt(row.get("outstanding") if hasattr(row, "get") else getattr(row, "outstanding", 0), 2)
		date = row.get("posting_date") if hasattr(row, "get") else getattr(row, "posting_date", "")
		lines.append(f"{vtype}: {vno} | {outstanding} | {date}")

	return "<br>".join(lines)
