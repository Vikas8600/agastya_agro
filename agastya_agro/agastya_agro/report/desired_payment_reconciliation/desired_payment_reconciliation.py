# Copyright (c) 2025, Dexciss and contributors
# For license information, please see license.txt

# =============================================================================
# OLD CODE - COMMENTED OUT
# =============================================================================
# import frappe
# from frappe.utils import date_diff

# def execute(filters=None):
# 	columns, data = get_columns(filters),get_data(filters)
# 	return columns, data

# def get_columns(filters):

# 	columns = [
# 		{'label': 'Customer','fieldname': 'customer','fieldtype': 'Link','options':"Customer",'width': 120},
# 		{'label': 'Customer Name','fieldname': 'customer_name','fieldtype': 'Data','width': 120},
# 		{'label': 'Invoice Number','fieldname': 'inv_no','fieldtype': 'Link','options':"Sales Invoice",'width': 120},
# 		{'label': 'Posting Date','fieldname': 'posting_date','fieldtype': 'Date','width': 120},
# 		{'label': 'Total','fieldname': 'total','fieldtype': 'Data','width': 120},
# 		{'label': 'Allocation Amount','fieldname': 'allc_amt','fieldtype': 'Currency','width': 120},
# 		# {'label': 'Balance amount','fieldname': 'bal_amt','fieldtype': 'Currency','width': 120},
# 		{'label': 'Receipt Date','fieldname': 'receipt_date','fieldtype': 'Date','width': 120},
# 		{'label': 'Collection Amount','fieldname': 'coll_amt','fieldtype': 'Currency','width': 120},
# 		{'label': 'Voucher No','fieldname': 'voucher_no','fieldtype': 'Data','width': 120},
# 		{'label': 'Voucher Type','fieldname': 'voucher_type','fieldtype': 'Data','width': 120},
# 		{'label': 'Against Account','fieldname': 'against_acc','fieldtype': 'Data','width': 120},
# 		{'label': 'Days','fieldname': 'days','fieldtype': 'Int','width': 120}
# 	]
# 	return columns



# def get_data(filters):
# 	data = []
# 	customer = filters.get("customer")
# 	f_date = filters.get("f_date")
# 	t_date = filters.get("t_date")
# 	inv_no = filters.get("inv_no")

# 	si_filters = {"docstatus":1}
# 	if customer:
# 		si_filters["customer"] = customer
# 	if f_date and t_date:
# 		si_filters["posting_date"] = ["between",[f_date,t_date]]
# 	if inv_no:
# 		si_filters["name"] = inv_no

# 	invoices = frappe.get_all("Sales Invoice",si_filters,["name","customer","customer_name","posting_date","rounded_total"],order_by="posting_date ASC")

# 	shown_invoices = []
# 	for invoice in invoices:
# 		# get payment entries for this invoice
# 		unique_pe = frappe.get_all("Payment Entry Reference",{"docstatus":1,"reference_doctype":"Sales Invoice","reference_name":invoice.get("name")},"distinct(parent) as parent")
# 		for pe in unique_pe:
# 			receipt_date, against_acc = frappe.get_value("Payment Entry",pe.get("parent"),["posting_date","paid_to"])
# 			allc_amt = frappe.get_all("Payment Entry Reference",{"reference_doctype":"Sales Invoice","reference_name":invoice.get("name"),"parent":pe.get("parent")},"sum(allocated_amount) as tot")[0].get("tot") or 0

# 			data_dict = {}
# 			data_dict["customer"] = invoice.get("customer")
# 			data_dict["customer_name"] = invoice.get("customer_name")
# 			if invoice.get("name") not in shown_invoices:
# 				data_dict["inv_no"] = invoice.get("name")
# 				data_dict["total"] = invoice.get("rounded_total")
# 				shown_invoices.append(invoice.get("name"))
# 			data_dict["posting_date"] = invoice.get("posting_date")
# 			data_dict["allc_amt"] = allc_amt
# 			data_dict["receipt_date"] = receipt_date
# 			# collection amount = allocation amount (as shown in GL)
# 			data_dict["coll_amt"] = allc_amt
# 			data_dict["voucher_no"] = pe.get("parent")
# 			data_dict["voucher_type"] = "Payment Entry"
# 			data_dict["against_acc"] = against_acc
# 			data_dict["days"] = date_diff(receipt_date, invoice.get("posting_date"))
# 			data.append(data_dict)

