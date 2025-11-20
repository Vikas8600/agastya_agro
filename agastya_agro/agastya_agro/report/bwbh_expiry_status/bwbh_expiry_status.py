# Copyright (c) 2025, Dexciss and contributors
# For license information, please see license.txt

import frappe
import datetime
from frappe.utils import flt,getdate,cint

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

# def get_data(filters):
# 	from_date = filters.get("from_date")
# 	to_date = filters.get("to_date")
# 	warehouse = filters.get("warehouse")
# 	item = filters.get("item")

# 	conditions = ""
# 	if warehouse:
# 		conditions += f" AND sle.warehouse = '{warehouse}'"
# 	if item:
# 		conditions += f" AND sle.item_code = '{item}'"

	
# 	opening_data = frappe.db.sql(f"""
# 	SELECT
# 		sle.item_code,
# 		sle.warehouse,
# 		COALESCE(sle.batch_no, sbbi.batch_no) AS batch_no,
# 		SUM(sle.actual_qty) AS opening_qty
# 	FROM `tabStock Ledger Entry` sle
# 	LEFT JOIN `tabSerial and Batch Bundle` sbb ON sbb.name = sle.serial_and_batch_bundle
# 	LEFT JOIN `tabSerial and Batch Entry` sbbi ON sbbi.parent = sbb.name
# 	WHERE sle.posting_date < %s {conditions}
# 	 	AND sle.is_cancelled = 0
#     	AND sle.docstatus < 2
# 	GROUP BY sle.item_code, sle.warehouse, COALESCE(sle.batch_no, sbbi.batch_no)
# 	""", (from_date,), as_dict=True)


# 	opening_map = {(d.item_code, d.warehouse, d.batch_no): d.opening_qty for d in opening_data}


# 	movement_data = frappe.db.sql(f"""
# 		SELECT
# 			sle.item_code,
# 			item.item_name,
# 			item.brand,
# 			item.class AS custom_class,
# 			sle.warehouse,
# 			COALESCE(sle.batch_no, sbbi.batch_no) AS batch_no,
# 			batch.manufacturing_date AS mfg_date,
# 			batch.expiry_date,
# 			batch.old_batch_no AS old_batch_no,
# 			item.stock_uom AS uom,
# 			item.case_per_unit AS case_per_unit,
# 			item.weight_per_unit AS wt_per_unit,
# 			SUM(CASE WHEN sle.actual_qty > 0 THEN sle.actual_qty ELSE 0 END) AS in_qty,
# 			SUM(CASE WHEN sle.actual_qty < 0 THEN ABS(sle.actual_qty) ELSE 0 END) AS out_qty
# 		FROM `tabStock Ledger Entry` sle
# 		LEFT JOIN `tabSerial and Batch Bundle` sbb ON sbb.name = sle.serial_and_batch_bundle
# 		LEFT JOIN `tabSerial and Batch Entry` sbbi ON sbbi.parent = sbb.name
# 		LEFT JOIN `tabBatch` batch ON batch.name = COALESCE(sle.batch_no, sbbi.batch_no)
# 		LEFT JOIN `tabItem` item ON item.name = sle.item_code
# 		WHERE sle.posting_date BETWEEN %s AND %s
# 			AND sle.is_cancelled = 0
# 			AND sle.docstatus < 2
# 			{conditions}
# 		GROUP BY sle.item_code, sle.warehouse, COALESCE(sle.batch_no, sbbi.batch_no)

# 	""", (from_date, to_date), as_dict=True)

# 		# GROUP BY sle.item_code, sle.warehouse, COALESCE(sle.batch_no, sbbi.batch_no)
# 		# WHERE sle.posting_date BETWEEN %s AND %s {conditions}

	

# 	data = []

# 	for d in movement_data:
# 		opening_qty = opening_map.get((d.item_code, d.warehouse, d.batch_no), 0)
# 		balance_qty = opening_qty + d.in_qty - d.out_qty

# 		shelf_life = None
# 		lapsed_life = None
# 		balance_life = None
# 		status = ""
# 		if d.mfg_date and d.expiry_date:
# 			shelf_life = (d.expiry_date - d.mfg_date).days

# 			today = frappe.utils.getdate(frappe.utils.nowdate())
# 			lapsed_life = (today - d.mfg_date).days
# 			balance_life = (d.expiry_date - today).days
# 			status = "Expired" if balance_life <= 0 else "Near Expiry" if balance_life > 0 and balance_life < 120 else "More Than 120 Days" 

