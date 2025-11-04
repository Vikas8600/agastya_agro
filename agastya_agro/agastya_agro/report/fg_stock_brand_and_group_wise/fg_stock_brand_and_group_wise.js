// Copyright (c) 2025, Dexciss and contributors
// For license information, please see license.txt

frappe.query_reports["FG Stock Brand and Group Wise"] = {
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
            "fieldname": "posting_date",
            "label": "Posting Date",
            "fieldtype": "Date",
            "default": frappe.datetime.get_today()
        },
        {
            "fieldname": "brand",
            "label": "Brand",
            "fieldtype": "Link",
            "options": "Brand",
            "reqd": 0
        }
    ]
};
