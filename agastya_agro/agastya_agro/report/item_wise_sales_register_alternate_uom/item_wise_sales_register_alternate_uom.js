// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt
/* eslint-disable */

// Where every column comes from. Grouped the same way the report is laid out so
// the dialog reads top-to-bottom against the columns on screen.
const COLUMN_REFERENCE = [
	["Customer & Invoice", [
		["A", "Year", "Derived from Posting Date. Financial year runs April to March, shown as 25-26."],
		["B", "Code", "Sales Invoice &rarr; Customer"],
		["C", "Name Of The Party", "Customer.customer_name, falling back to the name stored on the invoice"],
		["D", "City", "Customer.city"],
		["E", "Customer Group", "Customer.customer_group, falling back to the invoice"],
		["F", "Territory", "Sales Invoice.territory"],
		["G", "Sales Person", "Sales Team rows on the Customer. Comma separated when the customer has more than one."],
		["H", "Parent Sales Person", "Sales Team &rarr; parent_sales_person on the Customer"],
		["I", "Posting Date", "Sales Invoice.posting_date"],
		["J", "Month", "Full month name of the Posting Date"],
		["X", "Sale Order", "Sales Invoice Item.sales_order"],
		["Y", "Delivery Challan", "Sales Invoice Item.delivery_note. If blank, Delivery Notes linked through the Sales Order row; if the invoice itself updates stock, the invoice number."],
		["Z", "Invoice Number", "Sales Invoice.name"],
		["AA", "Return Against Invoice", "Sales Invoice.return_against"],
		["AB", "Return Inv Date", "Posting date of the invoice named in Return Against"],
		["AC", "Ret.Invoice Days", "Posting Date &minus; Return Inv Date. Blank when the row is not a return."],
		["AD", "Price List Name", "Sales Invoice.selling_price_list"],
	]],
	["GST & Transport", [
		["K", "E-Invoice Number", "Sales Invoice.ack_no. That field stopped being written after 2023, so when it is empty the acknowledgement number is read from the e-Invoice Log."],
		["L", "E-Way Bill Number", "Sales Invoice.ewaybill"],
		["M", "IRN", "Sales Invoice.irn"],
		["N", "Tax ID", "Sales Invoice.tax_id"],
		["O", "Transporter", "Sales Invoice.transporter"],
		["P", "Transporter Name", "Sales Invoice.transporter_name"],
		["Q", "GST Transporter ID", "Sales Invoice.gst_transporter_id"],
		["R", "GST Vehicle Type", "Sales Invoice.gst_vehicle_type"],
		["S", "Vehicle No", "Sales Invoice.vehicle_no"],
		["T", "Mode of Transport", "Sales Invoice.mode_of_transport"],
		["U", "Destination", "Sales Invoice.custom_destination"],
		["V", "Pincode", "Pincode of the invoice's Shipping Address. Falls back to the billing address when no shipping address is set."],
		["W", "Distance (in km)", "Sales Invoice.distance"],
	]],
	["Item & Batch", [
		["AE", "Item Code", "Sales Invoice Item.item_code"],
		["AF", "Item Name", "Item.item_name, falling back to the name stored on the invoice row"],
		["AG", "Brand", "Item.brand"],
		["AH", "Class", "Item.class"],
		["AI", "Item Group", "Item.item_group, falling back to the invoice row"],
		["AJ", "MFG Date", "Batch.manufacturing_date"],
		["AK", "Exp Date", "Batch.expiry_date"],
		["AL", "Batch No", "Sales Invoice Item.batch_no"],
		["AM", "Old Batch No", "Batch.old_batch_no"],
		["AN", "Cost Center", "Sales Invoice Item.cost_center"],
	]],
	["Quantity & Pricing", [
		["AO", "Stock Qty", "Sales Invoice Item.stock_qty"],
		["AP", "Weight", "Stock Qty &times; Item.weight_per_unit"],
		["AQ", "Cases", "Stock Qty &divide; the conversion factor of the item's alternate UOM. Zero when the item has no alternate UOM."],
		["AR", "Price List Rate", "Sales Invoice Item.price_list_rate"],
		["AS", "Disc.%", "Sales Invoice Item.discount_percentage"],
		["AT", "Disc.%,Price", "Sales Invoice Item.discount_amount &mdash; the per-unit discount"],
		["AU", "Disc.%,Price.Amnt", "This row's share of the invoice-level discount, split by value: row net amount &divide; invoice net total &times; invoice discount amount"],
		["AV", "Addnl.%", "Sales Invoice.additional_discount_percentage"],
		["AW", "Addnl.Disc.Amnt", "Sales Invoice.discount_amount &mdash; the invoice-level discount, repeated on every row of the invoice"],
		["AX", "Rate", "Sales Invoice Item.base_net_rate. Re-based to the stock UOM when the item is sold in a different UOM."],
		["AY", "Net Rate", "Sales Invoice Item.net_rate"],
	]],
	["NRV", [
		["AZ", "NRV Price", "Sales Invoice Item &rarr; NRV Price. This is the NRV maintained against the item, not a fixed percentage of Rate."],
		["BA", "Diff.Price", "Rate &minus; NRV Price. Held at zero when no NRV is maintained, so an unmaintained item does not report its whole rate as cushion."],
		["BB", "Cushion", "Stock Qty &times; Diff.Price"],
		["BC", "NRV Sales", "Stock Qty &times; NRV Price"],
	]],
	["Totals", [
		["BD", "Amount", "Sales Invoice Item.base_net_amount"],
		["BE", "Total Tax", "Sum of the per-tax-head amounts on this row"],
		["BF", "Total", "Amount + Total Tax"],
		["BG", "Type", "Returns when the invoice is a credit note, otherwise Sales"],
	]],
	["Payment", [
		["BI", "Invoice Vs Collection Days", "Date of the last Payment Entry &minus; Posting Date. Credit notes and journal entries are deliberately excluded, so this measures money actually collected. Negative values are advances received before the invoice was raised."],
		["BJ", "Payment reference Number", "Payment Entry.reference_no, or cheque no for a Journal Entry. All vouchers against the invoice, oldest first."],
		["BK", "Payment Date", "Posting date of each voucher, in the same order as the reference numbers"],
		["BL", "Voucher Amount", "Total allocated against this invoice across Payment Entries and Journal Entries. Invoice level, so it repeats on every row &mdash; do not sum this column."],
		["BM", "Voucher Type", "Payment Entry, or the Journal Entry's own type (Credit Note, Bank Entry, Opening Entry ...). Shows whether the invoice was settled with money or with a credit note."],
	]],
	["Extra columns (not in the format sheet)", [
		["&mdash;", "Posting Year", "Calendar year of the Posting Date"],
		["&mdash;", "&lt;tax head&gt; Rate / Amount", "One pair per tax head on the invoice, split across rows in proportion to net amount"],
		["&mdash;", "Currency", "Company default currency. Hidden, used to format the currency columns."],
	]],
];

