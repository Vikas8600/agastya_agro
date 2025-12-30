# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt


import frappe
from frappe import _
from frappe.model.meta import get_field_precision
from frappe.utils import cstr, flt
from frappe.utils.xlsxutils import handle_html

from erpnext.accounts.report.sales_register.sales_register import get_mode_of_payments
from erpnext.selling.report.item_wise_sales_history.item_wise_sales_history import (
	get_customer_details,
	get_item_details,
)


def execute(filters=None):
	return _execute(filters)

def _execute(filters=None, additional_table_columns=None, additional_query_columns=None):
	if not filters: filters = {}
	columns = get_columns(additional_table_columns, filters)

	company_currency = frappe.get_cached_value('Company',  filters.get('company'),  'default_currency')

	item_list = get_items(filters, additional_query_columns)
	if item_list:
		itemised_tax, tax_columns = get_tax_accounts(item_list, columns, company_currency)

	mode_of_payments = get_mode_of_payments(set(d.parent for d in item_list))
	so_dn_map = get_delivery_notes_against_sales_order(item_list)

	data = []
	total_row_map = {}
	skip_total_row = 0
	prev_group_by_value = ''

	if filters.get('group_by'):
		grand_total = get_grand_total(filters, 'Sales Invoice')

	customer_details = get_customer_details()
	item_details = get_item_details()

	for d in item_list:
		customer_record = customer_details.get(d.customer)
		item_record = item_details.get(d.item_code)

		delivery_note = None
		if d.delivery_note:
			delivery_note = d.delivery_note
		elif d.so_detail:
			delivery_note = ", ".join(so_dn_map.get(d.so_detail, []))

		if not delivery_note and d.update_stock:
			delivery_note = d.parent

		# Calculate fiscal year (April to March)
		posting_date = d.posting_date
		fiscal_year = ""
		month = ""
		posting_year = ""
		if posting_date:
			year = posting_date.year
			month_num = posting_date.month
			month = posting_date.strftime("%B")  # Full month name
			posting_year = str(year)
			if month_num >= 4:  # April onwards
				fiscal_year = f"{str(year)[-2:]}-{str(year + 1)[-2:]}"
			else:  # Jan to March
				fiscal_year = f"{str(year - 1)[-2:]}-{str(year)[-2:]}"

		# Get return invoice date
		return_inv_date = None
		return_against = d.return_against
		if return_against:
			return_inv_date = frappe.db.get_value("Sales Invoice", return_against, "posting_date")

		# Get batch details
		mfg_date = None
		exp_date = None
		old_batch_no = None
		if d.batch_no:
			batch_details = frappe.db.get_value("Batch", d.batch_no,
				["manufacturing_date", "expiry_date", "old_batch_no"], as_dict=True)
			if batch_details:
				mfg_date = batch_details.get("manufacturing_date")
				exp_date = batch_details.get("expiry_date")
				old_batch_no = batch_details.get("old_batch_no")

		# Get item details
		item_values = frappe.get_value("Item", d.item_code,
			["weight_per_unit", "brand", "class"], as_dict=True) or {}
		weight_per_unit = item_values.get("weight_per_unit") or 0
		brand = item_values.get("brand") or ""
		item_class = item_values.get("class") or ""

		# Get conversion factor for cases
		conv_factor = frappe.get_value(
			"UOM Conversion Detail",
			{'parent': d.item_code, 'is_alternate_uom': 1},
			'conversion_factor'
		)
		cases = (flt(d.stock_qty) / flt(conv_factor)) if conv_factor else 0
		weight = flt(d.stock_qty) * flt(weight_per_unit)

		# Calculate distributed discount amount (proportional share of invoice discount)
		distributed_discount = 0
		if d.invoice_discount_amount and d.base_net_total:
			distributed_discount = (flt(d.base_net_amount) / flt(d.base_net_total)) * flt(d.invoice_discount_amount)

		row = {
			'year': fiscal_year,
			'customer': d.customer,
			'customer_name': customer_record.customer_name if customer_record else d.customer_name,
			'customer_group': customer_record.customer_group if customer_record else d.customer_group,
			'territory': d.territory,
			'sales_order': d.sales_order,
			'delivery_note': delivery_note,
			'posting_date': d.posting_date,
			'invoice': d.parent,
			'month': month,
			'posting_year': posting_year,
			'return_invoice': return_against,
			'return_inv_date': return_inv_date,
			'price_list_name': d.selling_price_list,
			'item_code': d.item_code,
			'item_name': item_record.item_name if item_record else d.item_name,
			'brand': brand,
			'item_class': item_class,
			'item_group': item_record.item_group if item_record else d.item_group,
			'mfg_date': mfg_date,
			'exp_date': exp_date,
			'batch_no': d.batch_no,
			'old_batch_no': old_batch_no,
			'stock_qty': d.stock_qty,
			'weight': weight,
			'cases': cases,
			'price_list_rate': d.price_list_rate,
			'discount_percentage': d.discount_percentage,
			'discount_amount': d.item_discount_amount,
			'distributed_discount_amount': distributed_discount,
			'additional_discount_percentage': d.additional_discount_percentage,
			'additional_discount_amount': d.invoice_discount_amount,
			'net_rate': d.item_net_rate,
		}

		if additional_query_columns:
			for col in additional_query_columns:
				row.update({
					col: d.get(col)
				})

		if d.stock_uom != d.uom and d.stock_qty:
			row.update({
				'rate': (d.base_net_rate * d.qty)/d.stock_qty,
				'amount': d.base_net_amount
			})
		else:
			row.update({
				'rate': d.base_net_rate,
				'amount': d.base_net_amount
			})

		total_tax = 0
		for tax in tax_columns:
			item_tax = itemised_tax.get(d.name, {}).get(tax, {})
			row.update({
				frappe.scrub(tax + ' Rate'): item_tax.get('tax_rate', 0),
				frappe.scrub(tax + ' Amount'): item_tax.get('tax_amount', 0),
			})
			total_tax += flt(item_tax.get('tax_amount'))

		row.update({
			'total_tax': total_tax,
			'total': d.base_net_amount + total_tax,
			'currency': company_currency
		})

		if filters.get('group_by'):
			row.update({'percent_gt': flt(row['total']/grand_total) * 100})
			group_by_field, subtotal_display_field = get_group_by_and_display_fields(filters)
			data, prev_group_by_value = add_total_row(data, filters, prev_group_by_value, d, total_row_map,
				group_by_field, subtotal_display_field, grand_total, tax_columns)
			add_sub_total_row(row, total_row_map, d.get(group_by_field, ''), tax_columns)

		data.append(row)

	if filters.get('group_by') and item_list:
		total_row = total_row_map.get(prev_group_by_value or d.get('item_name'))
		total_row['percent_gt'] = flt(total_row['total']/grand_total * 100)
		data.append(total_row)
		data.append({})
		add_sub_total_row(total_row, total_row_map, 'total_row', tax_columns)
		data.append(total_row_map.get('total_row'))
		skip_total_row = 1

	# Add city and sales person data to rows
	for d in data:
		if d.get("customer"):
			d["city"] = frappe.db.get_value("Customer", d["customer"], "city") or ""

			sales_persons = frappe.db.get_all("Sales Team",
											filters={"parent": d["customer"]},
											fields=["sales_person", "parent_sales_person"])
			if sales_persons:
				d["sales_person"] = ", ".join([sp.get("sales_person") or "" for sp in sales_persons if sp.get("sales_person")])
				d["parent_sales_person"] = ", ".join([sp.get("parent_sales_person") or "" for sp in sales_persons if sp.get("parent_sales_person")])
			else:
				d["sales_person"] = ""
				d["parent_sales_person"] = ""

	return columns, data, None, None, None, skip_total_row

