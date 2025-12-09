# Copyright (c) 2025, Dexciss and contributors
# For license information, please see license.txt

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

def get_stock_transfer_price_list():
    """
    Get the Price List marked as Stock Transfer Price List
    Returns the first Price List with custom_is_stock_transfer_price_list = 1
    """
    price_list = frappe.db.get_value(
        "Price List",
        {"custom_is_stock_transfer_price_list": 1, "enabled": 1},
        "name"
    )
    return price_list

def get_item_prices(price_list, posting_date):
    """
    Get all valid Item Prices from the specified Price List
    Returns a dict: {item_code: price_list_rate}
    Only includes prices where:
    - valid_from <= posting_date (or valid_from is NULL)
    - valid_upto >= posting_date (or valid_upto is NULL)
    """
    if not price_list:
        return {}

    item_prices = frappe.db.sql("""
        SELECT
            item_code,
            price_list_rate
        FROM `tabItem Price`
        WHERE
            price_list = %s
            AND (valid_from IS NULL OR valid_from <= %s)
            AND (valid_upto IS NULL OR valid_upto >= %s)
        ORDER BY valid_from DESC
    """, (price_list, posting_date, posting_date), as_dict=True)

    # Build dict with latest valid price per item
    price_dict = {}
    for ip in item_prices:
        if ip['item_code'] not in price_dict:
            price_dict[ip['item_code']] = flt(ip['price_list_rate'])

    return price_dict

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
            SUM(sle.actual_qty) AS balance_qty
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

    # Get Stock Transfer Price List and Item Prices
    stock_transfer_price_list = get_stock_transfer_price_list()
    item_prices = get_item_prices(stock_transfer_price_list, posting_date)

    pivot = {}

    for d in balance_data:
        key = (d['class'], d['brand'])
        if not key[0] or not key[1]:
            continue

        qty = flt(d['balance_qty'])

        # Calculate value using Item Price from Stock Transfer Price List
        item_price = item_prices.get(d['item_code'], 0)
        value = qty * item_price

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


# ============================================================================
# OLD CODE - Using stock_value_difference from SLE
# ============================================================================

# import frappe
# from frappe.utils import getdate, nowdate, flt

# def execute(filters=None):
#     filters = filters or {}
#     posting_date = getdate(filters.get("posting_date") or nowdate())
#     company = filters.get("company")
#     selected_brand = filters.get("brand")

#     depots = get_depots()
#     columns = get_columns(depots)
#     data = get_data(filters, depots, posting_date, company, selected_brand)
#     return columns, data

# def get_depots():
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
#     brand_filter_sql = ""
#     brand_params = []
#     if selected_brand:
#         brand_filter_sql = " AND item.brand = %s "
#         brand_params = [selected_brand] if isinstance(selected_brand, str) else list(selected_brand)

#     query = """
#         SELECT
#             sle.item_code,
#             item.brand,
#             item.class AS class,
#             sle.warehouse,
#             COALESCE(sle.batch_no, sbbi.batch_no) AS batch_no,
#             SUM(sle.actual_qty) AS balance_qty,
#             SUM(sle.stock_value_difference) AS stock_value_diff
#         FROM `tabStock Ledger Entry` sle
#         LEFT JOIN `tabSerial and Batch Bundle` sbb ON sbb.name = sle.serial_and_batch_bundle
#         LEFT JOIN `tabSerial and Batch Entry` sbbi ON sbbi.parent = sbb.name
#         LEFT JOIN `tabBatch` batch ON batch.name = COALESCE(sle.batch_no, sbbi.batch_no)
#         LEFT JOIN `tabItem` item ON item.name = sle.item_code
#         WHERE
#             sle.company = %s
#             AND sle.is_cancelled = 0
#             AND sle.posting_date <= %s
#             AND item.is_stock_item = 1
#             AND (batch.expiry_date IS NULL OR DATEDIFF(batch.expiry_date, %s) > 120)
#             {}
#         GROUP BY sle.item_code, item.brand, item.class, sle.warehouse, COALESCE(sle.batch_no, sbbi.batch_no)
#         HAVING SUM(sle.actual_qty) != 0
#     """.format(brand_filter_sql)

#     params = [company, posting_date, posting_date] + brand_params

#     balance_data = frappe.db.sql(query, tuple(params), as_dict=True)

#     pivot = {}

#     for d in balance_data:
#         key = (d['class'], d['brand'])
#         if not key[0] or not key[1]:
#             continue

#         qty = flt(d['balance_qty'])
#         value = flt(d['stock_value_diff'])

#         pivot.setdefault(key, {})
#         warehouse = d['warehouse']
#         pivot[key].setdefault(warehouse, {'qty': 0, 'value': 0})
#         pivot[key][warehouse]['qty'] += qty
#         pivot[key][warehouse]['value'] += value

#     data = []
#     for (class_name, brand_name), wh_data in pivot.items():
#         row = {
#             'class': class_name,
#             'brand': brand_name,
#             'total_value': 0,
#             'total_qty': 0
#         }
#         for depot in depots:
#             val = wh_data.get(depot, {})
#             qty = flt(val.get('qty', 0))
#             amount = flt(val.get('value', 0))
#             row[frappe.scrub(depot)] = qty
#             row['total_qty'] += qty
#             row['total_value'] += amount

#         row['total_value'] = round(row['total_value'] / 100000, 2)  # Convert to lacs

#         if row['total_qty'] > 0:
#             data.append(row)

#     return data
