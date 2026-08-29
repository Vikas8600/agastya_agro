// Copyright (c) 2026, Dexciss and contributors
// For license information, please see license.txt

frappe.query_reports["Production Report"] = {
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
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"reqd": 1,
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -1)
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"reqd": 1,
			"default": frappe.datetime.get_today()
		},
		{
			"fieldname": "as_on_date",
			"label": __("Life As On"),
			"fieldtype": "Date",
			"reqd": 1,
			"default": frappe.datetime.get_today()
		},
		{
			"fieldname": "item_code",
			"label": __("FG Item"),
			"fieldtype": "Link",
			"options": "Item"
		},
		{
			"fieldname": "item_group",
			"label": __("Product Category"),
			"fieldtype": "Link",
			"options": "Item Group"
		},
		{
			"fieldname": "warehouse",
			"label": __("Warehouse"),
			"fieldtype": "Link",
			"options": "Warehouse"
		},
		{
			"fieldname": "transfer_price_list",
			"label": __("Stock Transfer Price List"),
			"fieldtype": "Link",
			"options": "Price List"
		}
	],

	"formatter": function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column.fieldname === "status" && data && data.status) {
			let colour = "green";
			if (data.status.indexOf("Expired") !== -1) {
				colour = "red";
			} else if (data.status.indexOf("Less than") !== -1) {
				colour = "orange";
			}
			value = `<span style="color:${colour}">${value}</span>`;
		}

		return value;
	},

	"onload": function (report) {
		report.page.add_inner_button(__("Column Reference"), () => {
			show_column_reference();
		}, __("Actions"));
	}
};

const COLUMN_REFERENCE = [
	["Reference", [
		["A", "Reference Number", "Stock Entry that produced the finished goods (purpose = Manufacture)"]
	]],
	["Consumption of Raw Material", [
		["B", "RM Item Code", "Item consumed by the bulk (WIP) production entry"],
		["C", "RM Item Name", "Item.item_name"],
		["D", "Purity %", "Batch.custom_purity, falling back to Item.custom_purity"],
		["E", "RM Batch Number", "Stock Entry Detail.batch_no on the consumed line"],
		["F", "MFG Date", "Batch.manufacturing_date"],
		["G", "Exp Date", "Batch.expiry_date"],
		["H", "RM Actual Qty", "Qty actually consumed on the bulk production entry"],
		["I", "RM Required Qty", "BOM requirement: (BOM Item qty / BOM qty) x bulk qty produced. Written once per item, on the first batch row"],
		["J", "RM price", "Item.last_purchase_rate"],
		["K", "RM Value", "I x J. Zero for items consumed as a substitution, since they carry no BOM requirement"]
	]],
	["Bulk / WIP", [
		["L", "WIP Qty (Convertion)", "Bulk qty consumed by the finished goods entry"],
		["M", "WIP Batch Number", "Batch of the bulk item; links the two production stages"]
	]],
	["Consumption of Packing", [
		["N", "Item Code", "Packing item consumed by the finished goods entry"],
		["O", "Item Name", "Item.item_name"],
		["P", "Required Qty", "Qty consumed on the entry"],
		["Q", "Packing rate", "Item.last_purchase_rate"],
		["R", "Packing value", "P x Q"]
	]],
	["FG Stock Position", [
		["S", "FG Item Code", "Finished item produced by the entry"],
		["T", "FG Item Name", "Item.item_name"],
		["U", "Product Category", "Item.item_group"],
		["V", "Product Group", "Item.class"],
		["W", "FG Qty", "Qty produced on this entry"],
		["X", "Mfg Date", "Batch.manufacturing_date of the FG batch"],
		["Y", "Exp Date", "Batch.expiry_date of the FG batch"],
		["Z", "Self Life", "Item.shelf_life_in_days"],
		["AA", "Lapsed Life", "Life As On filter - Mfg Date"],
		["AB", "Balance Life", "Self Life - Lapsed Life"],
		["AC", "Status", "Already Expired / Less than 120 days / Morethan 120 days, on Balance Life"],
		["AD", "FG price Stock Transfer.Price", "Item Price on the stock transfer price list; falls back to the last rate billed on a transfer delivery note"],
		["AE", "FG Opening Qy", "Stock Ledger balance before From Date, for this item and batch"],
		["AF", "FG Opening Value", "AE x AD"],
		["AG", "FG Incoming Qy", "Inward ledger qty within the period"],
		["AH", "FG Incoming Value", "AG x AD"],
		["AI", "FG Sales Qy", "Outward ledger qty within the period (includes depot transfers)"],
		["AJ", "FG Sales Value", "AI x AD"],
		["AK", "FG Balance Qty", "AE + AG - AI"],
		["AL", "FG Balance Value", "AK x AD"]
	]]
];

function show_column_reference() {
	const dialog = new frappe.ui.Dialog({
		title: __("Column Reference"),
		size: "extra-large",
		fields: [
			{ fieldname: "search", fieldtype: "Data", label: __("Search"), change: filter_reference },
			{ fieldname: "body", fieldtype: "HTML" }
		]
	});

	let html = "";
	COLUMN_REFERENCE.forEach(([heading, entries]) => {
		html += `<div class="cr-group" style="margin-bottom:18px">
			<div style="font-weight:600;color:var(--heading-color);margin-bottom:6px">${heading}</div>
			<table class="table table-bordered" style="margin:0">
				<tbody>${entries.map(([letter, label, source]) => `
					<tr class="cr-row">
						<td style="width:48px;color:var(--text-muted)">${letter}</td>
						<td style="width:230px;font-weight:500">${label}</td>
						<td>${source}</td>
					</tr>`).join("")}
				</tbody>
			</table>
		</div>`;
	});

	dialog.fields_dict.body.$wrapper.html(html);
	dialog.show();

	function filter_reference() {
		const term = (dialog.get_value("search") || "").toLowerCase();
		dialog.fields_dict.body.$wrapper.find(".cr-group").each(function () {
			let visible = 0;
			$(this).find(".cr-row").each(function () {
				const match = $(this).text().toLowerCase().indexOf(term) !== -1;
				$(this).toggle(match);
				if (match) visible++;
			});
			$(this).toggle(visible > 0);
		});
	}
}
