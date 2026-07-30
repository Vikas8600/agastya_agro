frappe.pages["ld-explaination"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Leadership Dashboard Explained"),
		single_column: true,
	});

	page.set_primary_action(__("Open Dashboard"), () => {
		frappe.set_route("leadership-dashboard");
	});
	page.add_menu_item(__("Accounts Receivable Report"), () => {
		frappe.set_route("query-report", "Accounts Receivable");
	});
	page.add_menu_item(__("Stock Balance Report"), () => {
		frappe.set_route("query-report", "Stock Balance");
	});
	page.add_menu_item(__("Dashboard Settings"), () => {
		frappe.set_route("leadership-dashboard-settings");
	});

	$(page.body).html(`
	<style>
		.ldx { max-width: 900px; margin: 0 auto; padding-bottom: 60px; color: var(--text-color); font-size: 14px; line-height: 1.6; }
		.ldx .lead { font-size: 15px; color: var(--text-muted); margin: 4px 0 18px; }
		.ldx-tabs { display: flex; gap: 6px; flex-wrap: wrap; border-bottom: 1px solid var(--border-color); margin-bottom: 18px; position: sticky; top: var(--navbar-height, 60px); background: var(--bg-color); padding: 6px 0; z-index: 5; }
		.ldx-tabs button { font: inherit; font-size: 13.5px; border: 0; background: transparent; color: var(--text-muted); padding: 7px 14px; border-radius: 8px 8px 0 0; cursor: pointer; border-bottom: 2px solid transparent; }
		.ldx-tabs button:hover { color: var(--text-color); }
		.ldx-tabs button[aria-selected="true"] { color: var(--text-color); font-weight: 650; border-bottom-color: var(--primary, #2490ef); }
		.ldx-panel { display: none; }
		.ldx-panel.active { display: block; }
		.ldx h2 { font-size: 17px; margin: 26px 0 6px; }
		.ldx h3 { font-size: 15px; margin: 0 0 8px; display: flex; align-items: center; }
		.ldx .card-doc { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 12px; padding: 16px 20px; margin: 14px 0; }
		.ldx .num { display: inline-flex; align-items: center; justify-content: center; width: 24px; height: 24px; border-radius: 50%; background: var(--control-bg); font-weight: 700; font-size: 12.5px; margin-right: 8px; flex: none; }
		.ldx dl { display: grid; grid-template-columns: 130px 1fr; gap: 4px 14px; margin: 10px 0 0; }
		.ldx dt { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; color: var(--text-muted); padding-top: 3px; }
		.ldx dd { margin: 0; }
		.ldx .verify { background: var(--control-bg); border-radius: 8px; padding: 10px 14px; margin-top: 12px; }
		.ldx .verify .vt { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; color: var(--text-muted); margin-bottom: 4px; }
		.ldx .verify ol { margin: 4px 0 0; padding-left: 20px; }
		.ldx .verify li { margin: 3px 0; }
		.ldx .formula { font-family: var(--font-family-monospace, monospace); background: var(--control-bg); border-radius: 6px; padding: 6px 12px; display: inline-block; margin: 6px 0; }
		.ldx table { width: 100%; border-collapse: collapse; font-size: 13.5px; margin: 10px 0; }
		.ldx th { text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: .06em; color: var(--text-muted); border-bottom: 1px solid var(--border-color); padding: 7px 10px; }
		.ldx td { border-bottom: 1px solid var(--border-color); padding: 7px 10px; vertical-align: top; }
		.ldx .note { border-left: 3px solid var(--yellow-500, #b58a00); background: var(--control-bg); border-radius: 0 8px 8px 0; padding: 10px 14px; margin: 14px 0; }
		.ldx .chip { display: inline-block; font-size: 11px; font-weight: 700; border-radius: 999px; padding: 1px 9px; margin-left: 8px; vertical-align: 1px; }
		.ldx .chip.live { color: #0ca30c; background: rgba(12,163,12,.12); }
		.ldx .chip.hourly { color: #1c5cab; background: rgba(42,120,214,.12); }
	</style>
	<div class="ldx">
		<p class="lead">${__("What every number and chart on the Leadership Dashboard means, where it comes from, and how to verify it against standard ERPNext reports.")}</p>

		<div class="ldx-tabs" role="tablist">
			<button role="tab" aria-selected="true" data-tab="cards">${__("Number Cards")}</button>
			<button role="tab" aria-selected="false" data-tab="stock">${__("Stock Charts")}</button>
			<button role="tab" aria-selected="false" data-tab="receivables">${__("Receivables Charts")}</button>
			<button role="tab" aria-selected="false" data-tab="usage">${__("Filters, Access & Refresh")}</button>
		</div>

		<!-- ============================================================ TAB 1 -->
		<div class="ldx-panel active" data-panel="cards">

			<div class="card-doc">
				<h3><span class="num">1</span>${__("Finished Goods Stock")}<span class="chip live">${__("near-live")}</span></h3>
				<p>${__("The total value of finished goods lying in all depot warehouses right now, at book valuation (the value stock carries in the accounts, not the selling price).")}</p>
				<dl>
					<dt>${__("Source")}</dt><dd>${__("Live warehouse stock balances (the same data behind the Stock Balance report), for items under the Finished Goods item group, in each depot's FG warehouse.")}</dd>
					<dt>${__("Depot")}</dt><dd>${__("Every depot (Cost Center) is linked to its FG warehouse; the depot filter narrows this card to the selected depots' warehouses.")}</dd>
					<dt>${__("Freshness")}</dt><dd>${__("Refreshed within 10 minutes of any stock transaction.")}</dd>
				</dl>
				<div class="verify"><div class="vt">${__("How to verify")}</div><ol>
					<li>${__("Open the Stock Balance report.")}</li>
					<li>${__("Set Item Group = Finished Goods and Warehouse = a depot's FG warehouse.")}</li>
					<li>${__("Compare the Balance Value total with the card (same depot selected on the dashboard).")}</li>
				</ol></div>
			</div>

			<div class="card-doc">
				<h3><span class="num">2</span>${__("FG Near Expiry (<120 days)")}<span class="chip hourly">${__("hourly")}</span></h3>
				<p>${__("How much of the finished goods value will cross its expiry date within the next 120 days — the money at shelf-life risk.")}</p>
				<div class="formula">${__("near-expiry value ÷ total FG value × 100")}</div>
				<p>${__("Hover on the card itself to see this formula with the actual rupee values behind today's percentage.")}</p>
				<dl>
					<dt>${__("Source")}</dt><dd>${__("An hourly scan of every batch in stock: the batch's expiry date decides its band (Expired / within 120 days / Regular), and its quantity is valued at the item's current valuation rate.")}</dd>
					<dt>${__("Freshness")}</dt><dd>${__("Recomputed every hour; the dashboard footer shows when the last computation ran.")}</dd>
				</dl>
				<div class="verify"><div class="vt">${__("How to verify")}</div><ol>
					<li>${__("Open the BWBH Expiry Status report (or Finished Goods Stock Position for the per-warehouse split).")}</li>
					<li>${__("Filter batches whose Balance Life is under 120 days and total their stock value.")}</li>
					<li>${__("Divide by total FG value — it should match the card within the hour's refresh window.")}</li>
				</ol></div>
			</div>

			<div class="card-doc">
				<h3><span class="num">3</span>${__("RM Lines Below Threshold")}<span class="chip live">${__("near-live")}</span></h3>
				<p>${__("A count of raw material categories (Technical, Primary, Bulk) whose current stock value has fallen below the minimum level the business has defined. The sub-line shows how many are Critical (below the Red limit).")}</p>
				<dl>
					<dt>${__("Source")}</dt><dd>${__("Live raw material stock across all warehouses, grouped by material type as mapped in Leadership Dashboard Settings, compared with the Red / Orange limits set there.")}</dd>
					<dt>${__("Thresholds")}</dt><dd>${__("Pure configuration — changing a limit in Settings changes the count immediately, no development needed.")}</dd>
				</dl>
				<div class="verify"><div class="vt">${__("How to verify")}</div><ol>
					<li>${__("Open Leadership Dashboard Settings for the material-type mapping and Red/Orange limits (₹ lakh).")}</li>
					<li>${__("Open Stock Balance filtered by that material type's item group and total the Balance Value.")}</li>
					<li>${__("Compare against the limit: below Orange = Low, below Red = Critical.")}</li>
				</ol></div>
			</div>

			<div class="card-doc">
				<h3><span class="num">4</span>${__("Total Outstanding")}<span class="chip hourly">${__("hourly")}</span></h3>
				<p>${__("Total money receivable from customers as per the accounting books, with the sub-line showing how much has been outstanding for more than 90 days.")}</p>
				<dl>
					<dt>${__("Source")}</dt><dd>${__("The same engine as the standard Accounts Receivable report, computed hourly. Every rupee is aged into 0–30 / 31–60 / 61–90 / 90+ day buckets by due date.")}</dd>
					<dt>${__("Depot split")}</dt><dd>${__("Each invoice carries a mandatory Depot Name (cost center); receivables are attributed to depots through it.")}</dd>
				</dl>
				<div class="note">${__("Why this differs from totalling invoice outstanding: payments that are received but not yet matched to specific invoices reduce the books immediately, but not the invoice-wise outstanding. The dashboard follows the books — it will always agree with the Accounts Receivable report. Old imported invoices without a due date are aged by their posting date so no amount is left out.")}</div>
				<div class="verify"><div class="vt">${__("How to verify")}</div><ol>
					<li>${__("Open Accounts Receivable with Ageing Based On = Due Date, ranges 30 / 60 / 90 / 120, as on today.")}</li>
					<li>${__("The report's Total Outstanding should equal the card (within the hourly refresh).")}</li>
					<li>${__("For the 90+ figure, total the 91–120 and 120-above columns, plus no-due-date rows older than 90 days by posting date.")}</li>
				</ol></div>
			</div>

			<h2>${__("Quick verification map")}</h2>
			<table>
				<thead><tr><th>${__("Card")}</th><th>${__("Verify against")}</th><th>${__("Key filters")}</th></tr></thead>
				<tbody>
					<tr><td>${__("Finished Goods Stock")}</td><td>${__("Stock Balance")}</td><td>${__("Item Group = Finished Goods, depot FG warehouses")}</td></tr>
					<tr><td>${__("FG Near Expiry")}</td><td>${__("BWBH Expiry Status / FG Stock Position")}</td><td>${__("Balance Life < 120 days")}</td></tr>
					<tr><td>${__("RM Below Threshold")}</td><td>${__("Stock Balance + Dashboard Settings")}</td><td>${__("RM item groups vs Red/Orange limits")}</td></tr>
					<tr><td>${__("Total Outstanding")}</td><td>${__("Accounts Receivable")}</td><td>${__("Due Date ageing, 30/60/90/120, as on today")}</td></tr>
				</tbody>
			</table>
		</div>

		<!-- ============================================================ TAB 2 -->
		<div class="ldx-panel" data-panel="stock">

			<div class="card-doc">
				<h3><span class="num">1</span>${__("Finished Goods Stock — bar chart")}<span class="chip live">${__("near-live")}</span></h3>
				<p>${__("Live FG stock as bars — one per depot, or one per SKU (top 15 plus an 'Other' rollup) using the toggle on the card. Same source as the Finished Goods Stock card.")}</p>
				<dl>
					<dt>${__("Bar color")}</dt><dd>${__("The bar's status against the thresholds in Settings — Green (healthy), Orange (moderate), Red (low). The legend counts how many bars are in each state.")}</dd>
					<dt>${__("Labels")}</dt><dd>${__("Only the highest and lowest bars carry printed values; hover or tap any bar for its exact value, quantity and status.")}</dd>
					<dt>${__("Drill-down")}</dt><dd>${__("Tap a depot bar to open that depot's SKU list with quantities and values. Selecting a single depot in the filter switches the chart to SKU view automatically.")}</dd>
				</dl>
				<div class="verify"><div class="vt">${__("How to verify")}</div><ol>
					<li>${__("Pick any depot bar and note its value from the hover tooltip.")}</li>
					<li>${__("Open Stock Balance with Item Group = Finished Goods, Warehouse = that depot's FG warehouse.")}</li>
					<li>${__("The report's Balance Value total should match the bar.")}</li>
				</ol></div>
			</div>

			<div class="card-doc">
				<h3><span class="num">2</span>${__("Stock Ageing — stacked bars")}<span class="chip hourly">${__("hourly")}</span></h3>
				<p>${__("For each depot, how old its stock is — measured in days since the batch was manufactured, split into 0–30, 31–60, 61–90, 91–120 and 120+ day bands, in ₹ value. Older stock (darker bands at the top) is capital sitting longest and closest to expiry.")}</p>
				<dl>
					<dt>${__("Source")}</dt><dd>${__("The hourly batch scan: every batch's manufacturing date gives its age; the batch quantity is valued at the item's current valuation rate.")}</dd>
					<dt>${__("Unknown age")}</dt><dd>${__("Batches without a manufacturing date are never forced into a band — they are tracked separately so the bands never overstate. (Currently zero on this site: batch data is clean.)")}</dd>
					<dt>${__("Reading it")}</dt><dd>${__("Hover any segment for the depot, band, ₹ value and its share of that depot's stock.")}</dd>
				</dl>
				<div class="verify"><div class="vt">${__("How to verify")}</div><ol>
					<li>${__("Open the BWBH Expiry Status report for a warehouse.")}</li>
					<li>${__("The Lapsed Life column is the same days-since-manufacture measure; group by its ranges and total the balance quantities.")}</li>
					<li>${__("Value them at the item valuation rate to reconcile with a band.")}</li>
				</ol></div>
			</div>

			<div class="card-doc">
				<h3><span class="num">3</span>${__("Expiry Status — donut")}<span class="chip hourly">${__("hourly")}</span></h3>
				<p>${__("The whole FG stock value split three ways: Regular (more than 120 days of life left), Near Expiry (less than 120 days), and Expired. The centre shows the near-expiry percentage — the same number as the card.")}</p>
				<dl>
					<dt>${__("Source")}</dt><dd>${__("Same hourly batch scan as the ageing chart, banded by expiry date instead of manufacturing date.")}</dd>
					<dt>${__("Reading it")}</dt><dd>${__("Green = safe, Orange = act soon (schemes, liquidation, transfers), Red = value already lost unless disposed/re-tested. Hover any slice for its ₹ value and share.")}</dd>
				</dl>
				<div class="verify"><div class="vt">${__("How to verify")}</div><ol>
					<li>${__("Open Finished Goods Stock Position — its Already Expired / Near Expiry / Regular columns are the same three bands per warehouse.")}</li>
					<li>${__("Total each column across depot warehouses and compare with the slices.")}</li>
				</ol></div>
			</div>

			<div class="card-doc">
				<h3><span class="num">4</span>${__("Raw Material Stock — horizontal bars")}<span class="chip live">${__("near-live")}</span></h3>
				<p>${__("Current RM stock value by material type — Technical, Primary (packing), Bulk (solvents, emulsifiers, fillers and other process chemicals). Bar color and the legend show adequacy against the Settings thresholds.")}</p>
				<dl>
					<dt>${__("Source")}</dt><dd>${__("Live stock balances for the item groups mapped to each material type in Settings, across all warehouses (RM is held at factory stores, so the depot filter does not apply — the card says so).")}</dd>
					<dt>${__("Reading it")}</dt><dd>${__("Hover a bar for the exact value and its status word (Adequate / Low / Critical).")}</dd>
				</dl>
				<div class="verify"><div class="vt">${__("How to verify")}</div><ol>
					<li>${__("Open Stock Balance filtered by the material type's item group (mapping visible in Settings).")}</li>
					<li>${__("Total Balance Value and compare with the bar.")}</li>
				</ol></div>
			</div>
		</div>

		<!-- ============================================================ TAB 3 -->
		<div class="ldx-panel" data-panel="receivables">

			<div class="card-doc">
				<h3><span class="num">1</span>${__("Receivables Ageing — donut")}<span class="chip hourly">${__("hourly")}</span></h3>
				<p>${__("The total book receivable split by how long it has been outstanding: 0–30, 31–60, 61–90 and 90+ days, by due date. The centre shows the total — the same number as the Total Outstanding card.")}</p>
				<dl>
					<dt>${__("Source")}</dt><dd>${__("The hourly Accounts Receivable computation — the books, not invoice-wise outstanding (see the note on the Number Cards tab).")}</dd>
					<dt>${__("Reading it")}</dt><dd>${__("Darker blue = older money. A growing 90+ slice is the collection team's priority list. Hover a slice for its ₹ value and share.")}</dd>
					<dt>${__("Depot filter")}</dt><dd>${__("With depots selected, the donut recomputes for just those depots' receivables.")}</dd>
				</dl>
				<div class="verify"><div class="vt">${__("How to verify")}</div><ol>
					<li>${__("Open Accounts Receivable (Due Date ageing, ranges 30/60/90/120, as on today).")}</li>
					<li>${__("Total each ageing column; combine 91–120 and 120-above into the 90+ slice.")}</li>
					<li>${__("No-due-date rows are aged by posting date on the dashboard.")}</li>
				</ol></div>
			</div>

			<div class="card-doc">
				<h3><span class="num">2</span>${__("Top Outstanding — Sales Offices")}<span class="chip hourly">${__("hourly")}</span></h3>
				<p>${__("Which depots hold the most receivables — total outstanding per depot as bars, largest first.")}</p>
				<dl>
					<dt>${__("Attribution")}</dt><dd>${__("Every sales invoice carries a mandatory Depot Name (cost center); its book outstanding is attributed to that depot. Advances and journal balances with no invoice go to a 'Central / Unmapped' bucket, visible only on the unrestricted all-depot view.")}</dd>
					<dt>${__("Drill-down")}</dt><dd>${__("Tap a depot bar for its customer list — top 100 customers by outstanding with each one's oldest due date, the collection call-list ready-made.")}</dd>
					<dt>${__("Reading it")}</dt><dd>${__("Hover a bar for the depot's total and how much of it is over 90 days old.")}</dd>
				</dl>
				<div class="verify"><div class="vt">${__("How to verify")}</div><ol>
					<li>${__("Open Accounts Receivable filtered by that depot's Cost Center.")}</li>
					<li>${__("Compare the report's Total Outstanding with the bar.")}</li>
					<li>${__("Cross-check a customer from the drill-down against the same report filtered by that customer.")}</li>
				</ol></div>
			</div>
		</div>

		<!-- ============================================================ TAB 4 -->
		<div class="ldx-panel" data-panel="usage">

			<div class="card-doc">
				<h3>${__("Filters")}</h3>
				<dl>
					<dt>${__("Depot")}</dt><dd>${__("Multi-select over depots (Cost Centers). Leave empty to see all permitted depots; pick one or more to narrow every card, chart and drill-down to exactly that slice — all numbers on screen always agree because a single filter scopes everything. The list only ever offers depots the logged-in user is permitted to see. Selecting exactly one depot switches the FG chart to its SKU view automatically (a one-depot depot chart would be a single bar).")}</dd>
					<dt>${__("Warehouse")}</dt><dd>${__("Multi-select over the depot warehouses (FG and RM stores). Narrows the stock-side blocks — FG card and chart, stock ageing, expiry, and RM — to just those warehouses. Receivables are money against depots, not warehouses, so the receivables views ignore this filter and say so on the card. Combining both filters intersects them: Depot = Nagpur + Warehouse = Nagpur FG store shows exactly that store. The list only offers warehouses of depots the user is permitted to see.")}</dd>
					<dt>${__("Units")}</dt><dd>${__("₹ Value (default, in lakh/crore) or Lt-Kg quantity. Switching changes exactly four things: the Finished Goods Stock card, the FG bar chart (bar heights, axis and tooltips), the RM bar chart, and the values inside their tooltips. Everything else deliberately stays as it is: bar colors do not change (Green/Orange/Red thresholds are defined in ₹, so a bar keeps its status in both views), the near-expiry % is a ratio so it is unit-free, and the ageing, expiry and all receivables views remain in rupees — mixing litres and kilograms of different products into one 'quantity' would misstate where the money is.")}</dd>
					<dt>${__("Refresh")}</dt><dd>${__("The Refresh button re-reads all data. While anything reloads, the previous view stays visible, dimmed — no blank flashes. Rapid filter clicks are safe: an older, slower response can never overwrite a newer one.")}</dd>
				</dl>
				<div class="verify"><div class="vt">${__("How to verify")}</div><ol>
					<li>${__("Select a single depot. Every card should shrink to that depot: the FG card should now equal Stock Balance for that depot's FG warehouse, and the receivables donut should equal Accounts Receivable filtered by that Cost Center.")}</li>
					<li>${__("Switch Units to Lt-Kg. The FG bar values should match the Balance Qty column of the same Stock Balance report (value and quantity views come from the same rows).")}</li>
					<li>${__("Select a single warehouse. The FG card should equal Stock Balance for exactly that warehouse, and the receivables card should stay unchanged with a 'warehouse filter not applicable' note.")}</li>
					<li>${__("Clear the filters — totals should return to the all-depot figures exactly; nothing is lost or double counted.")}</li>
				</ol></div>
			</div>

			<div class="card-doc">
				<h3>${__("Access control")}</h3>
				<dl>
					<dt>${__("Who sees it")}</dt><dd>${__("Only users with the Leadership Dashboard role (and System Managers). Everyone else neither sees the page nor can call its data.")}</dd>
					<dt>${__("Depot scoping")}</dt><dd>${__("A user given User Permissions on specific Cost Centers sees only those depots — in every card, chart and drill-down. This is enforced on the server, not in the browser, so it cannot be bypassed.")}</dd>
					<dt>${__("Central bucket")}</dt><dd>${__("The Central / Unmapped receivable bucket appears only for unrestricted users viewing all depots.")}</dd>
					<dt>${__("Customer lists")}</dt><dd>${__("The customer drill-down can be limited to System Managers via a checkbox in Settings, if receivable details are considered sensitive.")}</dd>
				</dl>
				<div class="verify"><div class="vt">${__("How to verify")}</div><ol>
					<li>${__("Give a test user the Leadership Dashboard role only — logging in as them, the dashboard shows all depots (no User Permission = unrestricted).")}</li>
					<li>${__("Add a User Permission for that user: Allow = Cost Center, Value = one depot. Reload as them — the depot filter now offers only that depot, every card shows only its numbers, and the Central/Unmapped receivable bucket disappears.")}</li>
					<li>${__("Remove the role from a user — the page vanishes from their workspace and opening the URL directly is denied.")}</li>
					<li>${__("Tick 'Restrict Customer Drill-down' in Settings — the test user's tap on a depot receivable bar is refused, while a System Manager still gets the customer list.")}</li>
				</ol></div>
			</div>

			<div class="card-doc">
				<h3>${__("Data refresh model")}</h3>
				<table>
					<thead><tr><th>${__("Data")}</th><th>${__("How fresh")}</th><th>${__("A new transaction shows up in…")}</th></tr></thead>
					<tbody>
						<tr><td>${__("FG stock, RM stock (cards + charts)")}</td><td>${__("Near-live")}</td><td>${__("At most 10 minutes after a stock entry is submitted.")}</td></tr>
						<tr><td>${__("Expiry, stock ageing")}</td><td>${__("Hourly")}</td><td>${__("On the next hourly computation — within the hour of a batch movement.")}</td></tr>
						<tr><td>${__("Receivables (all views)")}</td><td>${__("Hourly")}</td><td>${__("On the next hourly computation — within the hour of a payment or invoice.")}</td></tr>
					</tbody>
				</table>
				<p>${__("The dashboard footer shows when the hourly figures were last computed, so it is always visible how current the heavy numbers are. Opening or refreshing the page is instant in all cases — the hourly work happens in the background, never while someone waits.")}</p>
				<div class="note">${__("The 'Computing…' state: the first time the system runs (or right after a system update / maintenance restart), the ageing, expiry and receivables cards show 'Computing…' while their figures are prepared — batch ageing takes around 5 minutes and receivables around 10–15 minutes on this data size. The cards fill in on their own; no one needs to do anything. During normal daily use this state does not appear, because the hourly cycle keeps the figures ready in advance.")}</div>
				<div class="verify"><div class="vt">${__("How to verify")}</div><ol>
					<li>${__("Submit any stock transaction (e.g. a Material Transfer into a depot FG warehouse) — the FG card and chart reflect it within 10 minutes.")}</li>
					<li>${__("Note the footer's 'Ageing computed' stamp — it should never be older than about an hour while the system is running.")}</li>
					<li>${__("Book and submit a payment entry against a customer — the receivables figures update on the next hourly computation (they follow the books, so expect the change within the hour, not instantly).")}</li>
				</ol></div>
			</div>

			<div class="card-doc">
				<h3>${__("Settings (System Manager only)")}</h3>
				<dl>
					<dt>${__("Thresholds")}</dt><dd>${__("Red / Orange limits (₹ lakh) per FG depot, FG SKU and RM material type — a blank Key row is the default rule. Every Green/Orange/Red on the dashboard comes from this table; tuning needs no development.")}</dd>
					<dt>${__("Material types")}</dt><dd>${__("Which item groups roll up into Technical / Primary / Bulk on the RM chart.")}</dd>
					<dt>${__("Other")}</dt><dd>${__("Top-N bars per chart, ageing basis (Due Date / Posting Date), cache duration, customer drill-down restriction.")}</dd>
				</dl>
				<div class="verify"><div class="vt">${__("How to verify")}</div><ol>
					<li>${__("Open Leadership Dashboard Settings and raise the Orange limit for one FG depot above its current stock value.")}</li>
					<li>${__("Save and reload the dashboard — that depot's bar turns Orange immediately (saving Settings clears the cache) and the legend counts update.")}</li>
					<li>${__("Restore the limit; the bar returns to Green. No code or restart was involved — that is the whole point of the thresholds table.")}</li>
				</ol></div>
			</div>
		</div>
	</div>
	`);

	const $tabs = $(page.body).find(".ldx-tabs button");
	const $panels = $(page.body).find(".ldx-panel");
	$tabs.on("click", function () {
		$tabs.attr("aria-selected", "false");
		$(this).attr("aria-selected", "true");
		$panels.removeClass("active");
		$panels.filter(`[data-panel='${$(this).data("tab")}']`).addClass("active");
	});
};
