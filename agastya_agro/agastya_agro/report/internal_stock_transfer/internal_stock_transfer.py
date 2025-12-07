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
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 150},
		# Sales Order
		{"label": _("Sales Order"), "fieldname": "sales_order", "fieldtype": "Link", "options": "Sales Order", "width": 130},
		{"label": _("SO Date"), "fieldname": "so_date", "fieldtype": "Date", "width": 100},
		{"label": _("SO Item"), "fieldname": "so_item", "fieldtype": "Link", "options": "Item", "width": 120},
		{"label": _("SO Qty"), "fieldname": "so_qty", "fieldtype": "Float", "width": 80},
		# Delivery Note
		{"label": _("Delivery Note"), "fieldname": "delivery_note", "fieldtype": "Link", "options": "Delivery Note", "width": 130},
		{"label": _("DN Date"), "fieldname": "dn_date", "fieldtype": "Date", "width": 100},
		{"label": _("DN Qty"), "fieldname": "dn_qty", "fieldtype": "Float", "width": 80},
		{"label": _("DN Item"), "fieldname": "dn_item", "fieldtype": "Link", "options": "Item", "width": 120},

		{"label": _("From Depot"), "fieldname": "from_depot", "fieldtype": "Data", "width": 120},
		{"label": _("To Depot"), "fieldname": "to_depot", "fieldtype": "Data", "width": 120},
		# Sales Invoice
		{"label": _("Sales Invoice"), "fieldname": "sales_invoice", "fieldtype": "Link", "options": "Sales Invoice", "width": 130},
		{"label": _("SI Date"), "fieldname": "si_date", "fieldtype": "Date", "width": 100},
		{"label": _("SI Qty"), "fieldname": "si_qty", "fieldtype": "Float", "width": 80},
		{"label": _("SI Item"), "fieldname": "si_item", "fieldtype": "Link", "options": "Item", "width": 120},

		# Purchase Receipt
		{"label": _("Purchase Receipt"), "fieldname": "purchase_receipt", "fieldtype": "Link", "options": "Purchase Receipt", "width": 130},
		{"label": _("PR Date"), "fieldname": "pr_date", "fieldtype": "Date", "width": 100},
		{"label": _("PR Qty"), "fieldname": "pr_qty", "fieldtype": "Float", "width": 80},
		{"label": _("PR Item"), "fieldname": "pr_item", "fieldtype": "Link", "options": "Item", "width": 120},

		# Purchase Invoice (linked from PR)
		{"label": _("Purchase Invoice"), "fieldname": "purchase_invoice", "fieldtype": "Link", "options": "Purchase Invoice", "width": 130},
		{"label": _("PI Date"), "fieldname": "pi_date", "fieldtype": "Date", "width": 100},
		{"label": _("PI Qty"), "fieldname": "pi_qty", "fieldtype": "Float", "width": 80},
		{"label": _("PI Item"), "fieldname": "pi_item", "fieldtype": "Link", "options": "Item", "width": 120},

		
	]


