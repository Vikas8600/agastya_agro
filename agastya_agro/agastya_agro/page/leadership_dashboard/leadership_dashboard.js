frappe.pages["leadership-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Leadership Dashboard"),
		single_column: true,
	});
	new LeadershipDashboard(page);
};

const LD_API = "agastya_agro.api.leadership_dashboard";

const LD_STATUS = { good: "#0ca30c", warn: "#fab219", crit: "#d03b3b" };
const LD_STATUS_LABEL = { good: __("Healthy"), warn: __("Moderate"), crit: __("Low") };
const LD_RM_LABEL = { good: __("Adequate"), warn: __("Low"), crit: __("Critical") };
// single-hue ordinal ramps (light / dark desk theme)
const LD_RAMP5 = {
	light: ["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#104281"],
	dark: ["#cde2fb", "#86b6ef", "#5598e7", "#2a78d6", "#1c5cab"],
};
const LD_RAMP4 = {
	light: ["#86b6ef", "#3987e5", "#1c5cab", "#0d366b"],
	dark: ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab"],
};
const LD_SERIES1 = { light: "#2a78d6", dark: "#3987e5" };

class LeadershipDashboard {
	constructor(page) {
		this.page = page;
		this.state = { depots: [], warehouses: [], unit: "value", fg_view: "depot" };
		this.context = null;
		// monotonically increasing request tokens: a response is applied only if
		// it belongs to the latest request, so rapid filter changes can't leave
		// a stale response painted over a newer one
		this.seq = 0;
		this.fg_seq = 0;
		this.make_filters();
		this.make_body();
		this.show_skeletons();
		this.load();
	}

	theme() {
		return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
	}

	make_filters() {
		this.depot_field = this.page.add_field({
			fieldname: "depots",
			label: __("Depot"),
			fieldtype: "MultiSelectList",
			get_data: () =>
				(this.context ? this.context.depots : []).map((d) => ({
					value: d.name,
					description: "",
				})),
			change: () => {
				this.state.depots = this.depot_field.get_value() || [];
				this.refresh();
			},
		});
		this.warehouse_field = this.page.add_field({
			fieldname: "warehouses",
			label: __("Warehouse"),
			fieldtype: "MultiSelectList",
			get_data: () =>
				(this.context ? this.context.warehouses : []).map((w) => ({
					value: w,
					description: "",
				})),
			change: () => {
				this.state.warehouses = this.warehouse_field.get_value() || [];
				this.refresh();
			},
		});
		this.unit_field = this.page.add_field({
			fieldname: "unit",
			label: __("Units"),
			fieldtype: "Select",
			options: [
				{ value: "value", label: __("₹ Value") },
				{ value: "qty", label: __("Qty (Lt-Kg)") },
			],
			default: "value",
			change: () => {
				this.state.unit = this.unit_field.get_value() || "value";
				this.render_all();
			},
		});
		this.page.set_secondary_action(__("Refresh"), () => this.refresh(), "refresh");
	}

	make_body() {
		this.$body = $(`
			<div class="ld-root">
				<div class="ld-kpis" data-el="kpis"></div>
				<div class="ld-grid">
					<div class="ld-card ld-wide" data-card="fg">
						<div class="ld-card-h">
							<h4>${__("Finished Goods stock")}</h4>
							<span class="ld-sub" data-el="fg-sub"></span>
							<div class="ld-tools">
								<div class="ld-seg" data-el="fg-toggle">
									<button data-view="depot" class="active">${__("Depot-wise")}</button>
									<button data-view="sku">${__("SKU-wise")}</button>
								</div>
							</div>
						</div>
						<div class="ld-legend" data-el="fg-legend"></div>
						<div class="ld-chart" data-el="fg-chart"></div>
					</div>
					<div class="ld-card ld-wide" data-card="ageing">
						<div class="ld-card-h"><h4>${__("Stock ageing")}</h4>
							<span class="ld-sub" data-el="ageing-sub">${__("days since manufacture, ₹")}</span></div>
						<div class="ld-legend" data-el="ageing-legend"></div>
						<div class="ld-chart" data-el="ageing-chart"></div>
					</div>
					<div class="ld-card" data-card="expiry">
						<div class="ld-card-h"><h4>${__("Expiry status")}</h4>
							<span class="ld-sub">${__("shelf-life risk, ₹ of FG stock")}</span></div>
						<div class="ld-chart" data-el="expiry-chart"></div>
						<div class="ld-legend" data-el="expiry-legend"></div>
					</div>
					<div class="ld-card" data-card="debt">
						<div class="ld-card-h"><h4>${__("Receivables ageing")}</h4>
							<span class="ld-sub" data-el="debt-sub"></span></div>
						<div class="ld-chart" data-el="debt-chart"></div>
						<div class="ld-legend" data-el="debt-legend"></div>
					</div>
					<div class="ld-card ld-wide" data-card="rm">
						<div class="ld-card-h"><h4>${__("Raw Material stock")}</h4>
							<span class="ld-sub">${__("all warehouses, by material type")}</span></div>
						<div class="ld-legend" data-el="rm-legend"></div>
						<div class="ld-chart" data-el="rm-chart"></div>
					</div>
					<div class="ld-card ld-wide" data-card="top">
						<div class="ld-card-h"><h4>${__("Top outstanding — sales offices")}</h4>
							<span class="ld-sub">${__("invoice outstanding per depot")}</span></div>
						<div class="ld-chart" data-el="top-chart"></div>
					</div>
				</div>
				<p class="ld-foot" data-el="foot"></p>
			</div>
		`).appendTo(this.page.body);

		this.$tip = $(`<div class="ld-tip" role="status"></div>`).appendTo(document.body);
		this.inject_style();

		this.$body.find("[data-el='fg-toggle'] button").on("click", (e) => {
			this.state.fg_view = $(e.currentTarget).data("view");
			this.$body.find("[data-el='fg-toggle'] button").removeClass("active");
			$(e.currentTarget).addClass("active");
			this.fetch_fg();
		});

		let resize_timer;
		$(window).on("resize.ld", () => {
			clearTimeout(resize_timer);
			resize_timer = setTimeout(() => this.render_all(), 200);
		});
	}

