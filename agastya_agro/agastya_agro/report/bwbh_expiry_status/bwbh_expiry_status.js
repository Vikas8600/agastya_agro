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
        },
        {
            "fieldname": "ageing_basis",
            "label": "Ageing Basis",
            "fieldtype": "Select",
            "options": ["Balance Days", "Lapsed Days"],
            "default": "Balance Days"
        },
        {
            "fieldname": "ageing_range",
            "label": "Ageing Range",
            "fieldtype": "Select",
            "options": [
                "",
                "0-30",
                "31-60",
                "61-90",
                "91-120",
                "121-150",
                "151-180",
                "181-200",
                "201-300",
                "301-400",
                "401-500",
                "501-600",
                "601-700",
                "701-800",
                "801-900",
                "901-1000",
                "1001-1100",
                ">1100",
                "Expired",
                "No Expiry Date"
            ]
        }
    ]
};