def get_data(filters):
	"""
	Hierarchical structure - all on same rows:
	Customer -> SO (with items) -> DN (with items) -> SI -> PR -> PI
	SO items and DN items are aligned by item_code.
	"""
	data = []

	# Step 1: Get internal transfer customers
	internal_customers = get_internal_customers(filters)
	if not internal_customers:
		return []

	# Step 2: For each customer, get SO -> DN -> SI -> PR -> PI
	for customer in internal_customers:
		customer_added = False

		# Get all Sales Orders for this customer
		sales_orders = get_sales_orders(customer, filters)

		for so in sales_orders:
			so_added = False

			# Get SO items
			so_items = get_so_items(so.name, filters)

			# Get all DN data for this SO (dict keyed by item_code)
			dn_data_by_item = get_all_dn_data(so.name, filters)

			# Track which DN data rows have been used per item
			dn_data_index = {item_code: 0 for item_code in dn_data_by_item}

			# Process SO items first, aligning with their corresponding DN data
			for so_item in so_items:
				item_code = so_item.item_code
				dn_rows = dn_data_by_item.get(item_code, [])

				# Calculate how many rows needed for this SO item
				max_rows_for_item = max(len(dn_rows), 1)
				so_item_added = False

				for i in range(max_rows_for_item):
					row = {}

					# Customer - only first row of entire result
					if not customer_added:
						row["customer"] = customer
						customer_added = True

					# SO - only first row of this SO
					if not so_added:
						row["sales_order"] = so.name
						row["so_date"] = so.transaction_date
						so_added = True

					# SO Item - only first row for this item
					if not so_item_added:
						row["so_item"] = item_code
						row["so_qty"] = so_item.qty
						so_item_added = True

					# DN data for this item at current index
					if i < len(dn_rows):
						dn_row = dn_rows[i]
						row["delivery_note"] = dn_row.get("delivery_note")
						row["dn_date"] = dn_row.get("dn_date")
						row["dn_item"] = dn_row.get("dn_item")
						row["dn_qty"] = dn_row.get("dn_qty")
						row["from_depot"] = dn_row.get("from_depot")
						row["to_depot"] = dn_row.get("to_depot")
						row["sales_invoice"] = dn_row.get("sales_invoice")
						row["si_date"] = dn_row.get("si_date")
						row["si_item"] = dn_row.get("si_item")
						row["si_qty"] = dn_row.get("si_qty")
						row["purchase_receipt"] = dn_row.get("purchase_receipt")
						row["pr_date"] = dn_row.get("pr_date")
						row["pr_item"] = dn_row.get("pr_item")
						row["pr_qty"] = dn_row.get("pr_qty")
						row["purchase_invoice"] = dn_row.get("purchase_invoice")
						row["pi_date"] = dn_row.get("pi_date")
						row["pi_item"] = dn_row.get("pi_item")
						row["pi_qty"] = dn_row.get("pi_qty")
						dn_data_index[item_code] = i + 1

					data.append(row)

			# Handle DN items that don't have matching SO items
			for item_code, dn_rows in dn_data_by_item.items():
				start_index = dn_data_index.get(item_code, 0)
				for i in range(start_index, len(dn_rows)):
					row = {}

					if not customer_added:
						row["customer"] = customer
						customer_added = True

					if not so_added:
						row["sales_order"] = so.name
						row["so_date"] = so.transaction_date
						so_added = True

					dn_row = dn_rows[i]
					row["delivery_note"] = dn_row.get("delivery_note")
					row["dn_date"] = dn_row.get("dn_date")
					row["dn_item"] = dn_row.get("dn_item")
					row["dn_qty"] = dn_row.get("dn_qty")
					row["from_depot"] = dn_row.get("from_depot")
					row["to_depot"] = dn_row.get("to_depot")
					row["sales_invoice"] = dn_row.get("sales_invoice")
					row["si_date"] = dn_row.get("si_date")
					row["si_item"] = dn_row.get("si_item")
					row["si_qty"] = dn_row.get("si_qty")
					row["purchase_receipt"] = dn_row.get("purchase_receipt")
					row["pr_date"] = dn_row.get("pr_date")
					row["pr_item"] = dn_row.get("pr_item")
					row["pr_qty"] = dn_row.get("pr_qty")
					row["purchase_invoice"] = dn_row.get("purchase_invoice")
					row["pi_date"] = dn_row.get("pi_date")
					row["pi_item"] = dn_row.get("pi_item")
					row["pi_qty"] = dn_row.get("pi_qty")

					data.append(row)

	return data


