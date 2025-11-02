
import frappe
from frappe.utils import getdate, nowdate, flt, date_diff

def execute(filters=None):
    item_groups = frappe.get_all("Item Group", pluck="name")
    columns = get_columns(item_groups)
    data = get_data(filters, item_groups)
    return columns, data


def get_columns(item_groups):
    columns = [
        {"label": "Warehouse", "fieldname": "warehouse", "fieldtype": "Data", "width": 220},
    ]

    for g in item_groups:
        columns.append({
            "label": g,
            "fieldname": frappe.scrub(g),
            "fieldtype": "Float",
            "width": 130,
        })

    columns += [
        {"label": "Grand Total", "fieldname": "grand_total", "fieldtype": "Float", "width": 140},
        {"label": "Depot State", "fieldname": "depot_state", "fieldtype": "Data", "width": 120},
    ]
    return columns

def get_data(filters, item_groups):
    company = filters.get("company")
    posting_date = getdate(filters.get("posting_date") or nowdate())

    if not company:
        frappe.throw("Please select a Company")

    # Warehouses linked to Address
    linked_warehouses = frappe.get_all(
        "Dynamic Link",
        filters={"parenttype": "Address", "link_doctype": "Warehouse"},
        pluck="link_name"
    )

    wh_filter = {
        "disabled": 0,
        "is_group": 0,
        "name": ["in", linked_warehouses]
    }

    if filters.get("warehouse"):
        wh_filter["name"] = filters.get("warehouse")

    warehouses = frappe.get_all("Warehouse", wh_filter, pluck="name")
    data = []

    # Track grand total and state-wise totals
    grand_total_row = {frappe.scrub(g): 0 for g in item_groups}
    grand_total_row["warehouse"] = "<b>Grand Total</b>"
    grand_total_row["grand_total"] = 0
    grand_total_row["depot_state"] = ""

    state_summary = {}

    for wh in warehouses:
        row = {frappe.scrub(g): 0 for g in item_groups}
        row["warehouse"] = wh

        sle_data = frappe.db.sql("""
            SELECT
                sle.item_code,
                i.item_group,
                COALESCE(sle.batch_no, sbbi.batch_no) AS batch_no,
                SUM(sle.actual_qty * sle.valuation_rate) AS stock_value
            FROM `tabStock Ledger Entry` sle
            LEFT JOIN `tabSerial and Batch Bundle` sbb ON sbb.name = sle.serial_and_batch_bundle
            LEFT JOIN `tabSerial and Batch Entry` sbbi ON sbbi.parent = sbb.name
            LEFT JOIN `tabItem` i ON i.name = sle.item_code
            WHERE
                sle.company = %s
                AND sle.warehouse = %s
                AND sle.is_cancelled = 0
                AND sle.posting_date <= %s
                AND i.is_stock_item = 1
            GROUP BY sle.item_code, COALESCE(sle.batch_no, sbbi.batch_no)
            HAVING SUM(sle.actual_qty) > 0
        """, (company, wh, posting_date), as_dict=True)

        for d in sle_data:
            group_key = frappe.scrub(d.item_group)
            if group_key in row:
                row[group_key] += flt(d.stock_value)

        row["grand_total"] = sum(row[frappe.scrub(g)] for g in item_groups)

        address = frappe.get_value(
            "Dynamic Link",
            {"parenttype": "Address", "link_doctype": "Warehouse", "link_name": wh},
            "parent"
        )
        state = frappe.get_value("Address", address, "state") if address else None
        row["depot_state"] = state or "Unknown"

        if row["grand_total"] > 0:
            data.append(row)

            # Accumulate overall totals
            for g in item_groups:
                grand_total_row[frappe.scrub(g)] += row[frappe.scrub(g)]
            grand_total_row["grand_total"] += row["grand_total"]

            # Accumulate state-level totals
            state_key = row["depot_state"]
            if state_key not in state_summary:
                state_summary[state_key] = {frappe.scrub(g): 0 for g in item_groups}
                state_summary[state_key]["grand_total"] = 0
            for g in item_groups:
                state_summary[state_key][frappe.scrub(g)] += row[frappe.scrub(g)]
            state_summary[state_key]["grand_total"] += row["grand_total"]

    # Add grand total
    data.append(grand_total_row)

    # % of Closing Stock row
    total_stock_value = grand_total_row["grand_total"]
    if total_stock_value > 0:
        percent_row = {frappe.scrub(g): 0 for g in item_groups}
        percent_row["warehouse"] = "<b>% of Closing Stock</b>"
        percent_row["depot_state"] = ""
        for g in item_groups:
            percent_row[frappe.scrub(g)] = round(
                (grand_total_row[frappe.scrub(g)] / total_stock_value) * 100, 2
            )
        percent_row["grand_total"] = 100.0
        data.append(percent_row)

    # -------------------------
    # ABSTRACT OF FG STOCK
    # -------------------------
    data.append({})
    data.append({"warehouse": "<b>ABSTRACT OF FG STOCK</b>"})

    abstract_total = 0
    for state, values in state_summary.items():
        row = {frappe.scrub(g): 0 for g in item_groups}
        row["warehouse"] = state
        for g in item_groups:
            row[frappe.scrub(g)] = flt(values[frappe.scrub(g)])
        row["grand_total"] = flt(values["grand_total"])
        abstract_total += row["grand_total"]
        data.append(row)

    # % of Stock per state
    if abstract_total > 0:
        for row in data:
            if row.get("warehouse") in state_summary:
                row["% of stock"] = round(
                    (row["grand_total"] / abstract_total) * 100, 2
                )

    return data
