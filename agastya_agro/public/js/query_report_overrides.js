(() => {
	const original_get_data_for_print =
		frappe.views?.QueryReport?.prototype?.get_data_for_print;
	const original_get_filters_html_for_print =
		frappe.views?.QueryReport?.prototype?.get_filters_html_for_print;
	const original_pdf_report = frappe.views?.QueryReport?.prototype?.pdf_report;
	const original_print_report = frappe.views?.QueryReport?.prototype?.print_report;
	const original_get_print_settings = frappe.ui.get_print_settings;
	if (!original_get_print_settings || original_get_print_settings._agastya_gl_defaults) {
		return;
	}

	const preferred_columns = [
		"posting_date",
		"account",
		"debit",
		"credit",
		"balance",
		"voucher_type",
		"voucher_no",
		"remarks",
	];

	const normalize_party_values = (party_value) => {
		if (!party_value) return [];
		if (Array.isArray(party_value)) return party_value.filter(Boolean);
		if (typeof party_value === "string") {
			try {
				const parsed = JSON.parse(party_value);
				if (Array.isArray(parsed)) return parsed.filter(Boolean);
			} catch (e) {
				// ignore parse errors
			}
			return party_value
				.split(",")
				.map((value) => value.trim())
				.filter(Boolean);
		}
		return [];
	};

	const load_customer_city_map = async (report) => {
		const applied_filters = report.get_filter_values();
		const party_type = (applied_filters.party_type || "").toLowerCase();
		const party_values = normalize_party_values(applied_filters.party);

		if (party_type !== "customer" || !party_values.length) {
			report._agastya_city_map = null;
			report._agastya_city_map_key = null;
			return;
		}

		const key = JSON.stringify(party_values);
		if (report._agastya_city_map_key === key && report._agastya_city_map) {
			return;
		}

		const rows = await frappe.db.get_list("Customer", {
			filters: { name: ["in", party_values] },
			fields: ["name", "city"],
		});

		const city_map = {};
		(rows || []).forEach((row) => {
			if (row.name && row.city) {
				city_map[row.name] = row.city;
			}
		});

		report._agastya_city_map = city_map;
		report._agastya_city_map_key = key;
	};

	frappe.ui.get_print_settings = function (
		pdf,
		callback,
		letter_head,
		pick_columns,
		has_filters = false
	) {
		const dialog = original_get_print_settings.apply(this, arguments);

		try {
			const report_name = frappe.query_report && frappe.query_report.report_name;
			if (report_name !== "General Ledger") {
				return dialog;
			}

			if (!Array.isArray(pick_columns) || pick_columns.length === 0) {
				return dialog;
			}

			const available = new Set(pick_columns.map((column) => column.fieldname));
			const selected_columns = preferred_columns.filter((fieldname) => available.has(fieldname));

			if (!selected_columns.length) {
				return dialog;
			}

			const apply_defaults = () => {
				if (dialog._agastya_gl_defaults_applied) return;
				dialog._agastya_gl_defaults_applied = true;

				Promise.resolve(dialog.set_value("pick_columns", 1)).then(() => {
					if (dialog.has_field("include_filters")) {
						dialog.set_value("include_filters", 1);
					}
					dialog.refresh_dependency();
					const columns_field = dialog.fields_dict?.columns;
					if (!columns_field) {
						return;
					}

					columns_field.df.options = (columns_field.df.options || []).map((option) => ({
						...option,
						checked: selected_columns.includes(option.value),
					}));
					columns_field.refresh();
					columns_field.set_value(selected_columns);
					columns_field.refresh_input?.();
				});
			};

			$(document).on("frappe.ui.Dialog:shown", () => {
				if (window.cur_dialog === dialog) {
					apply_defaults();
				}
			});

			const pick_columns_field = dialog.fields_dict?.pick_columns;
			if (pick_columns_field?.$input) {
				pick_columns_field.$input.on("change", () => {
					if (dialog.get_value("pick_columns")) {
						dialog._agastya_gl_defaults_applied = false;
						apply_defaults();
					}
				});
			}
		} catch (e) {
			// Ignore errors to avoid blocking the print dialog.
		}

		return dialog;
	};

	frappe.ui.get_print_settings._agastya_gl_defaults = true;

	if (original_get_data_for_print) {
		frappe.views.QueryReport.prototype.get_data_for_print = function () {
			const rows = original_get_data_for_print.call(this);
			if (this.report_name !== "General Ledger") {
				return rows;
			}

			const applied_filters = this.get_filter_values();
			const party_type = (applied_filters.party_type || "").toLowerCase();
			const party_values = normalize_party_values(applied_filters.party);

			if (party_type !== "customer" || !party_values.length || !rows.length) {
				return rows;
			}

			const adjusted = rows.map((row) => ({ ...row }));
			const first_row = adjusted[0];
			const last_row = adjusted[adjusted.length - 1];

			if (first_row) {
				first_row.debit = "";
				first_row.credit = "";
			}

			if (last_row && last_row !== first_row) {
				last_row.debit = "";
				last_row.credit = "";
			}

			return adjusted;
		};
	}

	if (original_get_filters_html_for_print) {
		const allowed_filter_fieldnames = new Set([
			"company",
			"from_date",
			"to_date",
			"account",
			"party_type",
			"party",
			"party_name",
		]);

		frappe.views.QueryReport.prototype.get_filters_html_for_print = function () {
			if (this.report_name !== "General Ledger") {
				return original_get_filters_html_for_print.call(this);
			}

			const applied_filters = this.get_filter_values();
			const filter_rows = Object.keys(applied_filters)
				.filter((fieldname) => allowed_filter_fieldnames.has(fieldname))
				.map((fieldname) => {
					const docfield = frappe.query_report.get_filter(fieldname).df;
					const value = applied_filters[fieldname];

					if (docfield.hidden_due_to_dependency) {
						return null;
					}

					return `<div class="filter-row">
						<b>${__(docfield.label, null, docfield.parent)}:</b> ${frappe.format(
						value,
						docfield
					)}
					</div>`;
				});

			const party_type = (applied_filters.party_type || "").toLowerCase();
			const party_values = normalize_party_values(applied_filters.party);
			if (party_type === "customer" && party_values.length && this._agastya_city_map) {
				let insert_after_index = filter_rows.findIndex(
					(row_html) => row_html && row_html.includes("<b>Party Name:")
				);
				if (insert_after_index === -1) {
					insert_after_index = filter_rows.findIndex(
						(row_html) => row_html && row_html.includes("<b>Party:")
					);
				}

				if (insert_after_index !== -1) {
					const city_rows = party_values
						.map((party) => {
							const city = this._agastya_city_map[party];
							if (!city) return null;
							return `<div class="filter-row"><b>${__("City")}:</b> ${city}</div>`;
						})
						.filter(Boolean);

					filter_rows.splice(insert_after_index + 1, 0, ...city_rows);
				}
			}

			return filter_rows.join("");
		};
	}

	if (original_pdf_report) {
		frappe.views.QueryReport.prototype.pdf_report = async function (print_settings) {
			if (this.report_name === "General Ledger") {
				await load_customer_city_map(this);
			}
			return original_pdf_report.call(this, print_settings);
		};
	}

	if (original_print_report) {
		frappe.views.QueryReport.prototype.print_report = async function (print_settings) {
			if (this.report_name === "General Ledger") {
				await load_customer_city_map(this);
			}
			return original_print_report.call(this, print_settings);
		};
	}
})();
