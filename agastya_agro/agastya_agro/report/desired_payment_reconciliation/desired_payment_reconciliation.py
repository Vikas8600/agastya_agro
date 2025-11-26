# Copyright (c) 2025, Dexciss and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import date_diff

def execute(filters=None):
	columns, data = get_columns(filters),get_data(filters)
	return columns, data

def get_columns(filters):

	columns = [
		{'label': 'Customer','fieldname': 'customer','fieldtype': 'Link','options':"Customer",'width': 120},
		{'label': 'Customer Name','fieldname': 'customer_name','fieldtype': 'Data','width': 120},
		{'label': 'Invoice Number','fieldname': 'inv_no','fieldtype': 'Link','options':"Sales Invoice",'width': 120},
		{'label': 'Posting Date','fieldname': 'posting_date','fieldtype': 'Date','width': 120},
		{'label': 'Total','fieldname': 'total','fieldtype': 'Data','width': 120},
		{'label': 'Allocation amount','fieldname': 'allc_amt','fieldtype': 'Currency','width': 120},
		{'label': 'Balance amount','fieldname': 'bal_amt','fieldtype': 'Currency','width': 120},
		{'label': 'Receipt Date','fieldname': 'receipt_date','fieldtype': 'Date','width': 120},
		{'label': 'Collection amount','fieldname': 'coll_amt','fieldtype': 'Currency','width': 120},
		{'label': 'Voucher No','fieldname': 'voucher_no','fieldtype': 'Data','width': 120},
		{'label': 'Voucher Type','fieldname': 'voucher_type','fieldtype': 'Data','width': 120},
		{'label': 'Against Account','fieldname': 'against_acc','fieldtype': 'Data','width': 120},
		{'label': 'Days','fieldname': 'days','fieldtype': 'Int','width': 120}
	]
	return columns
def get_data(filters):
	data = []
	customer = filters.get("customer")
	f_date = filters.get("f_date")
	t_date = filters.get("t_date")
	inv_no = filters.get("inv_no")

	si_filters = {"docstatus":1}
	if customer:
		si_filters["customer"] = customer
	if f_date and t_date:
		si_filters["posting_date"] = ["between",[f_date,t_date]]
	if inv_no:
		si_filters["name"] = inv_no
	frappe.msgprint(str(si_filters))
	invoices = frappe.get_all("Sales Invoice",si_filters,["name","customer","customer_name","posting_date","rounded_total","outstanding_amount"],order_by="posting_date DESC")
	# frappe.throw(str([i["name"] for i in invoices]))
	shown_invoices = []
	for invoice in invoices:
		unique_pe = frappe.get_all("Payment Entry Reference",{"docstatus":1,"reference_doctype":"Sales Invoice","reference_name":invoice.get("name")},"distinct(parent) as parent")
		for pe in unique_pe:
			receipt_date, against_acc, paid_amount = frappe.get_value("Payment Entry",pe.get("parent"),["posting_date","paid_to","paid_amount"])
			data_dict = {}
			data_dict["customer"] = invoice.get("customer")
			data_dict["customer_name"] = invoice.get("customer_name")
			if invoice.get("name") not in shown_invoices:
				data_dict["inv_no"] = invoice.get("name")
				data_dict["total"] = frappe.utils.fmt_money(invoice.get("rounded_total"),precision=2,currency="INR")
				data_dict["bal_amt"] = invoice.get("outstanding_amount")
				shown_invoices.append(invoice.get("name"))
			else:
				data_dict["inv_no"] = ""
			
			data_dict["posting_date"] = invoice.get("posting_date")
			data_dict["allc_amt"] = frappe.get_all("Payment Entry Reference",{"reference_doctype":"Sales Invoice","reference_name":invoice.get("name"),"parent":pe.get("parent")},"sum(allocated_amount) as tot")[0].get("tot") or 0
			data_dict["receipt_date"] = receipt_date
			data_dict["voucher_no"] = pe.get("parent")
			data_dict["voucher_type"] = "Payment Entry"
			data_dict["against_acc"] = against_acc
			data_dict["days"] = date_diff(receipt_date, invoice.get("posting_date"))
			data_dict["coll_amt"] = paid_amount
			data.append(data_dict)

		unique_jv = frappe.get_all("Journal Entry Account",{"docstatus":1,"reference_type":"Sales Invoice","reference_name":invoice.get("name")},"distinct(parent) as parent")
		for jv in unique_jv:
			receipt_date,is_system_generated = frappe.get_value("Journal Entry",jv.get("parent"),["posting_date","is_system_generated"])
			if is_system_generated:
				continue
			data_dict = {}
			data_dict["customer"] = invoice.get("customer")
			data_dict["customer_name"] = invoice.get("customer_name")
			if invoice.get("name") not in shown_invoices:
				data_dict["inv_no"] = invoice.get("name")
				data_dict["total"] = frappe.utils.fmt_money(invoice.get("rounded_total"),precision=2,currency="INR")
				data_dict["bal_amt"] = invoice.get("outstanding_amount")
				shown_invoices.append(invoice.get("name"))
			else:
				data_dict["inv_no"] = ""
			data_dict["posting_date"] = invoice.get("posting_date")
			data_dict["allc_amt"] = frappe.get_all("Journal Entry Account",{"reference_type":"Sales Invoice","reference_name":invoice.get("name"),"parent":jv.get("parent")},"sum(credit_in_account_currency) as tot")[0].get("tot") or 0
			data_dict["receipt_date"] = receipt_date
			data_dict["voucher_no"] = jv.get("parent")
			data_dict["voucher_type"] = "Journal Entry"
			data_dict["against_acc"] = frappe.get_value("Journal Entry Account",{"debit_in_account_currency":[">",0],"parent":jv.get("parent")},"account")
			data_dict["days"] = date_diff(receipt_date, invoice.get("posting_date"))
			data_dict["coll_amt"] = frappe.get_all("Journal Entry Account",{"docstatus":1,"reference_type":"Sales Invoice","reference_name":invoice.get("name"),"parent":jv.get("parent")},"sum(credit_in_account_currency) as amt")[0].get("amt") or 0

			data.append(data_dict)

	return data