# 		# get journal entries for this invoice
# 		unique_jv = frappe.get_all("Journal Entry Account",{"docstatus":1,"reference_type":"Sales Invoice","reference_name":invoice.get("name")},"distinct(parent) as parent")
# 		for jv in unique_jv:
# 			receipt_date, is_system_generated = frappe.get_value("Journal Entry",jv.get("parent"),["posting_date","is_system_generated"])
# 			if is_system_generated:
# 				continue

# 			allc_amt = frappe.get_all("Journal Entry Account",{"reference_type":"Sales Invoice","reference_name":invoice.get("name"),"parent":jv.get("parent")},"sum(credit_in_account_currency) as tot")[0].get("tot") or 0
# 			against_acc = frappe.get_value("Journal Entry Account",{"debit_in_account_currency":[">",0],"parent":jv.get("parent")},"account")

# 			data_dict = {}
# 			data_dict["customer"] = invoice.get("customer")
# 			data_dict["customer_name"] = invoice.get("customer_name")
# 			if invoice.get("name") not in shown_invoices:
# 				data_dict["inv_no"] = invoice.get("name")
# 				data_dict["total"] = invoice.get("rounded_total")
# 				shown_invoices.append(invoice.get("name"))
# 			data_dict["posting_date"] = invoice.get("posting_date")
# 			data_dict["allc_amt"] = allc_amt
# 			data_dict["receipt_date"] = receipt_date
# 			# collection amount = allocation amount (as shown in GL)
# 			data_dict["coll_amt"] = allc_amt
# 			data_dict["voucher_no"] = jv.get("parent")
# 			data_dict["voucher_type"] = "Journal Entry"
# 			data_dict["against_acc"] = against_acc
# 			data_dict["days"] = date_diff(receipt_date, invoice.get("posting_date"))
# 			data.append(data_dict)

# 	return data

# =============================================================================
# NEW CODE - FIFO Payment Reconciliation (NOT based on linked references)
# Allocates payments to invoices in FIFO order based on dates
# =============================================================================

import frappe
from frappe.utils import flt

def execute(filters=None):
	columns = get_columns(filters)
	data = get_data(filters)
	return columns, data

def get_columns(filters):
	"""
	Columns matching the image format:
	Sales Invoice | Date | Amount | Allocation Amount | Balance | Collection Amount | (gap) | Voucher No | Voucher Type | Date | Amount
	"""
	columns = [
		{'label': 'Sales Invoice', 'fieldname': 'sales_invoice', 'fieldtype': 'Link', 'options': 'Sales Invoice', 'width': 140},
		{'label': 'Date', 'fieldname': 'invoice_date', 'fieldtype': 'Date', 'width': 100},
		{'label': 'Amount', 'fieldname': 'invoice_amount', 'fieldtype': 'Currency', 'width': 120},
		{'label': 'Allocation Amount', 'fieldname': 'allocation_amount', 'fieldtype': 'Currency', 'width': 130},
		{'label': 'Balance', 'fieldname': 'balance', 'fieldtype': 'Currency', 'width': 120},
		{'label': 'Collection Amount', 'fieldname': 'collection_amount', 'fieldtype': 'Currency', 'width': 130},
		{'label': '', 'fieldname': 'blank', 'fieldtype': 'Data', 'width': 30},
		{'label': 'Voucher No', 'fieldname': 'voucher_no', 'fieldtype': 'Dynamic Link', 'options': 'voucher_type', 'width': 140},
		{'label': 'Voucher Type', 'fieldname': 'voucher_type', 'fieldtype': 'Data', 'width': 120},
		{'label': 'Date', 'fieldname': 'voucher_date', 'fieldtype': 'Date', 'width': 100},
		{'label': 'Amount', 'fieldname': 'voucher_amount', 'fieldtype': 'Currency', 'width': 120},
	]
	return columns

