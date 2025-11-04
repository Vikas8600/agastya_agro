// Copyright (c) 2025, Dexciss and contributors
// For license information, please see license.txt

frappe.query_reports["FG Stock State Wise"] = {
	    "filters": [
        {
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company",
            "reqd": 1,
            "default": frappe.defaults.get_user_default("Company")
        },
        {
            "fieldname": "posting_date",
            "label": __("As On Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today()
        },
        {
            "fieldname": "state",
            "label": __("State"),
            "fieldtype": "Data",
            "reqd": 0
        }
    ]
};
