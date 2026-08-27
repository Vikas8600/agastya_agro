# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt


import frappe
from frappe import _
from frappe.model.meta import get_field_precision
from frappe.utils import cstr, date_diff, flt, formatdate
from frappe.utils.xlsxutils import handle_html


def execute(filters=None):
	return _execute(filters)

def _execute(filters=None, additional_table_columns=None, additional_query_columns=None):
	if not filters: filters = {}
	columns = get_columns(additional_table_columns, filters)

	company_currency = frappe.get_cached_value('Company',  filters.get('company'),  'default_currency')

	item_list = get_items(filters, additional_query_columns)
	if not item_list:
		return columns, [], None, None, None, 0

	itemised_tax, tax_columns = get_tax_accounts(item_list, columns, company_currency)
	so_dn_map = get_delivery_notes_against_sales_order(item_list)
	refs = get_reference_maps(item_list)

	data = []
	total_row_map = {}
	skip_total_row = 0
	prev_group_by_value = ''

	if filters.get('group_by'):
		grand_total = get_grand_total(filters, 'Sales Invoice')

	for d in item_list:
		customer_record = refs.customers.get(d.customer) or frappe._dict()
		item_record = refs.item_docs.get(d.item_code) or frappe._dict()

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

		# Get return invoice date, and how long after it the return was raised
		return_against = d.return_against
		return_inv_date = refs.return_dates.get(return_against) if return_against else None
		return_invoice_days = date_diff(posting_date, return_inv_date) if (posting_date and return_inv_date) else None

		# Get batch details
		batch_details = refs.batches.get(d.batch_no) or frappe._dict()
		mfg_date = batch_details.get("manufacturing_date")
		exp_date = batch_details.get("expiry_date")
		old_batch_no = batch_details.get("old_batch_no")

		# Get item details
		weight_per_unit = item_record.get("weight_per_unit") or 0
		brand = item_record.get("brand") or ""
		item_class = item_record.get("item_class") or ""

		# Get conversion factor for cases
		conv_factor = refs.conv_factors.get(d.item_code)
		cases = (flt(d.stock_qty) / flt(conv_factor)) if conv_factor else 0
		weight = flt(d.stock_qty) * flt(weight_per_unit)

		# Calculate distributed discount amount (proportional share of invoice discount)
		distributed_discount = 0
		if d.invoice_discount_amount and d.base_net_total:
			distributed_discount = (flt(d.base_net_amount) / flt(d.base_net_total)) * flt(d.invoice_discount_amount)

		# Pincode falls back to the billing address when no shipping address is set
		pincode = refs.pincodes.get(d.shipping_address_name) or refs.pincodes.get(d.customer_address) or ""

		# Payment vouchers settled against this invoice
		voucher = refs.vouchers.get(d.parent) or frappe._dict()

		row = {
			'year': fiscal_year,
			'customer': d.customer,
			'customer_name': customer_record.get("customer_name") or d.customer_name,
			'city': customer_record.get("city") or "",
			'customer_group': customer_record.get("customer_group") or d.customer_group,
			'territory': d.territory,
			'sales_person': customer_record.get("sales_person") or "",
			'parent_sales_person': customer_record.get("parent_sales_person") or "",
			'posting_date': d.posting_date,
			'month': month,
			'ack_no': d.ack_no or refs.ack_nos.get(d.parent),
			'ewaybill': d.ewaybill,
			'irn': d.irn,
			'tax_id': d.tax_id,
			'transporter': d.transporter,
			'transporter_name': d.transporter_name,
			'gst_transporter_id': d.gst_transporter_id,
			'gst_vehicle_type': d.gst_vehicle_type,
			'vehicle_no': d.vehicle_no,
			'mode_of_transport': d.mode_of_transport,
			'destination': d.custom_destination,
			'pincode': pincode,
			'distance': d.distance,
			'sales_order': d.sales_order,
			'delivery_note': delivery_note,
			'invoice': d.parent,
			'return_invoice': return_against,
			'return_inv_date': return_inv_date,
			'return_invoice_days': return_invoice_days,
			'price_list_name': d.selling_price_list,
			'item_code': d.item_code,
			'item_name': item_record.get("item_name") or d.item_name,
			'brand': brand,
			'item_class': item_class,
			'item_group': item_record.get("item_group") or d.item_group,
			'mfg_date': mfg_date,
			'exp_date': exp_date,
			'batch_no': d.batch_no,
			'old_batch_no': old_batch_no,
			'cost_center': d.cost_center,
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
			'posting_year': posting_year,
			'invoice_type': 'Returns' if d.is_return else 'Sales',
			'collection_days': (date_diff(voucher.get("collected_on"), posting_date)
				if (voucher.get("collected_on") and posting_date) else None),
			'payment_reference': voucher.get("references") or "",
			'payment_date': voucher.get("dates") or "",
			'voucher_amount': voucher.get("amount") or 0,
			'voucher_type': voucher.get("types") or "",
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

		# NRV block -- nrv is the "NRV Price" field maintained on the invoice item.
		# Items with no NRV maintained (packing material, etc.) leave the whole
		# block at zero rather than reporting the full rate as cushion.
		nrv_price = flt(d.nrv)
		diff_price = (flt(row['rate']) - nrv_price) if nrv_price else 0
		row.update({
			'nrv_price': nrv_price,
			'diff_price': diff_price,
			'cushion': flt(d.stock_qty) * diff_price,
			'nrv_sales': flt(d.stock_qty) * nrv_price,
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

	if filters.get('group_by'):
		total_row = total_row_map.get(prev_group_by_value or d.get('item_name'))
		total_row['percent_gt'] = flt(total_row['total']/grand_total * 100)
		data.append(total_row)
		data.append({})
		add_sub_total_row(total_row, total_row_map, 'total_row', tax_columns)
		data.append(total_row_map.get('total_row'))
		skip_total_row = 1

	return columns, data, None, None, None, skip_total_row

def get_reference_maps(item_list):
	"""Pre-fetch every lookup the row loop needs, one query per doctype.

	Doing these inside the loop costs six round trips per invoice item, which is
	what made the report unusable over a full year.
	"""
	customers = {d.customer for d in item_list if d.customer}
	items = {d.item_code for d in item_list if d.item_code}
	batches = {d.batch_no for d in item_list if d.batch_no}
	returns = {d.return_against for d in item_list if d.return_against}
	invoices = {d.parent for d in item_list}
	addresses = {a for d in item_list for a in (d.shipping_address_name, d.customer_address) if a}

	refs = frappe._dict({
		'customers': {}, 'item_docs': {}, 'batches': {}, 'return_dates': {},
		'conv_factors': {}, 'pincodes': {}, 'vouchers': {}, 'ack_nos': {},
	})

	if customers:
		for c in frappe.db.sql("""
			select name, customer_name, customer_group, city
			from `tabCustomer` where name in %(customers)s
		""", {'customers': tuple(customers)}, as_dict=1):
			refs.customers[c.name] = c

		# Sales Team rows hang off the Customer; collapse them the same way the
		# report used to, but in a single pass.
		team = {}
		for t in frappe.db.sql("""
			select parent, sales_person, parent_sales_person
			from `tabSales Team` where parenttype='Customer' and parent in %(customers)s
			order by idx
		""", {'customers': tuple(customers)}, as_dict=1):
			team.setdefault(t.parent, []).append(t)

		for name, rows in team.items():
			customer = refs.customers.setdefault(name, frappe._dict({'name': name}))
			customer.sales_person = ", ".join([r.sales_person for r in rows if r.sales_person])
			customer.parent_sales_person = ", ".join([r.parent_sales_person for r in rows if r.parent_sales_person])

	if items:
		for i in frappe.db.sql("""
			select name, item_name, item_group, brand, weight_per_unit, `class` as item_class
			from `tabItem` where name in %(items)s
		""", {'items': tuple(items)}, as_dict=1):
			refs.item_docs[i.name] = i

		for u in frappe.db.sql("""
			select parent, conversion_factor from `tabUOM Conversion Detail`
			where parenttype='Item' and is_alternate_uom=1 and parent in %(items)s
		""", {'items': tuple(items)}, as_dict=1):
			refs.conv_factors.setdefault(u.parent, u.conversion_factor)

	if batches:
		for b in frappe.db.sql("""
			select name, manufacturing_date, expiry_date, old_batch_no
			from `tabBatch` where name in %(batches)s
		""", {'batches': tuple(batches)}, as_dict=1):
			refs.batches[b.name] = b

	if returns:
		for r in frappe.db.sql("""
			select name, posting_date from `tabSales Invoice` where name in %(returns)s
		""", {'returns': tuple(returns)}, as_dict=1):
			refs.return_dates[r.name] = r.posting_date

	if addresses:
		for a in frappe.db.sql("""
			select name, pincode from `tabAddress`
			where name in %(addresses)s and ifnull(pincode, '') != ''
		""", {'addresses': tuple(addresses)}, as_dict=1):
			refs.pincodes[a.name] = a.pincode

	if invoices:
		# Sales Invoice.ack_no stopped being written after 2023; the acknowledgement
		# number lives on the e-Invoice Log. Keyed off reference_name because that
		# column is indexed -- looking it up by IRN is twice as slow.
		for e in frappe.db.sql("""
			select reference_name, acknowledgement_number from `tabe-Invoice Log`
			where reference_doctype = 'Sales Invoice' and reference_name in %(invoices)s
				and ifnull(acknowledgement_number, '') != ''
		""", {'invoices': tuple(invoices)}, as_dict=1):
			refs.ack_nos[e.reference_name] = e.acknowledgement_number

	if invoices:
		# is_cash marks a real bank/cash receipt. Journal Entries carry their own
		# voucher_type (Credit Note, Bank Entry, ...) which is what the register wants
		# to show -- 'Journal Entry' alone hides a scheme credit behind a payment.
		vouchers = frappe.db.sql("""
			select per.reference_name as invoice, 'Payment Entry' as voucher_type,
				per.allocated_amount as amount, pe.posting_date as voucher_date,
				pe.reference_no as reference_no, 1 as is_cash
			from `tabPayment Entry Reference` per
			inner join `tabPayment Entry` pe on pe.name = per.parent
			where per.docstatus = 1 and per.reference_doctype = 'Sales Invoice'
				and per.reference_name in %(invoices)s
			union all
			select jea.reference_name as invoice, je.voucher_type as voucher_type,
				(jea.credit - jea.debit) as amount, je.posting_date as voucher_date,
				je.cheque_no as reference_no, 0 as is_cash
			from `tabJournal Entry Account` jea
			inner join `tabJournal Entry` je on je.name = jea.parent
			where jea.docstatus = 1 and jea.reference_type = 'Sales Invoice'
				and jea.reference_name in %(invoices)s
		""", {'invoices': tuple(invoices)}, as_dict=1)

		for v in vouchers:
			entry = refs.vouchers.setdefault(v.invoice,
				frappe._dict({'amount': 0, 'rows': [], 'collected_on': None}))
			entry.amount += flt(v.amount)
			entry.rows.append(v)
			# Collection days measures money in, so credit notes and other journal
			# adjustments do not count as a collection.
			if v.is_cash and v.voucher_date and (not entry.collected_on or v.voucher_date > entry.collected_on):
				entry.collected_on = v.voucher_date

		for entry in refs.vouchers.values():
			# keep reference numbers, dates and types positionally aligned
			rows = sorted(entry.rows, key=lambda r: (r.voucher_date is None, r.voucher_date or ''))
			entry.types = ", ".join(dict.fromkeys(r.voucher_type for r in rows if r.voucher_type))
			entry.references = ", ".join(r.reference_no for r in rows if r.reference_no)
			entry.dates = ", ".join(formatdate(r.voucher_date) for r in rows if r.voucher_date)

	return refs

def get_columns(additional_table_columns, filters):
	# Ordered to match the Sales Register format sheet (columns A -> BM).
	columns = [
		{'label': _('Year'), 'fieldname': 'year', 'fieldtype': 'Data', 'width': 80},
		{'label': _('Code'), 'fieldname': 'customer', 'fieldtype': 'Link', 'options': 'Customer', 'width': 120},
		{'label': _('Name Of The Party'), 'fieldname': 'customer_name', 'fieldtype': 'Data', 'width': 180},
		{'label': _('City'), 'fieldname': 'city', 'fieldtype': 'Data', 'width': 100},
		{'label': _('Customer Group'), 'fieldname': 'customer_group', 'fieldtype': 'Link', 'options': 'Customer Group', 'width': 120},
		{'label': _('Territory'), 'fieldname': 'territory', 'fieldtype': 'Link', 'options': 'Territory', 'width': 100},
		{'label': _('Sales Person'), 'fieldname': 'sales_person', 'fieldtype': 'Data', 'width': 140},
		{'label': _('Parent Sales Person'), 'fieldname': 'parent_sales_person', 'fieldtype': 'Data', 'width': 140},
		{'label': _('Posting Date'), 'fieldname': 'posting_date', 'fieldtype': 'Date', 'width': 100},
		{'label': _('Month'), 'fieldname': 'month', 'fieldtype': 'Data', 'width': 90},
		{'label': _('E-Invoice Number'), 'fieldname': 'ack_no', 'fieldtype': 'Data', 'width': 140},
		{'label': _('E-Way Bill Number'), 'fieldname': 'ewaybill', 'fieldtype': 'Data', 'width': 140},
		{'label': _('IRN'), 'fieldname': 'irn', 'fieldtype': 'Data', 'width': 160},
		{'label': _('Tax ID'), 'fieldname': 'tax_id', 'fieldtype': 'Data', 'width': 120},
		{'label': _('Transporter'), 'fieldname': 'transporter', 'fieldtype': 'Link', 'options': 'Supplier', 'width': 120},
		{'label': _('Transporter Name'), 'fieldname': 'transporter_name', 'fieldtype': 'Data', 'width': 160},
		{'label': _('GST Transporter ID'), 'fieldname': 'gst_transporter_id', 'fieldtype': 'Data', 'width': 140},
		{'label': _('GST Vehicle Type'), 'fieldname': 'gst_vehicle_type', 'fieldtype': 'Data', 'width': 120},
		{'label': _('Vehicle No'), 'fieldname': 'vehicle_no', 'fieldtype': 'Data', 'width': 110},
		{'label': _('Mode of Transport'), 'fieldname': 'mode_of_transport', 'fieldtype': 'Data', 'width': 130},
		{'label': _('Destination'), 'fieldname': 'destination', 'fieldtype': 'Data', 'width': 130},
		{'label': _('Pincode'), 'fieldname': 'pincode', 'fieldtype': 'Data', 'width': 90},
		{'label': _('Distance (in km)'), 'fieldname': 'distance', 'fieldtype': 'Float', 'width': 110},
		{'label': _('Sale Order'), 'fieldname': 'sales_order', 'fieldtype': 'Link', 'options': 'Sales Order', 'width': 140},
		{'label': _('Delivery Challan'), 'fieldname': 'delivery_note', 'fieldtype': 'Link', 'options': 'Delivery Note', 'width': 140},
		{'label': _('Invoice Number'), 'fieldname': 'invoice', 'fieldtype': 'Link', 'options': 'Sales Invoice', 'width': 140},
		{'label': _('Return Against Invoice'), 'fieldname': 'return_invoice', 'fieldtype': 'Link', 'options': 'Sales Invoice', 'width': 150},
		{'label': _('Return Inv Date'), 'fieldname': 'return_inv_date', 'fieldtype': 'Date', 'width': 110},
		{'label': _('Ret.Invoice Days'), 'fieldname': 'return_invoice_days', 'fieldtype': 'Int', 'width': 120},
		{'label': _('Price List Name'), 'fieldname': 'price_list_name', 'fieldtype': 'Link', 'options': 'Price List', 'width': 160},
		{'label': _('Item Code'), 'fieldname': 'item_code', 'fieldtype': 'Link', 'options': 'Item', 'width': 160},
		{'label': _('Item Name'), 'fieldname': 'item_name', 'fieldtype': 'Data', 'width': 180},
		{'label': _('Brand'), 'fieldname': 'brand', 'fieldtype': 'Data', 'width': 110},
		{'label': _('Class'), 'fieldname': 'item_class', 'fieldtype': 'Data', 'width': 100},
		{'label': _('Item Group'), 'fieldname': 'item_group', 'fieldtype': 'Link', 'options': 'Item Group', 'width': 130},
		{'label': _('MFG Date'), 'fieldname': 'mfg_date', 'fieldtype': 'Date', 'width': 100},
		{'label': _('Exp Date'), 'fieldname': 'exp_date', 'fieldtype': 'Date', 'width': 100},
		{'label': _('Batch No'), 'fieldname': 'batch_no', 'fieldtype': 'Link', 'options': 'Batch', 'width': 130},
		{'label': _('Old Batch No'), 'fieldname': 'old_batch_no', 'fieldtype': 'Data', 'width': 130},
		{'label': _('Cost Center'), 'fieldname': 'cost_center', 'fieldtype': 'Link', 'options': 'Cost Center', 'width': 140},
		{'label': _('Stock Qty'), 'fieldname': 'stock_qty', 'fieldtype': 'Float', 'width': 100},
		{'label': _('Weight'), 'fieldname': 'weight', 'fieldtype': 'Float', 'width': 100},
		{'label': _('Cases'), 'fieldname': 'cases', 'fieldtype': 'Float', 'width': 90},
		{'label': _('Price List Rate'), 'fieldname': 'price_list_rate', 'fieldtype': 'Currency', 'options': 'currency', 'width': 120},
		{'label': _('Disc.%'), 'fieldname': 'discount_percentage', 'fieldtype': 'Float', 'width': 90},
		{'label': _('Disc.%,Price'), 'fieldname': 'discount_amount', 'fieldtype': 'Currency', 'options': 'currency', 'width': 120},
		{'label': _('Disc.%,Price.Amnt'), 'fieldname': 'distributed_discount_amount', 'fieldtype': 'Currency', 'options': 'currency', 'width': 140},
		{'label': _('Addnl.%'), 'fieldname': 'additional_discount_percentage', 'fieldtype': 'Float', 'width': 90},
		{'label': _('Addnl.Disc.Amnt'), 'fieldname': 'additional_discount_amount', 'fieldtype': 'Currency', 'options': 'currency', 'width': 130},
		{'label': _('Rate'), 'fieldname': 'rate', 'fieldtype': 'Currency', 'options': 'currency', 'width': 110},
		{'label': _('Net Rate'), 'fieldname': 'net_rate', 'fieldtype': 'Currency', 'options': 'currency', 'width': 110},
		{'label': _('NRV Price'), 'fieldname': 'nrv_price', 'fieldtype': 'Currency', 'options': 'currency', 'width': 110},
		{'label': _('Diff.Price'), 'fieldname': 'diff_price', 'fieldtype': 'Currency', 'options': 'currency', 'width': 110},
		{'label': _('Cushion'), 'fieldname': 'cushion', 'fieldtype': 'Currency', 'options': 'currency', 'width': 110},
		{'label': _('NRV Sales'), 'fieldname': 'nrv_sales', 'fieldtype': 'Currency', 'options': 'currency', 'width': 120},
		{'label': _('Amount'), 'fieldname': 'amount', 'fieldtype': 'Currency', 'options': 'currency', 'width': 120},
		{'label': _('Total Tax'), 'fieldname': 'total_tax', 'fieldtype': 'Currency', 'options': 'currency', 'width': 110},
		{'label': _('Total'), 'fieldname': 'total', 'fieldtype': 'Currency', 'options': 'currency', 'width': 120},
		{'label': _('Type'), 'fieldname': 'invoice_type', 'fieldtype': 'Data', 'width': 90},
		{'label': _('Invoice Vs Collection Days'), 'fieldname': 'collection_days', 'fieldtype': 'Int', 'width': 170},
		{'label': _('Payment reference Number'), 'fieldname': 'payment_reference', 'fieldtype': 'Data', 'width': 220},
		{'label': _('Payment Date'), 'fieldname': 'payment_date', 'fieldtype': 'Data', 'width': 150},
		{'label': _('Voucher Amount'), 'fieldname': 'voucher_amount', 'fieldtype': 'Currency', 'options': 'currency', 'width': 130},
		{'label': _('Voucher Type'), 'fieldname': 'voucher_type', 'fieldtype': 'Data', 'width': 130},
		{'label': _('Posting Year'), 'fieldname': 'posting_year', 'fieldtype': 'Data', 'width': 90},
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
		# `name` breaks ties so repeated runs (and exports) keep the same row order
		conditions += ("ORDER BY `tabSales Invoice`.posting_date desc,"
			" `tabSales Invoice Item`.item_group desc, `tabSales Invoice Item`.name")
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
			`tabSales Invoice Item`.nrv,
			`tabSales Invoice`.ack_no, `tabSales Invoice`.ewaybill, `tabSales Invoice`.irn,
			`tabSales Invoice`.tax_id, `tabSales Invoice`.transporter,
			`tabSales Invoice`.transporter_name, `tabSales Invoice`.gst_transporter_id,
			`tabSales Invoice`.gst_vehicle_type, `tabSales Invoice`.vehicle_no,
			`tabSales Invoice`.mode_of_transport, `tabSales Invoice`.custom_destination,
			`tabSales Invoice`.distance, `tabSales Invoice`.shipping_address_name,
			`tabSales Invoice`.customer_address, `tabSales Invoice`.is_return,
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

	columns.append({
		'fieldname': 'currency',
		'label': _('Currency'),
		'fieldtype': 'Currency',
		'width': 80,
		'hidden': 1
	})

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