def get_columns(additional_table_columns, filters):
	columns = [
		{
			'label': _('Year'),
			'fieldname': 'year',
			'fieldtype': 'Data',
			'width': 80
		},
		{
			'label': _('Customer Code'),
			'fieldname': 'customer',
			'fieldtype': 'Link',
			'options': 'Customer',
			'width': 120
		},
		{
			'label': _('Customer Name'),
			'fieldname': 'customer_name',
			'fieldtype': 'Data',
			'width': 150
		},
		{
			'label': _('City'),
			'fieldname': 'city',
			'fieldtype': 'Data',
			'width': 100
		},
		{
			'label': _('Cust Group'),
			'fieldname': 'customer_group',
			'fieldtype': 'Link',
			'options': 'Customer Group',
			'width': 120
		},
		{
			'label': _('Territory'),
			'fieldname': 'territory',
			'fieldtype': 'Link',
			'options': 'Territory',
			'width': 100
		},
		{
			'label': _('Sales Person'),
			'fieldname': 'sales_person',
			'fieldtype': 'Data',
			'width': 120
		},
		{
			'label': _('Parent Sales Person'),
			'fieldname': 'parent_sales_person',
			'fieldtype': 'Data',
			'width': 120
		},
		{
			'label': _('Sale Order'),
			'fieldname': 'sales_order',
			'fieldtype': 'Link',
			'options': 'Sales Order',
			'width': 120
		},
		{
			'label': _('Delivery Challan'),
			'fieldname': 'delivery_note',
			'fieldtype': 'Link',
			'options': 'Delivery Note',
			'width': 120
		},
		{
			'label': _('Posting Date'),
			'fieldname': 'posting_date',
			'fieldtype': 'Date',
			'width': 100
		},
		{
			'label': _('Invoice Number'),
			'fieldname': 'invoice',
			'fieldtype': 'Link',
			'options': 'Sales Invoice',
			'width': 120
		},
		{
			'label': _('Month'),
			'fieldname': 'month',
			'fieldtype': 'Data',
			'width': 80
		},
		{
			'label': _('Posting Year'),
			'fieldname': 'posting_year',
			'fieldtype': 'Data',
			'width': 80
		},
		{
			'label': _('Return Against Invoice'),
			'fieldname': 'return_invoice',
			'fieldtype': 'Link',
			'options': 'Sales Invoice',
			'width': 140
		},
		{
			'label': _('Return Inv Date'),
			'fieldname': 'return_inv_date',
			'fieldtype': 'Date',
			'width': 100
		},
		{
			'label': _('Price List Name'),
			'fieldname': 'price_list_name',
			'fieldtype': 'Link',
			'options': 'Price List',
			'width': 120
		},
		{
			'label': _('Item Code'),
			'fieldname': 'item_code',
			'fieldtype': 'Link',
			'options': 'Item',
			'width': 120
		},
		{
			'label': _('Item Name'),
			'fieldname': 'item_name',
			'fieldtype': 'Data',
			'width': 150
		},
		{
			'label': _('Brand'),
			'fieldname': 'brand',
			'fieldtype': 'Data',
			'width': 100
		},
		{
			'label': _('Class'),
			'fieldname': 'item_class',
			'fieldtype': 'Data',
			'width': 100
		},
		{
			'label': _('Item Group'),
			'fieldname': 'item_group',
			'fieldtype': 'Link',
			'options': 'Item Group',
			'width': 120
		},
		{
			'label': _('MFG Date'),
			'fieldname': 'mfg_date',
			'fieldtype': 'Date',
			'width': 100
		},
		{
			'label': _('Exp Date'),
			'fieldname': 'exp_date',
			'fieldtype': 'Date',
			'width': 100
		},
		{
			'label': _('Batch No'),
			'fieldname': 'batch_no',
			'fieldtype': 'Link',
			'options': 'Batch',
			'width': 120
		},
		{
			'label': _('Old Batch No'),
			'fieldname': 'old_batch_no',
			'fieldtype': 'Data',
			'width': 120
		},
		{
			'label': _('Stock Qty'),
			'fieldname': 'stock_qty',
			'fieldtype': 'Float',
			'width': 100
		},
		{
			'label': _('Weight'),
			'fieldname': 'weight',
			'fieldtype': 'Float',
			'width': 100
		},
		{
			'label': _('Cases'),
			'fieldname': 'cases',
			'fieldtype': 'Float',
			'width': 100
		},
		{
			'label': _('Price List Rate'),
			'fieldname': 'price_list_rate',
			'fieldtype': 'Currency',
			'options': 'currency',
			'width': 120
		},
		{
			'label': _('Discount (%) on Price List Rate with Margin'),
			'fieldname': 'discount_percentage',
			'fieldtype': 'Float',
			'width': 150
		},
		{
			'label': _('Discount Amount'),
			'fieldname': 'discount_amount',
			'fieldtype': 'Currency',
			'options': 'currency',
			'width': 120
		},
		{
			'label': _('Distributed Discount Amount'),
			'fieldname': 'distributed_discount_amount',
			'fieldtype': 'Currency',
			'options': 'currency',
			'width': 150
		},
		{
			'label': _('Additional Discount Percentage'),
			'fieldname': 'additional_discount_percentage',
			'fieldtype': 'Float',
			'width': 150
		},
		{
			'label': _('Additional Discount Amount INR'),
			'fieldname': 'additional_discount_amount',
			'fieldtype': 'Currency',
			'options': 'currency',
			'width': 150
		},
		{
			'label': _('Rate'),
			'fieldname': 'rate',
			'fieldtype': 'Currency',
			'options': 'currency',
			'width': 100
		},
		{
			'label': _('Net Rate'),
			'fieldname': 'net_rate',
			'fieldtype': 'Currency',
			'options': 'currency',
			'width': 100
		},
		{
			'label': _('Amount'),
			'fieldname': 'amount',
			'fieldtype': 'Currency',
			'options': 'currency',
			'width': 100
		}
	]

	if additional_table_columns:
		columns += additional_table_columns

	if filters.get('group_by'):
		columns.append({
			'label': _('% Of Grand Total'),
			'fieldname': 'percent_gt',
			'fieldtype': 'Float',
			'width': 80
		})

	return columns

