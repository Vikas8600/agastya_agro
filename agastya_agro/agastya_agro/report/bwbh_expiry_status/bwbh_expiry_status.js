// Copyright (c) 2025, Dexciss and contributors
// For license information, please see license.txt

frappe.query_reports["BWBH Expiry Status"] = {
	"filters": [
        {
            "fieldname": "company",
            "label": "Company",
            "fieldtype": "Link",
            "options": "Company",
			"default": frappe.defaults.get_default("company"),
            "reqd": 1
        },
        {
            "fieldname": "from_date",
            "label": "From Date",
            "fieldtype": "Date",
            "reqd": 1,
            "default": frappe.datetime.month_start()
        },
        {
            "fieldname": "to_date",
            "label": "To Date",
            "fieldtype": "Date",
            "reqd": 1,
            "default": frappe.datetime.month_end()
        },
        {
            "fieldname": "item",
            "label": "Item",
            "fieldtype": "Link",
            "options": "Item"
        },
        {
            "fieldname": "batch_no",
            "label": "Batch No",
            "fieldtype": "Link",
            "options": "Batch"
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
        }
    ]
};
