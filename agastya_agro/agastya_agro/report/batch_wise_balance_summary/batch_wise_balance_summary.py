import frappe
from frappe.desk.query_report import generate_report_result as get_report
from frappe import _

def execute(filters=None):
    report = frappe.get_doc("Report", "Batch-Wise Balance History")
    report_data = get_report(report, filters=filters)
    columns = report_data.get("columns", [])
    data = report_data.get("result", [])

    columns = [col for col in columns if not (
        (isinstance(col, dict) and col.get("fieldname") == "description") or
        (isinstance(col, str) and col.startswith("Description"))
    )]

    item_name_idx = None
    batch_idx = None
    for i, col in enumerate(columns):
        fieldname = col.get("fieldname") if isinstance(col, dict) else col.split(":")[0].lower().replace(" ", "_")
        if fieldname == "item_name":
            item_name_idx = i
        if fieldname == "batch":
            batch_idx = i

    if item_name_idx is not None:
        columns.insert(item_name_idx + 1, {"label": _("Brand"), "fieldname": "brand", "fieldtype": "Data", "width": 120})
        columns.insert(item_name_idx + 2, {"label": _("Class"), "fieldname": "class", "fieldtype": "Data", "width": 120})
        if batch_idx is not None and batch_idx > item_name_idx:
            batch_idx += 2

    # Insert Old Batch No after Batch
    if batch_idx is not None:
        columns.insert(batch_idx + 1, {"label": _("Old Batch No"), "fieldname": "old_batch_no", "fieldtype": "Data", "width": 120})

    # Add Alternate UOM at the end
    columns.append({"label": _("Alternate UOM"), "fieldname": "alternate_uom", "fieldtype": "Data", "width": 120})

    brand_filter = filters.get("brand")

    if brand_filter:
        # Fetch all items with this brand
        brand_items = set(
            frappe.get_all("Item",
                filters={"brand": brand_filter},
                pluck="name"
            )
        )

        # Keep only rows whose item is in brand_items
        data = [
            row for row in data
            if isinstance(row, dict) and row.get("item") in brand_items
        ]

    new_data = []
    for row in data:
        # Handle dict rows only
        if isinstance(row, dict):
            item_code = row.get("item")
            batch_no = row.get("batch")
            alternate_uom = frappe.get_value("UOM Conversion Detail", {"parent": item_code, "is_alternate_uom": 1}, "uom") or ""
            old_batch_no = frappe.db.get_value("Batch", batch_no, "old_batch_no") or ""
            brand = frappe.db.get_value("Item", item_code, "brand") or ""
            item_class = frappe.db.get_value("Item", item_code, "class") or ""

            # Build new row with columns in correct order
            new_row = {}
            for col in columns:
                fieldname = col.get("fieldname") if isinstance(col, dict) else col.split(":")[0].lower().replace(" ", "_")
                if fieldname == "brand":
                    new_row[fieldname] = brand
                elif fieldname == "class":
                    new_row[fieldname] = item_class
                elif fieldname == "old_batch_no":
                    new_row[fieldname] = old_batch_no
                elif fieldname == "alternate_uom":
                    new_row[fieldname] = alternate_uom
                elif fieldname == "description":
                    continue 
                elif fieldname in row:
                    new_row[fieldname] = row.get(fieldname)
                else:
                    new_row[fieldname] = row.get(fieldname, "")
            new_data.append(new_row)
        else:
            new_data.append(row)

    return columns, new_data






# import frappe
# from frappe.desk.query_report import generate_report_result as get_report
# from frappe import _

# def execute(filters=None):
#     report = frappe.get_doc("Report", "Batch-Wise Balance History")
#     report_data = get_report(report, filters=filters)
#     columns = report_data.get("columns", [])
#     data = report_data.get("result", [])

#     columns.extend([
#         _("Alternate UOM") + ":Data:120",
#         _("Old Batch No") + ":Data:120",
#         _("Brand") + ":Data:120",
#         _("Class") + ":Data:120",
#     ])
    
#     brand_filter = filters.get("brand")

#     if brand_filter:
#         # Fetch all items with this brand
#         brand_items = set(
#             frappe.get_all("Item",
#                 filters={"brand": brand_filter},
#                 pluck="name"
#             )
#         )

#         # Keep only rows whose item is in brand_items
#         data = [
#             row for row in data
#             if isinstance(row, dict) and row.get("item") in brand_items
#         ]
#     new_data = []
#     for row in data:
#         # Handle dict rows only
#         if isinstance(row, dict):
#             item_code = row.get("item")
#             batch_no = row.get("batch")
#             alternate_uom = frappe.get_value("UOM Conversion Detail", {"parent": item_code, "is_alternate_uom": 1}, "uom") or ""
#             old_batch_no = frappe.db.get_value("Batch", batch_no, "old_batch_no") or ""
#             brand = frappe.db.get_value("Item", item_code, "brand") or ""
#             item_class = frappe.db.get_value("Item", item_code, "class") or ""
#             new_row = list(row.values()) + [alternate_uom, old_batch_no, brand, item_class]
#         else:
#             # For summary row (if present)
#             new_row = list(row) + [""] * 4
#         new_data.append(new_row)
#     return columns, new_data
