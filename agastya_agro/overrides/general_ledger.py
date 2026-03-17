import frappe
from frappe import _

import erpnext.accounts.report.general_ledger.general_ledger as original_gl

_original_execute = original_gl.execute


def custom_execute(filters=None):
	columns, data = _original_execute(filters)

	if not data:
		return columns, data

	# Collect voucher names to fetch reference numbers in bulk
	pe_names = set()
	je_names = set()

	for row in data:
		if not isinstance(row, dict):
			continue
		voucher_type = row.get("voucher_type")
		voucher_no = row.get("voucher_no")
		if voucher_type == "Payment Entry" and voucher_no:
			pe_names.add(voucher_no)
		elif voucher_type == "Journal Entry" and voucher_no:
			je_names.add(voucher_no)

	# Fetch reference numbers in bulk
	pe_ref_map = {}
	if pe_names:
		pe_data = frappe.get_all(
			"Payment Entry",
			filters={"name": ["in", list(pe_names)]},
			fields=["name", "reference_no"],
		)
		pe_ref_map = {d.name: d.reference_no for d in pe_data}

	je_ref_map = {}
	if je_names:
		je_data = frappe.get_all(
			"Journal Entry",
			filters={"name": ["in", list(je_names)]},
			fields=["name", "cheque_no"],
		)
		je_ref_map = {d.name: d.cheque_no for d in je_data}

	for row in data:
		if not isinstance(row, dict):
			continue

		if row.get("account") == f"'{_('Total')}'":
			row["voucher_type"] = _("Total")

		voucher_type = row.get("voucher_type")
		voucher_no = row.get("voucher_no")

		voucher_subtype = row.get("voucher_subtype")

		if voucher_type == "Sales Invoice" and voucher_subtype == "Credit Note":
			row["voucher_subtype"] = "Sales Return Credit Note"
		elif voucher_type == "Journal Entry" and voucher_subtype == "Credit Note":
			row["voucher_subtype"] = "Discount Credit Note"

		if voucher_type == "Journal Entry":
			ref_no = je_ref_map.get(voucher_no)
			if ref_no:
				row["remarks"] = ref_no
		elif voucher_type == "Payment Entry":
			ref_no = pe_ref_map.get(voucher_no)
			if ref_no:
				row["remarks"] = ref_no

	return columns, data
