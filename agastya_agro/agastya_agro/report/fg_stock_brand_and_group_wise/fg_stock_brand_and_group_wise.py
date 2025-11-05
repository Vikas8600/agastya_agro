# Copyright (c) 2025, Dexciss and contributors

import frappe
from frappe.utils import getdate, flt

def execute(filters=None):
    filters = filters or {}
    as_on_date = getdate(filters.get("posting_date") or None)
    company = filters.get("company")
    selected_brand = filters.get("brand")

    fiscal_years = frappe.get_all(
        "Fiscal Year",
        filters={"disabled": 0},
        fields=["name", "year_start_date", "year_end_date"],
        order_by="year_start_date asc"
    )

    columns = get_columns(fiscal_years)
    data = get_data(company, as_on_date, selected_brand, fiscal_years)
    return columns, data

def get_columns(fiscal_years):
    columns = [
        {"label": "Brand", "fieldname": "brand", "fieldtype": "Data", "width": 180},
		{"label": "Class", "fieldname": "item_class", "fieldtype": "Data", "width": 100}
    ]

    for fy in fiscal_years:
        columns.append({
            "label": fy.name,
            "fieldname": frappe.scrub(fy.name),
            "fieldtype": "Float",
            "width": 90
        })

    columns += [
        {"label": "Total Value (Rs.)", "fieldname": "total_value", "fieldtype": "Currency", "width": 130},
        {"label": "Total Qty (Kgs/Ltrs)", "fieldname": "total_qty", "fieldtype": "Float", "width": 120},
        {"label": "Ave.Price", "fieldname": "average_rate", "fieldtype": "Currency", "width": 100}
    ]

    return columns

def get_data(company, as_on_date, selected_brand, fiscal_years):
	brand_filter = ""
	params = [company]
	if selected_brand:
		brand_filter = " AND item.brand = %s "
		params.append(selected_brand)

	result_map = {}

	# Loop over each fiscal year
	for fy in fiscal_years:
		effective_end = min(as_on_date, fy.year_end_date)
		fy_start = fy.year_start_date
		fy_end = effective_end

		query = f"""
			SELECT
				item.brand,
				item.class AS item_class,
				COALESCE(sle.batch_no, sbe.batch_no) AS batch_no,
				batch.expiry_date,
				SUM(sle.stock_value_difference) AS stock_value,
				SUM(sle.actual_qty) AS qty
			FROM `tabStock Ledger Entry` sle
			LEFT JOIN `tabSerial and Batch Bundle` sbb 
				ON sbb.name = sle.serial_and_batch_bundle
			LEFT JOIN `tabSerial and Batch Entry` sbe 
				ON sbe.parent = sbb.name
			LEFT JOIN `tabBatch` batch 
				ON batch.name = COALESCE(sle.batch_no, sbe.batch_no)
			INNER JOIN `tabItem` item 
				ON item.name = sle.item_code
			WHERE 
				sle.company = %s
				AND sle.is_cancelled = 0
				AND item.is_stock_item = 1
				AND sle.posting_date BETWEEN %s AND %s
				{brand_filter}
				GROUP BY item.brand, item.class, batch.expiry_date,COALESCE(sle.batch_no, sbe.batch_no)

		"""

		fy_params = params.copy()
		fy_params.insert(1, fy_start)
		fy_params.insert(2, fy_end)

		rows = frappe.db.sql(query, tuple(fy_params), as_dict=True)

		for row in rows:
			expiry = row.get("expiry_date")
			days_left = (expiry - as_on_date).days if expiry else None

			# Exclude expired or near-expiry batches (<=120 days)
			if expiry and days_left <= 120:
				continue

			brand = row.get("brand") or ""
			group = row.get("item_class") or ""
			qty = flt(row.get("qty") or 0)
			value = flt(row.get("stock_value") or 0)

			key = (brand, group)
			if key not in result_map:
				result_map[key] = {
					"fy_value": {fy.name: 0 for fy in fiscal_years},
					"total_value": 0,
					"total_qty": 0,
				}

			result_map[key]["fy_value"][fy.name] += value
			result_map[key]["total_value"] += value
			result_map[key]["total_qty"] += qty

	# Prepare final rows
	data = []
	for (brand, group), vals in sorted(result_map.items()):
		total_qty = vals["total_qty"]
		total_value = vals["total_value"]
		avg_rate = round(total_value / total_qty, 2) if total_qty else 0

		row = {
			"brand": brand,
			"item_class": group,
			"total_value": round(total_value, 2),
			"total_qty": round(total_qty, 2),
			"average_rate": avg_rate,
		}

		for fy in fiscal_years:
			row[frappe.scrub(fy.name)] = round(vals["fy_value"].get(fy.name, 0), 2)
		data.append(row)

	# Add Grand Total row
	grand_totals = {
		"brand": "Grand Total",
		"item_class": "",
		"total_value": round(sum(r["total_value"] for r in data), 2),
		"total_qty": round(sum(r["total_qty"] for r in data), 2),
		"average_rate": 0,
	}
	for fy in fiscal_years:
		grand_totals[frappe.scrub(fy.name)] = round(
			sum(r.get(frappe.scrub(fy.name), 0) for r in data), 2
		)
	if grand_totals["total_qty"]:
		grand_totals["average_rate"] = round(
			grand_totals["total_value"] / grand_totals["total_qty"], 2
		)

	data.append(grand_totals)
	return data


