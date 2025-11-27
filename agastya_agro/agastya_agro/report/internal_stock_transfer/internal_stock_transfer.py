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
		{
			"label": _("Sales Order"),
			"fieldname": "sales_order",
			"fieldtype": "Link",
			"options": "Sales Order",
			"width": 180,
		},
		{
			"label": _("Customer"),
			"fieldname": "customer",
			"fieldtype": "Link",
			"options": "Customer",
			"width": 180,
		},
		{
			"label": _("Delivery Note"),
			"fieldname": "delivery_note",
			"fieldtype": "Link",
			"options": "Delivery Note",
			"width": 180,
		},
		{
			"label": _("To Depot"),
			"fieldname": "to_depot",
			"fieldtype": "Link",
			"options": "Cost Center",
			"width": 180,
		},
		{
			"label": _("Purchase Receipt"),
			"fieldname": "purchase_receipt",
			"fieldtype": "Link",
			"options": "Purchase Receipt",
			"width": 180,
		},
		{
			"label": _("Sales Invoice"),
			"fieldname": "sales_invoice",
			"fieldtype": "Link",
			"options": "Sales Invoice",
			"width": 180,
		},
		{
			"label": _("Purchase Invoice"),
			"fieldname": "purchase_invoice",
			"fieldtype": "Link",
			"options": "Purchase Invoice",
			"width": 180,
		},
		{
			"label": _("Transfer Status"),
			"fieldname": "transfer_status",
			"fieldtype": "Data",
			"width": 150,
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

	# Get Sales Orders for internal transfer customers
	sales_order_conditions = conditions.get("sales_order_conditions", "")
	sales_order_query = f"""
		SELECT
			so.name as sales_order,
			so.customer
		FROM `tabSales Order` so
		WHERE so.docstatus = 1
		AND so.customer IN ({','.join(['%s'] * len(internal_customers))})
		{sales_order_conditions}
		ORDER BY so.transaction_date DESC, so.name DESC
	"""

	sales_orders = frappe.db.sql(sales_order_query, tuple(internal_customers), as_dict=True)

	# Also get Delivery Notes that might not have a Sales Order but are internal transfers
	delivery_note_without_sales_order_query = f"""
		SELECT DISTINCT
			dn.name as delivery_note,
			dn.customer,
			dn.custom_to_depot_name as to_depot
		FROM `tabDelivery Note` dn
		WHERE dn.docstatus = 1
		AND dn.customer IN ({','.join(['%s'] * len(internal_customers))})
		AND NOT EXISTS (
			SELECT 1 FROM `tabDelivery Note Item` dni
			WHERE dni.parent = dn.name
			AND dni.against_sales_order IS NOT NULL
			AND dni.against_sales_order != ''
		)
		{conditions.get("delivery_note_conditions", "")}
		ORDER BY dn.posting_date DESC, dn.name DESC
	"""

	delivery_notes_without_sales_order = frappe.db.sql(
		delivery_note_without_sales_order_query, tuple(internal_customers), as_dict=True
	)

	# Track what we've already shown to avoid duplicates in hierarchy display
	shown_sales_orders = set()
	shown_delivery_notes = {}
	shown_purchase_receipts = {}

	# Process Sales Orders
	for sales_order in sales_orders:
		delivery_notes = get_delivery_notes_for_sales_order(
			sales_order.sales_order, conditions.get("delivery_note_conditions", "")
		)

		if delivery_notes:
			for idx_dn, delivery_note in enumerate(delivery_notes):
				purchase_receipts = get_purchase_receipts_for_delivery_note(
					delivery_note.delivery_note, conditions.get("purchase_receipt_conditions", "")
				)
				sales_invoices = get_sales_invoices_for_delivery_note(
					delivery_note.delivery_note, conditions.get("sales_invoice_conditions", "")
				)

				# Build all combinations
				purchase_receipt_list = purchase_receipts if purchase_receipts else [{}]
				sales_invoice_list = sales_invoices if sales_invoices else [{}]

				row_count = 0
				for idx_pr, purchase_receipt in enumerate(purchase_receipt_list):
					for idx_si, sales_invoice in enumerate(sales_invoice_list):
						purchase_invoice_data = {}
						if sales_invoice.get("sales_invoice"):
							purchase_invoices = get_purchase_invoices_for_sales_invoice(
								sales_invoice.sales_invoice, conditions.get("purchase_invoice_conditions", "")
							)
							if purchase_invoices:
								purchase_invoice_data = purchase_invoices[0]

						row = build_row(
							sales_order_data=sales_order if row_count == 0 else {},
							delivery_note_data=delivery_note if (row_count == 0 or idx_dn > shown_delivery_notes.get(delivery_note.delivery_note, -1)) else {},
							purchase_receipt_data=purchase_receipt if (row_count == 0 or idx_pr > shown_purchase_receipts.get(purchase_receipt.get("purchase_receipt"), -1)) else {},
							sales_invoice_data=sales_invoice,
							purchase_invoice_data=purchase_invoice_data,
							is_first_row=(row_count == 0)
						)

						# Track shown items
						if delivery_note.delivery_note:
							shown_delivery_notes[delivery_note.delivery_note] = idx_dn
						if purchase_receipt.get("purchase_receipt"):
							shown_purchase_receipts[purchase_receipt.get("purchase_receipt")] = idx_pr

						data.append(row)
						row_count += 1
		else:
			# No Delivery Note yet - show Sales Order only
			row = build_row(
				sales_order_data=sales_order,
				delivery_note_data={},
				purchase_receipt_data={},
				sales_invoice_data={},
				purchase_invoice_data={},
				is_first_row=True
			)
			data.append(row)

		shown_sales_orders.add(sales_order.sales_order)

	# Process Delivery Notes without Sales Order
	for delivery_note in delivery_notes_without_sales_order:
		delivery_note_data = {
			"delivery_note": delivery_note.delivery_note,
			"to_depot": delivery_note.to_depot,
		}

		purchase_receipts = get_purchase_receipts_for_delivery_note(
			delivery_note.delivery_note, conditions.get("purchase_receipt_conditions", "")
		)
		sales_invoices = get_sales_invoices_for_delivery_note(
			delivery_note.delivery_note, conditions.get("sales_invoice_conditions", "")
		)

		sales_order_data = {"customer": delivery_note.customer}

		purchase_receipt_list = purchase_receipts if purchase_receipts else [{}]
		sales_invoice_list = sales_invoices if sales_invoices else [{}]

		row_count = 0
		for idx_pr, purchase_receipt in enumerate(purchase_receipt_list):
			for idx_si, sales_invoice in enumerate(sales_invoice_list):
				purchase_invoice_data = {}
				if sales_invoice.get("sales_invoice"):
					purchase_invoices = get_purchase_invoices_for_sales_invoice(
						sales_invoice.sales_invoice, conditions.get("purchase_invoice_conditions", "")
					)
					if purchase_invoices:
						purchase_invoice_data = purchase_invoices[0]

				row = build_row(
					sales_order_data=sales_order_data if row_count == 0 else {},
					delivery_note_data=delivery_note_data if row_count == 0 else {},
					purchase_receipt_data=purchase_receipt if row_count == 0 or idx_pr > 0 else {},
					sales_invoice_data=sales_invoice,
					purchase_invoice_data=purchase_invoice_data,
					is_first_row=(row_count == 0)
				)
				data.append(row)
				row_count += 1

	# Apply transfer status filter if specified
	if filters.get("transfer_status"):
		data = [d for d in data if d.get("transfer_status") == filters.get("transfer_status")]

	return data


def get_delivery_notes_for_sales_order(sales_order, delivery_note_conditions=""):
	query = f"""
		SELECT DISTINCT
			dn.name as delivery_note,
			dn.custom_to_depot_name as to_depot
		FROM `tabDelivery Note` dn
		INNER JOIN `tabDelivery Note Item` dni ON dni.parent = dn.name
		WHERE dn.docstatus = 1
		AND dni.against_sales_order = %s
		{delivery_note_conditions}
		ORDER BY dn.posting_date, dn.name
	"""
	return frappe.db.sql(query, (sales_order,), as_dict=True)


def get_purchase_receipts_for_delivery_note(delivery_note, purchase_receipt_conditions=""):
	query = f"""
		SELECT DISTINCT
			pr.name as purchase_receipt
		FROM `tabPurchase Receipt` pr
		WHERE pr.docstatus = 1
		AND (pr.custom_delivery_note = %s OR pr.supplier_delivery_note = %s)
		{purchase_receipt_conditions}
		ORDER BY pr.posting_date, pr.name
	"""
	return frappe.db.sql(query, (delivery_note, delivery_note), as_dict=True)


def get_sales_invoices_for_delivery_note(delivery_note, sales_invoice_conditions=""):
	query = f"""
		SELECT DISTINCT
			si.name as sales_invoice
		FROM `tabSales Invoice` si
		INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		WHERE si.docstatus = 1
		AND sii.delivery_note = %s
		{sales_invoice_conditions}
		ORDER BY si.posting_date, si.name
	"""
	return frappe.db.sql(query, (delivery_note,), as_dict=True)


def get_purchase_invoices_for_sales_invoice(sales_invoice, purchase_invoice_conditions=""):
	query = f"""
		SELECT DISTINCT
			pi.name as purchase_invoice
		FROM `tabPurchase Invoice` pi
		WHERE pi.docstatus = 1
		AND pi.custom_sales_invoice = %s
		{purchase_invoice_conditions}
		ORDER BY pi.posting_date, pi.name
	"""
	return frappe.db.sql(query, (sales_invoice,), as_dict=True)


def build_row(sales_order_data, delivery_note_data, purchase_receipt_data, sales_invoice_data, purchase_invoice_data, is_first_row=False):
	row = {
		"sales_order": sales_order_data.get("sales_order"),
		"customer": sales_order_data.get("customer"),
		"delivery_note": delivery_note_data.get("delivery_note"),
		"to_depot": delivery_note_data.get("to_depot"),
		"purchase_receipt": purchase_receipt_data.get("purchase_receipt"),
		"sales_invoice": sales_invoice_data.get("sales_invoice"),
		"purchase_invoice": purchase_invoice_data.get("purchase_invoice"),
	}

	# Determine transfer status
	row["transfer_status"] = get_transfer_status(row)

	return row


def get_transfer_status(row):
	if row.get("purchase_invoice"):
		return "Completed"
	elif row.get("sales_invoice") and not row.get("purchase_invoice"):
		return "Purchase Invoice Pending"
	elif row.get("purchase_receipt") and not row.get("sales_invoice"):
		return "Sales Invoice Pending"
	elif row.get("delivery_note") and not row.get("purchase_receipt"):
		return "Purchase Receipt Pending"
	elif row.get("sales_order") and not row.get("delivery_note"):
		return "Delivery Note Pending"
	else:
		return "In Progress"


def get_conditions(filters):
	conditions = {
		"sales_order_conditions": "",
		"delivery_note_conditions": "",
		"purchase_receipt_conditions": "",
		"sales_invoice_conditions": "",
		"purchase_invoice_conditions": "",
	}

	if filters.get("from_date"):
		conditions["sales_order_conditions"] += f" AND so.transaction_date >= '{filters.get('from_date')}'"
		conditions["delivery_note_conditions"] += f" AND dn.posting_date >= '{filters.get('from_date')}'"

	if filters.get("to_date"):
		conditions["sales_order_conditions"] += f" AND so.transaction_date <= '{filters.get('to_date')}'"
		conditions["delivery_note_conditions"] += f" AND dn.posting_date <= '{filters.get('to_date')}'"

	if filters.get("customer"):
		conditions["sales_order_conditions"] += f" AND so.customer = '{filters.get('customer')}'"
		conditions["delivery_note_conditions"] += f" AND dn.customer = '{filters.get('customer')}'"

	if filters.get("to_depot"):
		conditions["delivery_note_conditions"] += f" AND dn.custom_to_depot_name = '{filters.get('to_depot')}'"

	return conditions