# 		conv_factor = frappe.get_value(
# 			"UOM Conversion Detail",
# 			{'parent': d.item_code, 'is_alternate_uom': 1},
# 			'conversion_factor'
# 			)

# 		cases = (flt(balance_qty) / flt(conv_factor)) if conv_factor else 0

# 		row = {
# 			"item_code": d.item_code,
# 			"item_name": d.item_name,
# 			"wt_per_unit":d.wt_per_unit,
# 			"case_per_unit":d.case_per_unit,
# 			"brand": d.brand,
# 			"class": d.custom_class,
# 			"warehouse": d.warehouse,
# 			"batch_no": d.batch_no,
# 			"old_batch_no": d.old_batch_no,
# 			"opening_qty": opening_qty,
# 			"in_qty": d.in_qty,
# 			"out_qty": d.out_qty,
# 			"balance_qty": balance_qty,
# 			"uom": d.uom,
# 			"cases": cases,
# 			"weight": balance_qty * (d.wt_per_unit or 0),
# 			"mfg_date": d.mfg_date,
# 			"expiry_date": d.expiry_date,
# 			"shelf_life": shelf_life,
# 			"lapsed_life": lapsed_life,
# 			"balance_life": balance_life,
# 			"status": status,
# 		}

# 		data.append(row)

# 	return data

# def get_data(filters):
# 	from_date = filters.get("from_date")
# 	to_date = filters.get("to_date")
# 	warehouse = filters.get("warehouse")
# 	item = filters.get("item")

# 	if not from_date:
# 		frappe.throw("'From Date' is required")
# 	if not to_date:
# 		frappe.throw("'To Date' is required")

# 	wh_cond = ""
# 	if warehouse:
# 		wh_cond = f" AND sle.warehouse = '{warehouse}'"

# 	item_cond = ""
# 	if item:
# 		item_cond = f" AND sle.item_code = '{item}'"

# 	to_datetime = to_date + " 23:59:59"

# 	query_batch_no = f"""
# 		SELECT
# 			sle.item_code,
# 			sle.warehouse,
# 			sle.batch_no,
# 			sle.posting_date,
# 			SUM(sle.actual_qty) AS actual_qty,
# 			SUM(sle.stock_value_difference) AS stock_value_difference
# 		FROM `tabStock Ledger Entry` sle
# 		WHERE sle.docstatus < 2
# 		  AND sle.is_cancelled = 0
# 		  AND sle.batch_no IS NOT NULL
# 		  AND sle.batch_no != ''
# 		  AND sle.posting_datetime <= %s
# 		  {wh_cond}
# 		  {item_cond}
# 		GROUP BY sle.voucher_no, sle.batch_no, sle.item_code, sle.warehouse
# 	"""
# 	sle_batch_no = frappe.db.sql(query_batch_no, (to_datetime,), as_dict=True) or []

# 	query_bundle = f"""
# 		SELECT
# 			sle.item_code,
# 			batch_package.warehouse AS warehouse,
# 			batch_package.batch_no,
# 			sle.posting_date,
# 			SUM(batch_package.qty) AS actual_qty,
# 			SUM(batch_package.stock_value_difference) AS stock_value_difference
# 		FROM `tabStock Ledger Entry` sle
# 		INNER JOIN `tabSerial and Batch Entry` batch_package
# 			ON batch_package.parent = sle.serial_and_batch_bundle
# 		WHERE sle.docstatus < 2
# 		  AND sle.is_cancelled = 0
# 		  AND sle.has_batch_no = 1
# 		  AND sle.posting_datetime <= %s
# 		  {(" AND batch_package.warehouse = '%s'" % warehouse) if (warehouse and not wh_cond) else ""}
# 		  {(" AND sle.item_code = '%s'" % item) if (item and not item_cond) else ""}
# 		GROUP BY sle.voucher_no, batch_package.batch_no, batch_package.warehouse
# 	"""
# 	# Note: we use same to_datetime
# 	sle_bundle = frappe.db.sql(query_bundle, (to_datetime,), as_dict=True) or []

# 	# combine both kinds of SLE entries (this mirrors standard get_stock_ledger_entries)
# 	all_sle = sle_batch_no + sle_bundle

# 	# Build item-warehouse-batch map exactly like standard iwb_map
# 	from frappe.utils import getdate, flt, cint
# 	float_precision = cint(frappe.db.get_default("float_precision")) or 3

# 	iwb_map = {}
# 	from_date_dt = getdate(from_date)
# 	to_date_dt = getdate(to_date)

