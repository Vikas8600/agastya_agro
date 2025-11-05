# Copyright (c) 2025, Dexciss and contributors

import frappe
from frappe.utils import getdate, flt


def execute(filters=None):
	filters = filters or {}
	as_on_date = getdate(filters.get("posting_date") or None)
	company = filters.get("company")
	selected_warehouse = filters.get("warehouse")

	columns = get_columns()
	data = get_data(company, as_on_date, selected_warehouse)
	return columns, data


def get_columns():
	return [
		{"label": "Warehouse", "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 220},
		{"label": "Already Expired", "fieldname": "already_expired", "fieldtype": "Float", "width": 130},
		{"label": "Near Expiry (<120 days)", "fieldname": "near_expiry", "fieldtype": "Float", "width": 150},
		{"label": "Regular Stock (>120 days)", "fieldname": "regular_stock", "fieldtype": "Float", "width": 160},
		{"label": "Total (Rs.)", "fieldname": "total_value", "fieldtype": "Float", "width": 130},
	]


def get_data(company, as_on_date, selected_warehouse):
	warehouse_filter = ""
	params = [company, as_on_date]
	if selected_warehouse:
		warehouse_filter = " AND sle.warehouse = %s "
		params.append(selected_warehouse)

	query = f"""
		SELECT
			sle.warehouse,
			addr.state,
			COALESCE(sle.batch_no, sbe.batch_no) AS batch_no,
			batch.expiry_date,
			SUM(sle.actual_qty) AS stock_value
		FROM `tabStock Ledger Entry` sle
		LEFT JOIN `tabSerial and Batch Bundle` sbb 
			ON sbb.name = sle.serial_and_batch_bundle
		LEFT JOIN `tabSerial and Batch Entry` sbe 
			ON sbe.parent = sbb.name
		LEFT JOIN `tabBatch` batch 
			ON batch.name = COALESCE(sle.batch_no, sbe.batch_no)
		INNER JOIN `tabItem` item 
			ON item.name = sle.item_code
		LEFT JOIN `tabDynamic Link` dl 
			ON dl.link_doctype = 'Warehouse' 
			AND dl.link_name = sle.warehouse 
			AND dl.parenttype = 'Address'
		LEFT JOIN `tabAddress` addr 
			ON addr.name = dl.parent
		WHERE 
			sle.company = %s
			AND sle.is_cancelled = 0
			AND item.is_stock_item = 1
			AND sle.posting_date <= %s
			{warehouse_filter}
		GROUP BY sle.warehouse, batch.expiry_date, addr.state
	"""

	rows = frappe.db.sql(query, tuple(params), as_dict=True)

	result_map = {}
	for row in rows:
		expiry = row.get("expiry_date")
		value = flt(row.get("stock_value") or 0)
		warehouse = row.get("warehouse") or ""
		state = row.get("state") or ""

		if warehouse not in result_map:
			result_map[warehouse] = {
				"state": state,
				"already_expired": 0,
				"near_expiry": 0,
				"regular_stock": 0,
				"total_value": 0,
			}

		if expiry:
			days_left = (expiry - as_on_date).days
			if days_left < 0:
				result_map[warehouse]["already_expired"] += value
			elif days_left <= 120:
				result_map[warehouse]["near_expiry"] += value
			else:
				result_map[warehouse]["regular_stock"] += value
		else:
			# Treat batches without expiry as regular
			result_map[warehouse]["regular_stock"] += value

		result_map[warehouse]["total_value"] += value

	# Prepare final data
	data = []
	for wh, vals in sorted(result_map.items()):
		data.append({
			"warehouse": wh,
			"already_expired": round(vals["already_expired"], 2),
			"near_expiry": round(vals["near_expiry"], 2),
			"regular_stock": round(vals["regular_stock"], 2),
			"total_value": round(vals["total_value"], 2),
		})

	# ---- Grand Total ----
	grand_total = {
		"warehouse": "Grand Total",
		"already_expired": round(sum(r["already_expired"] for r in data), 2),
		"near_expiry": round(sum(r["near_expiry"] for r in data), 2),
		"regular_stock": round(sum(r["regular_stock"] for r in data), 2),
		"total_value": round(sum(r["total_value"] for r in data), 2),
	}
	data.append(grand_total)

	# ---- Hyderabad and Other Summaries ----
	hyderabad_states = ["Telangana"]
	hyderabad_rows = [r for r in data if r.get("warehouse") and get_state(r["warehouse"]) in hyderabad_states]
	other_rows = [r for r in data if r.get("warehouse") and get_state(r["warehouse"]) not in hyderabad_states and r["warehouse"] != "Grand Total"]

	def sum_rows(rows):
		return {
			"already_expired": round(sum(r["already_expired"] for r in rows), 2),
			"near_expiry": round(sum(r["near_expiry"] for r in rows), 2),
			"regular_stock": round(sum(r["regular_stock"] for r in rows), 2),
			"total_value": round(sum(r["total_value"] for r in rows), 2),
		}

	if hyderabad_rows:
		hyb = sum_rows(hyderabad_rows)
		data.append({
			"warehouse": "At Hyderabad Depots",
			**hyb,
		})

	if other_rows:
		oth = sum_rows(other_rows)
		data.append({
			"warehouse": "Other Depots",
			**oth,
		})

	return data


def get_state(warehouse):
	"""Utility: fetch state from Address via Dynamic Link."""
	state = frappe.db.get_value(
		"Address",
		{
			"name": ["in", frappe.db.get_all(
				"Dynamic Link",
				filters={
					"link_doctype": "Warehouse",
					"link_name": warehouse,
					"parenttype": "Address"
				},
				pluck="parent"
			)]
		},
		"state"
	)
	return state or ""
