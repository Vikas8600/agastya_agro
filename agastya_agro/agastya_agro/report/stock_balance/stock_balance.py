# Copyright (c) 2025, Dexciss and contributors
# For license information, please see license.txt


# import frappe
# from frappe.desk.query_report import generate_report_result as get_report
# from frappe import _
# from frappe.utils import flt

# def execute(filters=None):
# 	columns, data = [], []
# 	report = frappe.get_doc("Report","Stock Balance")
# 	report_data = get_report(report,filters=filters)
# 	columns, data = report_data.get("columns",[]),report_data.get("result",[])
# 	columns.extend([
# 		{
# 			'label': _('Item Weight'),
# 			'fieldname': 'item_weight',
# 			'fieldtype': 'Float',
# 			'width': 120
# 		},
# 		{
# 			'label': _('Brand'),
# 			'fieldname': 'brand',
# 			'fieldtype': 'Data',
# 			'width': 120
# 		},
# 		{
# 			'label': _('No Of Cases'),
# 			'fieldname': 'cases',
# 			'fieldtype': 'Float',
# 			'width': 120
# 		},
# 		{
# 			'label': _('Class'),
# 			'fieldname': 'item_class',
# 			'fieldtype': 'Data',
# 			'width': 120
# 		},
# 		])
# 	for d in data:
# 		if isinstance(d, dict) and d.get("item_code") and frappe.db.exists("Item", d.get("item_code")):
# 			values_dict = frappe.get_value("Item", d.get("item_code"), ["weight_per_unit", "brand", "class"], as_dict=1)
# 			if filters.get("brand") and filters.get("brand") != values_dict.get("brand"):
# 				continue
# 			if values_dict:
# 				item_weight = values_dict.get("weight_per_unit") or 0
# 				brand = values_dict.get("brand") or ""
# 				item_class = values_dict.get("class") or ""

# 				conv_factor = frappe.get_value(
# 					"UOM Conversion Detail",
# 					{'parent': d.get("item_code"), 'is_alternate_uom': 1},
# 					'conversion_factor'
# 				)

# 				d["item_weight"] = flt(d.get("bal_qty")) * flt(item_weight)
# 				d["brand"] = brand
# 				d["cases"] = (flt(d.get("bal_qty")) / flt(conv_factor)) if conv_factor else 0
# 				d["item_class"] = item_class



# 	return columns, data

import frappe
from frappe.desk.query_report import generate_report_result as get_report
from frappe import _
from frappe.utils import flt

def execute(filters=None):
    columns, data = [], []

    # Load Stock Balance report definition
    report = frappe.get_doc("Report", "Stock Balance")
    report_data = get_report(report, filters=filters)

    columns = report_data.get("columns", [])
    data = report_data.get("result", [])

    # --- FIX 1: Convert list-type rows (totals) into dict ---
    cleaned_data = []

    for row in data:
        if isinstance(row, list):
            row_dict = {}
            for idx, col in enumerate(columns):
                field = col.get("fieldname")
                if field:
                    row_dict[field] = row[idx] if idx < len(row) else None
            cleaned_data.append(row_dict)
        else:
            cleaned_data.append(row)

    data = cleaned_data
    # --------------------------------------------------------

    # Add extra columns
    columns.extend([
        {
            "label": _("Item Weight"),
            "fieldname": "item_weight",
            "fieldtype": "Float",
            "width": 120
        },
        {
            "label": _("Brand"),
            "fieldname": "brand",
            "fieldtype": "Data",
            "width": 120
        },
        {
            "label": _("No Of Cases"),
            "fieldname": "cases",
            "fieldtype": "Float",
            "width": 120
        },
        {
            "label": _("Class"),
            "fieldname": "item_class",
            "fieldtype": "Data",
            "width": 120
        },
    ])

    # Process each row
    for d in data:
        item_code = d.get("item_code")
        if item_code and frappe.db.exists("Item", item_code):

            values_dict = frappe.get_value(
                "Item",
                item_code,
                ["weight_per_unit", "brand", "class"],
                as_dict=True
            )

            # brand filter
            if filters.get("brand") and values_dict.get("brand") != filters.get("brand"):
                continue

            item_weight = flt(values_dict.get("weight_per_unit") or 0)
            brand = values_dict.get("brand") or ""
            item_class = values_dict.get("class") or ""

            # Get conversion factor
            conv_factor = frappe.get_value(
                "UOM Conversion Detail",
                {'parent': item_code, 'is_alternate_uom': 1},
                'conversion_factor'
            )

            # Populate additional fields
            d["item_weight"] = flt(d.get("bal_qty")) * item_weight
            d["brand"] = brand
            d["cases"] = (flt(d.get("bal_qty")) / flt(conv_factor)) if conv_factor else 0
            d["item_class"] = item_class

    return columns, data