def get_conditions(filters):
	conditions = ""

	for opts in (("company", " and company=%(company)s"),
		("customer", " and `tabSales Invoice`.customer = %(customer)s"),
		("item_code", " and `tabSales Invoice Item`.item_code = %(item_code)s"),
		("from_date", " and `tabSales Invoice`.posting_date>=%(from_date)s"),
		("to_date", " and `tabSales Invoice`.posting_date<=%(to_date)s")):
			if filters.get(opts[0]):
				conditions += opts[1]

	if filters.get("mode_of_payment"):
		conditions += """ and exists(select name from `tabSales Invoice Payment`
			where parent=`tabSales Invoice`.name
				and ifnull(`tabSales Invoice Payment`.mode_of_payment, '') = %(mode_of_payment)s)"""

	if filters.get("warehouse"):
		conditions +=  """and ifnull(`tabSales Invoice Item`.warehouse, '') = %(warehouse)s"""


	if filters.get("brand"):
		conditions +=  """and ifnull(`tabSales Invoice Item`.brand, '') = %(brand)s"""

	if filters.get("item_group"):
		conditions +=  """and ifnull(`tabSales Invoice Item`.item_group, '') = %(item_group)s"""

	if not filters.get("group_by"):
		conditions += "ORDER BY `tabSales Invoice`.posting_date desc, `tabSales Invoice Item`.item_group desc"
	else:
		conditions += get_group_by_conditions(filters, 'Sales Invoice')

	return conditions