	el(name) {
		return this.$body.find(`[data-el='${name}']`)[0];
	}

	// ------------------------------------------------------------ data

	load() {
		frappe.call(`${LD_API}.get_context_data`).then((r) => {
			this.context = r.message;
			this.depot_field.refresh();
			this.warehouse_field.refresh();
			this.refresh();
		});
	}

	refresh() {
		const seq = ++this.seq;
		const depots = JSON.stringify(this.state.depots || []);
		const warehouses = JSON.stringify(this.state.warehouses || []);
		// refetch keeps the previous render dimmed — skeletons only before first data
		this.$body.addClass("ld-loading");
		const calls = [
			frappe.call(`${LD_API}.get_summary`, { depots, warehouses }),
			frappe.call(`${LD_API}.get_ageing_expiry`, { depots, warehouses }),
			frappe.call(`${LD_API}.get_rm_stock`, { warehouses }),
			frappe.call(`${LD_API}.get_debtors`, { depots }),
		];
		Promise.all(calls)
			.then(([summary, ageing, rm, debt]) => {
				if (seq !== this.seq) return; // a newer refresh superseded this one
				this.data = {
					summary: summary.message,
					ageing: ageing.message,
					rm: rm.message,
					debt: debt.message,
				};
				this.render_all();
				if (this.data.ageing.pending || this.data.debt.pending) this.poll_pending();
			})
			.finally(() => {
				if (seq === this.seq) this.$body.removeClass("ld-loading");
			});
		this.fetch_fg();
	}

	fetch_fg() {
		const seq = ++this.fg_seq;
		const single = (this.state.depots || []).length === 1;
		const view = single ? "sku" : this.state.fg_view;
		this.$body.find("[data-el='fg-toggle']").toggle(!single);
		frappe
			.call(`${LD_API}.get_fg_stock`, {
				view,
				depots: JSON.stringify(this.state.depots || []),
				warehouses: JSON.stringify(this.state.warehouses || []),
			})
			.then((r) => {
				if (seq !== this.fg_seq) return;
				this.fg = r.message;
				this.render_fg();
			});
	}

	poll_pending() {
		// heavy datasets are computed by background jobs on a cold cache;
		// check back until every pending one lands
		if (this._poll) clearTimeout(this._poll);
		this._poll = setTimeout(async () => {
			const depots = JSON.stringify(this.state.depots || []);
			const warehouses = JSON.stringify(this.state.warehouses || []);
			let still_pending = false;
			if (this.data.ageing.pending) {
				const r = await frappe.call(`${LD_API}.get_ageing_expiry`, { depots, warehouses });
				this.data.ageing = r.message;
				if (r.message.pending) still_pending = true;
				else {
					this.render_ageing();
					this.render_expiry();
				}
			}
			if (this.data.debt.pending) {
				const r = await frappe.call(`${LD_API}.get_debtors`, { depots });
				this.data.debt = r.message;
				if (r.message.pending) still_pending = true;
				else this.render_debt();
			}
			if (!still_pending) {
				const r = await frappe.call(`${LD_API}.get_summary`, { depots, warehouses });
				this.data.summary = r.message;
				this.render_kpis();
			} else {
				this.poll_pending();
			}
		}, 15000);
	}

	// ------------------------------------------------------------ formats

	fmt_val(rupees) {
		const l = rupees / 100000;
		return l >= 100 ? "₹" + (l / 100).toFixed(1) + " Cr" : "₹" + Math.round(l) + " L";
	}