# =================================================================================
# def get_data(filters, item_groups):
#     company = filters.get("company")
#     posting_date = getdate(filters.get("posting_date") or nowdate())

#     if not company:
#         frappe.throw("Please select a Company")

#     # Get warehouses linked to Address
#     linked_warehouses = frappe.get_all(
#         "Dynamic Link",
#         filters={
#             "parenttype": "Address",
#             "link_doctype": "Warehouse"
#         },
#         pluck="link_name"
#     )

#     wh_filter = {
#         "disabled": 0,
#         "is_group": 0,
#         "name": ["in", linked_warehouses]
#     }

#     if filters.get("warehouse"):
#         wh_filter["name"] = filters.get("warehouse")

#     warehouses = frappe.get_all("Warehouse", wh_filter, pluck="name")
#     data = []

#     # initialize grand total row
#     grand_total_row = {frappe.scrub(g): 0 for g in item_groups}
#     grand_total_row["warehouse"] = "<b>Grand Total</b>"
#     grand_total_row["depot_state"] = ""
#     grand_total_row["grand_total"] = 0

#     for wh in warehouses:
#         row = {frappe.scrub(g): 0 for g in item_groups}
#         row["warehouse"] = wh

#         sle_data = frappe.db.sql("""
#             SELECT
#                 sle.item_code,
#                 i.item_group,
#                 COALESCE(sle.batch_no, sbbi.batch_no) AS batch_no,
#                 b.expiry_date,
#                 SUM(sle.actual_qty) AS qty,
#                 (SUM(sle.actual_qty) * MAX(sle.valuation_rate)) AS stock_value
#             FROM `tabStock Ledger Entry` sle
#             LEFT JOIN `tabSerial and Batch Bundle` sbb ON sbb.name = sle.serial_and_batch_bundle
#             LEFT JOIN `tabSerial and Batch Entry` sbbi ON sbbi.parent = sbb.name
#             LEFT JOIN `tabBatch` b ON b.name = COALESCE(sle.batch_no, sbbi.batch_no)
#             LEFT JOIN `tabItem` i ON i.name = sle.item_code
#             WHERE
#                 sle.company = %s
#                 AND sle.warehouse = %s
#                 AND sle.is_cancelled = 0
#                 AND sle.posting_date <= %s
#                 AND i.is_stock_item = 1
#                 AND COALESCE(sle.batch_no, sbbi.batch_no) IS NOT NULL
#             GROUP BY sle.item_code, COALESCE(sle.batch_no, sbbi.batch_no)
#             HAVING SUM(sle.actual_qty) > 0
#         """, (company, wh, posting_date), as_dict=True)

#         for d in sle_data:
#             group_key = frappe.scrub(d.item_group)
#             if group_key in row:
#                 row[group_key] += flt(d.stock_value)

#         row["grand_total"] = sum(row[frappe.scrub(g)] for g in item_groups)

#         address = frappe.get_value("Dynamic Link", {
#             "parenttype": "Address",
#             "link_doctype": "Warehouse",
#             "link_name": wh
#         }, "parent")

#         state = frappe.get_value("Address", address, "state") if address else None
#         row["depot_state"] = state

#         if row["grand_total"] > 0:
#             data.append(row)

#             # accumulate totals
#             for g in item_groups:
#                 grand_total_row[frappe.scrub(g)] += row[frappe.scrub(g)]
#             grand_total_row["grand_total"] += row["grand_total"]

