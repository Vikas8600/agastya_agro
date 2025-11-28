# Copyright (c) 2025, Dexciss and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		# Customer Info
		{
			"label": _("Customer"),
			"fieldname": "customer",
			"fieldtype": "Link",
			"options": "Customer",
			"width": 150,
		},
		# Sales Order
		{
			"label": _("Sales Order"),
			"fieldname": "sales_order",
			"fieldtype": "Link",
			"options": "Sales Order",
			"width": 150,
		},
		{
			"label": _("SO Date"),
			"fieldname": "so_date",
			"fieldtype": "Date",
			"width": 100,
		},
		{
			"label": _("SO Item"),
			"fieldname": "so_item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 120,
		},
		{
			"label": _("SO Item Name"),
			"fieldname": "so_item_name",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": _("SO Qty"),
			"fieldname": "so_qty",
			"fieldtype": "Float",
			"width": 80,
		},
		# Delivery Note
		{
			"label": _("Delivery Note"),
			"fieldname": "delivery_note",
			"fieldtype": "Link",
			"options": "Delivery Note",
			"width": 150,
		},
		{
			"label": _("DN Date"),
			"fieldname": "dn_date",
			"fieldtype": "Date",
			"width": 100,
		},
		{
			"label": _("DN Item"),
			"fieldname": "dn_item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 120,
		},
		{
			"label": _("DN Item Name"),
			"fieldname": "dn_item_name",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": _("DN Qty"),
			"fieldname": "dn_qty",
			"fieldtype": "Float",
			"width": 80,
		},
		{
			"label": _("From Depot"),
			"fieldname": "from_depot",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("To Depot"),
			"fieldname": "to_depot",
			"fieldtype": "Data",
			"width": 120,
		},
		# Purchase Receipt
		{
			"label": _("Purchase Receipt"),
			"fieldname": "purchase_receipt",
			"fieldtype": "Link",
			"options": "Purchase Receipt",
			"width": 150,
		},
		{
			"label": _("PR Date"),
			"fieldname": "pr_date",
			"fieldtype": "Date",
			"width": 100,
		},
		{
			"label": _("PR Item"),
			"fieldname": "pr_item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 120,
		},
		{
			"label": _("PR Item Name"),
			"fieldname": "pr_item_name",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": _("PR Qty"),
			"fieldname": "pr_qty",
			"fieldtype": "Float",
			"width": 80,
		},
		# Sales Invoice
		{
			"label": _("Sales Invoice"),
			"fieldname": "sales_invoice",
			"fieldtype": "Link",
			"options": "Sales Invoice",
			"width": 150,
		},
		{
			"label": _("SI Date"),
			"fieldname": "si_date",
			"fieldtype": "Date",
			"width": 100,
		},
		{
			"label": _("SI Item"),
			"fieldname": "si_item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 120,
		},
		{
			"label": _("SI Item Name"),
			"fieldname": "si_item_name",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": _("SI Qty"),
			"fieldname": "si_qty",
			"fieldtype": "Float",
			"width": 80,
		},
		# Purchase Invoice
		{
			"label": _("Purchase Invoice"),
			"fieldname": "purchase_invoice",
			"fieldtype": "Link",
			"options": "Purchase Invoice",
			"width": 150,
		},
		{
			"label": _("PI Date"),
			"fieldname": "pi_date",
			"fieldtype": "Date",
			"width": 100,
		},
		{
			"label": _("PI Item"),
			"fieldname": "pi_item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 120,
		},
		{
			"label": _("PI Item Name"),
			"fieldname": "pi_item_name",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": _("PI Qty"),
			"fieldname": "pi_qty",
			"fieldtype": "Float",
			"width": 80,
		},
	]


