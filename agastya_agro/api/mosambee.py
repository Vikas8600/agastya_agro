# Copyright (c) 2026, Dexciss and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

from erpnext.accounts.utils import get_balance_on


@frappe.whitelist(allow_guest=False, methods=["GET", "POST"])
def get_customer_details(customer_id=None, company=None):
	if not customer_id:
		frappe.local.response.http_status_code = 400
		return {
			"success": False,
			"error_code": "MISSING_PARAM",
			"message": "customer_id is required",
		}

	customer = frappe.db.get_value(
		"Customer",
		customer_id,
		["name", "customer_name", "disabled", "default_currency"],
		as_dict=True,
	)

	if not customer:
		frappe.local.response.http_status_code = 404
		return {
			"success": False,
			"error_code": "CUSTOMER_NOT_FOUND",
			"message": f"No customer found with id {customer_id}",
			"customer_id": customer_id,
		}

	if customer.disabled:
		frappe.local.response.http_status_code = 403
		return {
			"success": False,
			"error_code": "CUSTOMER_DISABLED",
			"message": f"Customer {customer_id} is disabled",
			"customer_id": customer.name,
			"customer_name": customer.customer_name,
		}

	if not company:
		company = frappe.db.get_single_value("Global Defaults", "default_company")

	if not company:
		frappe.local.response.http_status_code = 500
		return {
			"success": False,
			"error_code": "NO_COMPANY",
			"message": "No company supplied and no default company configured",
		}

	receivable_account = frappe.get_cached_value("Company", company, "default_receivable_account")

	balance = get_balance_on(
		party_type="Customer",
		party=customer.name,
		company=company,
		account=receivable_account,
	)

	currency = (
		customer.default_currency
		or frappe.get_cached_value("Company", company, "default_currency")
		or "INR"
	)

	return {
		"success": True,
		"customer_id": customer.name,
		"customer_name": customer.customer_name,
		"outstanding_amount": flt(balance, 2),
		"currency": currency,
		"company": company,
	}
