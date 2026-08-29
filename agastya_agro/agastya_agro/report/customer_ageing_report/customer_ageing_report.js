// Copyright (c) 2026, Dexciss and contributors
// For license information, please see license.txt

frappe.query_reports["Customer Ageing Report"] = {
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
			"fieldname": "as_on_date",
			"label": __("As On Date"),
			"fieldtype": "Date",
			"reqd": 1,
			"default": frappe.datetime.get_today()
		},
		{
			"fieldname": "customer",
			"label": __("Customer"),
			"fieldtype": "Link",
			"options": "Customer"
		},
		{
			"fieldname": "customer_group",
			"label": __("Customer Group"),
			"fieldtype": "Link",
			"options": "Customer Group"
		},
		{
			"fieldname": "territory",
			"label": __("Territory"),
			"fieldtype": "Link",
			"options": "Territory"
		},
		{
			// Picking a team node covers everyone below it in the tree.
			"fieldname": "sales_person",
			"label": __("Sales Person / Team"),
			"fieldtype": "Link",
			"options": "Sales Person"
		},
		{
			"fieldname": "ageing_based_on",
			"label": __("Ageing Based On"),
			"fieldtype": "Select",
			"options": "Posting Date\nDue Date",
			"default": "Posting Date",
			"reqd": 1
		},
		{
			"fieldname": "os_type",
			"label": __("O/s Type"),
			"fieldtype": "Select",
			"options": "\nDr\nCr"
		},
		{
			"fieldname": "hide_nil_rows",
			"label": __("Hide Customers With No Balance And No Sales"),
			"fieldtype": "Check",
			"default": 1
		}
	],

	"formatter": function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column.fieldname === "os_type" && data && data.os_type) {
			const colour = data.os_type === "Dr" ? "red" : "green";
			value = `<span style="color:${colour}">${value}</span>`;
		}

		if (column.fieldname === "long_overdue" && data && data.long_overdue > 0) {
			value = `<span style="color:red;font-weight:600">${value}</span>`;
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
	["Party", [
		["Code", "Customer.name"],
		["Name Of The Party", "Customer.customer_name"],
		["Place", "Customer.city"],
		["Sales Person", "Sales person on the customer's Sales Team row"],
		["Sales Team", "Parent Sales Person recorded on that same row"],
		["Sales Team Head", "Parent of the Sales Team in the Sales Person tree"]
	]],
	["Sales History (in lakhs)", [
		["FY .. Sales", "Sum of Sales Invoice rounded total for that fiscal year, up to the As On Date. Credit notes excluded. Divided by 1,00,000"]
	]],
	["Trial Balance", [
		["Opening", "Customer GL balance (debit - credit) before the start of the fiscal year holding the As On Date"],
		["Debit", "GL debit from the fiscal year start to the As On Date"],
		["Credit", "GL credit over the same period"],
		["Closing", "Customer GL balance up to and including the As On Date"],
		["O/s Type", "Dr when Closing is positive, Cr when negative"],
		["Old Balance", "Opening, shown as zero when it is a credit balance"]
	]],
	["Ageing", [
		["0-30 .. > 181", "Closing balance spread across buckets by invoice age, newest bucket first. Receipts are taken to clear the oldest invoices, so what remains outstanding sits against the most recent billing. Each bucket holds at most what was billed into it; anything beyond the invoices on hand falls into > 181. Age runs from the invoice's posting date, or its due date when Ageing Based On says so"],
		["> 121 Outstanding", "121-150 + 151-180 + > 181"]
	]],
	["Collection", [
		["Actual Received Collection", "Submitted Payment Entries of type Receive, from the first of the As On Date's month to the As On Date"],
		["Coll.Tgt / ABS.Tgt", "Collection targets. No source in ERP yet — these columns report zero until targets are captured"]
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
				<tbody>${entries.map(([label, source]) => `
					<tr class="cr-row">
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
