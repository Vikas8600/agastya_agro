import frappe
from frappe.utils import getdate, nowdate, flt

def execute(filters=None):
    filters = filters or {}
    posting_date = getdate(filters.get("posting_date") or nowdate())
    company = filters.get("company")
    selected_brand = filters.get("brand")  

    depots = get_depots()
    columns = get_columns(depots)
    data = get_data(filters, depots, posting_date, company, selected_brand)
    return columns, data

def get_depots():
    return frappe.get_all("Warehouse", filters={"disabled": 0, "is_group": 0}, pluck="name")

def get_columns(depots):
    columns = [
        {"label": "New Class", "fieldname": "class", "fieldtype": "Data", "width": 120},
        {"label": "Brand", "fieldname": "brand", "fieldtype": "Data", "width": 120},
        {"label": "Total Value In Lacs", "fieldname": "total_value", "fieldtype": "Float", "width": 120},
        {"label": "Total Qty's Lt/Kg", "fieldname": "total_qty", "fieldtype": "Float", "width": 120}
    ]
    for depot in depots:
        columns.append({
            "label": depot,
            "fieldname": frappe.scrub(depot),
            "fieldtype": "Float",
            "width": 90
        })
    return columns

def get_data(filters, depots, posting_date, company, selected_brand):
    brand_filter_sql = ""
    brand_params = []
    if selected_brand:
        brand_filter_sql = " AND item.brand = %s "
        brand_params = [selected_brand] if isinstance(selected_brand, str) else list(selected_brand)

    query = """
        SELECT
            sle.item_code,
            item.brand,
            item.class AS class,
            sle.warehouse,
            COALESCE(sle.batch_no, sbbi.batch_no) AS batch_no,
            SUM(sle.actual_qty) AS balance_qty,
            SUM(sle.stock_value_difference) AS stock_value_diff
        FROM `tabStock Ledger Entry` sle
        LEFT JOIN `tabSerial and Batch Bundle` sbb ON sbb.name = sle.serial_and_batch_bundle
        LEFT JOIN `tabSerial and Batch Entry` sbbi ON sbbi.parent = sbb.name
        LEFT JOIN `tabBatch` batch ON batch.name = COALESCE(sle.batch_no, sbbi.batch_no)
        LEFT JOIN `tabItem` item ON item.name = sle.item_code
        WHERE
            sle.company = %s
            AND sle.is_cancelled = 0
            AND sle.posting_date <= %s
            AND item.is_stock_item = 1
            AND (batch.expiry_date IS NULL OR DATEDIFF(batch.expiry_date, %s) > 120)
            {}
        GROUP BY sle.item_code, item.brand, item.class, sle.warehouse, COALESCE(sle.batch_no, sbbi.batch_no)
        HAVING SUM(sle.actual_qty) != 0
    """.format(brand_filter_sql)

    params = [company, posting_date, posting_date] + brand_params

    balance_data = frappe.db.sql(query, tuple(params), as_dict=True)

    pivot = {}

    for d in balance_data:
        key = (d['class'], d['brand'])
        if not key[0]:
            continue

        qty = flt(d['balance_qty'])
        value = flt(d['stock_value_diff'])

        pivot.setdefault(key, {})
        warehouse = d['warehouse']
        pivot[key].setdefault(warehouse, {'qty': 0, 'value': 0})
        pivot[key][warehouse]['qty'] += qty
        pivot[key][warehouse]['value'] += value

    data = []
    for (class_name, brand_name), wh_data in pivot.items():
        row = {
            'class': class_name,
            'brand': brand_name,
            'total_value': 0,
            'total_qty': 0
        }
        for depot in depots:
            val = wh_data.get(depot, {})
            qty = flt(val.get('qty', 0))
            amount = flt(val.get('value', 0))
            row[frappe.scrub(depot)] = qty
            row['total_qty'] += qty
            row['total_value'] += amount

        row['total_value'] = round(row['total_value'] / 100000, 2)  # Convert to lacs

        if row['total_qty'] > 0:
            data.append(row)

    return data



# # Copyright (c) 2025, Dexciss and contributors
# # For license information, please see license.txt

# import frappe
# from frappe.utils import getdate, nowdate, flt


# def execute(filters=None):
#     filters = filters or {}
#     posting_date = getdate(filters.get("posting_date") or nowdate())
#     company = filters.get("company")
#     selected_brand = filters.get("brand")  # Single brand