# def get_data(company, as_on_date, selected_brand, fiscal_years):
#     brand_filter = ""
#     params = [company]
#     if selected_brand:
#         brand_filter = " AND item.brand = %s "
#         params.append(selected_brand)

#     # Prepare fiscal year-wise stock quantities
#     fy_data = []
#     for fy in fiscal_years:
#         effective_end = min(as_on_date, fy.year_end_date)

#         query = f"""
#             SELECT
#                 item.brand,
#                 item.item_group,
#                 SUM(sle.actual_qty) AS balance_qty,
#                 SUM(sle.actual_qty * bin.valuation_rate) AS stock_value
#             FROM `tabStock Ledger Entry` sle
#             INNER JOIN `tabItem` item ON item.name = sle.item_code
#             LEFT JOIN `tabBin` bin 
#                 ON bin.item_code = sle.item_code AND bin.warehouse = sle.warehouse
#             WHERE 
#                 sle.company = %s
#                 AND sle.is_cancelled = 0
#                 AND sle.posting_date BETWEEN %s AND %s
#                 AND item.is_stock_item = 1
#                 {brand_filter}
#             GROUP BY item.brand, item.item_group
#         """

#         fy_start = fy.year_start_date
#         fy_end = effective_end
#         fy_params = params.copy()
#         fy_params.insert(1, fy_start)
#         fy_params.insert(2, fy_end)

#         fy_rows = frappe.db.sql(query, tuple(fy_params), as_dict=True)
#         fy_data.append((fy.name, fy_rows))

#     # Combine all fiscal years into a single result map
#     result_map = {}
#     for fy_name, fy_rows in fy_data:
#         for row in fy_rows:
#             key = (row.get("brand") or "", row.get("item_group") or "")
#             if key not in result_map:
#                 result_map[key] = {
#                     "total_qty": 0,
#                     "total_value": 0,
#                     "fy_qty": {fy.name: 0 for fy in fiscal_years},
#                     "fy_value": {fy.name: 0 for fy in fiscal_years}
#                 }

#             qty = flt(row.get("balance_qty") or 0)
#             value = flt(row.get("stock_value") or 0)
#             result_map[key]["fy_qty"][fy_name] += qty
#             result_map[key]["fy_value"][fy_name] += value
#             result_map[key]["total_qty"] += qty
#             result_map[key]["total_value"] += value

#     # Prepare report rows
#     data = []
#     idx = 1
#     for (brand, group), vals in sorted(result_map.items()):
#         row = {
#             "idx": idx,
#             "brand": brand,
#             "item_group": group
#         }
#         for fy in fiscal_years:
#             row[frappe.scrub(fy.name)] = round(vals["fy_value"].get(fy.name, 0), 2)
#         row["total_value"] = round(vals["total_value"], 2)
#         row["total_qty"] = round(vals["total_qty"], 2)
#         row["average_rate"] = (
#             round(vals["total_value"] / vals["total_qty"], 2)
#             if vals["total_qty"] else 0
#         )
#         data.append(row)
#         idx += 1

#     # Add grand totals
#     grand_totals = {
#         "idx": "",
#         "brand": "Grand Total",
#         "item_group": "",
#         "total_value": sum(r["total_value"] for r in data),
#         "total_qty": sum(r["total_qty"] for r in data),
#         "average_rate": 0
#     }
#     for fy in fiscal_years:
#         grand_totals[frappe.scrub(fy.name)] = round(
#             sum(r.get(frappe.scrub(fy.name), 0) for r in data), 2)
#     if grand_totals["total_qty"]:
#         grand_totals["average_rate"] = round(grand_totals["total_value"] / grand_totals["total_qty"], 2)
#     data.append(grand_totals)

#     return data