def get_group_by_conditions(filters, doctype):
	if filters.get("group_by") == 'Invoice':
		return "ORDER BY `tab{0} Item`.parent desc".format(doctype)
	elif filters.get("group_by") == 'Item':
		return "ORDER BY `tab{0} Item`.`item_code`".format(doctype)
	elif filters.get("group_by") == 'Item Group':
		return "ORDER BY `tab{0} Item`.{1}".format(doctype, frappe.scrub(filters.get('group_by')))
	elif filters.get("group_by") in ('Customer', 'Customer Group', 'Territory', 'Supplier'):
		return "ORDER BY `tab{0}`.{1}".format(doctype, frappe.scrub(filters.get('group_by')))

def get_items(filters, additional_query_columns):
	conditions = get_conditions(filters)

	if additional_query_columns:
		additional_query_columns = ', ' + ', '.join(additional_query_columns)
	else:
		additional_query_columns = ''

	return frappe.db.sql("""
		select
			`tabSales Invoice Item`.name, `tabSales Invoice Item`.parent,
			`tabSales Invoice`.posting_date, `tabSales Invoice`.debit_to,
			`tabSales Invoice`.unrealized_profit_loss_account,
			`tabSales Invoice`.is_internal_customer,
			`tabSales Invoice`.project, `tabSales Invoice`.customer, `tabSales Invoice`.remarks,
			`tabSales Invoice`.territory, `tabSales Invoice`.company, `tabSales Invoice`.base_net_total,
			`tabSales Invoice Item`.item_code,
			`tabSales Invoice Item`.`item_name`, `tabSales Invoice Item`.`item_group`,`tabSales Invoice Item`.`batch_no`,
			`tabSales Invoice Item`.sales_order, `tabSales Invoice Item`.delivery_note,
			`tabSales Invoice Item`.income_account, `tabSales Invoice Item`.cost_center,
			`tabSales Invoice Item`.stock_qty, `tabSales Invoice Item`.stock_uom,
			`tabSales Invoice Item`.base_net_rate, `tabSales Invoice Item`.base_net_amount,
			`tabSales Invoice`.customer_name, `tabSales Invoice`.customer_group, `tabSales Invoice Item`.so_detail,
			`tabSales Invoice`.update_stock, `tabSales Invoice Item`.uom, `tabSales Invoice Item`.qty,
			`tabSales Invoice`.selling_price_list,
			`tabSales Invoice`.return_against,
			`tabSales Invoice`.additional_discount_percentage,
			`tabSales Invoice`.discount_amount as invoice_discount_amount,
			`tabSales Invoice Item`.price_list_rate,
			`tabSales Invoice Item`.discount_percentage,
			`tabSales Invoice Item`.discount_amount as item_discount_amount,
			`tabSales Invoice Item`.rate as item_rate,
			`tabSales Invoice Item`.net_rate as item_net_rate,
			`tabSales Invoice Item`.base_rate,
			`tabSales Invoice Item`.base_amount {0}
		from `tabSales Invoice`, `tabSales Invoice Item`
		where `tabSales Invoice`.name = `tabSales Invoice Item`.parent
			and `tabSales Invoice`.docstatus = 1 {1}
		""".format(additional_query_columns or '', conditions), filters, as_dict=1) #nosec

