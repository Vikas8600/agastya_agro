// Copyright (c) 2025, Dexciss and contributors
// For license information, please see license.txt

frappe.query_reports["Internal Stock Transfer"] = {
	"filters": [
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
			"reqd": 0
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"reqd": 0
		},
		{
			"fieldname": "customer",
			"label": __("Customer"),
			"fieldtype": "Link",
			"options": "Customer",
			"get_query": function() {
				return {
					"filters": {
						"custom_is_internal_transfer": 1
					}
				};
			}
		},
		{
			"fieldname": "to_depot",
			"label": __("To Depot"),
			"fieldtype": "Link",
			"options": "Cost Center"
		},
		{
			"fieldname": "transfer_status",
			"label": __("Transfer Status"),
			"fieldtype": "Select",
			"options": "\nDelivery Note Pending\nPurchase Receipt Pending\nSales Invoice Pending\nPurchase Invoice Pending\nCompleted\nIn Progress"
		}
	],
	"formatter": function(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column.fieldname == "transfer_status") {
			if (data.transfer_status == "Completed") {
				value = "<span style='color:green; font-weight:bold'>" + value + "</span>";
			} else if (data.transfer_status == "Delivery Note Pending") {
				value = "<span style='color:red; font-weight:bold'>" + value + "</span>";
			} else if (data.transfer_status == "Purchase Receipt Pending") {
				value = "<span style='color:orange; font-weight:bold'>" + value + "</span>";
			} else if (data.transfer_status == "Sales Invoice Pending") {
				value = "<span style='color:#e6b800; font-weight:bold'>" + value + "</span>";
			} else if (data.transfer_status == "Purchase Invoice Pending") {
				value = "<span style='color:#cc7a00; font-weight:bold'>" + value + "</span>";
			} else {
				value = "<span style='color:blue; font-weight:bold'>" + value + "</span>";
			}
		}

		return value;
	}
};
