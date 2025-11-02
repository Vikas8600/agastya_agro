// Copyright (c) 2025, Dexciss and contributors
// For license information, please see license.txt

frappe.query_reports["Depot Wise FG Stock (More than 120 Days)"] = {
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
     "default": "Today"
   },
    {
     "fieldname": "warehouse",
     "label": "Warehouse",
     "fieldtype": "Link",
     "options": "Warehouse",
   },

]
};
