# Copyright (c) 2026, Dexciss and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {
            "fieldname": "item_group",
            "label": _("Item Group"),
            "fieldtype": "Link",
            "options": "Item Group",
            "width": 150
        },
        {
            "fieldname": "gl_account",
            "label": _("GL Account"),
            "fieldtype": "Link",
            "options": "Account",
            "width": 180
        },
        {
            "fieldname": "item_code",
            "label": _("Item No."),
            "fieldtype": "Link",
            "options": "Item",
            "width": 150
        },
        {
            "fieldname": "uom",
            "label": _("UoM"),
            "fieldtype": "Link",
            "options": "UOM",
            "width": 80
        },
        {
            "fieldname": "opening_qty",
            "label": _("Opening Qty"),
            "fieldtype": "Float",
            "width": 120
        },
        {
            "fieldname": "opening_amt",
            "label": _("Opening Amt."),
            "fieldtype": "Currency",
            "width": 130
        },
        {
            "fieldname": "purchase_qty",
            "label": _("Purchase Qty"),
            "fieldtype": "Float",
            "width": 120
        },
        {
            "fieldname": "purchase_amt",
            "label": _("Purchase Amt."),
            "fieldtype": "Currency",
            "width": 130
        },
        {
            "fieldname": "closing_qty",
            "label": _("Closing Qty"),
            "fieldtype": "Float",
            "width": 120
        },
        {
            "fieldname": "closing_amt",
            "label": _("Closing Amt."),
            "fieldtype": "Currency",
            "width": 130
        },
        {
            "fieldname": "consumption_qty",
            "label": _("Consumption Qty"),
            "fieldtype": "Float",
            "width": 140
        },
        {
            "fieldname": "consumption_amt",
            "label": _("Consumption Amt"),
            "fieldtype": "Currency",
            "width": 150
        },
        {
            "fieldname": "other_qty",
            "label": _("Other Qty"),
            "fieldtype": "Float",
            "width": 130
        }
    ]

def get_data(filters):
    conditions = get_conditions(filters)

    items = frappe.db.sql(f"""
        SELECT
            i.name as item_code,
            i.item_group,
            i.stock_uom as uom,
            id.expense_account as gl_account
        FROM `tabItem` i
        JOIN `tabItem Default` id ON i.name = id.parent
        WHERE i.is_stock_item = 1
        {conditions}
        ORDER BY i.item_group, i.name
    """, filters, as_dict=1)

    data = []

    totals = {
        "opening_qty": 0,
        "opening_amt": 0,
        "purchase_qty": 0,
        "purchase_amt": 0,
        "closing_qty": 0,
        "closing_amt": 0,
        "consumption_qty": 0,
        "consumption_amt": 0,
        "other_qty": 0
    }

    from_date = getdate(filters.get("from_date"))
    to_date = getdate(filters.get("to_date"))
    company = filters.get("company")
    warehouse = filters.get("warehouse")

    for item in items:
        opening = get_opening_stock(item.item_code, warehouse, from_date, company)
        closing = get_closing_stock(item.item_code, warehouse, to_date, company)
        purchase = get_purchase_data(item.item_code, warehouse, from_date, to_date, company)
        consumption = get_manufacturing_consumption(
            item.item_code, warehouse, from_date, to_date, company
        )
        other_qty = get_other_qty(item.item_code, warehouse, from_date, to_date, company)

        if (opening["qty"] or purchase["qty"] or closing["qty"] or consumption["qty"] or other_qty):

            row = {
                "item_group": item.item_group,
                "gl_account": item.gl_account,
                "item_code": item.item_code,
                "uom": item.uom,
                "opening_qty": opening["qty"],
                "opening_amt": opening["value"],
                "purchase_qty": purchase["qty"],
                "purchase_amt": purchase["amt"],
                "closing_qty": closing["qty"],
                "closing_amt": closing["value"],
                "consumption_qty": consumption["qty"],
                "consumption_amt": consumption["amt"],
                "other_qty": other_qty
            }

            data.append(row)
            totals["opening_qty"] += opening["qty"]
            totals["opening_amt"] += opening["value"]
            totals["purchase_qty"] += purchase["qty"]
            totals["purchase_amt"] += purchase["amt"]
            totals["closing_qty"] += closing["qty"]
            totals["closing_amt"] += closing["value"]
            totals["consumption_qty"] += consumption["qty"]
            totals["consumption_amt"] += consumption["amt"]
            totals["other_qty"] += other_qty

    if data:
        data.append({
            "item_group": _("Total"),
            "opening_qty": totals["opening_qty"],
            "opening_amt": totals["opening_amt"],
            "purchase_qty": totals["purchase_qty"],
            "purchase_amt": totals["purchase_amt"],
            "closing_qty": totals["closing_qty"],
            "closing_amt": totals["closing_amt"],
            "consumption_qty": totals["consumption_qty"],
            "consumption_amt": totals["consumption_amt"],
            "other_qty": totals["other_qty"]
        })

    return data

def get_conditions(filters):
    conditions = ""

    if filters.get("item_group"):
        conditions += " AND i.item_group = %(item_group)s"

    if filters.get("item_code"):
        conditions += " AND i.name = %(item_code)s"

    return conditions