def get_data(filters):
	conditions = get_conditions(filters)

	# Get all internal transfer customers
	internal_customers = frappe.get_all(
		"Customer",
		filters={"custom_is_internal_transfer": 1},
		pluck="name"
	)

	if not internal_customers:
		return []

	data = []

	# Build item filter condition
	item_condition = ""
	if filters.get("item"):
		item_condition = f" AND soi.item_code = '{filters.get('item')}'"

	# Get Sales Orders for internal transfer customers
	so_query = f"""
		SELECT DISTINCT
			so.name as sales_order,
			so.transaction_date as so_date,
			so.customer
		FROM `tabSales Order` so
		WHERE so.docstatus = 1
		AND so.customer IN ({','.join(['%s'] * len(internal_customers))})
		{conditions.get("sales_order_conditions", "")}
		ORDER BY so.transaction_date DESC, so.name DESC
	"""

	sales_orders = frappe.db.sql(so_query, tuple(internal_customers), as_dict=True)

	for so in sales_orders:
		# Get all items from this Sales Order
		so_items = get_sales_order_items(so.sales_order, filters.get("item"))

		# Get all Delivery Notes for this Sales Order
		delivery_notes = get_delivery_notes_for_so(so.sales_order, filters)

		# Get all Sales Invoices for this Sales Order
		sales_invoices = get_sales_invoices_for_so(so.sales_order)

		# Get all Purchase Receipts for the Delivery Notes
		purchase_receipts = []
		for dn in delivery_notes:
			prs = get_purchase_receipts_for_dn(dn.get("delivery_note"))
			purchase_receipts.extend(prs)

		# Get all Purchase Invoices for the Sales Invoices
		purchase_invoices = []
		for si in sales_invoices:
			pis = get_purchase_invoices_for_si(si.get("sales_invoice"))
			purchase_invoices.extend(pis)

		# Find the maximum number of rows needed
		max_rows = max(
			len(so_items),
			len(delivery_notes),
			len(purchase_receipts),
			len(sales_invoices),
			len(purchase_invoices),
			1
		)

		# Create rows
		for i in range(max_rows):
			row = {}

			# Customer (only on first row)
			if i == 0:
				row["customer"] = so.customer

			# Sales Order info (only on first row)
			if i == 0:
				row["sales_order"] = so.sales_order
				row["so_date"] = so.so_date

			# SO Item
			if i < len(so_items):
				row["so_item_code"] = so_items[i].get("item_code")
				row["so_item_name"] = so_items[i].get("item_name")
				row["so_qty"] = so_items[i].get("qty")

			# Delivery Note
			if i < len(delivery_notes):
				dn = delivery_notes[i]
				if i == 0 or (i > 0 and delivery_notes[i].get("delivery_note") != delivery_notes[i-1].get("delivery_note")):
					row["delivery_note"] = dn.get("delivery_note")
					row["dn_date"] = dn.get("dn_date")
					row["from_depot"] = dn.get("from_depot")
					row["to_depot"] = dn.get("to_depot")
				row["dn_item_code"] = dn.get("item_code")
				row["dn_item_name"] = dn.get("item_name")
				row["dn_qty"] = dn.get("qty")

			# Purchase Receipt
			if i < len(purchase_receipts):
				pr = purchase_receipts[i]
				if i == 0 or (i > 0 and purchase_receipts[i].get("purchase_receipt") != purchase_receipts[i-1].get("purchase_receipt")):
					row["purchase_receipt"] = pr.get("purchase_receipt")
					row["pr_date"] = pr.get("pr_date")
				row["pr_item_code"] = pr.get("item_code")
				row["pr_item_name"] = pr.get("item_name")
				row["pr_qty"] = pr.get("qty")

			# Sales Invoice
			if i < len(sales_invoices):
				si = sales_invoices[i]
				if i == 0 or (i > 0 and sales_invoices[i].get("sales_invoice") != sales_invoices[i-1].get("sales_invoice")):
					row["sales_invoice"] = si.get("sales_invoice")
					row["si_date"] = si.get("si_date")
				row["si_item_code"] = si.get("item_code")
				row["si_item_name"] = si.get("item_name")
				row["si_qty"] = si.get("qty")

			# Purchase Invoice
			if i < len(purchase_invoices):
				pi = purchase_invoices[i]
				if i == 0 or (i > 0 and purchase_invoices[i].get("purchase_invoice") != purchase_invoices[i-1].get("purchase_invoice")):
					row["purchase_invoice"] = pi.get("purchase_invoice")
					row["pi_date"] = pi.get("pi_date")
				row["pi_item_code"] = pi.get("item_code")
				row["pi_item_name"] = pi.get("item_name")
				row["pi_qty"] = pi.get("qty")

			data.append(row)

	return data


