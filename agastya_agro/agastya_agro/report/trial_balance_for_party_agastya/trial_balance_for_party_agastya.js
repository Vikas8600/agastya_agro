// Copyright (c) 2026, Dexciss and contributors
// For license information, please see license.txt

// The same filters as the standard Trial Balance for Party, so the two reports
// can be run on identical selections and compared line for line.
// The key must match the report name exactly, or none of these filters render.
frappe.query_reports["Trial Balance for Party Agastya"] = {
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
			fieldname: "fiscal_year",
			label: __("Fiscal Year"),
			fieldtype: "Link",
			options: "Fiscal Year",
			default: erpnext.utils.get_fiscal_year(frappe.datetime.get_today()),
			reqd: 1,
			on_change: function (query_report) {
				var fiscal_year = query_report.get_values().fiscal_year;
				if (!fiscal_year) {
					return;
				}
				frappe.model.with_doc("Fiscal Year", fiscal_year, function (r) {
					var fy = frappe.model.get_doc("Fiscal Year", fiscal_year);
					frappe.query_report.set_filter_value({
						from_date: fy.year_start_date,
						to_date: fy.year_end_date,
					});
				});
			},
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: erpnext.utils.get_fiscal_year(frappe.datetime.get_today(), true)[1],
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: erpnext.utils.get_fiscal_year(frappe.datetime.get_today(), true)[2],
		},
		{
			fieldname: "party_type",
			label: __("Party Type"),
			fieldtype: "Link",
			options: "Party Type",
			default: "Customer",
			reqd: 1,
		},
		{
			fieldname: "party",
			label: __("Party"),
			fieldtype: "Dynamic Link",
			get_options: function () {
				var party_type = frappe.query_report.get_filter_value("party_type");
				var party = frappe.query_report.get_filter_value("party");
				if (party && !party_type) {
					frappe.throw(__("Please select Party Type first"));
				}
				return party_type;
			},
		},
		{
			fieldname: "account",
			label: __("Account"),
			fieldtype: "MultiSelectList",
			options: "Account",
			get_data: function (txt) {
				return frappe.db.get_link_options("Account", txt, {
					company: frappe.query_report.get_filter_value("company"),
				});
			},
		},
		{
			fieldname: "show_zero_values",
			label: __("Show zero values"),
			fieldtype: "Check",
		},
		{
			fieldname: "exclude_zero_balance_parties",
			label: __("Exclude Zero Balance Parties"),
			fieldtype: "Check",
			default: 1,
		},
	],

	onload: function (report) {
		report.page.add_inner_button(__("How This Report Works"), () => {
			show_guidance();
		});
	},
};

const GUIDANCE = [
	{
		heading: "What this report shows",
		body: `This is the standard <b>Trial Balance for Party</b>, with one difference:
			the <b>Debit</b> and <b>Credit</b> columns leave out entries that are not
			a real movement on the account.
			<br><br>
			Two kinds of entry post an equal debit and credit against the same party on
			the same day. They change no balance at all, and only make the debit and
			credit figures larger than the business the party actually did:`,
		points: [
			["Reconciliation credit and debit notes",
			 "Written by the system itself when payments are reconciled against invoices. These are the same entries General Ledger removes under <i>Ignore System Generated Credit / Debit Notes</i>."],
			["Bounced cheques",
			 "The receipt that was banked and the journal that reverses it when the cheque is returned. A cheque that never cleared is not a collection, and the pair together is not a movement."]
		]
	},
	{
		heading: "What is never changed",
		body: `<b>Opening</b> and <b>Closing</b> are taken from the standard report and
			are not touched. Whatever is left out above, the balances on this report
			always agree with the ledger and with the standard Trial Balance for Party.`
	},
	{
		heading: "For the figures to come out right",
		highlight: true,
		body: `The report can only leave out a bounced cheque if it has been told which
			entries belong to it. There is no link between a receipt and the journal
			that reverses it, so both have to be marked:`,
		points: [
			["Tick <i>Is bounced Cheque</i> on the Payment Entry",
			 "The receipt for the cheque that was returned."],
			["Tick <i>is bounced cheque</i> on the Journal Entry as well",
			 "The reversal passed when the bank returned the cheque. Marking only one of the two is not enough."],
			["Leave the bank charge alone",
			 "The small charge the bank recovers for a returned cheque is a genuine expense to the party. It is not part of the pair and should not be marked."]
		]
	},
	{
		heading: "How to check the report is right",
		points: [
			["Opening + Debit &minus; Credit should equal Closing",
			 "On every line. Where a line does not add up, that party has a bounced cheque marked on one entry and not on the other. Correcting the second entry settles the line."],
			["Compare against General Ledger",
			 "Run General Ledger for the same party and period with <i>Ignore System Generated Credit / Debit Notes</i> ticked. The debit and credit will agree with this report, apart from any bounced cheques, which General Ledger does not remove."],
			["Compare against the standard report",
			 "Run <b>Trial Balance for Party</b> on the same selection. Opening and Closing will be identical; the difference in Debit and Credit is exactly what has been left out."]
		]
	}
];

function show_guidance() {
	const dialog = new frappe.ui.Dialog({
		title: __("How This Report Works"),
		size: "large",
		fields: [{ fieldname: "body", fieldtype: "HTML" }]
	});

	const html = GUIDANCE.map((section) => {
		const points = (section.points || []).map(([label, text]) => `
			<tr>
				<td style="width:270px;font-weight:500;vertical-align:top">${label}</td>
				<td style="vertical-align:top">${text}</td>
			</tr>`).join("");

		return `<div style="margin-bottom:20px${section.highlight
			? ";border-left:3px solid var(--primary-color);padding-left:12px" : ""}">
			<div style="font-weight:600;color:var(--heading-color);margin-bottom:6px">
				${__(section.heading)}</div>
			${section.body ? `<div style="margin-bottom:${points ? "8px" : "0"}">${section.body}</div>` : ""}
			${points ? `<table class="table table-bordered" style="margin:0"><tbody>${points}</tbody></table>` : ""}
		</div>`;
	}).join("");

	dialog.fields_dict.body.$wrapper.html(html);
	dialog.show();
}