# 	for d in all_sle:
# 		item_code = d.get("item_code")
# 		warehouse_key = d.get("warehouse")
# 		batch_no = d.get("batch_no") or ""

# 		iwb_map.setdefault(item_code, {}).setdefault(warehouse_key, {}).setdefault(
# 			batch_no,
# 			frappe._dict(
# 				{"opening_qty": 0.0, "in_qty": 0.0, "out_qty": 0.0, "bal_qty": 0.0, "bal_value": 0.0}
# 			),
# 		)
# 		qty_dict = iwb_map[item_code][warehouse_key][batch_no]

# 		# posting_date may be datetime or date — convert to date for comparisons
# 		posting_date = d.get("posting_date")
# 		if isinstance(posting_date, str):
# 			# when posting_date comes as string date
# 			try:
# 				post_dt = getdate(posting_date)
# 			except Exception:
# 				post_dt = posting_date
# 		else:
# 			post_dt = getdate(posting_date)

# 		# Opening (before from_date) OR movement (within date range)
# 		if post_dt < from_date_dt:
# 			qty_dict.opening_qty = flt(qty_dict.opening_qty, float_precision) + flt(d.get("actual_qty"), float_precision)
# 		elif post_dt >= from_date_dt and post_dt <= to_date_dt:
# 			if flt(d.get("actual_qty")) > 0:
# 				qty_dict.in_qty = flt(qty_dict.in_qty, float_precision) + flt(d.get("actual_qty"), float_precision)
# 			else:
# 				qty_dict.out_qty = flt(qty_dict.out_qty, float_precision) + abs(flt(d.get("actual_qty"), float_precision))

# 		# balance and balance value are cumulative regardless of date (as standard)
# 		qty_dict.bal_qty = flt(qty_dict.bal_qty, float_precision) + flt(d.get("actual_qty"), float_precision)
# 		qty_dict.bal_value += flt(d.get("stock_value_difference"), float_precision)

# 	# Now build final rows from iwb_map ensuring we include batches that have only opening_qty
# 	data = []
# 	# We'll need item fields and batch fields for each row
# 	for item_code in sorted(iwb_map):
# 		# if item filter provided, skip otherwise
# 		if item and item != item_code:
# 			continue

# 		# get item static fields once
# 		item_doc = frappe.get_doc("Item", item_code) if item_code else None
# 		item_name = item_doc.item_name if item_doc else frappe.db.get_value("Item", item_code, "item_name")
# 		brand = item_doc.brand if item_doc else frappe.db.get_value("Item", item_code, "brand")
# 		custom_class = item_doc.get("class") if item_doc else frappe.db.get_value("Item", item_code, "class")
# 		uom = item_doc.stock_uom if item_doc else frappe.db.get_value("Item", item_code, "stock_uom")
# 		case_per_unit = item_doc.case_per_unit if item_doc else frappe.db.get_value("Item", item_code, "case_per_unit")
# 		wt_per_unit = item_doc.weight_per_unit if item_doc else frappe.db.get_value("Item", item_code, "weight_per_unit")

# 		for wh in sorted(iwb_map[item_code]):
# 			# warehouse filter already applied in queries, but double-check
# 			if warehouse and wh != warehouse:
# 				continue

# 			for batch_no in sorted(iwb_map[item_code][wh]):
# 				qty_dict = iwb_map[item_code][wh][batch_no]

# 				# only include rows that have opening/in/out/bal (same behaviour as standard)
# 				if not (qty_dict.opening_qty or qty_dict.in_qty or qty_dict.out_qty or qty_dict.bal_qty):
# 					continue

# 				opening_qty = flt(qty_dict.opening_qty, float_precision)
# 				in_qty = flt(qty_dict.in_qty, float_precision)
# 				out_qty = flt(qty_dict.out_qty, float_precision)
# 				balance_qty = flt(qty_dict.bal_qty, float_precision)

# 				# batch fields
# 				mfg_date = frappe.db.get_value("Batch", batch_no, "manufacturing_date") if batch_no else None
# 				expiry_date = frappe.db.get_value("Batch", batch_no, "expiry_date") if batch_no else None
# 				old_batch_no = frappe.db.get_value("Batch", batch_no, "old_batch_no") if batch_no else None