def get_all_dn_data(sales_order, filters):
	"""
	Get all DN items with SI, PR, PI data for a SO.
	Returns a dict keyed by item_code for proper alignment with SO items.
	"""
	# Result is a dict: item_code -> list of rows for that item
	result_by_item = {}

	delivery_notes = get_delivery_notes(sales_order, filters)

	for dn in delivery_notes:
		dn_added = False
		dn_items = get_dn_items(dn.name, filters)

		# Get all PRs for this DN (at DN level, not per item)
		all_pr_items = get_all_pr_items_for_dn(dn.name)

		# Get all PIs for all PRs
		all_pi_items = []
		seen_pr_items = set()
		for pr in all_pr_items:
			pr_key = (pr.get("purchase_receipt"), pr.get("pr_item"))
			if pr_key not in seen_pr_items:
				seen_pr_items.add(pr_key)
				pis = get_all_pi_items(pr.get("purchase_receipt"), pr.get("pr_item"))
				all_pi_items.extend(pis)

		for dn_item in dn_items:
			item_code = dn_item.item_code
			if item_code not in result_by_item:
				result_by_item[item_code] = []

			dn_item_added = False

			# Get all SIs for this DN item
			si_list = get_all_si_items(dn.name, item_code)

			# Get PR items matching this DN item
			pr_list_for_item = [pr for pr in all_pr_items if pr.get("pr_item") == item_code]

			# Get PI items matching this DN item
			pi_list_for_item = [pi for pi in all_pi_items if pi.get("pi_item") == item_code]

			# Calculate max rows needed for this DN item
			max_sub_rows = max(len(si_list), len(pr_list_for_item), len(pi_list_for_item), 1)

			for j in range(max_sub_rows):
				row = {
					"delivery_note": dn.name if not dn_added else None,
					"dn_date": dn.posting_date if not dn_added else None,
					"from_depot": dn.set_warehouse if not dn_added else None,
					"to_depot": dn.custom_to_depot_name if not dn_added else None,
					"dn_item": item_code if not dn_item_added else None,
					"dn_qty": dn_item.qty if not dn_item_added else None,
				}

				# SI data
				if j < len(si_list):
					row["sales_invoice"] = si_list[j].get("sales_invoice")
					row["si_date"] = si_list[j].get("si_date")
					row["si_item"] = si_list[j].get("si_item")
					row["si_qty"] = si_list[j].get("si_qty")

				# PR data
				if j < len(pr_list_for_item):
					row["purchase_receipt"] = pr_list_for_item[j].get("purchase_receipt")
					row["pr_date"] = pr_list_for_item[j].get("pr_date")
					row["pr_item"] = pr_list_for_item[j].get("pr_item")
					row["pr_qty"] = pr_list_for_item[j].get("pr_qty")

				# PI data
				if j < len(pi_list_for_item):
					row["purchase_invoice"] = pi_list_for_item[j].get("purchase_invoice")
					row["pi_date"] = pi_list_for_item[j].get("pi_date")
					row["pi_item"] = pi_list_for_item[j].get("pi_item")
					row["pi_qty"] = pi_list_for_item[j].get("pi_qty")

				result_by_item[item_code].append(row)
				dn_added = True
				dn_item_added = True

	return result_by_item


def get_all_pr_items_for_dn(delivery_note):
	"""Get ALL Purchase Receipt items linked to DN (all items, not filtered by item_code)"""
	result = []

	# Try custom_delivery_note first
	pr_items = frappe.db.sql("""
		SELECT
			pr.name as purchase_receipt,
			pr.posting_date as pr_date,
			pri.item_code as pr_item,
			pri.qty as pr_qty
		FROM `tabPurchase Receipt` pr
		INNER JOIN `tabPurchase Receipt Item` pri ON pri.parent = pr.name
		WHERE pr.custom_delivery_note = %s
		AND pr.docstatus = 1
		ORDER BY pr.posting_date DESC, pri.idx
	""", (delivery_note,), as_dict=True)

	result.extend(pr_items)

	# Also try supplier_delivery_note
	pr_items2 = frappe.db.sql("""
		SELECT
			pr.name as purchase_receipt,
			pr.posting_date as pr_date,
			pri.item_code as pr_item,
			pri.qty as pr_qty
		FROM `tabPurchase Receipt` pr
		INNER JOIN `tabPurchase Receipt Item` pri ON pri.parent = pr.name
		WHERE pr.supplier_delivery_note = %s
		AND pr.docstatus = 1
		ORDER BY pr.posting_date DESC, pri.idx
	""", (delivery_note,), as_dict=True)

	# Add only if not already in result (avoid duplicates)
	existing_keys = {(r.get("purchase_receipt"), r.get("pr_item")) for r in result}
	for pr in pr_items2:
		if (pr.get("purchase_receipt"), pr.get("pr_item")) not in existing_keys:
			result.append(pr)

	return result


def get_internal_customers(filters):
	"""Get customers with internal stock transfer enabled"""
	customer_filters = {"custom_is_internal_transfer": 1}
	if filters.get("customer"):
		customer_filters["name"] = filters.get("customer")

	return frappe.get_all("Customer", filters=customer_filters, pluck="name")


def get_sales_orders(customer, filters):
	"""Get Sales Orders for a customer"""
	so_filters = {
		"docstatus": 1,
		"customer": customer
	}

	if filters.get("from_date"):
		so_filters["transaction_date"] = [">=", filters.get("from_date")]
	if filters.get("to_date"):
		if "transaction_date" in so_filters:
			so_filters["transaction_date"] = ["between", [filters.get("from_date"), filters.get("to_date")]]
		else:
			so_filters["transaction_date"] = ["<=", filters.get("to_date")]

	return frappe.get_all(
		"Sales Order",
		filters=so_filters,
		fields=["name", "transaction_date"],
		order_by="transaction_date desc"
	)