# def get_data(company, as_on_date, selected_brand, fiscal_years):
#     # Fetch balances per item/batch/warehouse excluding expired & near expiry
#     balance_query = """
#         SELECT
#             item.name AS item_code,
#             item.brand,
#             item.item_group,
#             sle.warehouse,
#             COALESCE(sle.batch_no, sbbi.batch_no) AS batch_no,
#             batch.expiry_date,
#             SUM(sle.actual_qty) AS balance_qty
#         FROM `tabStock Ledger Entry` sle
#         LEFT JOIN `tabSerial and Batch Bundle` sbb ON sbb.name = sle.serial_and_batch_bundle
#         LEFT JOIN `tabSerial and Batch Entry` sbbi ON sbbi.parent = sbb.name
#         LEFT JOIN `tabBatch` batch ON batch.name = COALESCE(sle.batch_no, sbbi.batch_no)
#         LEFT JOIN `tabItem` item ON item.name = sle.item_code
#         WHERE sle.company = %s
#             AND sle.is_cancelled = 0
#             AND sle.posting_date <= %s
#             AND item.is_stock_item = 1
#             {brand_filter}
#         GROUP BY item.name, item.brand, item.item_group, sle.warehouse, batch.name
#         HAVING SUM(sle.actual_qty) != 0
#     """

#     brand_filter = ""
#     params = [company, as_on_date]
#     if selected_brand:
#         brand_filter = " AND item.brand = %s "
#         params.append(selected_brand)

#     balance_query = balance_query.format(brand_filter=brand_filter)

#     raw_balances = frappe.db.sql(balance_query, tuple(params), as_dict=True)

#     # Exclude expired and near expired batches (<120 days)
#     filtered_balances = []
#     for bal in raw_balances:
#         expiry_date = bal.get("expiry_date")
#         days_left = (expiry_date - as_on_date).days if expiry_date else None
#         if expiry_date is None or (days_left and days_left > 120):
#             filtered_balances.append(bal)

#     # Prepare mapping of fiscal year to quantities per brand/item group
#     # Make fiscal year columns zero initialized per row key (brand, group)
#     fy_map = {}
#     result_map = {}

#     # Cache valuation rates per item & warehouse
#     valuation_cache = {}

#     for bal in filtered_balances:
#         brand = bal.get("brand") or ""
#         group = bal.get("item_group") or ""
#         item_code = bal.get("item_code")
#         warehouse = bal.get("warehouse")
#         qty = flt(bal.get("balance_qty") or 0)

#         # Get valuation rate from Bin
#         val_key = (item_code, warehouse)
#         if val_key not in valuation_cache:
#             valuation_cache[val_key] = frappe.db.get_value("Bin", {
#                 "item_code": item_code, "warehouse": warehouse
#             }, "valuation_rate") or 0
#         valuation_rate = valuation_cache[val_key]

#         value = qty * valuation_rate

#         key = (brand, group)

#         if key not in result_map:
#             result_map[key] = {
#                 "total_qty": 0,
#                 "total_value": 0,
#                 "fy_qty": {fy.name: 0 for fy in fiscal_years}
#             }

#         result_map[key]["total_qty"] += qty
#         result_map[key]["total_value"] += value

#         # Determine fiscal years this qty belongs to by batch posting date less than fiscal year end
#         # For simplification: count all qty into the latest fiscal year which has end_date >= as_on_date
#         # More accurate approach: split qty into fiscal years according to posting dates, if needed

#         for fy in fiscal_years:
#             field = fy.name
#             if as_on_date <= fy.year_end_date:
#                 # Add qty to this fiscal year
#                 result_map[key]["fy_qty"][field] += qty
#                 break
#             elif fy == fiscal_years[-1]:
#                 # Assign to last fiscal year if no other matched, to avoid missing qty
#                 result_map[key]["fy_qty"][field] += qty

#     # Prepare final data rows
#     data = []
#     idx = 1
#     for (brand, group), vals in sorted(result_map.items()):
#         row = {
#             "idx": idx,
#             "brand": brand,
#             "item_group": group
#         }
#         for fy in fiscal_years:
#             row[frappe.scrub(fy.name)] = round(vals["fy_qty"].get(fy.name, 0), 2)
#         row["total_value"] = round(vals["total_value"], 2)
#         row["total_qty"] = round(vals["total_qty"], 2)
#         row["average_rate"] = round(vals["total_value"] / vals["total_qty"], 2) if vals["total_qty"] else 0
#         data.append(row)
#         idx += 1

#     # Add grand totals
#     grand_totals = {
#         "idx": "",
#         "brand": "Grand Total",
#         "item_group": "",
#         "total_value": sum(r["total_value"] for r in data),
#         "total_qty": sum(r["total_qty"] for r in data),
#         "average_rate": 0
#     }
#     for fy in fiscal_years:
#         grand_totals[frappe.scrub(fy.name)] = round(
#             sum(r.get(frappe.scrub(fy.name), 0) for r in data), 2)
#     if grand_totals["total_qty"]:
#         grand_totals["average_rate"] = round(grand_totals["total_value"] / grand_totals["total_qty"], 2)
#     data.append(grand_totals)

#     return data