# 				# shelf life calculations (same as your old code)
# 				shelf_life = None
# 				lapsed_life = None
# 				balance_life = None
# 				status = ""
# 				if mfg_date and expiry_date:
# 					shelf_life = (expiry_date - mfg_date).days if hasattr(expiry_date, "day") else None
# 					today = frappe.utils.getdate(frappe.utils.nowdate())
# 					lapsed_life = (today - mfg_date).days if hasattr(mfg_date, "day") else None
# 					balance_life = (expiry_date - today).days if hasattr(expiry_date, "day") else None
# 					status = "Expired" if balance_life <= 0 else "Near Expiry" if balance_life > 0 and balance_life < 120 else "More Than 120 Days"

# 				# conv factor for cases (same as you had)
# 				conv_factor = frappe.get_value(
# 					"UOM Conversion Detail",
# 					{'parent': item_code, 'is_alternate_uom': 1},
# 					'conversion_factor'
# 				)
# 				cases = (flt(balance_qty) / flt(conv_factor)) if conv_factor else 0

# 				row = {
# 					"item_code": item_code,
# 					"item_name": item_name,
# 					"wt_per_unit": wt_per_unit,
# 					"case_per_unit": case_per_unit,
# 					"brand": brand,
# 					"class": custom_class,
# 					"warehouse": wh,
# 					"batch_no": batch_no,
# 					"old_batch_no": old_batch_no,
# 					"opening_qty": opening_qty,
# 					"in_qty": in_qty,
# 					"out_qty": out_qty,
# 					"balance_qty": balance_qty,
# 					"uom": uom,
# 					"cases": cases,
# 					"weight": balance_qty * (wt_per_unit or 0),
# 					"mfg_date": mfg_date,
# 					"expiry_date": expiry_date,
# 					"shelf_life": shelf_life,
# 					"lapsed_life": lapsed_life,
# 					"balance_life": balance_life,
# 					"status": status,
# 				}

# 				data.append(row)

# 	return data

