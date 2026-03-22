// Copyright (c) 2026, Dexciss and contributors
// For license information, please see license.txt

frappe.ui.form.on("Auto Payment Reconciliation", {
	refresh(frm) {
		if (frm.doc.enabled && frm.doc.company && frm.doc.receivable_payable_account) {
			frm.add_custom_button(__("Run Now"), function () {
				frappe.confirm(
					"This will create Process Payment Reconciliation docs for all applicable customers. Continue?",
					function () {
						frm.call("run_reconciliation").then(() => {
							frappe.show_alert({ message: __("Reconciliation queued"), indicator: "green" });
						});
					}
				);
			}).addClass("btn-primary");
		}

		frm.add_custom_button(__("View Scheduled Job"), function () {
			frappe.set_route("Form", "Scheduled Job Type", "auto_payment_reconciliation.process_auto_reconciliation");
		});
	},

	company(frm) {
		frm.set_value("receivable_payable_account", "");
	},

	setup(frm) {
		frm.set_query("receivable_payable_account", function () {
			return {
				filters: {
					company: frm.doc.company,
					is_group: 0,
					account_type: frm.doc.party_type == "Customer" ? "Receivable" : "Payable",
				},
			};
		});

		frm.set_query("cost_center", function () {
			return {
				filters: {
					company: frm.doc.company,
					is_group: 0,
				},
			};
		});

		frm.set_query("bank_cash_account", function () {
			return {
				filters: {
					company: frm.doc.company,
					is_group: 0,
					account_type: ["in", ["Bank", "Cash"]],
				},
			};
		});

		frm.set_query("customer", "customers", function () {
			return {
				filters: {
					disabled: 0,
				},
			};
		});
	},
});
