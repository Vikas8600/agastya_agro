frappe.pages['pr-redo-required'].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('Payment Reconciliation Redo Required'),
		single_column: true,
	});

	page.set_primary_action(__('Open the Report'), () => {
		frappe.set_route('query-report', 'Payment Reconciliation Redo Required');
	});

	page.add_menu_item(__('Desired Payment Reconciliation'), () => {
		frappe.set_route('query-report', 'Desired Payment Reconciliation');
	});
	page.add_menu_item(__('Auto Payment Reconciliation settings'), () => {
		frappe.set_route('Form', 'Auto Payment Reconciliation');
	});

	// Appended as plain HTML rather than through render_template -- the content is
	// static, and running CSS full of braces through the template engine only
	// invites trouble.
	$(TEMPLATE).appendTo(page.main);

	// Colours come from the desk's CSS variables, so the page follows whatever
	// theme the user is on instead of fighting it in dark mode.
	$(wrapper).find('.prx-toc a').on('click', function (e) {
		e.preventDefault();
		const target = document.querySelector($(this).attr('href'));
		if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
	});
};

const TEMPLATE = `
<style>
	.prx { max-width: 940px; padding-bottom: 60px; }
	.prx h2 {
		font-size: 20px; font-weight: 600; margin: 34px 0 10px;
		padding-top: 20px; border-top: 1px solid var(--border-color);
	}
	.prx h2:first-of-type { border-top: 0; padding-top: 0; margin-top: 8px; }
	.prx h3 { font-size: 15px; font-weight: 600; margin: 20px 0 8px; }
	.prx p { color: var(--text-color); line-height: 1.65; margin-bottom: 12px; }
	.prx .muted { color: var(--text-muted); }

	.prx-lede {
		background: var(--bg-light-gray); border: 1px solid var(--border-color);
		border-left: 3px solid var(--red-500);
		border-radius: var(--border-radius-md); padding: 16px 18px; margin-bottom: 22px;
	}
	.prx-lede p { margin: 0; font-size: 15px; }

	.prx-toc { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 26px; }
	.prx-toc a {
		font-size: 12px; padding: 4px 10px; border-radius: 100px;
		border: 1px solid var(--border-color); color: var(--text-muted);
		text-decoration: none; background: var(--card-bg);
	}
	.prx-toc a:hover { color: var(--text-color); border-color: var(--gray-400); }

	.prx-flow { display: flex; flex-wrap: wrap; align-items: stretch; gap: 10px; margin: 18px 0 6px; }
	.prx-step {
		flex: 1 1 190px; background: var(--card-bg); border: 1px solid var(--border-color);
		border-radius: var(--border-radius-md); padding: 13px 15px;
	}
	.prx-step .n {
		font-size: 11px; font-weight: 600; color: var(--text-muted);
		letter-spacing: .06em; text-transform: uppercase;
	}
	.prx-step .t { font-weight: 600; margin: 3px 0 4px; }
	.prx-step .d { font-size: 12.5px; color: var(--text-muted); line-height: 1.5; }

	.prx table { width: 100%; border-collapse: collapse; margin: 12px 0 6px; font-size: 13px; }
	.prx th {
		text-align: left; font-weight: 600; font-size: 11px; text-transform: uppercase;
		letter-spacing: .04em; color: var(--text-muted);
		padding: 8px 10px; border-bottom: 1px solid var(--border-color); white-space: nowrap;
	}
	.prx td {
		padding: 9px 10px; border-bottom: 1px solid var(--border-color);
		vertical-align: top; color: var(--text-color);
	}
	.prx tr:last-child td { border-bottom: 0; }
	.prx td code, .prx p code {
		background: var(--bg-light-gray); padding: 1px 5px;
		border-radius: 4px; font-size: 12px;
	}
	.prx-scroll { overflow-x: auto; }

	.prx-pill {
		display: inline-block; font-size: 11px; font-weight: 500;
		padding: 2px 8px; border-radius: 100px; white-space: nowrap;
	}
	.p-red   { background: var(--red-100);    color: var(--red-600); }
	.p-blue  { background: var(--blue-100);   color: var(--blue-600); }
	.p-amber { background: var(--orange-100); color: var(--orange-600); }
	.p-grey  { background: var(--gray-200);   color: var(--gray-700); }

	.prx-note {
		border: 1px solid var(--border-color); border-left: 3px solid var(--blue-500);
		background: var(--bg-light-gray); border-radius: var(--border-radius-md);
		padding: 13px 16px; margin: 16px 0; font-size: 13.5px;
	}
	.prx-note.warn { border-left-color: var(--orange-500); }
	.prx-note.good { border-left-color: var(--green-500); }
	.prx-note p:last-child { margin-bottom: 0; }
	.prx-note .h { font-weight: 600; margin-bottom: 4px; }

	.prx-eg {
		background: var(--card-bg); border: 1px solid var(--border-color);
		border-radius: var(--border-radius-md); padding: 16px 18px; margin: 14px 0;
	}
	.prx-eg .ledger {
		font-family: var(--font-stack-monospace, monospace);
		font-size: 12.5px; line-height: 1.75; white-space: pre; overflow-x: auto;
		color: var(--text-color);
	}
	.prx-key { font-weight: 600; }
</style>

<div class="prx">

	<div class="prx-lede">
		<p><b>What this report answers:</b> which customers need a Payment Reconciliation Redo,
		and why &mdash; instead of somebody guessing a customer name and checking by hand.</p>
	</div>

	<div class="prx-toc">
		<a href="#prx-why">The problem</a>
		<a href="#prx-how">How it works</a>
		<a href="#prx-eg">Worked example</a>
		<a href="#prx-types">Mismatch types</a>
		<a href="#prx-summary">Summary columns</a>
		<a href="#prx-detail">Detail columns</a>
		<a href="#prx-filters">Filters</a>
		<a href="#prx-actions">Buttons</a>
		<a href="#prx-faq">Common questions</a>
	</div>

	<h2 id="prx-why">The problem</h2>
	<p>ERPNext matches a payment to an invoice at the moment somebody reconciles it. If an invoice
	is entered <i>later</i> but dated <i>earlier</i> &mdash; a back-dated entry &mdash; the payment
	that should have cleared it has already gone somewhere else.</p>
	<p>The customer's <b>total dues stay correct</b>. What breaks is <b>which invoice</b> holds the
	money &mdash; and that is what every ageing and outstanding report reads from. Nothing in
	ERPNext looks back at allocations it has already made, so nobody notices.</p>
	<p class="muted">The only cure is a Payment Reconciliation Redo, and that needs a customer name
	and a date range. With thousands of customers, nobody knows which to name. This report is that
	missing list.</p>

	<h2 id="prx-how">How it works</h2>
	<div class="prx-flow">
		<div class="prx-step">
			<div class="n">Step 1</div>
			<div class="t">Desired</div>
			<div class="d">What the allocation <i>should</i> be under strict FIFO &mdash; oldest
			invoice cleared first.</div>
		</div>
		<div class="prx-step">
			<div class="n">Step 2</div>
			<div class="t">Actual</div>
			<div class="d">What the payment ledger actually holds today &mdash; the same ledger
			ERPNext's own reconciliation reads.</div>
		</div>
		<div class="prx-step">
			<div class="n">Step 3</div>
			<div class="t">Difference</div>
			<div class="d">Every disagreement is written down as a mismatch row, grouped by
			customer.</div>
		</div>
		<div class="prx-step">
			<div class="n">Step 4</div>
			<div class="t">You decide</div>
			<div class="d">Create Redo prepares a <b>draft</b> correction. Nothing changes until a
			person submits it.</div>
		</div>
	</div>
	<div class="prx-note good">
		<div class="h">No new accounting rules were invented</div>
		<p>"Desired" is the same strict-FIFO logic the <b>Desired Payment Reconciliation</b> report
		already uses. This report simply compares it against reality and reports the gap.</p>
	</div>
	<div class="prx-note warn">
		<div class="h">It reads and reports. It never fixes anything on its own.</div>
		<p>The scan writes rows. It does not unreconcile a single entry. Even pressing
		<b>Create Redo</b> only produces a <b>draft</b> &mdash; the ledger is untouched until
		somebody opens that draft and submits it.</p>
	</div>

	<h2 id="prx-eg">Worked example</h2>
	<p>A real customer, four ledger entries, so the arithmetic can be checked by hand.</p>
	<div class="prx-eg">
		<div class="ledger">01-Apr-2022   Receivable          + 23,822     &lt;- still open
06-Jan-2024   Receivable          + 39,595
06-Jan-2024   Payment             - 39,595     -&gt; all of it went here
31-Mar-2026   Credit              - 23,822     &lt;- applied to nothing</div>
	</div>
	<p>The ₹39,595 payment cleared a bill raised <b>the same morning</b>, while ₹23,822 from
	<b>2022</b> sat untouched. Oldest-first, it should have gone:</p>
	<div class="prx-eg">
		<div class="ledger">₹39,595 payment
   ├─ ₹23,822  →  clears the April-2022 receivable
   └─ ₹15,773  →  part-pays the Jan-2024 receivable

₹23,822 credit (Mar-2026)
   └─ ₹23,822  →  clears the rest of the Jan-2024 receivable

Everything clears. The customer owes nothing.</div>
	</div>
	<div class="prx-note">
		<div class="h">What the ageing report was saying</div>
		<p>₹23,822 outstanding since April 2022 &mdash; a <b>four-year-old debt</b> &mdash; while a
		credit for the exact same amount sat unapplied a few rows away. The debt was never real.
		That is the <span class="prx-key">Ageing Shift</span> column doing its job.</p>
	</div>

	<h2 id="prx-types">The four mismatch types</h2>
	<div class="prx-scroll"><table>
		<thead><tr><th>Type</th><th>What it means</th><th>Usual cause</th></tr></thead>
		<tbody>
			<tr>
				<td><span class="prx-pill p-red">Wrong Pairing</span></td>
				<td>Money is sitting on an invoice FIFO says it should not be on.</td>
				<td>A back-dated invoice arrived after the reconciliation was done.</td>
			</tr>
			<tr>
				<td><span class="prx-pill p-blue">Missing Allocation</span></td>
				<td>A payment should be on this invoice but is not.</td>
				<td>The other half of a Wrong Pairing.</td>
			</tr>
			<tr>
				<td><span class="prx-pill p-amber">Amount Mismatch</span></td>
				<td>Right invoice, wrong split.</td>
				<td>A partial allocation drifted.</td>
			</tr>
			<tr>
				<td><span class="prx-pill p-grey">Unallocated Payment</span></td>
				<td>A receipt or credit is lying unapplied while invoices are open.</td>
				<td>Never reconciled at all.</td>
			</tr>
		</tbody>
	</table></div>
	<div class="prx-note">
		<p><b>Wrong Pairing and Missing Allocation usually appear in pairs.</b> They are the two ends
		of one movement of money &mdash; it comes off one invoice and goes onto another. The report
		knows this and never counts the amount twice.</p>
	</div>

	<h2 id="prx-summary">Summary view &mdash; one row per customer</h2>
	<p>This is the view to work from. It is sorted by <b>Ageing Shift</b>, worst first.</p>
	<div class="prx-scroll"><table>
		<thead><tr><th>Column</th><th>What it tells you</th></tr></thead>
		<tbody>
			<tr><td class="prx-key">Customer / Customer Name</td><td>Who it is.</td></tr>
			<tr><td class="prx-key">Mismatched Pairs</td><td>How many allocations differ. <span class="muted">Do not read this as a count of problems &mdash; one back-dated invoice shifts every allocation after it, so a single cause can show as dozens of rows.</span></td></tr>
			<tr><td class="prx-key">Impacted Amount</td><td>Rupees that need to move. Only the positive side is summed, so a movement is not double counted.</td></tr>
			<tr><td class="prx-key">Wrong Pairing / Missing Allocation / Amount Mismatch / Unallocated Payment</td><td>Breakdown of the pairs by type.</td></tr>
			<tr><td class="prx-key">Oldest Affected</td><td>How far back the problem reaches.</td></tr>
			<tr><td class="prx-key">Max Backdated (Days)</td><td>The worst gap between an invoice's date and the day it was actually entered. Usually the root cause.</td></tr>
			<tr><td class="prx-key">Money Sitting On</td><td>Date of the invoice currently holding the money.</td></tr>
			<tr><td class="prx-key">Should Sit On</td><td>Date of the invoice that should hold it.</td></tr>
			<tr><td class="prx-key" style="color:var(--red-600)">Ageing Shift (Days)</td><td><b>The number that matters.</b> How far the customer's ageing is wrong. Shown in red past 30 days. The list is ranked by this.</td></tr>
			<tr><td class="prx-key">Suggested Redo Runs</td><td>How many Redo documents this customer needs &mdash; long histories are split into windows that fit the size limit.</td></tr>
			<tr><td class="prx-key">Last Redo / Redo Status</td><td>Whether a correction has already been raised, and where it got to.</td></tr>
			<tr><td class="prx-key">Action</td><td><b>Create Redo</b> &mdash; opens a prefilled draft.</td></tr>
		</tbody>
	</table></div>
	<div class="prx-note warn">
		<div class="h">Why it is ranked by Ageing Shift and not by rupees</div>
		<p>Under FIFO a customer's total dues never change &mdash; money only moves between invoices.
		So the only thing that genuinely breaks is the <b>ageing</b>. A customer can have hundreds of
		mismatched pairs worth lakhs and still age perfectly correctly; sorting by amount would put
		that customer on top and bury the ones whose reports are actually lying.</p>
	</div>

	<h2 id="prx-detail">Detail view &mdash; one row per allocation</h2>
	<p>Use this to investigate <b>one</b> customer, not to read a whole company.</p>
	<div class="prx-scroll"><table>
		<thead><tr><th>Column</th><th>What it tells you</th></tr></thead>
		<tbody>
			<tr><td class="prx-key">Mismatch Type</td><td>One of the four above, colour coded.</td></tr>
			<tr><td class="prx-key">Invoice / Invoice Date / Invoice Amount</td><td>The receivable in question. Clickable.</td></tr>
			<tr><td class="prx-key">Backdated By (Days)</td><td>Gap between the invoice's posting date and the day it was actually entered. This is <i>why</i> the allocation drifted. Read from the document itself, so a later repost does not distort it.</td></tr>
			<tr><td class="prx-key">Payment / Payment Date / Payment Amount</td><td>The payment, credit note or journal entry. Clickable.</td></tr>
			<tr><td class="prx-key">Actual Allocated</td><td>What the ledger holds today.</td></tr>
			<tr><td class="prx-key">Desired Allocated</td><td>What FIFO says it should be.</td></tr>
			<tr><td class="prx-key">Difference</td><td>Desired minus actual. The two halves of one movement cancel out.</td></tr>
			<tr><td class="prx-key">Suggested From / To</td><td>The date window for the Redo, pre-sized to fit the limit.</td></tr>
			<tr><td class="prx-key">Redo / Status</td><td>Link to the correction, and whether the row is Open, Redo Created, Resolved or Ignored.</td></tr>
		</tbody>
	</table></div>
	<p class="muted">Detail is capped at 2,000 rows. If you hit the cap the report says so &mdash;
	filter by customer to see a complete list.</p>

	<h2 id="prx-filters">Filters</h2>
	<div class="prx-scroll"><table>
		<thead><tr><th>Filter</th><th>Use it to</th></tr></thead>
		<tbody>
			<tr><td class="prx-key">View</td><td>Switch between Summary (per customer) and Detail (per allocation).</td></tr>
			<tr><td class="prx-key">Customer / Customer Group</td><td>Narrow to one account or one segment.</td></tr>
			<tr><td class="prx-key">Mismatch Type</td><td>e.g. only <span class="prx-pill p-red">Wrong Pairing</span> to see money in the wrong place.</td></tr>
			<tr><td class="prx-key">Upto Date</td><td>Ignore anything after a date.</td></tr>
			<tr><td class="prx-key">Min Impact Amount</td><td>Drop rounding noise.</td></tr>
			<tr><td class="prx-key">Backdated Beyond (Days)</td><td>Isolate entries booked long after their posting date &mdash; the back-dating problem itself.</td></tr>
			<tr><td class="prx-key">Redo Status</td><td><i>Pending</i> = not yet actioned, <i>Redo Created</i> = in progress, <i>All</i> = includes fixed ones.</td></tr>
			<tr><td class="prx-key">Show Ignored</td><td>Bring back rows somebody deliberately silenced.</td></tr>
		</tbody>
	</table></div>

	<h2 id="prx-actions">Buttons</h2>
	<div class="prx-scroll"><table>
		<thead><tr><th>Button</th><th>What happens</th></tr></thead>
		<tbody>
			<tr><td class="prx-key">Create Redo</td><td>Opens a <b>draft</b> Payment Reconciliation Redo with the customer, the date window and the receivable account that customer's balances actually sit in. Nothing is applied until you submit it.</td></tr>
			<tr><td class="prx-key">Create Redo for Selected</td><td>Same, in bulk. Shows exactly what it will create before doing it.</td></tr>
			<tr><td class="prx-key">Refresh Scan</td><td><i>Changed customers only</i> &mdash; usually minutes. <i>Rebuild everything</i> &mdash; re-checks every customer, expect an hour or more.</td></tr>
			<tr><td class="prx-key">Desired Reconciliation</td><td>Opens the full FIFO working, so you can see how the answer was reached.</td></tr>
		</tbody>
	</table></div>
	<div class="prx-note">
		<div class="h">Silencing a false alarm</div>
		<p>If an allocation was deliberate and FIFO is simply not what the business wants there, open
		the mismatch row and set <b>Status = Ignored</b> with a reason. It is never raised again,
		even after a re-scan &mdash; which is what lets the list shrink toward zero instead of
		crying wolf forever.</p>
	</div>

	<h2 id="prx-faq">Common questions</h2>
	<h3>Will this change my outstanding figures?</h3>
	<p>Per customer the net position does not change &mdash; money moves between invoices, it is not
	created or destroyed. What changes is which invoice holds it, and therefore the ageing.</p>
	<h3>Will it change my accounts or GL?</h3>
	<p>No new accounting entries. Existing payments are re-linked to different invoices. The trial
	balance does not move.</p>
	<h3>What about credit notes?</h3>
	<p>Counted. The scan reads the same payment ledger ERPNext's own reconciliation uses, so credit
	notes, refunds and journal adjustments all count as settlement.</p>
	<h3>Are these figures live?</h3>
	<p>No. They are as of the last scan &mdash; the banner at the top of the report always says
	when that was. Entries posted since then are not included.</p>
	<h3>How many customers will be flagged?</h3>
	<p>A majority show some difference from strict oldest-first matching, but most are cosmetic.
	That is exactly why the list is ranked by Ageing Shift &mdash; it separates the ones that
	actually distort your reports from the ones that merely look different.</p>
	<h3>Can it run on its own?</h3>
	<p>It already finds problems on its own, nightly. Applying the corrections is still a person
	clicking submit &mdash; deliberately, until you are satisfied the suggestions are right.</p>

</div>
`;
