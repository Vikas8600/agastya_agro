# Copyright (c) 2026, Dexciss and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import formatdate, getdate

LINK_FILTERS = (
	("company", "Company"),
	("sales_person", "Sales Person"),
	("customer", "Customer"),
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)

	return get_columns(), get_data(filters)


def validate_filters(filters):
	if not filters.from_date or not filters.to_date:
		frappe.throw(_("Please select both From Date and To Date."))

	if getdate(filters.from_date) > getdate(filters.to_date):
		frappe.throw(
			_("From Date {0} is after To Date {1}. No payment falls in that range.").format(
				formatdate(filters.from_date), formatdate(filters.to_date)
			)
		)

	# Prepared Report and API callers bypass the Link field's own lookup, so the
	# references are checked here rather than assumed valid.
	for fieldname, doctype in LINK_FILTERS:
		value = filters.get(fieldname)
		if value and not frappe.db.exists(doctype, value):
			frappe.throw(_("{0} {1} does not exist.").format(_(doctype), frappe.bold(value)))


def get_data(filters):
	conditions, values = get_conditions(filters)

	return frappe.db.sql(
		"""
		select
			pe.posting_date as date,
			pe.party as party,
			pe.party_name as party_name,
			sum(pe.paid_amount) as paid_amount,
			cus.sales_person as sales_person,
			count(pe.name) as entry_count,
			group_concat(pe.name order by pe.name separator ', ') as payment_entries
		from `tabPayment Entry` pe
		inner join `tabCustomer` cus on cus.name = pe.party
		where {conditions}
		group by pe.posting_date, pe.company, pe.party, pe.party_name, cus.sales_person
		order by pe.posting_date, pe.party
	""".format(conditions=" and ".join(conditions)),
		values,
		as_dict=1,
	)


def get_conditions(filters):
	conditions = [
		"pe.docstatus = 1",
		"pe.payment_type = 'Receive'",
		"pe.party_type = 'Customer'",
		"ifnull(pe.custom_is_bounced_cheque, 0) = 0",
		"pe.posting_date between %(from_date)s and %(to_date)s",
	]
	values = {"from_date": filters.from_date, "to_date": filters.to_date}

	if filters.company:
		conditions.append("pe.company = %(company)s")
		values["company"] = filters.company

	if filters.customer:
		conditions.append("pe.party = %(customer)s")
		values["customer"] = filters.customer

	if filters.sales_person:
		conditions.append("cus.sales_person = %(sales_person)s")
		values["sales_person"] = filters.sales_person

	if filters.mode_of_payment:
		conditions.append("pe.mode_of_payment = %(mode_of_payment)s")
		values["mode_of_payment"] = filters.mode_of_payment

	return conditions, values


def get_columns():
	return [
		{"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 100},
		{
			"label": _("Party"),
			"fieldname": "party",
			"fieldtype": "Link",
			"options": "Customer",
			"width": 160,
		},
		{"label": _("Name"), "fieldname": "party_name", "fieldtype": "Data", "width": 280},
		{
			"label": _("Paid Amount"),
			"fieldname": "paid_amount",
			"fieldtype": "Currency",
			"width": 150,
		},
		{
			"label": _("Sales Person"),
			"fieldname": "sales_person",
			"fieldtype": "Link",
			"options": "Sales Person",
			"width": 200,
		},
		{"label": _("Entries"), "fieldname": "entry_count", "fieldtype": "Int", "width": 80},
		{
			"label": _("Payment Entries"),
			"fieldname": "payment_entries",
			"fieldtype": "Data",
			"width": 280,
		},
	]