#     # append grand total at the end
#     data.append(grand_total_row)

#     # ----------------------------
#     # Add "% of Closing Stock" row
#     # ----------------------------
#     total_stock_value = grand_total_row["grand_total"]

#     if total_stock_value > 0:
#         percent_row = {frappe.scrub(g): 0 for g in item_groups}
#         percent_row["warehouse"] = "<b>% of Closing Stock</b>"
#         percent_row["depot_state"] = ""

#         for g in item_groups:
#             group_key = frappe.scrub(g)
#             percent_row[group_key] = round(
#                 (grand_total_row[group_key] / total_stock_value) * 100, 2
#             ) if grand_total_row[group_key] else 0

#         percent_row["grand_total"] = 100.0
#         data.append(percent_row)

#     return data
# =========================================================================================================
# def get_data(filters, item_groups):
#     state_and_grp_wise = {}
#     company = filters.get("company")
#     posting_date = getdate(filters.get("posting_date") or nowdate())

#     if not company:
#         frappe.throw("Please select a Company")

#     # Apply warehouse filter if selected
#     linked_warehouses = frappe.get_all(
#         "Dynamic Link",
#         filters={
#             "parenttype": "Address",
#             "link_doctype": "Warehouse"
#         },
#         pluck="link_name"
#     )

#     wh_filter = {
#         "disabled": 0,
#         "is_group": 0,
#         "name": ["in", linked_warehouses]
#     }

#     if filters.get("warehouse"):
#         wh_filter["name"] = filters.get("warehouse")

#     warehouses = frappe.get_all("Warehouse", wh_filter, pluck="name")
#     data = []
#     grand_total_row = {frappe.scrub(g): 0 for g in item_groups}
#     grand_total_row["warehouse"] = "<b>Grand Total</b>"
#     grand_total_row["depot_state"] = ""
#     grand_total_row["grand_total"] = 0
#     for wh in warehouses:
#         row = {frappe.scrub(g): 0 for g in item_groups}
#         row["warehouse"] = wh

#         # Fetch batch-wise stock (as on posting date)
#         sle_data = frappe.db.sql("""
#             SELECT
#                 sle.item_code,
#                 i.item_group,
#                 COALESCE(sle.batch_no, sbbi.batch_no) AS batch_no,
#                 b.expiry_date,
#                 SUM(sle.actual_qty) AS qty,
#                 SUM(sle.stock_value_difference) AS stock_value
#             FROM `tabStock Ledger Entry` sle
#             LEFT JOIN `tabSerial and Batch Bundle` sbb ON sbb.name = sle.serial_and_batch_bundle
#             LEFT JOIN `tabSerial and Batch Entry` sbbi ON sbbi.parent = sbb.name
#             LEFT JOIN `tabBatch` b ON b.name = COALESCE(sle.batch_no, sbbi.batch_no)
#             LEFT JOIN `tabItem` i ON i.name = sle.item_code
#             WHERE
#                 sle.company = %s
#                 AND sle.warehouse = %s
#                 AND sle.is_cancelled = 0
#                 AND sle.posting_date <= %s
#                 AND i.is_stock_item = 1
#                 AND COALESCE(sle.batch_no, sbbi.batch_no) IS NOT NULL
#             GROUP BY sle.item_code, COALESCE(sle.batch_no, sbbi.batch_no)
#             HAVING SUM(sle.actual_qty) > 0
#         """, (company, wh, posting_date), as_dict=True)

#         for d in sle_data:
#             # if not d.expiry_date:
#             #     continue

#             # remaining_days = date_diff(d.expiry_date, posting_date)
#             # if remaining_days <= 120:
#             #     continue 

#             group_key = frappe.scrub(d.item_group)
#             if group_key in row:
#                 row[group_key] += flt(d.stock_value)/1

#         row["grand_total"] = sum(row[frappe.scrub(g)] for g in item_groups)
#         address = frappe.get_value("Dynamic Link",{"parenttype":"Address","link_doctype":"Warehouse","link_name":wh},"parent")
#         state = None
#         if address:
#             state = frappe.get_value("Address",address,"state")
#         row["depot_state"] = state
#         # Skip rows with 0 stock
#         if row["grand_total"] > 0:
#             data.append(row)
#             for g in item_groups:
#                 grand_total_row[frappe.scrub(g)] += row[frappe.scrub(g)]
#             grand_total_row["grand_total"] += row["grand_total"]

#     data.append(grand_total_row)
   
#     return data


