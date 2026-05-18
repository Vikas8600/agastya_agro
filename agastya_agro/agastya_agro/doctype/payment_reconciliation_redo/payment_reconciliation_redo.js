// Copyright (c) 2026, Dexciss and contributors
// For license information, please see license.txt

const IN_PROGRESS = ["Queued", "Unreconciling", "Re-Reconciling"];
const STATUS_COLOR = {
	Draft: "grey",
	Queued: "orange",
	Unreconciling: "blue",
	"Re-Reconciling": "blue",
	Completed: "green",
	"Partially Failed": "orange",
	Failed: "red",
	Cancelled: "grey",
};

frappe.ui.form.on("Payment Reconciliation Redo", {
	setup(frm) {
		frm.set_query("receivable_payable_account", function () {
			return {
				filters: {
					company: frm.doc.company,
					is_group: 0,
					account_type: frm.doc.party_type === "Customer" ? "Receivable" : "Payable",
				},
			};
		});

		frm.set_query("cost_center", function () {
			return {
				filters: { company: frm.doc.company, is_group: 0 },
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

		frm.set_query("party_type", function () {
			return {
				filters: { name: ["in", ["Customer", "Supplier"]] },
			};
		});
	},

	refresh(frm) {
		set_status_indicator(frm);
		update_intro_banner(frm);
		add_buttons(frm);
		schedule_auto_refresh(frm);
	},

	company(frm) {
		frm.set_value("receivable_payable_account", "");
	},

	party_type(frm) {
		frm.set_value("party", "");
		frm.set_value("receivable_payable_account", "");
	},

	before_cancel(frm) {
		// Block (and explain) for terminal/in-progress states where cancel cannot
		// actually undo anything on the ledger.
		const cancellable = ["Queued", "Failed"];
		if (!cancellable.includes(frm.doc.status)) {
			frappe.msgprint({
				title: __("Cannot cancel"),
				indicator: "red",
				message: __(
					"This run is in status <b>{0}</b>. Cancel only marks the record — it does NOT re-link the {1} payment(s) already unreconciled, nor cancel the linked Process Payment Reconciliation <b>{2}</b>.<br><br>" +
						"To fix any reconciliation mistake, create a <b>new</b> Payment Reconciliation Redo for the same party and the relevant date range.",
					[
						frm.doc.status,
						frm.doc.unreconciled_count || 0,
						frm.doc.reconciliation_doc || "—",
					]
				),
			});
			frappe.validated = false;
			return false;
		}

		// For Queued/Failed: cancel is technically safe (no ledger changes done)
		// but still warn so the user knows what it does and doesn't do.
		frappe.validated = false;
		return new Promise((resolve) => {
			frappe.warn(
				__("Cancel this Payment Reconciliation Redo?"),
				__(
					"Status is <b>{0}</b>. Cancelling will mark this record as Cancelled. " +
						"No ledger changes were made yet, so nothing needs to be reversed.",
					[frm.doc.status]
				),
				() => {
					frappe.validated = true;
					resolve();
					frm.savecancel();
				},
				__("Yes, cancel it"),
				true
			);
		});
	},
});

function update_intro_banner(frm) {
	// Clear any previous intro first — Frappe's set_intro can stack in some
	// reload paths, producing duplicate banners.
	frm.set_intro("");

	if (frm.is_new()) {
		frm.set_intro(
			__(
				"Pick a customer and a date range, then save. Use <b>Preview Allocations</b> to see what will be unreconciled before submitting."
			),
			"blue"
		);
		return;
	}

	if (frm.doc.docstatus === 0) {
		frm.set_intro(
			__(
				"This is a draft. Click <b>Preview Allocations</b> to inspect what will be touched, then <b>Submit</b> to unreconcile those payments and re-run reconciliation in the background."
			),
			"blue"
		);
		return;
	}

	if (frm.doc.docstatus === 2) {
		frm.set_intro(__("This run has been cancelled."), "red");
		return;
	}

	switch (frm.doc.status) {
		case "Queued":
			frm.set_intro(
				__("Queued for processing. This page will refresh automatically every 5 seconds."),
				"orange"
			);
			break;
		case "Unreconciling":
			frm.set_intro(
				__(
					"Reversing existing allocations one by one. See the <b>Affected Vouchers</b> table for live progress."
				),
				"blue"
			);
			break;
		case "Re-Reconciling":
			frm.set_intro(
				__(
					"All allocations reversed. Now creating a fresh Process Payment Reconciliation to re-allocate cleanly."
				),
				"blue"
			);
			break;
		case "Completed":
			frm.set_intro(
				__(
					"All done. Click <b>View Re-Reconciliation</b> above to see what the new reconciliation allocated."
				),
				"green"
			);
			break;
		case "Partially Failed":
			frm.set_intro(
				__(
					"Some allocations could not be reversed. Check the <b>Error Log</b> below and the <b>Affected Vouchers</b> table, then click <b>Retry</b> to re-process only the failed rows."
				),
				"orange"
			);
			break;
		case "Failed":
			frm.set_intro(
				__(
					"Run failed before completing. See the <b>Error Log</b> below and click <b>Retry</b> after fixing the underlying issue."
				),
				"red"
			);
			break;
		default:
			frm.set_intro("");
	}
}

function set_status_indicator(frm) {
	if (!frm.doc.status) return;
	const color = STATUS_COLOR[frm.doc.status] || "grey";
	frm.page.set_indicator(__(frm.doc.status), color);
}

function add_buttons(frm) {
	if (frm.doc.docstatus === 0 && !frm.is_new()) {
		frm.add_custom_button(__("Preview Allocations"), function () {
			show_preview(frm);
		}).addClass("btn-primary");
	}

	if (frm.doc.docstatus !== 1) return;

	if (frm.doc.reconciliation_doc) {
		frm.add_custom_button(__("View Re-Reconciliation"), function () {
			frappe.set_route("Form", "Process Payment Reconciliation", frm.doc.reconciliation_doc);
		});
	}

	if (["Failed", "Partially Failed"].includes(frm.doc.status)) {
		frm.add_custom_button(__("Retry"), function () {
			frappe.confirm(
				__("Retry will re-process failed allocations and trigger reconciliation again. Continue?"),
				function () {
					frm.call("retry").then(() => {
						frappe.show_alert({ message: __("Retry queued"), indicator: "blue" });
						frm.reload_doc();
					});
				}
			);
		}).addClass("btn-primary");
	}
}

function show_preview(frm) {
	frm.call("preview_allocations")
		.then((r) => {
			const rows = (r && r.message) || [];
			if (!rows.length) {
				frappe.msgprint({
					title: __("Preview"),
					message: __(
						"No reconciled allocations found for this party in the selected date range. Nothing would be unreconciled."
					),
					indicator: "orange",
				});
				return;
			}

			const total = rows.reduce(
				(s, row) => s + (parseFloat(row.allocated_amount) || 0),
				0
			);

			const body = `
				<div class="mb-3">
					<strong>${rows.length}</strong> ${__("allocation(s) will be unreconciled.")}
					${__("Total amount")}: <strong>${format_currency(total)}</strong>
				</div>
				<table class="table table-bordered table-sm">
					<thead>
						<tr>
							<th>#</th>
							<th>${__("Voucher Type")}</th>
							<th>${__("Voucher No")}</th>
							<th>${__("Against Voucher Type")}</th>
							<th>${__("Against Voucher No")}</th>
							<th class="text-right">${__("Amount")}</th>
						</tr>
					</thead>
					<tbody>
						${rows
							.map(
								(row, idx) => `
							<tr>
								<td>${idx + 1}</td>
								<td>${frappe.utils.escape_html(row.voucher_type || "")}</td>
								<td>${frappe.utils.escape_html(row.voucher_no || "")}</td>
								<td>${frappe.utils.escape_html(row.against_voucher_type || "")}</td>
								<td>${frappe.utils.escape_html(row.against_voucher_no || "")}</td>
								<td class="text-right">${format_currency(row.allocated_amount || 0)}</td>
							</tr>
						`
							)
							.join("")}
					</tbody>
				</table>
				<p class="text-muted small">${__(
					"This is a preview only — nothing has been changed yet. Submit the document to actually unreconcile and re-run reconciliation."
				)}</p>
			`;

			const dlg = new frappe.ui.Dialog({
				title: __("Allocations that will be unreconciled"),
				size: "large",
				fields: [{ fieldtype: "HTML", options: body }],
				primary_action_label: __("Close"),
				primary_action: () => dlg.hide(),
			});
			dlg.show();
		});
}

function schedule_auto_refresh(frm) {
	if (frm.__redo_refresh_timer) {
		clearTimeout(frm.__redo_refresh_timer);
		frm.__redo_refresh_timer = null;
	}
	if (IN_PROGRESS.includes(frm.doc.status)) {
		frm.__redo_refresh_timer = setTimeout(() => {
			if (!frm.is_dirty()) frm.reload_doc();
		}, 5000);
	}
}
