# Copyright (c) 2025, Dexciss and contributors
# For license information, please see license.txt

import frappe
import datetime
from frappe.utils import flt

def execute(filters=None):
	columns, data = get_columns(filters), get_data(filters)
	return columns, data

def get_columns(filters):
	columns = [
		{"label": "Item", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
		{"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data", "width": 150},
		{"label": "Brand", "fieldname": "brand", "fieldtype": "Data", "width": 150},
		{"label": "Class", "fieldname": "class", "fieldtype": "Data", "width": 150},
		{"label": "Warehouse", "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 150},
		{"label": "Weight Per Unit", "fieldname": "wt_per_unit", "fieldtype": "Float", "width": 120},
		{"label": "Case Per Unit", "fieldname": "case_per_unit", "fieldtype": "Float", "width": 120},
		{"label": "Manufacturing Date", "fieldname": "mfg_date", "fieldtype": "Date", "width": 120},
		{"label": "Expiry Date", "fieldname": "expiry_date", "fieldtype": "Date", "width": 120},
		{"label": "Batch No", "fieldname": "batch_no", "fieldtype": "Link", "options": "Batch", "width": 120},
		{"label": "Old Batch No", "fieldname": "old_batch_no", "fieldtype": "Data", "width": 150},
		{"label": "Opening Qty", "fieldname": "opening_qty", "fieldtype": "Float", "width": 120},
		{"label": "In Qty", "fieldname": "in_qty", "fieldtype": "Float", "width": 120},
		{"label": "Out Qty", "fieldname": "out_qty", "fieldtype": "Float", "width": 120},
		{"label": "Balance Qty", "fieldname": "balance_qty", "fieldtype": "Float", "width": 120},
		{"label": "UOM", "fieldname": "uom", "fieldtype": "Data", "width": 120},
		{"label": "Cases", "fieldname": "cases", "fieldtype": "Float", "width": 120},
		{"label": "Weight", "fieldname": "weight", "fieldtype": "Float", "width": 120},
		{"label": "Shelf Life", "fieldname": "shelf_life", "fieldtype": "Int", "width": 120},
		{"label": "Lapsed Life", "fieldname": "lapsed_life", "fieldtype": "Int", "width": 120},
		{"label": "Balance Life", "fieldname": "balance_life", "fieldtype": "Int", "width": 120},
		{"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 170},
	]
	return columns

def get_data(filters):
	from_date = filters.get("from_date")
	to_date = filters.get("to_date")
	warehouse = filters.get("warehouse")
	item = filters.get("item")

	conditions = ""
	if warehouse:
		conditions += f" AND sle.warehouse = '{warehouse}'"
	if item:
		conditions += f" AND sle.item_code = '{item}'"

	# Opening qty before from_date
	# opening_data = frappe.db.sql(f"""
	# 	SELECT
	# 		sle.item_code,
	# 		sle.warehouse,
	# 		sle.batch_no,
	# 		SUM(sle.actual_qty) AS opening_qty
	# 	FROM `tabStock Ledger Entry` sle
	# 	WHERE sle.posting_date < %s AND sle.is_cancelled = 0 {conditions}
	# 	GROUP BY sle.item_code, sle.warehouse, sle.batch_no
	# """, (from_date,), as_dict=True)
	opening_data = frappe.db.sql(f"""
	SELECT
		sle.item_code,
		sle.warehouse,
		COALESCE(sle.batch_no, sbbi.batch_no) AS batch_no,
		SUM(sle.actual_qty) AS opening_qty
	FROM `tabStock Ledger Entry` sle
	LEFT JOIN `tabSerial and Batch Bundle` sbb ON sbb.name = sle.serial_and_batch_bundle
	LEFT JOIN `tabSerial and Batch Entry` sbbi ON sbbi.parent = sbb.name
	WHERE sle.posting_date < %s {conditions}
	GROUP BY sle.item_code, sle.warehouse, COALESCE(sle.batch_no, sbbi.batch_no)
	""", (from_date,), as_dict=True)


	opening_map = {(d.item_code, d.warehouse, d.batch_no): d.opening_qty for d in opening_data}

	# Movement between date range
	# movement_data = frappe.db.sql(f"""
	# 	SELECT
	# 		sle.item_code,
	# 		item.item_name,
	# 		item.brand,
	# 		item.class AS custom_class,
	# 		sle.warehouse,
	# 		batch.manufacturing_date AS mfg_date,
	# 		batch.expiry_date,
	# 		batch.name AS batch_no,
	# 		batch.old_batch_no AS old_batch_no,
	# 		item.stock_uom AS uom,
	# 		item.case_per_unit AS case_per_unit,
	# 		item.weight_per_unit AS wt_per_unit,
	# 		SUM(CASE WHEN sle.actual_qty > 0 THEN sle.actual_qty ELSE 0 END) AS in_qty,
	# 		SUM(CASE WHEN sle.actual_qty < 0 THEN ABS(sle.actual_qty) ELSE 0 END) AS out_qty
	# 	FROM `tabStock Ledger Entry` sle
	# 	LEFT JOIN `tabItem` item ON item.name = sle.item_code
	# 	LEFT JOIN `tabBatch` batch ON batch.name = sle.batch_no
	# 	WHERE sle.posting_date BETWEEN %s AND %s AND sle.is_cancelled = 0 {conditions}
	# 	GROUP BY sle.item_code, sle.warehouse, sle.batch_no
	# """, (from_date, to_date), as_dict=True)

	movement_data = frappe.db.sql(f"""
		SELECT
			sle.item_code,
			item.item_name,
			item.brand,
			item.class AS custom_class,
			sle.warehouse,
			COALESCE(sle.batch_no, sbbi.batch_no) AS batch_no,
			batch.manufacturing_date AS mfg_date,
			batch.expiry_date,
			batch.old_batch_no AS old_batch_no,
			item.stock_uom AS uom,
			item.case_per_unit AS case_per_unit,
			item.weight_per_unit AS wt_per_unit,
			SUM(CASE WHEN sle.actual_qty > 0 THEN sle.actual_qty ELSE 0 END) AS in_qty,
			SUM(CASE WHEN sle.actual_qty < 0 THEN ABS(sle.actual_qty) ELSE 0 END) AS out_qty
		FROM `tabStock Ledger Entry` sle
		LEFT JOIN `tabSerial and Batch Bundle` sbb ON sbb.name = sle.serial_and_batch_bundle
		LEFT JOIN `tabSerial and Batch Entry` sbbi ON sbbi.parent = sbb.name
		LEFT JOIN `tabBatch` batch ON batch.name = COALESCE(sle.batch_no, sbbi.batch_no)
		LEFT JOIN `tabItem` item ON item.name = sle.item_code
		WHERE sle.posting_date BETWEEN %s AND %s {conditions}
		GROUP BY sle.item_code, sle.warehouse, COALESCE(sle.batch_no, sbbi.batch_no)
	""", (from_date, to_date), as_dict=True)


	data = []

	for d in movement_data:
		opening_qty = opening_map.get((d.item_code, d.warehouse, d.batch_no), 0)
		balance_qty = opening_qty + d.in_qty - d.out_qty

		shelf_life = None
		lapsed_life = None
		balance_life = None
		status = ""
		if d.mfg_date and d.expiry_date:
			shelf_life = (d.expiry_date - d.mfg_date).days

			today = frappe.utils.getdate(frappe.utils.nowdate())
			lapsed_life = (today - d.mfg_date).days
			balance_life = (d.expiry_date - today).days
			status = "Expired" if balance_life <= 0 else "Near Expiry" if balance_life > 0 and balance_life < 120 else "More Than 120 Days" 

		conv_factor = frappe.get_value(
			"UOM Conversion Detail",
			{'parent': d.item_code, 'is_alternate_uom': 1},
			'conversion_factor'
			)

		cases = (flt(balance_qty) / flt(conv_factor)) if conv_factor else 0

		row = {
			"item_code": d.item_code,
			"item_name": d.item_name,
			"wt_per_unit":d.wt_per_unit,
			"case_per_unit":d.case_per_unit,
			"brand": d.brand,
			"class": d.custom_class,
			"warehouse": d.warehouse,
			"batch_no": d.batch_no,
			"old_batch_no": d.old_batch_no,
			"opening_qty": opening_qty,
			"in_qty": d.in_qty,
			"out_qty": d.out_qty,
			"balance_qty": balance_qty,
			"uom": d.uom,
			"cases": cases,
			"weight": balance_qty * (d.wt_per_unit or 0),
			"mfg_date": d.mfg_date,
			"expiry_date": d.expiry_date,
			"shelf_life": shelf_life,
			"lapsed_life": lapsed_life,
			"balance_life": balance_life,
			"status": status,
		}

		data.append(row)

	return data