def get_data(filters):
	data = []
	customer = filters.get("customer")
	f_date = filters.get("f_date")
	t_date = filters.get("t_date")

	if not customer:
		return data

	# Get customer's receivable account
	company = filters.get("company")
	receivable_account = frappe.get_cached_value("Company", company, "default_receivable_account")

	# =========================================================================
	# STEP 1: Get all Sales Invoices for the customer (FIFO - oldest first)
	# =========================================================================
	si_filters = {
		"docstatus": 1,
		"customer": customer
	}
	if f_date and t_date:
		si_filters["posting_date"] = ["between", [f_date, t_date]]

	invoices = frappe.get_all(
		"Sales Invoice",
		filters=si_filters,
		fields=["name", "posting_date", "rounded_total", "grand_total"],
		order_by="posting_date ASC, name ASC"
	)

	# Create invoice list with remaining balance
	invoice_list = []
	for inv in invoices:
		invoice_list.append({
			"name": inv.get("name"),
			"date": inv.get("posting_date"),
			"amount": flt(inv.get("rounded_total") or inv.get("grand_total")),
			"remaining": flt(inv.get("rounded_total") or inv.get("grand_total"))
		})

	# =========================================================================
	# STEP 2: Get all Payment Vouchers for the customer (FIFO - oldest first)
	# Payment Entries + Journal Entries (credit to receivable account)
	# =========================================================================
	vouchers = []

	# Get Payment Entries (Receive type for customer)
	pe_list = frappe.get_all(
		"Payment Entry",
		filters={
			"docstatus": 1,
			"party_type": "Customer",
			"party": customer,
			"payment_type": "Receive"
		},
		fields=["name", "posting_date", "paid_amount"],
		order_by="posting_date ASC, name ASC"
	)

	for pe in pe_list:
		vouchers.append({
			"voucher_type": "Payment Entry",
			"voucher_name": pe.get("name"),
			"voucher_date": pe.get("posting_date"),
			"voucher_amount": flt(pe.get("paid_amount")),
			"remaining": flt(pe.get("paid_amount"))
		})

	# Get Journal Entries (credit to customer's receivable account)
	if receivable_account:
		jv_accounts = frappe.db.sql("""
			SELECT DISTINCT jea.parent, jea.credit_in_account_currency, je.posting_date
			FROM `tabJournal Entry Account` jea
			INNER JOIN `tabJournal Entry` je ON je.name = jea.parent
			WHERE jea.docstatus = 1
			AND jea.party_type = 'Customer'
			AND jea.party = %s
			AND jea.credit_in_account_currency > 0
			AND je.is_system_generated = 0
			ORDER BY je.posting_date ASC, jea.parent ASC
		""", (customer,), as_dict=True)

		for jv in jv_accounts:
			vouchers.append({
				"voucher_type": "Journal Entry",
				"voucher_name": jv.get("parent"),
				"voucher_date": jv.get("posting_date"),
				"voucher_amount": flt(jv.get("credit_in_account_currency")),
				"remaining": flt(jv.get("credit_in_account_currency"))
			})

	# Sort all vouchers by date (FIFO)
	vouchers.sort(key=lambda x: (x["voucher_date"], x["voucher_name"]))

	# =========================================================================
	# STEP 3: FIFO Allocation - Allocate oldest payments to oldest invoices
	# =========================================================================
	voucher_idx = 0

	for inv in invoice_list:
		inv_name = inv["name"]
		inv_date = inv["date"]
		inv_amount = inv["amount"]
		inv_remaining = inv["remaining"]

		# Track if any allocation was made for this invoice
		has_allocation = False

		# Allocate from vouchers while invoice has remaining balance
		while inv_remaining > 0 and voucher_idx < len(vouchers):
			voucher = vouchers[voucher_idx]

			if voucher["remaining"] <= 0:
				voucher_idx += 1
				continue

			# Calculate allocation amount
			allocation = min(inv_remaining, voucher["remaining"])

			# Deduct from both
			inv_remaining = flt(inv_remaining - allocation)
			voucher["remaining"] = flt(voucher["remaining"] - allocation)
			inv["remaining"] = inv_remaining

			# Add row to data
			row = {
				"sales_invoice": inv_name,
				"invoice_date": inv_date,
				"invoice_amount": inv_amount,
				"allocation_amount": allocation,
				"balance": inv_remaining,
				"collection_amount": voucher["voucher_amount"],
				"blank": "",
				"voucher_no": voucher["voucher_name"],
				"voucher_type": voucher["voucher_type"],
				"voucher_date": voucher["voucher_date"],
				"voucher_amount": voucher["voucher_amount"]
			}
			data.append(row)
			has_allocation = True

			# If voucher is exhausted, move to next voucher
			if voucher["remaining"] <= 0:
				voucher_idx += 1

		# If invoice has no allocation at all, show it with empty payment
		if not has_allocation:
			row = {
				"sales_invoice": inv_name,
				"invoice_date": inv_date,
				"invoice_amount": inv_amount,
				"allocation_amount": 0,
				"balance": inv_amount,
				"collection_amount": 0,
				"blank": "",
				"voucher_no": "",
				"voucher_type": "",
				"voucher_date": None,
				"voucher_amount": 0
			}
			data.append(row)

	return data