def get_data(filters):
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    warehouse = filters.get("warehouse")
    item = filters.get("item")
    brand = filters.get("brand")

    if not from_date:
        frappe.throw("'From Date' is required")
    if not to_date:
        frappe.throw("'To Date' is required")

    # --- conditions ---
    wh_cond = f" AND sle.warehouse = '{warehouse}'" if warehouse else ""
    item_cond = f" AND sle.item_code = '{item}'" if item else ""
    brand_cond = f" AND item.brand = '{brand}'" if brand else ""

    to_datetime = to_date + " 23:59:59"

    # -----------------------------
    # 1) Direct SLE batch rows
    # -----------------------------
    query_batch_no = f"""
        SELECT
            sle.item_code,
            sle.warehouse,
            sle.batch_no,
            sle.posting_date,
            SUM(sle.actual_qty) AS actual_qty,
            SUM(sle.stock_value_difference) AS stock_value_difference
        FROM `tabStock Ledger Entry` sle
        INNER JOIN `tabItem` item ON item.name = sle.item_code
        WHERE sle.docstatus < 2
          AND sle.is_cancelled = 0
          AND sle.batch_no IS NOT NULL
          AND sle.batch_no != ''
          AND sle.posting_datetime <= %s
          {wh_cond}
          {item_cond}
          {brand_cond}
        GROUP BY sle.voucher_no, sle.batch_no, sle.item_code, sle.warehouse
    """

    sle_batch_no = frappe.db.sql(query_batch_no, (to_datetime,), as_dict=True) or []

    # -----------------------------
    # 2) Serial & Batch Bundle SLE rows
    # -----------------------------
    query_bundle = f"""
        SELECT
            sle.item_code,
            batch_package.warehouse AS warehouse,
            batch_package.batch_no,
            sle.posting_date,
            SUM(batch_package.qty) AS actual_qty,
            SUM(batch_package.stock_value_difference) AS stock_value_difference
        FROM `tabStock Ledger Entry` sle
        INNER JOIN `tabItem` item ON item.name = sle.item_code
        INNER JOIN `tabSerial and Batch Entry` batch_package
            ON batch_package.parent = sle.serial_and_batch_bundle
        WHERE sle.docstatus < 2
          AND sle.is_cancelled = 0
          AND sle.has_batch_no = 1
          AND sle.posting_datetime <= %s
          {brand_cond}
          {f" AND batch_package.warehouse = '{warehouse}'" if warehouse else ""}
          {f" AND sle.item_code = '{item}'" if item else ""}
        GROUP BY sle.voucher_no, batch_package.batch_no, batch_package.warehouse
    """

    sle_bundle = frappe.db.sql(query_bundle, (to_datetime,), as_dict=True) or []

    # -------------------------------------------
    # Combine SLE list identical to ERPNext logic
    # -------------------------------------------
    all_sle = sle_batch_no + sle_bundle

    # Build iwb_map
    float_precision = cint(frappe.db.get_default("float_precision")) or 3
    iwb_map = {}
    from_date_dt = getdate(from_date)
    to_date_dt = getdate(to_date)

    for d in all_sle:
        item_code = d.get("item_code")
        wh = d.get("warehouse")
        batch_no = d.get("batch_no") or ""

        iwb_map.setdefault(item_code, {}).setdefault(wh, {}).setdefault(
            batch_no,
            frappe._dict({
                "opening_qty": 0.0,
                "in_qty": 0.0,
                "out_qty": 0.0,
                "bal_qty": 0.0,
                "bal_value": 0.0,
            })
        )

        qty_dict = iwb_map[item_code][wh][batch_no]

        post_dt = getdate(d.get("posting_date"))

        # Opening
        if post_dt < from_date_dt:
            qty_dict.opening_qty = flt(qty_dict.opening_qty) + flt(d.get("actual_qty"))

        # In / Out
        elif from_date_dt <= post_dt <= to_date_dt:
            if flt(d.get("actual_qty")) > 0:
                qty_dict.in_qty += flt(d.get("actual_qty"))
            else:
                qty_dict.out_qty += abs(flt(d.get("actual_qty")))

        # Balances (regardless of range)
        qty_dict.bal_qty += flt(d.get("actual_qty"))
        qty_dict.bal_value += flt(d.get("stock_value_difference"))

    # ---------------------------------
    # Build final output rows
    # ---------------------------------

    data = []

    for item_code in sorted(iwb_map.keys()):
        # Item filters
        if item and item != item_code:
            continue

        item_doc = frappe.get_doc("Item", item_code)
        item_name = item_doc.item_name
        brand_value = item_doc.brand
        custom_class = item_doc.get("class")
        uom = item_doc.stock_uom
        case_per_unit = item_doc.case_per_unit
        wt_per_unit = item_doc.weight_per_unit

        # Brand filter (double check)
        if brand and brand_value != brand:
            continue

        for wh in sorted(iwb_map[item_code].keys()):
            if warehouse and wh != warehouse:
                continue

            for batch_no in sorted(iwb_map[item_code][wh].keys()):
                qty_dict = iwb_map[item_code][wh][batch_no]

                if not (qty_dict.opening_qty or qty_dict.in_qty or qty_dict.out_qty or qty_dict.bal_qty):
                    continue

                opening_qty = qty_dict.opening_qty
                in_qty = qty_dict.in_qty
                out_qty = qty_dict.out_qty
                balance_qty = qty_dict.bal_qty

                # Batch fields
                mfg_date = frappe.db.get_value("Batch", batch_no, "manufacturing_date")
                expiry_date = frappe.db.get_value("Batch", batch_no, "expiry_date")
                old_batch_no = frappe.db.get_value("Batch", batch_no, "old_batch_no")

                # Shelf life logic
                shelf_life = lapsed_life = balance_life = None
                status = ""

                if mfg_date and expiry_date:
                    shelf_life = (expiry_date - mfg_date).days
                    today = getdate(frappe.utils.nowdate())
                    lapsed_life = (today - mfg_date).days
                    balance_life = (expiry_date - today).days

                    if balance_life <= 0:
                        status = "Expired"
                    elif balance_life < 120:
                        status = "Near Expiry"
                    else:
                        status = "More Than 120 Days"

                # Cases
                conv_factor = frappe.get_value(
                    "UOM Conversion Detail",
                    {'parent': item_code, 'is_alternate_uom': 1},
                    'conversion_factor'
                )

                cases = (flt(balance_qty) / flt(conv_factor)) if conv_factor else 0

                weight = balance_qty * (wt_per_unit or 0)

                data.append({
                    "item_code": item_code,
                    "item_name": item_name,
                    "brand": brand_value,
                    "class": custom_class,
                    "warehouse": wh,
                    "batch_no": batch_no,
                    "old_batch_no": old_batch_no,
                    "opening_qty": opening_qty,
                    "in_qty": in_qty,
                    "out_qty": out_qty,
                    "balance_qty": balance_qty,
                    "uom": uom,
                    "cases": cases,
                    "weight": weight,
                    "mfg_date": mfg_date,
                    "expiry_date": expiry_date,
                    "shelf_life": shelf_life,
                    "lapsed_life": lapsed_life,
                    "balance_life": balance_life,
                    "status": status,
                })

    return data