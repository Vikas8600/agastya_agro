# Copyright (c) 2025, Dexciss and contributors
# For license information, please see license.txt

import frappe
from frappe.desk.query_report import generate_report_result as get_report

def execute(filters=None):
    report = frappe.get_doc("Report", "Batch Item Expiry Status")
    report_data = get_report(report, filters=filters)

    columns = report_data.get("columns", [])
    data = report_data.get("result", [])

    columns.extend([
        {"label": "Brand", "fieldname": "brand", "fieldtype": "Data", "width": 150},
        {"label": "Class", "fieldname": "item_class", "fieldtype": "Data", "width": 150},
    ])

    for d in data:
        if d.get("item"):
            item_details = frappe.get_value("Item", d.get("item"), ["brand", "class"], as_dict=1) or {}
            d["brand"] = item_details.get("brand") or ""
            d["item_class"] = item_details.get("class") or ""

    return columns, data
