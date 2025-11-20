import frappe
from frappe.desk.query_report import generate_report_result as get_report
from frappe import _

def execute(filters=None):
    report = frappe.get_doc("Report", "Batch-Wise Balance History")
    report_data = get_report(report, filters=filters)
    columns = report_data.get("columns", [])
    data = report_data.get("result", [])

    columns.extend([
        _("Alternate UOM") + ":Data:120",
        _("Old Batch No") + ":Data:120",
        _("Brand") + ":Data:120",
        _("Class") + ":Data:120",
    ])
    
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
            new_row = list(row.values()) + [alternate_uom, old_batch_no, brand, item_class]
        else:
            # For summary row (if present)
            new_row = list(row) + [""] * 4
        new_data.append(new_row)
    return columns, new_data