#     depots = get_depots()
#     columns = get_columns(depots)
#     data = get_data(filters, depots, posting_date, company, selected_brand)
#     return columns, data


# def get_depots():
#     # Return list of all active non-group warehouses
#     return frappe.get_all("Warehouse", filters={"disabled": 0, "is_group": 0}, pluck="name")


# def get_columns(depots):
#     columns = [
#         {"label": "New Class", "fieldname": "class", "fieldtype": "Data", "width": 120},
#         {"label": "Brand", "fieldname": "brand", "fieldtype": "Data", "width": 120},
#         {"label": "Total Value In Lacs", "fieldname": "total_value", "fieldtype": "Float", "width": 120},
#         {"label": "Total Qty's Lt/Kg", "fieldname": "total_qty", "fieldtype": "Float", "width": 120}
#     ]
#     for depot in depots:
#         columns.append({
#             "label": depot,
#             "fieldname": frappe.scrub(depot),
#             "fieldtype": "Float",
#             "width": 90
#         })
#     return columns


# def get_data(filters, depots, posting_date, company, selected_brand):
# 	brand_filter_sql = ""
# 	brand_params = []
# 	if selected_brand:
# 		brand_filter_sql = " AND item.brand = %s "  # For single brand, or "IN (%s,...)" for multiple
# 		brand_params = [selected_brand] if isinstance(selected_brand, str) else list(selected_brand)

# 	query = """
# 		SELECT
# 			sle.item_code,
# 			item.brand,
# 			item.class,
# 			sle.warehouse,
# 			COALESCE(sle.batch_no, sbbi.batch_no) AS batch_no,
# 			SUM(sle.actual_qty) AS balance_qty
# 		FROM `tabStock Ledger Entry` sle
# 		LEFT JOIN `tabSerial and Batch Bundle` sbb ON sbb.name = sle.serial_and_batch_bundle
# 		LEFT JOIN `tabSerial and Batch Entry` sbbi ON sbbi.parent = sbb.name
# 		LEFT JOIN `tabBatch` batch ON batch.name = COALESCE(sle.batch_no, sbbi.batch_no)
# 		LEFT JOIN `tabItem` item ON item.name = sle.item_code
# 		WHERE
# 			sle.company = %s
# 			AND sle.is_cancelled = 0
# 			AND sle.posting_date <= %s
# 			AND item.is_stock_item = 1
# 			AND (batch.expiry_date IS NULL OR DATEDIFF(batch.expiry_date, %s) > 120)
# 			{}
# 		GROUP BY sle.item_code, item.brand, item.class, sle.warehouse, COALESCE(sle.batch_no, sbbi.batch_no)
# 		HAVING SUM(sle.actual_qty) != 0
# 	""".format(brand_filter_sql)

# 	params = [company, posting_date, posting_date] + brand_params

# 	balance_data = frappe.db.sql(query, tuple(params), as_dict=True)

# 	# Cache valuation rate per item-warehouse
# 	valuation_cache = {}
# 	pivot = {}

# 	for d in balance_data:
# 		key = (d['class'], d['brand'])
# 		if not key[0]:
# 			continue

# 		bin_key = (d['item_code'], d['warehouse'])
# 		if bin_key not in valuation_cache:
# 			valuation_cache[bin_key] = frappe.db.get_value("Bin", {
# 				"item_code": d['item_code'], "warehouse": d['warehouse']
# 			}, "valuation_rate") or 0
# 		valuation_rate = valuation_cache[bin_key]

# 		qty = flt(d['balance_qty'])
# 		value = qty * valuation_rate

# 		pivot.setdefault(key, {})
# 		warehouse = d['warehouse']
# 		pivot[key].setdefault(warehouse, {'qty': 0, 'value': 0})
# 		pivot[key][warehouse]['qty'] += qty
# 		pivot[key][warehouse]['value'] += value

# 	data = []
# 	for (class_name, brand_name), wh_data in pivot.items():
# 		row = {
# 			'class': class_name,
# 			'brand': brand_name,
# 			'total_value': 0,
# 			'total_qty': 0
# 		}
# 		for depot in depots:
# 			val = wh_data.get(depot, {})
# 			qty = flt(val.get('qty', 0))
# 			amount = flt(val.get('value', 0))
# 			row[frappe.scrub(depot)] = qty
# 			row['total_qty'] += qty
# 			row['total_value'] += amount

# 		row['total_value'] = round(row['total_value'] / 100000, 2)  # Convert to lacs

# 		if row['total_qty'] > 0:
# 			data.append(row)

# 	return data