def get_opening_stock(item_code, warehouse, from_date, company):
    opening_data = frappe.db.sql("""
        SELECT
            COALESCE(SUM(actual_qty), 0) as qty,
            COALESCE(SUM(stock_value_difference), 0) as value
        FROM `tabStock Ledger Entry`
        WHERE item_code = %s
            AND posting_date < %s
            AND company = %s
            AND is_cancelled = 0
            {warehouse_condition}
    """.format(
        warehouse_condition="AND warehouse = %s" if warehouse else ""
    ), (item_code, from_date, company, warehouse) if warehouse else (item_code, from_date, company), as_dict=1)

    if opening_data:
        return {
            "qty": flt(opening_data[0].qty),
            "value": flt(opening_data[0].value)
        }

    return {"qty": 0, "value": 0}

def get_closing_stock(item_code, warehouse, to_date, company):
    closing_data = frappe.db.sql("""
        SELECT
            COALESCE(SUM(actual_qty), 0) as qty,
            COALESCE(SUM(stock_value_difference), 0) as value
        FROM `tabStock Ledger Entry`
        WHERE item_code = %s
            AND posting_date <= %s
            AND company = %s
            AND is_cancelled = 0
            {warehouse_condition}
    """.format(
        warehouse_condition="AND warehouse = %s" if warehouse else ""
    ), (item_code, to_date, company, warehouse) if warehouse else (item_code, to_date, company), as_dict=1)

    if closing_data:
        return {
            "qty": flt(closing_data[0].qty),
            "value": flt(closing_data[0].value)
        }

    return {"qty": 0, "value": 0}

def get_purchase_data(item_code, warehouse, from_date, to_date, company):
    purchase_data = frappe.db.sql("""
        SELECT
            COALESCE(SUM(pri.qty), 0) as qty,
            COALESCE(SUM(pri.base_net_amount), 0) as value
        FROM `tabPurchase Receipt Item` pri
        INNER JOIN `tabPurchase Receipt` pr ON pri.parent = pr.name
        INNER JOIN `tabItem` i ON pri.item_code = i.name
        WHERE pri.item_code = %s
            {warehouse_condition}
            AND pr.posting_date BETWEEN %s AND %s
            AND pr.company = %s
            AND pr.docstatus = 1
            AND i.is_stock_item = 1
            AND IFNULL(pr.is_internal_supplier, 0) = 0
    """.format(
        warehouse_condition="AND pri.warehouse = %s" if warehouse else ""
    ), (item_code, warehouse, from_date, to_date, company) if warehouse else (item_code, from_date, to_date, company), as_dict=1)

    purchase_qty = flt(purchase_data[0].qty or 0) if purchase_data else 0
    purchase_value = flt(purchase_data[0].value or 0) if purchase_data else 0

    return {
        "qty": purchase_qty,
        "amt": purchase_value
    }

def get_manufacturing_consumption(item_code, warehouse, from_date, to_date, company):
    consumption_data = frappe.db.sql("""
        SELECT
            COALESCE(SUM(ABS(sed.qty)), 0) as qty,
            COALESCE(SUM(ABS(sed.amount)), 0) as amt
        FROM `tabStock Entry Detail` sed
        INNER JOIN `tabStock Entry` se ON sed.parent = se.name
        WHERE sed.item_code = %s
            AND se.company = %s
            AND se.posting_date BETWEEN %s AND %s
            AND se.stock_entry_type = 'Manufacture'
            AND se.docstatus = 1
            AND sed.s_warehouse IS NOT NULL
            AND sed.t_warehouse IS NULL
            {warehouse_condition}
    """.format(
        warehouse_condition="AND sed.s_warehouse = %s" if warehouse else ""
    ), (item_code, company, from_date, to_date, warehouse) if warehouse else (item_code, company, from_date, to_date), as_dict=1)

    if consumption_data:
        return {
            "qty": flt(consumption_data[0].qty),
            "amt": flt(consumption_data[0].amt)
        }

    return {"qty": 0, "amt": 0}


def get_other_qty(item_code, warehouse, from_date, to_date, company):
    other_data = frappe.db.sql("""
        SELECT
            COALESCE(SUM(ABS(sle.actual_qty)), 0) as qty
        FROM `tabStock Ledger Entry` sle
        WHERE sle.item_code = %s
            AND sle.company = %s
            AND sle.posting_date BETWEEN %s AND %s
            AND sle.is_cancelled = 0
            AND sle.actual_qty < 0
            AND (
                sle.voucher_type = 'Delivery Note'
                OR (
                    sle.voucher_type = 'Stock Entry'
                    AND EXISTS (
                        SELECT 1 FROM `tabStock Entry` se
                        WHERE se.name = sle.voucher_no
                        AND se.stock_entry_type = 'Material Issue'
                    )
                )
            )
            {warehouse_condition}
    """.format(
        warehouse_condition="AND sle.warehouse = %s" if warehouse else ""
    ), (item_code, company, from_date, to_date, warehouse) if warehouse
       else (item_code, company, from_date, to_date), as_dict=1)

    return flt(other_data[0].qty) if other_data else 0
