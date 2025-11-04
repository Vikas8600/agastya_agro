# Copyright (c) 2025, Dexciss and contributors

import frappe
from frappe.utils import getdate, flt

def execute(filters=None):
    filters = filters or {}
    as_on_date = getdate(filters.get("posting_date") or None)
    company = filters.get("company")
    selected_warehouse = filters.get("warehouse")

    fiscal_years = frappe.get_all(
        "Fiscal Year",
        filters={"disabled": 0},
        fields=["name", "year_start_date", "year_end_date"],
        order_by="year_start_date asc"
    )

    columns = get_columns(fiscal_years)
    data = get_data(company, as_on_date, selected_warehouse, fiscal_years)
    return columns, data


def get_columns(fiscal_years):
    columns = [
        {"label": "Warehouse", "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 200},
    ]

    for fy in fiscal_years:
        columns.append({
            "label": fy.name,
            "fieldname": frappe.scrub(fy.name),
            "fieldtype": "Float",
            "width": 100
        })

    columns.append({
        "label": "Grand Total",
        "fieldname": "grand_total",
        "fieldtype": "Float",
        "width": 120
    })
    columns.append({
        "label": "State",
        "fieldname": "state",
        "fieldtype": "Data",
        "width": 140
    })
    columns.append({
        "label": "% of stock",
        "fieldname": "percent_of_stock",
        "fieldtype": "Percent",
        "width": 100
    })

    return columns


def get_data(company, as_on_date, selected_warehouse, fiscal_years):
    warehouse_filter = ""
    params = [company]
    if selected_warehouse:
        warehouse_filter = " AND sle.warehouse = %s "
        params.append(selected_warehouse)

    result_map = {}

    for fy in fiscal_years:
        effective_end = min(as_on_date, fy.year_end_date)
        fy_start = fy.year_start_date
        fy_end = effective_end

        query = f"""
            SELECT
                sle.warehouse,
                addr.state,
                COALESCE(sle.batch_no, sbe.batch_no) AS batch_no,
                batch.expiry_date,
                SUM(sle.stock_value_difference) AS stock_value
            FROM `tabStock Ledger Entry` sle
            LEFT JOIN `tabSerial and Batch Bundle` sbb 
                ON sbb.name = sle.serial_and_batch_bundle
            LEFT JOIN `tabSerial and Batch Entry` sbe 
                ON sbe.parent = sbb.name
            LEFT JOIN `tabBatch` batch 
                ON batch.name = COALESCE(sle.batch_no, sbe.batch_no)
            INNER JOIN `tabItem` item 
                ON item.name = sle.item_code
            LEFT JOIN `tabDynamic Link` dl 
                ON dl.link_doctype = 'Warehouse' AND dl.link_name = sle.warehouse AND dl.parenttype = 'Address'
            LEFT JOIN `tabAddress` addr 
                ON addr.name = dl.parent
            WHERE 
                sle.company = %s
                AND sle.is_cancelled = 0
                AND item.is_stock_item = 1
                AND sle.posting_date BETWEEN %s AND %s
                {warehouse_filter}
            GROUP BY sle.warehouse, batch.expiry_date, COALESCE(sle.batch_no, sbe.batch_no), addr.state
        """

        fy_params = params.copy()
        fy_params.insert(1, fy_start)
        fy_params.insert(2, fy_end)

        rows = frappe.db.sql(query, tuple(fy_params), as_dict=True)

        for row in rows:
            expiry = row.get("expiry_date")
            days_left = (expiry - as_on_date).days if expiry else None

            # Skip expired or near-expiry batches (<=120 days)
            if expiry and days_left <= 120:
                continue

            warehouse = row.get("warehouse") or ""
            state = row.get("state") or ""
            value = flt(row.get("stock_value") or 0)

            if warehouse not in result_map:
                result_map[warehouse] = {
                    "state": state,
                    "fy_value": {fy.name: 0 for fy in fiscal_years},
                }

            result_map[warehouse]["fy_value"][fy.name] += value

    # Prepare main table rows
    data = []
    for warehouse, vals in sorted(result_map.items()):
        fy_values = vals["fy_value"]
        grand_total = sum(fy_values.values())

        row = {
            "warehouse": warehouse,
            "state": vals["state"],
            "grand_total": round(grand_total, 2),
        }

        for fy in fiscal_years:
            row[frappe.scrub(fy.name)] = round(fy_values.get(fy.name, 0), 2)

        data.append(row)

    # ---------- Grand Total row ----------
    grand_row = {"warehouse": "Grand Total", "state": ""}
    for fy in fiscal_years:
        total_fy = sum(r.get(frappe.scrub(fy.name), 0) for r in data)
        grand_row[frappe.scrub(fy.name)] = round(total_fy, 2)

    grand_total_value = sum(r["grand_total"] for r in data)
    grand_row["grand_total"] = round(grand_total_value, 2)
    data.append(grand_row)

    # ---------- Summary rows (Telangana vs Others) ----------
    telangana_rows = [r for r in data if r.get("state") == "Telangana"]
    other_rows = [r for r in data if r.get("state") and r.get("state") != "Telangana"]

    def summarize(rows, label):
        row_summary = {"warehouse": label, "state": ""}
        for fy in fiscal_years:
            field = frappe.scrub(fy.name)
            row_summary[field] = round(sum(r.get(field, 0) for r in rows), 2)
        total = sum(r["grand_total"] for r in rows)
        row_summary["grand_total"] = round(total, 2)
        return row_summary

    if telangana_rows or other_rows:
        telangana_summary = summarize(telangana_rows, "At Hyderabad Depots")
        other_summary = summarize(other_rows, "Other Depots")
        total_summary = summarize(telangana_rows + other_rows, "Total")

        for row in [telangana_summary, other_summary, total_summary]:
            row["percent_of_stock"] = round(
                (row["grand_total"] / grand_total_value * 100) if grand_total_value else 0, 2
            )

        # append after Grand Total
        data.extend([telangana_summary, other_summary, total_summary])

    return data


# # Copyright (c) 2025, Dexciss and contributors

# import frappe
# from frappe.utils import getdate, flt

# def execute(filters=None):
#     filters = filters or {}
#     as_on_date = getdate(filters.get("posting_date") or None)
#     company = filters.get("company")
#     selected_warehouse = filters.get("warehouse")

#     fiscal_years = frappe.get_all(
#         "Fiscal Year",
#         filters={"disabled": 0},
#         fields=["name", "year_start_date", "year_end_date"],
#         order_by="year_start_date asc"
#     )

#     columns = get_columns(fiscal_years)
#     data = get_data(company, as_on_date, selected_warehouse, fiscal_years)
#     return columns, data


# def get_columns(fiscal_years):
#     columns = [
#         {"label": "Warehouse", "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 200},
#     ]

#     for fy in fiscal_years:
#         columns.append({
#             "label": fy.name,
#             "fieldname": frappe.scrub(fy.name),
#             "fieldtype": "Float",
#             "width": 100
#         })

#     columns.append({
#         "label": "Grand Total",
#         "fieldname": "grand_total",
#         "fieldtype": "Float",
#         "width": 120
#     })
#     columns.append({
#         "label": "State",
#         "fieldname": "state",
#         "fieldtype": "Data",
#         "width": 140
#     })

#     return columns


# def get_data(company, as_on_date, selected_warehouse, fiscal_years):
#     warehouse_filter = ""
#     params = [company]
#     if selected_warehouse:
#         warehouse_filter = " AND sle.warehouse = %s "
#         params.append(selected_warehouse)

#     result_map = {}

#     for fy in fiscal_years:
#         effective_end = min(as_on_date, fy.year_end_date)
#         fy_start = fy.year_start_date
#         fy_end = effective_end

#         query = f"""
#             SELECT
#                 sle.warehouse,
#                 addr.state,
#                 COALESCE(sle.batch_no, sbe.batch_no) AS batch_no,
#                 batch.expiry_date,
#                 SUM(sle.stock_value_difference) AS stock_value
#             FROM `tabStock Ledger Entry` sle
#             LEFT JOIN `tabSerial and Batch Bundle` sbb 
#                 ON sbb.name = sle.serial_and_batch_bundle
#             LEFT JOIN `tabSerial and Batch Entry` sbe 
#                 ON sbe.parent = sbb.name
#             LEFT JOIN `tabBatch` batch 
#                 ON batch.name = COALESCE(sle.batch_no, sbe.batch_no)
#             INNER JOIN `tabItem` item 
#                 ON item.name = sle.item_code
#             LEFT JOIN `tabDynamic Link` dl 
#                 ON dl.link_doctype = 'Warehouse' AND dl.link_name = sle.warehouse AND dl.parenttype = 'Address'
#             LEFT JOIN `tabAddress` addr 
#                 ON addr.name = dl.parent
#             WHERE 
#                 sle.company = %s
#                 AND sle.is_cancelled = 0
#                 AND item.is_stock_item = 1
#                 AND sle.posting_date BETWEEN %s AND %s
#                 {warehouse_filter}
#             GROUP BY sle.warehouse, batch.expiry_date, COALESCE(sle.batch_no, sbe.batch_no), addr.state
#         """

#         fy_params = params.copy()
#         fy_params.insert(1, fy_start)
#         fy_params.insert(2, fy_end)

#         rows = frappe.db.sql(query, tuple(fy_params), as_dict=True)

#         for row in rows:
#             expiry = row.get("expiry_date")
#             days_left = (expiry - as_on_date).days if expiry else None

#             # Skip expired or near-expiry batches (<=120 days)
#             if expiry and days_left <= 120:
#                 continue

#             warehouse = row.get("warehouse") or ""
#             state = row.get("state") or ""
#             value = flt(row.get("stock_value") or 0)

#             if warehouse not in result_map:
#                 result_map[warehouse] = {
#                     "state": state,
#                     "fy_value": {fy.name: 0 for fy in fiscal_years},
#                 }

#             result_map[warehouse]["fy_value"][fy.name] += value

#     # Prepare final rows
#     data = []
#     for warehouse, vals in sorted(result_map.items()):
#         fy_values = vals["fy_value"]
#         grand_total = sum(fy_values.values())

#         row = {
#             "warehouse": warehouse,
#             "state": vals["state"],
#             "grand_total": round(grand_total, 2),
#         }

#         for fy in fiscal_years:
#             row[frappe.scrub(fy.name)] = round(fy_values.get(fy.name, 0), 2)

#         data.append(row)

#     # Add Grand Total row
#     grand_row = {
#         "warehouse": "Grand Total",
#         "state": "",
#     }
#     for fy in fiscal_years:
#         total_fy = sum(r.get(frappe.scrub(fy.name), 0) for r in data)
#         grand_row[frappe.scrub(fy.name)] = round(total_fy, 2)

#     grand_row["grand_total"] = round(sum(r["grand_total"] for r in data), 2)
#     data.append(grand_row)

	

#     return data




# # Copyright (c) 2025, Dexciss and contributors

# import frappe
# from frappe.utils import getdate, flt

# def execute(filters=None):
#     filters = filters or {}
#     as_on_date = getdate(filters.get("posting_date") or None)
#     company = filters.get("company")
#     selected_warehouse = filters.get("warehouse")

#     fiscal_years = frappe.get_all(
#         "Fiscal Year",
#         filters={"disabled": 0},
#         fields=["name", "year_start_date", "year_end_date"],
#         order_by="year_start_date asc"
#     )

#     columns = get_columns(fiscal_years)
#     data = get_data(company, as_on_date, selected_warehouse, fiscal_years)
#     return columns, data


# def get_columns(fiscal_years):
#     columns = [
#         {"label": "Warehouse", "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 200},
#     ]

#     for fy in fiscal_years:
#         columns.append({
#             "label": fy.name,
#             "fieldname": frappe.scrub(fy.name),
#             "fieldtype": "Float",
#             "width": 100
#         })

#     columns.append({
#         "label": "Grand Total",
#         "fieldname": "grand_total",
#         "fieldtype": "Float",
#         "width": 120
#     })
#     columns.append({
#         "label": "State",
#         "fieldname": "state",
#         "fieldtype": "Data",
#         "width": 140
#     })

#     return columns


# def get_data(company, as_on_date, selected_warehouse, fiscal_years):
#     warehouse_filter = ""
#     params = [company]
#     if selected_warehouse:
#         warehouse_filter = " AND sle.warehouse = %s "
#         params.append(selected_warehouse)

#     result_map = {}

#     for fy in fiscal_years:
#         effective_end = min(as_on_date, fy.year_end_date)
#         fy_start = fy.year_start_date
#         fy_end = effective_end

#         query = f"""
#             SELECT
#                 sle.warehouse,
#                 w.state,
#                 COALESCE(sle.batch_no, sbe.batch_no) AS batch_no,
#                 batch.expiry_date,
# 				SUM(sle.stock_value_difference) AS stock_value
#             FROM `tabStock Ledger Entry` sle
#             LEFT JOIN `tabWarehouse` w ON w.name = sle.warehouse
#             LEFT JOIN `tabSerial and Batch Bundle` sbb 
#                 ON sbb.name = sle.serial_and_batch_bundle
#             LEFT JOIN `tabSerial and Batch Entry` sbe 
#                 ON sbe.parent = sbb.name
#             LEFT JOIN `tabBatch` batch 
#                 ON batch.name = COALESCE(sle.batch_no, sbe.batch_no)
#             INNER JOIN `tabItem` item 
#                 ON item.name = sle.item_code
#             WHERE 
#                 sle.company = %s
#                 AND sle.is_cancelled = 0
#                 AND item.is_stock_item = 1
#                 AND sle.posting_date BETWEEN %s AND %s
#                 {warehouse_filter}
#             GROUP BY sle.warehouse, batch.expiry_date, COALESCE(sle.batch_no, sbe.batch_no), w.state
#         """

#         fy_params = params.copy()
#         fy_params.insert(1, fy_start)
#         fy_params.insert(2, fy_end)

#         rows = frappe.db.sql(query, tuple(fy_params), as_dict=True)

#         for row in rows:
#             expiry = row.get("expiry_date")
#             days_left = (expiry - as_on_date).days if expiry else None

#             # Skip expired or near-expiry batches (<=120 days)
#             if expiry and days_left <= 120:
#                 continue

#             warehouse = row.get("warehouse") or ""
#             state = row.get("state") or ""
#             value = flt(row.get("stock_value") or 0)

#             if warehouse not in result_map:
#                 result_map[warehouse] = {
#                     "state": state,
#                     "fy_value": {fy.name: 0 for fy in fiscal_years},
#                 }

#             result_map[warehouse]["fy_value"][fy.name] += value

#     # Prepare final rows
#     data = []
#     for warehouse, vals in sorted(result_map.items()):
#         fy_values = vals["fy_value"]
#         grand_total = sum(fy_values.values())

#         row = {
#             "warehouse": warehouse,
#             "state": vals["state"],
#             "grand_total": round(grand_total, 2),
#         }

#         for fy in fiscal_years:
#             row[frappe.scrub(fy.name)] = round(fy_values.get(fy.name, 0), 2)

#         data.append(row)

#     # Add Grand Total row
#     grand_row = {
#         "warehouse": "Grand Total",
#         "state": "",
#     }
#     for fy in fiscal_years:
#         total_fy = sum(r.get(frappe.scrub(fy.name), 0) for r in data)
#         grand_row[frappe.scrub(fy.name)] = round(total_fy, 2)

#     grand_row["grand_total"] = round(sum(r["grand_total"] for r in data), 2)
#     data.append(grand_row)

#     return data
