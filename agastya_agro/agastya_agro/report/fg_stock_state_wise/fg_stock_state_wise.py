# Copyright (c) 2025, Dexciss and contributors
# For License information, please see license.txt

import frappe
from frappe.utils import getdate, flt


def execute(filters=None):
    filters = filters or {}
    as_on_date = getdate(filters.get("posting_date") or None)
    company = filters.get("company")
    selected_state = filters.get("state")

    # Fetch all active fiscal years
    fiscal_years = frappe.get_all(
        "Fiscal Year",
        filters={"disabled": 0},
        fields=["name", "year_start_date", "year_end_date"],
        order_by="year_start_date asc"
    )

    columns = get_columns(fiscal_years)
    data = get_data(company, as_on_date, selected_state, fiscal_years)
    return columns, data


def get_columns(fiscal_years):
    columns = [
        {"label": "State", "fieldname": "state", "fieldtype": "Data", "width": 200},
    ]

    for fy in fiscal_years:
        columns.append({
            "label": fy.name,
            "fieldname": frappe.scrub(fy.name),
            "fieldtype": "Float",
            "width": 120
        })

    columns.append({
        "label": "Grand Total",
        "fieldname": "grand_total",
        "fieldtype": "Float",
        "width": 130
    })

    columns.append({
        "label": "% of Stock",
        "fieldname": "percentage_of_stock",
        "fieldtype": "Percent",
        "width": 120
    })

    return columns


def get_data(company, as_on_date, selected_state, fiscal_years):
    state_filter = ""
    params = [company]
    if selected_state:
        state_filter = " AND addr.state = %s "
        params.append(selected_state)

    result_map = {}

    for fy in fiscal_years:
        effective_end = min(as_on_date, fy.year_end_date)
        fy_start = fy.year_start_date
        fy_end = effective_end

        query = f"""
            SELECT
                addr.state,
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
                {state_filter}
            GROUP BY addr.state
        """

        fy_params = params.copy()
        fy_params.insert(1, fy_start)
        fy_params.insert(2, fy_end)

        rows = frappe.db.sql(query, tuple(fy_params), as_dict=True)

        for row in rows:
            state = row.get("state") or "Unknown"
            value = flt(row.get("stock_value") or 0)

            if state not in result_map:
                result_map[state] = {"fy_value": {fy.name: 0 for fy in fiscal_years}}

            result_map[state]["fy_value"][fy.name] += value

    # Prepare data rows
    data = []
    grand_total_all = 0

    for state, vals in sorted(result_map.items()):
        fy_values = vals["fy_value"]
        grand_total = sum(fy_values.values())
        grand_total_all += grand_total

        row = {"state": state, "grand_total": round(grand_total, 2)}
        for fy in fiscal_years:
            row[frappe.scrub(fy.name)] = round(fy_values.get(fy.name, 0), 2)

        data.append(row)

    # Compute % of stock for each state
    for row in data:
        row["percentage_of_stock"] = (
            round((row["grand_total"] / grand_total_all) * 100, 2)
            if grand_total_all else 0
        )

    # Add TOTAL row
    total_row = {"state": "TOTAL"}
    for fy in fiscal_years:
        total_row[frappe.scrub(fy.name)] = round(sum(r.get(frappe.scrub(fy.name), 0) for r in data), 2)

    total_row["grand_total"] = round(grand_total_all, 2)
    total_row["percentage_of_stock"] = 100.0

    data.append(total_row)
    return data