function show_column_reference() {
	const dialog = new frappe.ui.Dialog({
		title: __("Column Reference"),
		size: "extra-large",
		fields: [{ fieldtype: "HTML", fieldname: "body" }],
		primary_action_label: __("Close"),
		primary_action: () => dialog.hide(),
	});

	let html = `
		<div class="col-ref">
			<p class="text-muted small">
				${__("Where each column of this report is read from, and how the calculated ones are worked out. Letters match the Sales Register format sheet.")}
			</p>
			<input type="text" class="form-control col-ref-search"
				placeholder="${__("Search a column or a field name...")}" style="margin-bottom: 12px;">
			<div class="col-ref-body">`;

	COLUMN_REFERENCE.forEach(([group, rows]) => {
		html += `<div class="col-ref-group">
			<div class="col-ref-group-title">${__(group)}</div>
			<table class="table table-bordered col-ref-table">
				<colgroup><col style="width:56px"><col style="width:210px"><col></colgroup>
				<tbody>`;
		rows.forEach(([letter, label, source]) => {
			html += `<tr class="col-ref-row">
				<td class="col-ref-letter">${letter}</td>
				<td class="col-ref-label">${label}</td>
				<td class="col-ref-source">${source}</td>
			</tr>`;
		});
		html += `</tbody></table></div>`;
	});

	html += `</div>
			<div class="col-ref-empty text-muted" style="display:none; padding: 16px 0;">
				${__("No column matches that search.")}
			</div>
		</div>
		<style>
			.col-ref-group-title {
				font-weight: 600; margin: 14px 0 6px; padding-bottom: 4px;
				border-bottom: 1px solid var(--border-color); color: var(--heading-color);
			}
			.col-ref-table { margin-bottom: 0; font-size: var(--text-sm); }
			.col-ref-table td { vertical-align: top; padding: 6px 8px; }
			.col-ref-letter { font-family: var(--font-stack-mono, monospace); color: var(--text-muted); text-align: center; }
			.col-ref-label { font-weight: 500; }
			.col-ref-source { color: var(--text-muted); }
		</style>`;

	dialog.fields_dict.body.$wrapper.html(html);

	// live filter across letter, label and source text
	dialog.$wrapper.find(".col-ref-search").on("input", function () {
		const term = (this.value || "").trim().toLowerCase();
		let shown = 0;
		dialog.$wrapper.find(".col-ref-row").each(function () {
			const match = !term || $(this).text().toLowerCase().includes(term);
			$(this).toggle(match);
			if (match) shown++;
		});
		// hide a group heading once every row under it is filtered out
		dialog.$wrapper.find(".col-ref-group").each(function () {
			$(this).toggle($(this).find(".col-ref-row:visible").length > 0);
		});
		dialog.$wrapper.find(".col-ref-empty").toggle(shown === 0);
	});

	dialog.show();
}

frappe.query_reports["Item-wise Sales Register Alternate UOM"] = {
	"filters": [
		{
			"fieldname":"from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
			"reqd": 1,
		},
		{
			"fieldname":"to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"reqd": 1,
		},
		{
			"fieldname": "customer",
			"label": __("Customer"),
			"fieldtype": "Link",
			"options": "Customer"
		},
		{
			"fieldname": "company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"default": frappe.defaults.get_user_default("Company")
		},
		{
			"fieldname": "mode_of_payment",
			"label": __("Mode of Payment"),
			"fieldtype": "Link",
			"options": "Mode of Payment"
		},
		{
			"fieldname": "warehouse",
			"label": __("Warehouse"),
			"fieldtype": "Link",
			"options": "Warehouse"
		},
		{
			"fieldname": "brand",
			"label": __("Brand"),
			"fieldtype": "Link",
			"options": "Brand"
		},
		{
			"fieldname": "item_group",
			"label": __("Item Group"),
			"fieldtype": "Link",
			"options": "Item Group"
		},
		// {
		// 	"label": __("Group By"),
		// 	"fieldname": "group_by",
		// 	"fieldtype": "Select",
		// 	"options": ["Customer Group", "Customer", "Item Group", "Item", "Territory", "Invoice"]
		// }
	],
	"onload": function(report) {
		report.page.add_inner_button(__("Column Reference"), () => {
			show_column_reference();
		}, __("Actions"));
	},
	"formatter": function(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (data && data.bold) {
			value = value.bold();

		}
		return value;
	}
}