def get_so_items(sales_order, filters):
	"""Get items from Sales Order"""
	item_filters = {"parent": sales_order}
	if filters.get("item"):
		item_filters["item_code"] = filters.get("item")

	return frappe.get_all(
		"Sales Order Item",
		filters=item_filters,
		fields=["item_code", "qty"],
		order_by="idx"
	)


def get_delivery_notes(sales_order, filters):
	"""Get Delivery Notes linked to SO"""
	dn_list = frappe.db.sql("""
		SELECT DISTINCT dn.name, dn.posting_date, dn.set_warehouse, dn.custom_to_depot_name
		FROM `tabDelivery Note` dn
		INNER JOIN `tabDelivery Note Item` dni ON dni.parent = dn.name
		WHERE dni.against_sales_order = %s
		AND dn.docstatus = 1
		ORDER BY dn.posting_date DESC
	""", (sales_order,), as_dict=True)

	return dn_list


def get_dn_items(delivery_note, filters):
	"""Get items from Delivery Note"""
	item_filters = {"parent": delivery_note}
	if filters.get("item"):
		item_filters["item_code"] = filters.get("item")

	return frappe.get_all(
		"Delivery Note Item",
		filters=item_filters,
		fields=["item_code", "qty"],
		order_by="idx"
	)


def get_all_si_items(delivery_note, item_code):
	"""Get ALL Sales Invoice items linked to DN item"""
	result = frappe.db.sql("""
		SELECT
			si.name as sales_invoice,
			si.posting_date as si_date,
			sii.item_code as si_item,
			sii.qty as si_qty
		FROM `tabSales Invoice Item` sii
		INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
		WHERE sii.delivery_note = %s
		AND sii.item_code = %s
		AND si.docstatus = 1
		ORDER BY si.posting_date DESC
	""", (delivery_note, item_code), as_dict=True)

	return result


def get_all_pr_items(delivery_note, item_code):
	"""Get ALL Purchase Receipts linked to DN - returns all PR items for specific item"""
	result = []

	# Try custom_delivery_note first
	pr_items = frappe.db.sql("""
		SELECT
			pr.name as purchase_receipt,
			pr.posting_date as pr_date,
			pri.item_code as pr_item,
			pri.qty as pr_qty
		FROM `tabPurchase Receipt` pr
		INNER JOIN `tabPurchase Receipt Item` pri ON pri.parent = pr.name
		WHERE pr.custom_delivery_note = %s
		AND pri.item_code = %s
		AND pr.docstatus = 1
		ORDER BY pr.posting_date DESC, pri.idx
	""", (delivery_note, item_code), as_dict=True)

	result.extend(pr_items)

	# Also try supplier_delivery_note
	pr_items2 = frappe.db.sql("""
		SELECT
			pr.name as purchase_receipt,
			pr.posting_date as pr_date,
			pri.item_code as pr_item,
			pri.qty as pr_qty
		FROM `tabPurchase Receipt` pr
		INNER JOIN `tabPurchase Receipt Item` pri ON pri.parent = pr.name
		WHERE pr.supplier_delivery_note = %s
		AND pri.item_code = %s
		AND pr.docstatus = 1
		ORDER BY pr.posting_date DESC, pri.idx
	""", (delivery_note, item_code), as_dict=True)

	# Add only if not already in result (avoid duplicates)
	existing_prs = {r.get("purchase_receipt") for r in result}
	for pr in pr_items2:
		if pr.get("purchase_receipt") not in existing_prs:
			result.append(pr)

	return result


def get_all_pi_items(purchase_receipt, item_code):
	"""Get ALL Purchase Invoices linked to PR"""
	if not purchase_receipt:
		return []

	result = frappe.db.sql("""
		SELECT
			pi.name as purchase_invoice,
			pi.posting_date as pi_date,
			pii.item_code as pi_item,
			pii.qty as pi_qty
		FROM `tabPurchase Invoice Item` pii
		INNER JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
		WHERE pii.purchase_receipt = %s
		AND pii.item_code = %s
		AND pi.docstatus = 1
		ORDER BY pi.posting_date DESC
	""", (purchase_receipt, item_code), as_dict=True)

	return result