	fmt_qty(qty) {
		return qty >= 1000 ? (qty / 1000).toFixed(1) + " K" : String(Math.round(qty));
	}

	fmt(bar) {
		return this.state.unit === "value" ? this.fmt_val(bar.value) : this.fmt_qty(bar.qty);
	}

	measure(bar) {
		return this.state.unit === "value" ? bar.value : bar.qty;
	}

	tick_fmt(v) {
		if (!v) return "0";
		if (this.state.unit === "qty") return this.fmt_qty(v);
		const l = v / 100000;
		return l >= 100 ? l / 100 + "Cr" : Math.round(l) + "L";
	}

	// ------------------------------------------------------------ render

	render_all() {
		if (!this.data) return;
		this.render_kpis();
		this.render_fg();
		this.render_expiry();
		this.render_ageing();
		this.render_rm();
		this.render_debt();
		const stamp = this.data.ageing && this.data.ageing.computed_on
			? __("Ageing computed {0}", [frappe.datetime.comment_when(this.data.ageing.computed_on)])
			: "";
		$(this.el("foot")).text(
			__("Stock is live · debtors as on today · {0}", [stamp])
		);
	}

	render_kpis() {
		const s = this.data.summary;
		const near = s.near_expiry_pct === null ? "…" : s.near_expiry_pct + "%";
		const near_cls = s.near_expiry_pct >= 15 ? "warn" : "good";
		const near_tip = s.near_expiry_pct === null ? null : [
			{
				v: `${this.fmt_val(s.near_expiry_value)} ÷ ${this.fmt_val(s.expiry_total_value)} × 100 = ${s.near_expiry_pct}%`,
				l: __("near-expiry value ÷ total FG value × 100"),
			},
			{ v: "", l: __("Near expiry (<120 d): {0}", [this.fmt_val(s.near_expiry_value)]) },
			{ v: "", l: __("Total FG value (batch-wise): {0}", [this.fmt_val(s.expiry_total_value)]) },
		];
		const tiles = [
			{ label: __("Finished Goods stock"), value: this.fmt_val(s.fg_value), sub: "" },
			{ label: __("FG near expiry (<120 d)"), value: near, sub: __("of FG value"), cls: near_cls, tip: near_tip },
			{
				label: __("RM lines below threshold"),
				value: String(s.rm_below_threshold),
				sub: __("{0} critical", [s.rm_critical]),
				cls: s.rm_critical ? "crit" : s.rm_below_threshold ? "warn" : "good",
			},
			{
				label: __("Total outstanding"),
				value: s.outstanding === null ? "…" : this.fmt_val(s.outstanding),
				sub: s.outstanding === null ? __("computing") : __("{0} overdue >90 d", [this.fmt_val(s.overdue_90)]),
				cls: s.outstanding && s.overdue_90 / s.outstanding > 0.15 ? "crit" : "warn",
			},
		];
		const host = $(this.el("kpis")).empty();
		for (const t of tiles) {
			const tile = $(`<div class="ld-kpi"><div class="l"></div><div class="v"></div><div class="d"></div></div>`);
			tile.find(".l").text(t.label);
			tile.find(".v").text(t.value);
			tile.find(".d").text(t.sub).addClass(t.cls ? "st-" + t.cls : "");
			if (t.tip) {
				tile.addClass("ld-kpi-help").attr("tabindex", 0);
				this.bind_tip(tile[0], () => t.tip);
			}
			host.append(tile);
		}
	}

	render_fg() {
		if (!this.fg) return;
		const bars = this.fg.bars.map((b) => ({
			label: b.label,
			value: this.measure(b),
			color: LD_STATUS[b.status],
			tip: [
				{ v: this.fmt(b), l: b.label, key: LD_STATUS[b.status] },
				{ v: "", l: __("Status: {0}", [LD_STATUS_LABEL[b.status]]) },
			],
			meta: b,
		}));
		const counts = { good: 0, warn: 0, crit: 0 };
		this.fg.bars.forEach((b) => counts[b.status]++);
		this.legend(this.el("fg-legend"), Object.keys(counts).map((k) => ({
			color: LD_STATUS[k],
			text: `${LD_STATUS_LABEL[k]} · ${counts[k]}`,
		})));
		$(this.el("fg-sub")).text(
			this.fg.view === "depot" ? __("live stock per depot") : __("top SKUs")
		);
		this.column_chart(this.el("fg-chart"), bars, {
			on_click: this.fg.view === "depot"
				? (bar) => this.show_drilldown("fg_depot", bar.meta, __("SKUs at {0}", [bar.label]))
				: null,
		});
	}