def get_delivery_notes_against_sales_order(item_list):
	so_dn_map = frappe._dict()
	so_item_rows = list(set([d.so_detail for d in item_list]))

	if so_item_rows:
		delivery_notes = frappe.db.sql("""
			select parent, so_detail
			from `tabDelivery Note Item`
			where docstatus=1 and so_detail in (%s)
			group by so_detail, parent
		""" % (', '.join(['%s']*len(so_item_rows))), tuple(so_item_rows), as_dict=1)

		for dn in delivery_notes:
			so_dn_map.setdefault(dn.so_detail, []).append(dn.parent)

	return so_dn_map

def get_grand_total(filters, doctype):

	return frappe.db.sql(""" SELECT
		SUM(`tab{0}`.base_grand_total)
		FROM `tab{0}`
		WHERE `tab{0}`.docstatus = 1
		and posting_date between %s and %s
	""".format(doctype), (filters.get('from_date'), filters.get('to_date')))[0][0] #nosec

def get_deducted_taxes():
	return frappe.db.sql_list("select name from `tabPurchase Taxes and Charges` where add_deduct_tax = 'Deduct'")

def get_tax_accounts(item_list, columns, company_currency,
		doctype='Sales Invoice', tax_doctype='Sales Taxes and Charges'):
	import json
	item_row_map = {}
	tax_columns = []
	invoice_item_row = {}
	itemised_tax = {}

	tax_amount_precision = get_field_precision(frappe.get_meta(tax_doctype).get_field('tax_amount'),
		currency=company_currency) or 2

	for d in item_list:
		invoice_item_row.setdefault(d.parent, []).append(d)
		item_row_map.setdefault(d.parent, {}).setdefault(d.item_code or d.item_name, []).append(d)

	conditions = ""
	if doctype == "Purchase Invoice":
		conditions = " and category in ('Total', 'Valuation and Total') and base_tax_amount_after_discount_amount != 0"

	deducted_tax = get_deducted_taxes()
	tax_details = frappe.db.sql("""
		select
			name, parent, description, item_wise_tax_detail,
			charge_type, base_tax_amount_after_discount_amount
		from `tab%s`
		where
			parenttype = %s and docstatus = 1
			and (description is not null and description != '')
			and parent in (%s)
			%s
		order by description
	""" % (tax_doctype, '%s', ', '.join(['%s']*len(invoice_item_row)), conditions),
		tuple([doctype] + list(invoice_item_row)))

	for name, parent, description, item_wise_tax_detail, charge_type, tax_amount in tax_details:
		description = handle_html(description)
		if description not in tax_columns and tax_amount:
			# as description is text editor earlier and markup can break the column convention in reports
			tax_columns.append(description)

		if item_wise_tax_detail:
			try:
				item_wise_tax_detail = json.loads(item_wise_tax_detail)

				for item_code, tax_data in item_wise_tax_detail.items():
					itemised_tax.setdefault(item_code, frappe._dict())

					if isinstance(tax_data, list):
						tax_rate, tax_amount = tax_data
					else:
						tax_rate = tax_data
						tax_amount = 0

					if charge_type == 'Actual' and not tax_rate:
						tax_rate = 'NA'

					item_net_amount = sum([flt(d.base_net_amount)
						for d in item_row_map.get(parent, {}).get(item_code, [])])

					for d in item_row_map.get(parent, {}).get(item_code, []):
						item_tax_amount = flt((tax_amount * d.base_net_amount) / item_net_amount) \
							if item_net_amount else 0
						if item_tax_amount:
							tax_value = flt(item_tax_amount, tax_amount_precision)
							tax_value = (tax_value * -1
								if (doctype == 'Purchase Invoice' and name in deducted_tax) else tax_value)

							itemised_tax.setdefault(d.name, {})[description] = frappe._dict({
								'tax_rate': tax_rate,
								'tax_amount': tax_value
							})

			except ValueError:
				continue
		elif charge_type == 'Actual' and tax_amount:
			for d in invoice_item_row.get(parent, []):
				itemised_tax.setdefault(d.name, {})[description] = frappe._dict({
					'tax_rate': 'NA',
					'tax_amount': flt((tax_amount * d.base_net_amount) / d.base_net_total,
						tax_amount_precision)
				})

	tax_columns.sort()
	for desc in tax_columns:
		columns.append({
			'label': _(desc + ' Rate'),
			'fieldname': frappe.scrub(desc + ' Rate'),
			'fieldtype': 'Float',
			'width': 100
		})

		columns.append({
			'label': _(desc + ' Amount'),
			'fieldname': frappe.scrub(desc + ' Amount'),
			'fieldtype': 'Currency',
			'options': 'currency',
			'width': 100
		})

	columns += [
		{
			'label': _('Total Tax'),
			'fieldname': 'total_tax',
			'fieldtype': 'Currency',
			'options': 'currency',
			'width': 100
		},
		{
			'label': _('Total'),
			'fieldname': 'total',
			'fieldtype': 'Currency',
			'options': 'currency',
			'width': 100
		},
		{
			'fieldname': 'currency',
			'label': _('Currency'),
			'fieldtype': 'Currency',
			'width': 80,
			'hidden': 1
		}
	]

	return itemised_tax, tax_columns