def get_sales_order_items(sales_order, item_filter=None):
	"""Get all items from a Sales Order"""
	item_condition = ""
	if item_filter:
		item_condition = f" AND soi.item_code = '{item_filter}'"

	result = frappe.db.sql(f"""
		SELECT soi.item_code, soi.item_name, soi.qty
		FROM `tabSales Order Item` soi
		WHERE soi.parent = %s
		{item_condition}
		ORDER BY soi.idx
	""", (sales_order,), as_dict=True)

	return result


def get_delivery_notes_for_so(sales_order, filters=None):
	"""Get all Delivery Notes and their items for a Sales Order"""
	item_condition = ""
	if filters and filters.get("item"):
		item_condition = f" AND dni.item_code = '{filters.get('item')}'"

	result = frappe.db.sql(f"""
		SELECT
			dn.name as delivery_note,
			dn.posting_date as dn_date,
			dn.set_warehouse as from_depot,
			dn.custom_to_depot_name as to_depot,
			dni.item_code,
			dni.item_name,
			dni.qty
		FROM `tabDelivery Note` dn
		INNER JOIN `tabDelivery Note Item` dni ON dni.parent = dn.name
		WHERE dn.docstatus = 1
		AND dni.against_sales_order = %s
		{item_condition}
		ORDER BY dn.posting_date DESC, dn.name, dni.idx
	""", (sales_order,), as_dict=True)

	return result


def get_purchase_receipts_for_dn(delivery_note):
	"""Get all Purchase Receipts and their items for a Delivery Note"""
	if not delivery_note:
		return []

	result = frappe.db.sql("""
		SELECT
			pr.name as purchase_receipt,
			pr.posting_date as pr_date,
			pri.item_code,
			pri.item_name,
			pri.qty
		FROM `tabPurchase Receipt` pr
		INNER JOIN `tabPurchase Receipt Item` pri ON pri.parent = pr.name
		WHERE pr.docstatus = 1
		AND (pr.custom_delivery_note = %s OR pr.supplier_delivery_note = %s)
		ORDER BY pr.posting_date DESC, pr.name, pri.idx
	""", (delivery_note, delivery_note), as_dict=True)

	return result


def get_sales_invoices_for_so(sales_order):
	"""Get all Sales Invoices and their items for a Sales Order"""
	result = frappe.db.sql("""
		SELECT
			si.name as sales_invoice,
			si.posting_date as si_date,
			sii.item_code,
			sii.item_name,
			sii.qty
		FROM `tabSales Invoice` si
		INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		WHERE si.docstatus = 1
		AND sii.sales_order = %s
		ORDER BY si.posting_date DESC, si.name, sii.idx
	""", (sales_order,), as_dict=True)

	return result


def get_purchase_invoices_for_si(sales_invoice):
	"""Get all Purchase Invoices and their items for a Sales Invoice"""
	if not sales_invoice:
		return []

	result = frappe.db.sql("""
		SELECT
			pi.name as purchase_invoice,
			pi.posting_date as pi_date,
			pii.item_code,
			pii.item_name,
			pii.qty
		FROM `tabPurchase Invoice` pi
		INNER JOIN `tabPurchase Invoice Item` pii ON pii.parent = pi.name
		WHERE pi.docstatus = 1
		AND pi.custom_sales_invoice = %s
		ORDER BY pi.posting_date DESC, pi.name, pii.idx
	""", (sales_invoice,), as_dict=True)

	return result


def get_conditions(filters):
	conditions = {
		"sales_order_conditions": "",
	}

	if filters.get("from_date"):
		conditions["sales_order_conditions"] += f" AND so.transaction_date >= '{filters.get('from_date')}'"

	if filters.get("to_date"):
		conditions["sales_order_conditions"] += f" AND so.transaction_date <= '{filters.get('to_date')}'"

	if filters.get("customer"):
		conditions["sales_order_conditions"] += f" AND so.customer = '{filters.get('customer')}'"

	return conditions
