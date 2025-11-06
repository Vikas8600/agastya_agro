

# Copyright (c) 2025, Dexciss and contributors
# For license information, please see license.txt

# Copyright (c) 2025, Dexciss
# Statement showing the Expired and Near Expired Stock details as on Date

import frappe
from frappe.utils import flt, getdate


def execute(filters=None):
    if not filters:
        filters = {}

    as_on_date = getdate(filters.get("as_on_date")) if filters.get("as_on_date") else getdate()
    warehouse = filters.get("warehouse")
    brand = filters.get("brand")
    item = filters.get("item_code")

    columns = get_columns()
    data = get_data(as_on_date, warehouse, brand, item)

    return columns, data


def get_columns():
    return [
        {"label": "Warehouse", "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 180},
        {"label": "Brand", "fieldname": "brand", "fieldtype": "Data", "width": 150},
        {"label": "Item", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 220},
        {"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data", "width": 200},
        {"label": "Mfg Date", "fieldname": "mfg_date", "fieldtype": "Date", "width": 120},
        {"label": "Exp Date", "fieldname": "expiry_date", "fieldtype": "Date", "width": 120},
        {"label": "Batch", "fieldname": "batch_no", "fieldtype": "Link", "options": "Batch", "width": 150},
        {"label": "Old Batch No", "fieldname": "old_batch_no", "fieldtype": "Data", "width": 150},
        {"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 120},
        {"label": "Units", "fieldname": "balance_qty", "fieldtype": "Float", "width": 100},
        {"label": "Lt/Kg", "fieldname": "lt_kg", "fieldtype": "Float", "width": 100},
        {"label": "Cases", "fieldname": "cases", "fieldtype": "Float", "width": 100},
        {"label": "Value", "fieldname": "value", "fieldtype": "Currency", "width": 120},
    ]


def get_data(as_on_date, warehouse=None, brand=None, item=None):
	conditions = ""
	if warehouse:
		conditions += f" AND sle.warehouse = '{warehouse}'"
	if item:
		conditions += f" AND sle.item_code = '{item}'"
	if brand:
		conditions += f" AND item.brand = '{brand}'"

	# Fetch balance quantity up to as_on_date
	sle_data = frappe.db.sql(f"""
		SELECT
			sle.item_code,
			item.item_name,
			item.brand,
			sle.warehouse,
			COALESCE(sle.batch_no, sbbi.batch_no) AS batch_no,
			batch.manufacturing_date AS mfg_date,
			batch.expiry_date,
			batch.old_batch_no AS old_batch_no,
			item.stock_uom AS uom,
			item.case_per_unit AS case_per_unit,
			item.weight_per_unit AS wt_per_unit,
			SUM(sle.actual_qty) AS balance_qty,
			SUM(sle.stock_value_difference) AS stock_value
		FROM `tabStock Ledger Entry` sle
		LEFT JOIN `tabSerial and Batch Bundle` sbb ON sbb.name = sle.serial_and_batch_bundle
		LEFT JOIN `tabSerial and Batch Entry` sbbi ON sbbi.parent = sbb.name
		LEFT JOIN `tabBatch` batch ON batch.name = COALESCE(sle.batch_no, sbbi.batch_no)
		LEFT JOIN `tabItem` item ON item.name = sle.item_code
		WHERE sle.posting_date <= %s {conditions} AND COALESCE(sle.batch_no, sbbi.batch_no) IS NOT NULL 
		GROUP BY sle.item_code, sle.warehouse, COALESCE(sle.batch_no, sbbi.batch_no)
		HAVING SUM(sle.actual_qty) != 0
	""", (as_on_date,), as_dict=True)

	data = []

	for s in sle_data:
	
		mfg_date = s.mfg_date
		exp_date = s.expiry_date

		status = ""
		balance_life = 0
		if exp_date:
			balance_life = (exp_date - as_on_date).days
			if balance_life <= 0:
				status = "Expired"
			elif balance_life < 120:
				status = "Near Expired"
			else:
				continue  # skip active items

	
		conv_factor = frappe.get_value(
			"UOM Conversion Detail",
			{"parent": s.item_code, "is_alternate_uom": 1},
			"conversion_factor"
		)
	
		cases = flt(s.balance_qty) / flt(conv_factor or 1)
		lt_kg = flt(s.balance_qty) * flt(s.wt_per_unit or 0)

		# Get Valuation Rate
		# valuation_rate = frappe.db.get_value(
		# 	"Bin",
		# 	{"item_code": s.item_code, "warehouse": s.warehouse},
		# 	"valuation_rate",
		# 	order_by="creation desc"
		# ) or 0

		# value = flt(s.balance_qty) * flt(valuation_rate)

		# valuation_data = frappe.db.sql("""
		# 	SELECT valuation_rate
		# 	FROM `tabStock Ledger Entry`
		# 	WHERE item_code = %s
		# 	AND warehouse = %s
		# 	AND (batch_no = %s OR %s IS NULL)
		# 	AND posting_date <= %s
		# 	AND is_cancelled = 0
		# 	ORDER BY posting_date DESC, posting_time DESC, creation DESC
		# 	LIMIT 1
		# """, (s.item_code, s.warehouse, s.batch_no, s.batch_no, as_on_date), as_dict=True)

		# value = flt(valuation_data[0].valuation_rate) if valuation_data else 0



		
		data.append({
			"warehouse": s.warehouse,
			"brand": s.brand,
			"item_code": s.item_code,
			"item_name": s.item_name,
			"mfg_date": mfg_date,
			"expiry_date": exp_date,
			"batch_no": s.batch_no,
			"old_batch_no": s.old_batch_no,
			"status": status,
			"balance_qty": s.balance_qty,
			"lt_kg": lt_kg,
			"cases": round(cases),
			"value": s.stock_value
		})

	return data
