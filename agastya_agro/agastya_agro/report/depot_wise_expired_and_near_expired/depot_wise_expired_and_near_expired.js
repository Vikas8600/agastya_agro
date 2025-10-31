// Copyright (c) 2025, Dexciss and contributors
// For license information, please see license.txt

frappe.query_reports["Depot Wise Expired and Near Expired"] = {
	"filters": [
    {
        "fieldname": "as_on_date",
        "label": "As on Date",
        "fieldtype": "Date",
        "reqd": 1
    },
    {
        "fieldname": "warehouse",
        "label": "Warehouse",
        "fieldtype": "Link",
        "options": "Warehouse"
    },
    {
        "fieldname": "brand",
        "label": "Brand",
        "fieldtype": "Link",
        "options": "Brand"
    },
    {
        "fieldname": "item_code",
        "label": "Item",
        "fieldtype": "Link",
        "options": "Item"
    }
]

};