def add_total_row(data, filters, prev_group_by_value, item, total_row_map,
	group_by_field, subtotal_display_field, grand_total, tax_columns):
	if prev_group_by_value != item.get(group_by_field, ''):
		if prev_group_by_value:
			total_row = total_row_map.get(prev_group_by_value)
			data.append(total_row)
			data.append({})
			add_sub_total_row(total_row, total_row_map, 'total_row', tax_columns)

		prev_group_by_value = item.get(group_by_field, '')

		total_row_map.setdefault(item.get(group_by_field, ''), {
			subtotal_display_field: get_display_value(filters, group_by_field, item),
			'stock_qty': 0.0,
			'amount': 0.0,
			'bold': 1,
			'total_tax': 0.0,
			'total': 0.0,
			'percent_gt': 0.0
		})

		total_row_map.setdefault('total_row', {
			subtotal_display_field: 'Total',
			'stock_qty': 0.0,
			'amount': 0.0,
			'bold': 1,
			'total_tax': 0.0,
			'total': 0.0,
			'percent_gt': 0.0
		})

	return data, prev_group_by_value

def get_display_value(filters, group_by_field, item):
	if filters.get('group_by') == 'Item':
		if item.get('item_code') != item.get('item_name'):
			value =  cstr(item.get('item_code')) + "<br><br>" + \
			"<span style='font-weight: normal'>" + cstr(item.get('item_name')) + "</span>"
		else:
			value =  item.get('item_code', '')
	elif filters.get('group_by') in ('Customer', 'Supplier'):
		party = frappe.scrub(filters.get('group_by'))
		if item.get(party) != item.get(party+'_name'):
			value = item.get(party) + "<br><br>" + \
			"<span style='font-weight: normal'>" + item.get(party+'_name') + "</span>"
		else:
			value =  item.get(party)
	else:
		value = item.get(group_by_field)

	return value

def get_group_by_and_display_fields(filters):
	if filters.get('group_by') == 'Item':
		group_by_field = 'item_code'
		subtotal_display_field = 'invoice'
	elif filters.get('group_by') == 'Invoice':
		group_by_field = 'parent'
		subtotal_display_field = 'item_code'
	else:
		group_by_field = frappe.scrub(filters.get('group_by'))
		subtotal_display_field = 'item_code'

	return group_by_field, subtotal_display_field

def add_sub_total_row(item, total_row_map, group_by_value, tax_columns):
	total_row = total_row_map.get(group_by_value)
	total_row['stock_qty'] += item['stock_qty']
	total_row['amount'] += item['amount']
	total_row['total_tax'] += item['total_tax']
	total_row['total'] += item['total']
	total_row['percent_gt'] += item['percent_gt']

	for tax in tax_columns:
		total_row.setdefault(frappe.scrub(tax + ' Amount'), 0.0)
		total_row[frappe.scrub(tax + ' Amount')] += flt(item[frappe.scrub(tax + ' Amount')])