	render_expiry() {
		const a = this.data.ageing;
		const host = this.el("expiry-chart");
		if (a.pending) return this.pending_note(host);
		const e = a.expiry;
		const total = e.expired + e.near + e.regular;
		if (!total) return this.empty_note(host);
		const colors = [LD_STATUS.good, LD_STATUS.warn, LD_STATUS.crit];
		const labels = [__("Regular (>120 d)"), __("Near expiry (<120 d)"), __("Expired")];
		const vals = [e.regular, e.near, e.expired];
		this.donut_chart(host, labels.map((l, i) => ({ label: l, value: vals[i] })), colors, {
			center: Math.round((e.near / total) * 100) + "%",
			center_sub: __("near expiry"),
			val_fmt: (v) => this.fmt_val(v),
		});
		this.legend(this.el("expiry-legend"), labels.map((l, i) => ({
			color: colors[i],
			text: `${l} · ${Math.round((vals[i] / total) * 100)}%`,
		})));
	}

	render_ageing() {
		const a = this.data.ageing;
		const host = this.el("ageing-chart");
		if (a.pending) return this.pending_note(host);
		if (!a.depots.length) return this.empty_note(host);
		const buckets = ["0-30", "31-60", "61-90", "91-120", "120+"];
		const colors = LD_RAMP5[this.theme()];
		const labels = a.depots.map((d) => d.label);
		const series = buckets.map((b) => a.depots.map((d) => d.ageing_value[b]));
		this.legend(this.el("ageing-legend"), buckets.map((b, i) => ({
			color: colors[i], text: b + " d",
		})));
		this.stacked_chart(host, labels, series, colors, { buckets });
	}

	render_rm() {
		const bars = this.data.rm.bars.map((b) => ({
			label: b.label,
			value: this.measure(b),
			color: LD_STATUS[b.status],
			tip: [
				{ v: this.fmt(b), l: b.label, key: LD_STATUS[b.status] },
				{ v: "", l: LD_RM_LABEL[b.status] },
			],
		}));
		const counts = { good: 0, warn: 0, crit: 0 };
		this.data.rm.bars.forEach((b) => counts[b.status]++);
		this.legend(this.el("rm-legend"), Object.keys(counts).map((k) => ({
			color: LD_STATUS[k],
			text: `${LD_RM_LABEL[k]} · ${counts[k]}`,
		})));
		if (!bars.length) return this.empty_note(this.el("rm-chart"));
		this.hbar_chart(this.el("rm-chart"), bars);
	}

	render_debt() {
		const d = this.data.debt;
		const host = this.el("debt-chart");
		const wh_note = (this.state.warehouses || []).length ? " · " + __("warehouse filter not applicable") : "";
		$(this.el("debt-sub")).text(__("as per books, by days overdue ({0})", [this.context.ageing_basis]) + wh_note);
		if (d.pending) {
			this.pending_note(host);
			this.pending_note(this.el("top-chart"));
			return;
		}
		if (!d.total) {
			this.empty_note(host);
		} else {
			const buckets = ["0-30", "31-60", "61-90", "90+"];
			const colors = LD_RAMP4[this.theme()];
			this.donut_chart(host, buckets.map((b) => ({ label: b + " d", value: d.buckets[b] })), colors, {
				center: this.fmt_val(d.total),
				center_sub: __("outstanding"),
				val_fmt: (v) => this.fmt_val(v),
			});
			this.legend(this.el("debt-legend"), buckets.map((b, i) => ({
				color: colors[i],
				text: `${b} d · ${Math.round((d.buckets[b] / d.total) * 100)}%`,
			})));
		}
		const series1 = LD_SERIES1[this.theme()];
		const bars = d.depots.slice(0, 15).map((row) => ({
			label: row.label,
			value: row.outstanding,
			color: series1,
			tip: [
				{ v: this.fmt_val(row.outstanding), l: row.label, key: series1 },
				{ v: "", l: __("{0} overdue >90 d", [this.fmt_val(row.over_90)]) },
			],
			meta: row,
		}));
		if (!bars.length) return this.empty_note(this.el("top-chart"));
		this.column_chart(this.el("top-chart"), bars, {
			tick_fmt: (v) => (v ? this.fmt_val(v).replace(" ", "") : "0"),
			on_click: (bar) => {
				const depot = this.context.depots.find((x) => x.label === bar.label);
				if (depot) this.show_drilldown("debtors_depot", { name: depot.name }, __("Customers — {0}", [bar.label]));
			},
		});
	}

	show_drilldown(block, meta, title) {
		frappe
			.call(`${LD_API}.get_drilldown`, {
				block,
				key: meta.name || meta.label,
				depots: JSON.stringify(this.state.depots || []),
			})
			.then((r) => {
				const { columns, rows } = r.message;
				const body = $("<div class='ld-drill'><table class='table table-sm'><thead><tr></tr></thead><tbody></tbody></table></div>");
				const head = body.find("thead tr");
				columns.forEach((c) => head.append($("<th>").text(c)));
				const tbody = body.find("tbody");
				rows.forEach((row) => {
					const tr = $("<tr>");
					row.forEach((cell, i) => {
						const text = typeof cell === "number"
							? (columns[i] === __("Qty") ? this.fmt_qty(cell) : this.fmt_val(cell))
							: cell;
						tr.append($("<td>").text(text));
					});
					tbody.append(tr);
				});
				const dialog = new frappe.ui.Dialog({ title, size: "large" });
				$(dialog.body).append(body);
				dialog.show();
			});
	}

