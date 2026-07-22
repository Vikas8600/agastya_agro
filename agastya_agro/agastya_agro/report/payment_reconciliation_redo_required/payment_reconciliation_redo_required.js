// Copyright (c) 2026, Dexciss and contributors
// For license information, please see license.txt

const MISMATCH_COLOURS = {
	"Wrong Pairing": "red",
	"Amount Mismatch": "orange",
	"Missing Allocation": "blue",
	"Unallocated Payment": "purple",
};

// Above this many days of ageing drift the receivable report is materially
// wrong, not just untidy.
const AGEING_ALERT_DAYS = 30;

frappe.query_reports["Payment Reconciliation Redo Required"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "view",
			label: __("View"),
			fieldtype: "Select",
			options: "Summary\nDetail",
			default: "Summary",
		},
		{
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "MultiSelectList",
			get_data: function (txt) {
				return frappe.db.get_link_options("Customer", txt);
			},
		},
		{
			fieldname: "customer_group",
			label: __("Customer Group"),
			fieldtype: "Link",
			options: "Customer Group",
		},
		{
			fieldname: "mismatch_type",
			label: __("Mismatch Type"),
			fieldtype: "MultiSelectList",
			get_data: function () {
				return Object.keys(MISMATCH_COLOURS).map((value) => ({
					value: value,
					description: "",
				}));
			},
		},
		{
			fieldname: "upto_date",
			label: __("Upto Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "min_amount",
			label: __("Min Impact Amount"),
			fieldtype: "Currency",
			default: 1,
		},
		{
			fieldname: "backdated_beyond",
			label: __("Backdated Beyond (Days)"),
			fieldtype: "Int",
			default: 0,
		},
		{
			fieldname: "redo_status",
			label: __("Redo Status"),
			fieldtype: "Select",
			options: "Pending\nRedo Created\nAll",
			default: "Pending",
		},
		{
			fieldname: "show_ignored",
			label: __("Show Ignored"),
			fieldtype: "Check",
			default: 0,
		},
	],

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column.fieldname === "mismatch_type" && data && data.mismatch_type) {
			const colour = MISMATCH_COLOURS[data.mismatch_type] || "gray";
			value = `<span class="indicator-pill ${colour}">${data.mismatch_type}</span>`;
		}

		if (column.fieldname === "ageing_shift" && data && Math.abs(data.ageing_shift) >= AGEING_ALERT_DAYS) {
			value = `<span style="color:var(--red-500);font-weight:600">${value}</span>`;
		}

		if (column.fieldname === "redo_status" && data && data.redo_status === "Not Raised") {
			value = `<span style="color:var(--text-muted)">${value}</span>`;
		}

		return value;
	},

	onload: function (report) {
		report.page.add_inner_button(__("Refresh Scan"), () => refresh_scan(report));

		report.page.add_inner_button(__("Create Redo for Selected"), () =>
			create_redo_for_selected(report)
		);

		report.page.add_inner_button(__("Desired Reconciliation"), () => {
			frappe.set_route("query-report", "Desired Payment Reconciliation", {
				company: report.get_filter_value("company"),
			});
		});

		bind_row_buttons(report);
	},
};

function bind_row_buttons(report) {
	// Delegated, because the datatable re-renders its cells on every refresh.
	$(report.page.wrapper).on("click", "button[data-redo]", function () {
		const args = JSON.parse($(this).attr("data-redo"));
		open_redo(args.customer, args.from_date, args.to_date);
	});
}

function refresh_scan(report) {
	const company = report.get_filter_value("company");
	if (!company) {
		frappe.msgprint(__("Select a Company first"));
		return;
	}

	const customers = report.get_filter_value("customer") || [];

	const queue = (args) => {
		frappe.call({
			method: "agastya_agro.agastya_agro.reconciliation.mismatch_scan.enqueue_scan",
			args: Object.assign({ company: company, customers: customers }, args),
			callback: () => {
				frappe.show_alert({
					message: __("Scan queued. Refresh the report in a few minutes."),
					indicator: "blue",
				});
			},
		});
	};

	// A named set of customers is unambiguous -- just run it.
	if (customers.length) {
		queue({});
		return;
	}

	// Otherwise make the cost explicit. A rebuild walks every customer and takes
	// well over an hour; the incremental pass usually finishes in minutes.
	const dialog = new frappe.ui.Dialog({
		title: __("Refresh Scan"),
		fields: [
			{
				fieldname: "mode",
				fieldtype: "Select",
				label: __("Scan"),
				reqd: 1,
				default: "Changed customers only",
				options: ["Changed customers only", "Rebuild everything"].join("\n"),
			},
			{
				fieldtype: "HTML",
				options: `<p class="text-muted small">${__(
					"<b>Changed customers only</b> looks at customers whose ledger moved since the last scan &mdash; usually a few minutes.<br>" +
						"<b>Rebuild everything</b> re-checks every customer. Use after changing settings or fixing data. Expect an hour or more."
				)}</p>`,
			},
		],
		primary_action_label: __("Start"),
		primary_action(values) {
			dialog.hide();
			queue({ full: values.mode === "Rebuild everything" ? 1 : 0 });
		},
	});
	dialog.show();
}

function open_redo(customer, from_date, to_date) {
	frappe.new_doc("Payment Reconciliation Redo", {
		party_type: "Customer",
		party: customer,
		from_date: from_date,
		to_date: to_date,
	});
}

function create_redo_for_selected(report) {
	const rows = report.datatable ? report.datatable.rowmanager.getCheckedRows() : [];

	if (!rows || !rows.length) {
		frappe.msgprint(__("Tick the rows you want a Redo for."));
		return;
	}

	const customers = [
		...new Set(rows.map((i) => report.data[i] && report.data[i].customer).filter(Boolean)),
	];

	if (!customers.length) {
		frappe.msgprint(__("No customer found on the selected rows."));
		return;
	}

	frappe.confirm(
		__(
			"Create draft Payment Reconciliation Redo document(s) for {0} customer(s)?<br><br>" +
				"They are created as <b>drafts</b> &mdash; nothing is unreconciled until you submit them.",
			[customers.length]
		),
		() => {
			frappe.call({
				method: "agastya_agro.agastya_agro.reconciliation.mismatch_scan.create_redos",
				args: {
					company: report.get_filter_value("company"),
					customers: customers,
				},
				freeze: true,
				freeze_message: __("Creating Redo documents..."),
				callback: (r) => {
					const created = (r.message && r.message.created) || [];
					if (!created.length) {
						frappe.msgprint(__("Nothing to create."));
						return;
					}

					const links = created
						.map(
							(name) =>
								`<li>${frappe.utils.get_form_link(
									"Payment Reconciliation Redo",
									name,
									true
								)}</li>`
						)
						.join("");

					frappe.msgprint({
						title: __("{0} Redo draft(s) created", [created.length]),
						indicator: "green",
						message: `<ul>${links}</ul>`,
					});
					report.refresh();
				},
			});
		}
	);
}
