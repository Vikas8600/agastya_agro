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
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			width: "80",
			options: "Customer",
			reqd:1
		},
		{
			fieldname: "f_date",
			label: __("From Date"),
			fieldtype: "Date",
			width: "80",

		},
		{
			fieldname: "t_date",
			label: __("To Date"),
			fieldtype: "Date",
			width: "80",
		},
		{
			fieldname: "inv_no",
			label: __("Invoice No"),
			fieldtype: "Data",
			width: "80",
		},
	]
};