	// ------------------------------------------------------------ charts (SVG)

	svg_el(tag, attrs) {
		const e = document.createElementNS("http://www.w3.org/2000/svg", tag);
		for (const k in attrs) e.setAttribute(k, attrs[k]);
		return e;
	}

	chrome() {
		const style = getComputedStyle(document.documentElement);
		return {
			grid: style.getPropertyValue("--border-color").trim() || "#e1e0d9",
			muted: style.getPropertyValue("--text-muted").trim() || "#898781",
			ink: style.getPropertyValue("--text-color").trim() || "#0b0b0b",
		};
	}

	nice_ticks(max) {
		const raw = max / 3;
		const mag = Math.pow(10, Math.floor(Math.log10(raw || 1)));
		const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => max / s <= 4) || 10 * mag;
		const ticks = [];
		for (let v = 0; v <= max * 1.001; v += step) ticks.push(v);
		return ticks;
	}

	rounded_top(x, y, w, h, r) {
		if (h <= r) r = Math.max(1, h / 2);
		return `M${x},${y + h} L${x},${y + r} Q${x},${y} ${x + r},${y} L${x + w - r},${y} Q${x + w},${y} ${x + w},${y + r} L${x + w},${y + h} Z`;
	}

	rounded_right(x, y, w, h, r) {
		if (w <= r) r = Math.max(1, w / 2);
		return `M${x},${y} L${x + w - r},${y} Q${x + w},${y} ${x + w},${y + r} L${x + w},${y + h - r} Q${x + w},${y + h} ${x + w - r},${y + h} L${x},${y + h} Z`;
	}

	bind_tip(el, get_lines) {
		const show = (x, y) => {
			this.$tip.empty();
			for (const line of get_lines()) {
				if (line.v) this.$tip.append($("<div class='tv'>").text(line.v));
				const l = $("<div class='tl'>");
				if (line.key) l.append($("<span class='key'>").css("background", line.key));
				l.append(document.createTextNode(line.l));
				this.$tip.append(l);
			}
			this.$tip.css({ display: "block" });
			const r = this.$tip[0].getBoundingClientRect();
			this.$tip.css({
				left: Math.min(x + 14, window.innerWidth - r.width - 8) + "px",
				top: Math.min(y + 14, window.innerHeight - r.height - 8) + "px",
			});
		};
		el.addEventListener("pointerenter", (e) => show(e.clientX, e.clientY));
		el.addEventListener("pointermove", (e) => show(e.clientX, e.clientY));
		el.addEventListener("pointerleave", () => this.$tip.hide());
		el.addEventListener("focus", () => {
			const r = el.getBoundingClientRect();
			show(r.left + r.width / 2, r.top);
		});
		el.addEventListener("blur", () => this.$tip.hide());
	}

	column_chart(host, items, opts = {}) {
		host.replaceChildren();
		if (!items.length) return this.empty_note(host);
		const c = this.chrome();
		const W = Math.max(host.clientWidth || 600, 320);
		const H = 240, padL = 52, padR = 8, padT = 16, padB = 34;
		const svg = this.svg_el("svg", { viewBox: `0 0 ${W} ${H}`, width: "100%", height: H });
		const iw = W - padL - padR, ih = H - padT - padB;
		const max = Math.max(...items.map((i) => i.value)) * 1.08 || 1;
		const tick_fmt = opts.tick_fmt || ((v) => this.tick_fmt(v));
		for (const t of this.nice_ticks(max)) {
			const y = padT + ih - (t / max) * ih;
			if (t > 0) svg.appendChild(this.svg_el("line", { x1: padL, x2: W - padR, y1: y, y2: y, stroke: c.grid, "stroke-width": 1 }));
			const lb = this.svg_el("text", { x: padL - 6, y: y + 4, "text-anchor": "end", "font-size": 10.5, fill: c.muted });
			lb.textContent = tick_fmt(t);
			svg.appendChild(lb);
		}
		svg.appendChild(this.svg_el("line", { x1: padL, x2: W - padR, y1: padT + ih, y2: padT + ih, stroke: c.grid, "stroke-width": 1 }));
		const band = iw / items.length;
		const bw = Math.min(24, band * 0.55);
		const max_i = items.reduce((a, x, i) => (x.value > items[a].value ? i : a), 0);
		const min_i = items.reduce((a, x, i) => (x.value < items[a].value ? i : a), 0);
		items.forEach((it, i) => {
			const bh = Math.max(2, (it.value / max) * ih);
			const x = padL + band * i + (band - bw) / 2;
			const y = padT + ih - bh;
			const p = this.svg_el("path", { d: this.rounded_top(x, y, bw, bh, 4), fill: it.color, class: "ld-bar", tabindex: 0 });
			this.bind_tip(p, () => it.tip);
			if (opts.on_click) {
				p.classList.add("ld-clickable");
				p.addEventListener("click", () => opts.on_click(it));
			}
			svg.appendChild(p);
			if (i === max_i || i === min_i) {
				const vl = this.svg_el("text", { x: x + bw / 2, y: y - 5, "text-anchor": "middle", "font-size": 10.5, "font-weight": 600, fill: c.ink });
				vl.textContent = it.tip[0].v;
				svg.appendChild(vl);
			}
			const xl = this.svg_el("text", {
				x: padL + band * i + band / 2, y: H - 16, "text-anchor": "middle",
				"font-size": items.length > 6 ? 9.5 : 10.5, fill: c.muted,
			});
			xl.textContent = it.label.length > 10 ? it.label.slice(0, 9) + "…" : it.label;
			svg.appendChild(xl);
		});
		host.appendChild(svg);
	}

	stacked_chart(host, labels, series, colors, opts) {
		host.replaceChildren();
		const c = this.chrome();
		const W = Math.max(host.clientWidth || 460, 300);
		const H = 236, padL = 52, padR = 8, padT = 10, padB = 34;
		const svg = this.svg_el("svg", { viewBox: `0 0 ${W} ${H}`, width: "100%", height: H });
		const iw = W - padL - padR, ih = H - padT - padB;
		const totals = labels.map((_, d) => series.reduce((s, b) => s + b[d], 0));
		const max = Math.max(...totals) * 1.06 || 1;
		// ageing values are always rupees, independent of the unit toggle —
		// never format these ticks with the unit-aware formatter
		const rupee_tick = (v) => (!v ? "0" : v / 100000 >= 100 ? v / 1e7 + "Cr" : Math.round(v / 100000) + "L");
		for (const t of this.nice_ticks(max)) {
			const y = padT + ih - (t / max) * ih;
			if (t > 0) svg.appendChild(this.svg_el("line", { x1: padL, x2: W - padR, y1: y, y2: y, stroke: c.grid, "stroke-width": 1 }));
			const lb = this.svg_el("text", { x: padL - 6, y: y + 4, "text-anchor": "end", "font-size": 10.5, fill: c.muted });
			lb.textContent = rupee_tick(t);
			svg.appendChild(lb);
		}
		svg.appendChild(this.svg_el("line", { x1: padL, x2: W - padR, y1: padT + ih, y2: padT + ih, stroke: c.grid, "stroke-width": 1 }));
		const band = iw / labels.length;
		const bw = Math.min(24, band * 0.55);
		labels.forEach((lab, d) => {
			const x = padL + band * d + (band - bw) / 2;
			let cursor = padT + ih;
			series.forEach((bucket, b) => {
				const v = bucket[d];
				if (v <= 0) return;
				const seg = (v / max) * ih;
				const is_top = series.slice(b + 1).every((bb) => bb[d] <= 0);
				const h = Math.max(1, seg - (is_top ? 0 : 2));
				const y = cursor - seg;
				const shape = is_top
					? this.svg_el("path", { d: this.rounded_top(x, y, bw, h, 3), fill: colors[b] })
					: this.svg_el("rect", { x, y, width: bw, height: h, fill: colors[b] });
				shape.setAttribute("class", "ld-bar");
				shape.setAttribute("tabindex", 0);
				this.bind_tip(shape, () => [
					{ v: this.fmt_val(v), l: `${lab} · ${opts.buckets[b]} d`, key: colors[b] },
					{ v: "", l: Math.round((v / totals[d]) * 100) + __("% of depot stock") },
				]);
				svg.appendChild(shape);
				cursor -= seg;
			});
			const xl = this.svg_el("text", {
				x: padL + band * d + band / 2, y: H - 16, "text-anchor": "middle",
				"font-size": labels.length > 6 ? 9.5 : 10.5, fill: c.muted,
			});
			xl.textContent = lab.length > 10 ? lab.slice(0, 9) + "…" : lab;
			svg.appendChild(xl);
		});
		host.appendChild(svg);
	}

	hbar_chart(host, items) {
		host.replaceChildren();
		const c = this.chrome();
		const W = Math.max(host.clientWidth || 460, 300);
		const rowH = 30, padL = 128, padR = 80, padT = 4;
		const H = padT + items.length * rowH + 8;
		const svg = this.svg_el("svg", { viewBox: `0 0 ${W} ${H}`, width: "100%", height: H });
		const iw = W - padL - padR;
		const max = Math.max(...items.map((i) => i.value)) || 1;
		svg.appendChild(this.svg_el("line", { x1: padL, x2: padL, y1: padT, y2: H - 6, stroke: c.grid, "stroke-width": 1 }));
		items.forEach((it, i) => {
			const y = padT + i * rowH + (rowH - 18) / 2;
			const w = Math.max(3, (it.value / max) * iw);
			const lb = this.svg_el("text", { x: padL - 8, y: y + 13, "text-anchor": "end", "font-size": 11.5, fill: c.ink });
			lb.textContent = it.label.length > 16 ? it.label.slice(0, 15) + "…" : it.label;
			svg.appendChild(lb);
			const p = this.svg_el("path", { d: this.rounded_right(padL, y, w, 18, 4), fill: it.color, class: "ld-bar", tabindex: 0 });
			this.bind_tip(p, () => it.tip);
			svg.appendChild(p);
			const vl = this.svg_el("text", { x: padL + w + 7, y: y + 13, "font-size": 11, "font-weight": 600, fill: c.ink });
			vl.textContent = it.tip[0].v;
			svg.appendChild(vl);
		});
		host.appendChild(svg);
	}

	donut_chart(host, segments, colors, opts) {
		host.replaceChildren();
		const c = this.chrome();
		const S = 200, cx = S / 2, cy = S / 2, r = 70, sw = 26;
		const svg = this.svg_el("svg", { viewBox: `0 0 ${S} ${S}`, width: S, height: S, style: "display:block;margin:0 auto;max-width:210px" });
		const total = segments.reduce((s, x) => s + x.value, 0) || 1;
		const gap = (2 / (2 * Math.PI * r)) * 360 * 2;
		let a0 = -90;
		segments.forEach((seg, i) => {
			const sweep = (seg.value / total) * 360;
			const s = a0 + gap / 2, e = a0 + sweep - gap / 2;
			if (e > s) {
				const la = e - s > 180 ? 1 : 0;
				const p1 = [cx + r * Math.cos((s * Math.PI) / 180), cy + r * Math.sin((s * Math.PI) / 180)];
				const p2 = [cx + r * Math.cos((e * Math.PI) / 180), cy + r * Math.sin((e * Math.PI) / 180)];
				const path = this.svg_el("path", {
					d: `M${p1[0]},${p1[1]} A${r},${r} 0 ${la} 1 ${p2[0]},${p2[1]}`,
					stroke: colors[i], "stroke-width": sw, fill: "none", class: "ld-bar", tabindex: 0,
				});
				this.bind_tip(path, () => [
					{ v: opts.val_fmt(seg.value), l: seg.label, key: colors[i] },
					{ v: "", l: Math.round((seg.value / total) * 100) + __("% of total") },
				]);
				svg.appendChild(path);
			}
			a0 += sweep;
		});
		const c1 = this.svg_el("text", { x: cx, y: cy - 2, "text-anchor": "middle", "font-size": 19, "font-weight": 700, fill: c.ink });
		c1.textContent = opts.center;
		svg.appendChild(c1);
		const c2 = this.svg_el("text", { x: cx, y: cy + 16, "text-anchor": "middle", "font-size": 10.5, fill: c.muted });
		c2.textContent = opts.center_sub;
		svg.appendChild(c2);
		host.appendChild(svg);
	}

	legend(host, items) {
		const $host = $(host).empty();
		for (const it of items) {
			const s = $("<span class='it'>");
			s.append($("<span class='sw'>").css("background", it.color));
			s.append(document.createTextNode(it.text));
			$host.append(s);
		}
	}

	show_skeletons() {
		const kpis = $(this.el("kpis")).empty();
		for (let i = 0; i < 4; i++) {
			kpis.append(`
				<div class="ld-kpi">
					<div class="ld-skel" style="width:60%;height:12px"></div>
					<div class="ld-skel" style="width:45%;height:26px;margin:8px 0 6px"></div>
					<div class="ld-skel" style="width:70%;height:11px"></div>
				</div>`);
		}
		const chart_skeleton = (host, kind) => {
			const $host = $(host).empty();
			if (kind === "donut") {
				$host.append(`<div class="ld-skel ld-skel-donut"></div>`);
			} else if (kind === "hbar") {
				const box = $(`<div class="ld-skel-hbars">`);
				[85, 62, 44, 30].forEach((w) => box.append(`<div class="ld-skel" style="width:${w}%;height:16px"></div>`));
				$host.append(box);
			} else {
				const box = $(`<div class="ld-skel-cols">`);
				[85, 65, 55, 45, 35, 28, 20].forEach((h) => box.append(`<div class="ld-skel" style="height:${h}%"></div>`));
				$host.append(box);
			}
		};
		chart_skeleton(this.el("fg-chart"), "cols");
		chart_skeleton(this.el("expiry-chart"), "donut");
		chart_skeleton(this.el("ageing-chart"), "cols");
		chart_skeleton(this.el("rm-chart"), "hbar");
		chart_skeleton(this.el("debt-chart"), "donut");
		chart_skeleton(this.el("top-chart"), "cols");
	}

	pending_note(host) {
		$(host).empty().append(
			$("<div class='ld-note'>").text(__("Computing batch ageing in the background — this refreshes automatically."))
		);
	}

	empty_note(host) {
		$(host).empty().append($("<div class='ld-note'>").text(__("No data for the selected filters.")));
	}

	inject_style() {
		if ($("#ld-style").length) return;
		$(`<style id="ld-style">
			.ld-root { padding-bottom: 40px; }
			.ld-root.ld-loading { opacity: .55; pointer-events: none; transition: opacity .15s; }
			.ld-kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 14px; }
			@media (max-width: 860px) { .ld-kpis { grid-template-columns: repeat(2, 1fr); } }
			.ld-kpi { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 10px; padding: 11px 14px; }
			.ld-kpi .l { font-size: 12px; color: var(--text-muted); }
			.ld-kpi .v { font-size: 24px; font-weight: 650; margin: 2px 0; color: var(--text-color); }
			.ld-kpi .d { font-size: 12px; color: var(--text-muted); }
			.ld-kpi .d.st-good { color: #0ca30c; } .ld-kpi .d.st-warn { color: #8a5f00; } .ld-kpi .d.st-crit { color: #d03b3b; }
			.ld-kpi-help { cursor: help; }
			[data-theme="dark"] .ld-kpi .d.st-warn { color: #fab219; }
			.ld-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
			@media (max-width: 900px) { .ld-grid { grid-template-columns: 1fr; } }
			.ld-card { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 12px; padding: 12px 15px; min-width: 0; }
			.ld-wide { grid-column: 1 / -1; }
			.ld-card-h { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 4px; }
			.ld-card-h h4 { font-size: 14px; margin: 0; }
			.ld-sub { font-size: 12px; color: var(--text-muted); }
			.ld-tools { margin-left: auto; }
			.ld-seg { display: inline-flex; border: 1px solid var(--border-color); border-radius: 7px; padding: 1px; }
			.ld-seg button { font-size: 12px; border: 0; background: transparent; color: var(--text-muted); padding: 3px 10px; border-radius: 5px; cursor: pointer; }
			.ld-seg button.active { background: var(--control-bg); color: var(--text-color); font-weight: 600; }
			.ld-legend { display: flex; gap: 14px; flex-wrap: wrap; font-size: 12px; color: var(--text-muted); margin: 4px 0 2px; }
			.ld-legend .it { display: inline-flex; align-items: center; gap: 6px; }
			.ld-legend .sw { width: 10px; height: 10px; border-radius: 2px; flex: none; }
			.ld-chart { min-height: 120px; }
			.ld-bar { cursor: default; }
			.ld-bar:hover, .ld-bar:focus-visible { filter: brightness(1.12); }
			.ld-clickable { cursor: pointer; }
			.ld-note { padding: 34px 10px; text-align: center; font-size: 12.5px; color: var(--text-muted); }
			.ld-foot { margin-top: 14px; font-size: 12px; color: var(--text-muted); }
			.ld-tip { position: fixed; z-index: 1055; pointer-events: none; display: none;
				background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 8px;
				box-shadow: var(--shadow-md); padding: 7px 10px; font-size: 12.5px; max-width: 240px; }
			.ld-tip .tv { font-size: 14.5px; font-weight: 700; color: var(--text-color); }
			.ld-tip .tl { color: var(--text-muted); display: flex; align-items: center; gap: 6px; }
			.ld-tip .key { display: inline-block; width: 10px; height: 3px; border-radius: 2px; }
			.ld-drill { max-height: 60vh; overflow: auto; }
			.ld-skel { background: var(--control-bg); border-radius: 5px; position: relative; overflow: hidden; }
			.ld-skel::after { content: ""; position: absolute; inset: 0;
				background: linear-gradient(90deg, transparent, rgba(255,255,255,.35), transparent);
				transform: translateX(-100%); animation: ld-shimmer 1.3s infinite; }
			[data-theme="dark"] .ld-skel::after {
				background: linear-gradient(90deg, transparent, rgba(255,255,255,.08), transparent); }
			@keyframes ld-shimmer { to { transform: translateX(100%); } }
			@media (prefers-reduced-motion: reduce) { .ld-skel::after { animation: none; } }
			.ld-skel-cols { display: flex; align-items: flex-end; gap: 10px; height: 200px; padding: 10px 8px; }
			.ld-skel-cols .ld-skel { flex: 1; max-width: 34px; }
			.ld-skel-hbars { display: flex; flex-direction: column; gap: 14px; padding: 14px 8px; }
			.ld-skel-donut { width: 150px; height: 150px; border-radius: 50%; margin: 24px auto; }
		</style>`).appendTo("head");
	}
}
