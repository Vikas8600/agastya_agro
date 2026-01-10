// Copyright (c) 2025, Dexciss and contributors
// For license information, please see license.txt

frappe.query_reports["Desired Payment Reconciliation"] = {
	"filters": [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			width: "80",
			options: "Company",
			default: frappe.defaults.get_default("company"),
			reqd:1
		},
		{
			fieldname: "f_date",
			label: __("From Date"),
			fieldtype: "Date",
			width: "80",
			reqd:1
			
		},
		{
			fieldname: "t_date",
			label: __("To Date"),
			fieldtype: "Date",
			width: "80",
			reqd:1
			
		},
		{
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "MultiSelectList",
			width: "80",
			get_data: function(txt) {
				return frappe.db.get_link_options("Customer", txt);
			}
		},
		{
			fieldname: "inv_no",
			label: __("Invoice No"),
			fieldtype: "Data",
			width: "80",
		},
	]
};
