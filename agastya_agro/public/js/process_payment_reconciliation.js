// Adds an intro banner on Process Payment Reconciliation when the doc was
// created by a Payment Reconciliation Redo run, so users know what they're
// looking at and can jump back to the source.

frappe.ui.form.on("Process Payment Reconciliation", {
	refresh(frm) {
		if (frm.is_new()) return;
		if (frm.__redo_intro_checked) return;
		frm.__redo_intro_checked = true;

		frappe.db
			.get_list("Comment", {
				filters: {
					reference_doctype: "Process Payment Reconciliation",
					reference_name: frm.doc.name,
					content: ["like", "%Payment Reconciliation Redo%"],
				},
				fields: ["content"],
				order_by: "creation asc",
				limit: 1,
			})
			.then((comments) => {
				if (!comments || !comments.length) return;

				const html = comments[0].content || "";
				// Comment content is HTML — pull the linked Redo name out of it.
				const match =
					html.match(/Payment Reconciliation Redo[^A-Z0-9]*([A-Z0-9-]+)/i) || [];
				const redo_name = match[1];

				let msg;
				if (redo_name) {
					const url = `/app/payment-reconciliation-redo/${encodeURIComponent(redo_name)}`;
					msg = __(
						"This reconciliation was created by <b>Payment Reconciliation Redo</b> " +
							"<a href='{0}'><b>{1}</b></a>. The Redo first reversed existing allocations " +
							"for this party in the chosen date range, then queued this doc to re-allocate cleanly.",
						[url, redo_name]
					);
				} else {
					msg = __(
						"This reconciliation was created by a <b>Payment Reconciliation Redo</b> run. " +
							"See the Comments timeline below for the source link."
					);
				}

				frm.set_intro(msg, "blue");

				if (redo_name) {
					frm.add_custom_button(__("Source Redo"), function () {
						frappe.set_route("Form", "Payment Reconciliation Redo", redo_name);
					});
				}
			});
	},
});
