import frappe
from frappe.utils import getdate, nowdate, flt, date_diff

def execute(filters=None):
    filters = filters or {}
    posting_date = getdate(filters.get("posting_date") or nowdate())
    company = filters.get("company")
    if not company:
        frappe.throw("Please select a Company")
    sle_data = frappe.db.sql("""
        SELECT
            sle.warehouse,
            i.item_group,
            i.brand,
            sle.batch_no,
            b.expiry_date,
            SUM(sle.actual_qty) AS qty,
            SUM(sle.stock_value_difference) AS stock_value
        FROM `tabStock Ledger Entry` sle
        JOIN `tabItem` i ON i.name = sle.item_code
        LEFT JOIN `tabBatch` b ON b.name = sle.batch_no
        WHERE
            sle.company = %s
            AND sle.is_cancelled = 0
            AND sle.batch_no IS NOT NULL
            AND i.is_stock_item = 1
        GROUP BY sle.warehouse, i.item_group, sle.batch_no
    """, (company,), as_dict=True)

    if not sle_data:
        return get_columns([]), []


    filtered_data = []
    for d in sle_data:
        if not d.expiry_date:
            continue
        remaining_days = date_diff(d.expiry_date, posting_date)
        if remaining_days > 120 and d.qty > 0:
            filtered_data.append(d)

    if not filtered_data:
        return get_columns([]), []

    # -----------------------------
    # Step 3: Dynamic Item Groups
    # -----------------------------
    item_groups = sorted(list({d.item_group for d in filtered_data}))

    # -----------------------------
    # Step 4: Aggregate by Warehouse
    # -----------------------------
    warehouse_map = {}
    for d in filtered_data:
        wh = d.warehouse
        if wh not in warehouse_map:
            warehouse_map[wh] = {grp: 0 for grp in item_groups}
            warehouse_map[wh]["warehouse"] = wh

        # Convert stock value to Lacs
        warehouse_map[wh][d.item_group] += flt(d.stock_value) / 100000

    # -----------------------------
    # Step 5: Build Final Data
    # -----------------------------
    data = []
    for idx, (wh, row) in enumerate(warehouse_map.items(), start=1):
        grand_total = sum(flt(row[g]) for g in item_groups)
        depot_state = get_depot_state(wh)
        row.update({
            "sr": idx,
            "grand_total": grand_total,
            "depot_state": depot_state,
        })
        data.append(row)

    return get_columns(item_groups), data


# -----------------------------
# Helper Functions
# -----------------------------
def get_depot_state(warehouse):
    """Fetch depot state from Warehouse custom field or infer from name"""
    state = frappe.db.get_value("Warehouse", warehouse, "state")
    if state:
        return state
    if "-" in warehouse:
        return warehouse.split("-")[-1].strip()
    return "Unknown"


def get_columns(item_groups):
    """Dynamic columns"""
    columns = [
        {"label": "Sl.No", "fieldname": "sr", "fieldtype": "Int", "width": 50},
        {"label": "Warehouse", "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 200},
    ]
    for g in item_groups:
        columns.append({
            "label": g,
            "fieldname": frappe.scrub(g),
            "fieldtype": "Float",
            "width": 120,
        })
    columns += [
        {"label": "Grand Total (Lacs)", "fieldname": "grand_total", "fieldtype": "Float", "width": 140},
        {"label": "Depot State", "fieldname": "depot_state", "fieldtype": "Data", "width": 120},
    ]
    return columns
