# Copyright (c) 2026, Dexciss and contributors
# For license information, please see license.txt

"""Read-only data APIs for the Leadership Dashboard desk page.

Access model:
- Every endpoint requires the "Leadership Dashboard" (or System Manager) role.
- The caller's depot scope comes from User Permission rows on Cost Center;
  a requested depot list is always intersected with that scope server-side,
  so client input can narrow but never widen what is visible.

Data model:
- Depot = leaf Cost Center carrying finished_good_warehouse /
  raw_material_warehouse links (the same mapping the Internal GRN flow uses).
- FG / RM classification is by Item Group trees configured in
  Leadership Dashboard Settings.
- Live stock blocks read tabBin (fast). Batch ageing/expiry is precomputed by
  an hourly background job reusing the BWBH Expiry Status report, because that
  scan is too heavy for a request cycle.
- Debtors are computed from submitted Sales Invoice outstanding grouped by the
  invoice's Cost Center ("Depot Name", a mandatory field). This keeps every
  number depot-filterable and permission-consistent; on-account advances and
  journal balances are out of scope for the dashboard and remain visible in
  the full Accounts Receivable report linked from the drill-down.
"""

import hashlib
import json

import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, flt, getdate, nowdate

DASHBOARD_ROLES = ("Leadership Dashboard", "System Manager")
CACHE_PREFIX = "leadership_dashboard"
AGEING_CACHE_KEY = f"{CACHE_PREFIX}:ageing_v2"
AGEING_JOB_ID = "leadership_dashboard_ageing"
DEBTORS_CACHE_KEY = f"{CACHE_PREFIX}:debtors_book"
DEBTORS_JOB_ID = "leadership_dashboard_debtors"
UNMAPPED_DEPOT = "__unmapped__"
AGEING_BUCKETS = ("0-30", "31-60", "61-90", "91-120", "120+")
DEBT_BUCKETS = ("0-30", "31-60", "61-90", "90+")
NEAR_EXPIRY_DAYS = 120
DRILLDOWN_CAP = 100
LAKH = 100000
PRECOMPUTE_TTL = 7200


# ---------------------------------------------------------------- access

def _settings():
	settings = frappe.get_cached_doc("Leadership Dashboard Settings")
	if not settings.company or not settings.fg_item_group:
		frappe.throw(
			_("Leadership Dashboard Settings is not configured. Please set Company and FG Item Group."),
			title=_("Setup Incomplete"),
		)
	return settings


def _all_depots():
	"""Leaf cost centers of the configured company that map to a warehouse."""
	return frappe.get_all(
		"Cost Center",
		filters={"company": _settings().company, "is_group": 0, "disabled": 0},
		fields=["name", "cost_center_name", "finished_good_warehouse", "raw_material_warehouse"],
		order_by="cost_center_name",
	)


def _check_access(depots=None):
	"""Validate the caller's role and return the permitted depot rows.

	`depots` (JSON list of Cost Center names or None) is intersected with the
	caller's User Permission scope. Returns a list of Cost Center rows.
	"""
	frappe.only_for(DASHBOARD_ROLES)

	permitted = _all_depots()
	user_scope = frappe.get_all(
		"User Permission",
		filters={"user": frappe.session.user, "allow": "Cost Center"},
		pluck="for_value",
	)
	if user_scope:
		permitted = [d for d in permitted if d.name in set(user_scope)]

	requested = frappe.parse_json(depots) if depots else None
	if requested:
		requested = set(requested)
		permitted = [d for d in permitted if d.name in requested]

	if not permitted:
		frappe.throw(_("You do not have access to any depot"), frappe.PermissionError)
	return permitted


# ---------------------------------------------------------------- caching

def _cached(key_parts, generator):
	digest = hashlib.sha1(json.dumps(key_parts, sort_keys=True).encode()).hexdigest()[:16]
	key = f"{CACHE_PREFIX}:{key_parts[0]}:{digest}"
	# expires=True keeps frappe from memoizing a miss (None) in frappe.local,
	# which would otherwise shadow the freshly written value for the rest of
	# the request and force every caller in it to rebuild
	value = frappe.cache().get_value(key, expires=True)
	if value is None:
		value = generator()
		ttl = cint(_settings().cache_ttl_secs) or 600
		frappe.cache().set_value(key, value, expires_in_sec=ttl)
	return value


# ---------------------------------------------------------------- helpers

def _descendant_item_groups(parent):
	lft, rgt = frappe.db.get_value("Item Group", parent, ["lft", "rgt"])
	return frappe.get_all(
		"Item Group", filters={"lft": [">=", lft], "rgt": ["<=", rgt]}, pluck="name"
	)


def _threshold_rules():
	rules = {}
	for row in _settings().thresholds:
		rules[(row.applies_to, (row.key or "").strip().lower())] = (
			flt(row.red_below), flt(row.orange_below)
		)
	return rules


def _status(applies_to, key, value_lakh, rules):
	"""Green/Orange/Red for a value (in ₹ lakh) against the threshold table."""
	rule = rules.get((applies_to, key.strip().lower())) or rules.get((applies_to, ""))
	if not rule:
		return "good"
	red_below, orange_below = rule
	if value_lakh < red_below:
		return "crit"
	if value_lakh < orange_below:
		return "warn"
	return "good"


def _bin_stock(warehouses, item_groups):
	"""Live qty/value per warehouse+item from tabBin."""
	if not warehouses or not item_groups:
		return []
	return frappe.db.sql(
		"""
		SELECT b.warehouse, b.item_code, i.item_name, i.item_group,
			SUM(b.actual_qty) AS qty, SUM(b.stock_value) AS value
		FROM `tabBin` b
		INNER JOIN `tabItem` i ON i.name = b.item_code
		WHERE b.actual_qty > 0
			AND b.warehouse IN %(warehouses)s
			AND i.item_group IN %(item_groups)s
		GROUP BY b.warehouse, b.item_code
		""",
		{"warehouses": warehouses, "item_groups": item_groups},
		as_dict=True,
	)


def _fg_warehouse_map(depots):
	"""{fg_warehouse: depot row} for depots that have one."""
	return {d.finished_good_warehouse: d for d in depots if d.finished_good_warehouse}


def _check_warehouses(scope, warehouses=None):
	"""Validate a requested warehouse list against the caller's depot scope.

	Returns a set of warehouse names to narrow stock queries with, or None
	when no (valid) warehouse filter is active. Like depots, client input can
	only narrow the permitted set, never widen it.
	"""
	requested = frappe.parse_json(warehouses) if warehouses else None
	if not requested:
		return None
	allowed = set()
	for d in scope:
		if d.finished_good_warehouse:
			allowed.add(d.finished_good_warehouse)
		if d.raw_material_warehouse:
			allowed.add(d.raw_material_warehouse)
	selected = allowed & set(requested)
	return selected or None


# ---------------------------------------------------------------- endpoints

@frappe.whitelist()
def get_context_data():
	"""Bootstrap data for the page: permitted depots, warehouses and settings."""
	depots = _check_access()
	settings = _settings()
	warehouses = set()
	for d in depots:
		if d.finished_good_warehouse:
			warehouses.add(d.finished_good_warehouse)
		if d.raw_material_warehouse:
			warehouses.add(d.raw_material_warehouse)
	return {
		"company": settings.company,
		"top_n": cint(settings.top_n) or 15,
		"ageing_basis": settings.ageing_basis or "Due Date",
		"depots": [
			{"name": d.name, "label": d.cost_center_name} for d in depots
		],
		"warehouses": sorted(warehouses),
	}


@frappe.whitelist()
def get_fg_stock(view="depot", depots=None, limit=None, warehouses=None):
	scope = _check_access(depots)
	limit = cint(limit) or cint(_settings().top_n) or 15
	wh_map = _fg_warehouse_map(scope)
	selected_wh = _check_warehouses(scope, warehouses)
	if selected_wh:
		wh_map = {wh: d for wh, d in wh_map.items() if wh in selected_wh}
	item_groups = _descendant_item_groups(_settings().fg_item_group)

	def build():
		rows = _bin_stock(list(wh_map), item_groups)
		rules = _threshold_rules()
		if view == "depot":
			agg = {}
			for r in rows:
				depot = wh_map[r.warehouse]
				entry = agg.setdefault(
					depot.name, {"label": depot.cost_center_name, "qty": 0, "value": 0}
				)
				entry["qty"] += flt(r.qty)
				entry["value"] += flt(r.value)
			applies_to = "FG Depot"
		else:
			agg = {}
			for r in rows:
				entry = agg.setdefault(
					r.item_code, {"label": r.item_name or r.item_code, "qty": 0, "value": 0}
				)
				entry["qty"] += flt(r.qty)
				entry["value"] += flt(r.value)
			applies_to = "FG SKU"

		bars = sorted(agg.values(), key=lambda x: x["value"], reverse=True)
		shown, rest = bars[:limit], bars[limit:]
		if rest:
			shown.append({
				"label": _("Other ({0})").format(len(rest)),
				"qty": sum(b["qty"] for b in rest),
				"value": sum(b["value"] for b in rest),
				"status": "good",
			})
		for b in shown:
			b.setdefault("status", _status(applies_to, b["label"], b["value"] / LAKH, rules))
		return {"view": view, "bars": shown}

	return _cached(
		["fg", view, limit, sorted(d.name for d in scope), sorted(selected_wh or [])], build
	)


@frappe.whitelist()
def get_rm_stock(warehouses=None):
	scope = _check_access()
	settings = _settings()
	selected_wh = _check_warehouses(scope, warehouses)

	def build():
		group_to_type, all_groups = {}, set()
		for row in settings.material_types:
			for group in _descendant_item_groups(row.item_group):
				group_to_type[group] = row.material_type
				all_groups.add(group)

		query_warehouses = list(selected_wh) if selected_wh else frappe.get_all(
			"Warehouse",
			filters={"company": settings.company, "is_group": 0, "disabled": 0},
			pluck="name",
		)
		rules = _threshold_rules()
		agg = {}
		for r in _bin_stock(query_warehouses, list(all_groups)):
			mtype = group_to_type[r.item_group]
			entry = agg.setdefault(mtype, {"label": mtype, "qty": 0, "value": 0})
			entry["qty"] += flt(r.qty)
			entry["value"] += flt(r.value)
		bars = sorted(agg.values(), key=lambda x: x["value"], reverse=True)
		for b in bars:
			b["status"] = _status("RM Type", b["label"], b["value"] / LAKH, rules)
		return {"bars": bars}

	return _cached(["rm", sorted(selected_wh or [])], build)


@frappe.whitelist()
def get_ageing_expiry(depots=None, warehouses=None):
	scope = _check_access(depots)
	selected_wh = _check_warehouses(scope, warehouses)
	cache = frappe.cache().get_value(AGEING_CACHE_KEY, expires=True)
	if not cache:
		_enqueue_job(AGEING_JOB_ID, "compute_ageing_cache")
		return {"pending": True}

	# the cache is per FG warehouse; aggregate to depots for the chart,
	# honoring both the depot scope and any warehouse narrowing
	out = {
		"computed_on": cache["computed_on"],
		"depots": [],
		"expiry": {"expired": 0, "near": 0, "regular": 0},
	}
	for d in scope:
		wh = d.finished_good_warehouse
		if not wh or (selected_wh and wh not in selected_wh):
			continue
		entry = cache["warehouses"].get(wh)
		if not entry:
			continue
		out["depots"].append({
			"name": d.name,
			"label": d.cost_center_name,
			"ageing_value": entry["ageing_value"],
			"unknown_age_value": entry["unknown_age_value"],
		})
		for band in out["expiry"]:
			out["expiry"][band] += entry["expiry_value"][band]
	return out


@frappe.whitelist()
def get_debtors(depots=None):
	"""Receivables ageing and per-depot outstanding, as per the accounting
	books (ERPNext Accounts Receivable engine, precomputed by the hourly job).

	The book view is used instead of Sales Invoice.outstanding_amount because
	unreconciled payments and credit notes do not reduce invoice outstanding —
	on this site that difference runs into crores.
	"""
	scope = _check_access(depots)
	cache = frappe.cache().get_value(DEBTORS_CACHE_KEY, expires=True)
	if not cache:
		_enqueue_job(DEBTORS_JOB_ID, "compute_debtors_cache")
		return {"pending": True}

	scope_names = {d.name for d in scope}
	# the unmapped bucket (advances / journal balances without a Sales Invoice
	# cost center) belongs to no depot; show it only to an unrestricted,
	# unfiltered view so a depot-scoped user never sees other depots' money
	include_unmapped = scope_names == {d.name for d in _all_depots()}

	buckets = dict.fromkeys(DEBT_BUCKETS, 0)
	rows = []
	for name, entry in cache["depots"].items():
		if name == UNMAPPED_DEPOT:
			if not include_unmapped:
				continue
		elif name not in scope_names:
			continue
		for band in DEBT_BUCKETS:
			buckets[band] += entry["buckets"][band]
		rows.append({
			"label": entry["label"],
			"outstanding": entry["outstanding"],
			"over_90": entry["buckets"]["90+"],
		})

	return {
		"computed_on": cache["computed_on"],
		"buckets": buckets,
		"total": sum(buckets.values()),
		"depots": sorted(rows, key=lambda x: x["outstanding"], reverse=True),
	}


@frappe.whitelist()
def get_summary(depots=None, warehouses=None):
	scope = _check_access(depots)
	depot_names = json.dumps([d.name for d in scope])

	fg = get_fg_stock(view="depot", depots=depot_names, warehouses=warehouses)
	fg_total = sum(b["value"] for b in fg["bars"])

	ageing = get_ageing_expiry(depots=depot_names, warehouses=warehouses)
	near_pct = near_value = expiry_total = None
	if not ageing.get("pending"):
		expiry_total = sum(ageing["expiry"].values())
		near_value = ageing["expiry"]["near"]
		if expiry_total:
			near_pct = round(near_value / expiry_total * 100)

	rm = get_rm_stock(warehouses=warehouses)
	rm_low = [b for b in rm["bars"] if b["status"] != "good"]

	debtors = get_debtors(depots=depot_names)
	pending = debtors.get("pending")

	return {
		"fg_value": fg_total,
		"near_expiry_pct": near_pct,
		"near_expiry_value": near_value,
		"expiry_total_value": expiry_total,
		"rm_below_threshold": len(rm_low),
		"rm_critical": len([b for b in rm_low if b["status"] == "crit"]),
		"outstanding": None if pending else debtors["total"],
		"overdue_90": None if pending else debtors["buckets"]["90+"],
	}


@frappe.whitelist()
def get_drilldown(block, key, depots=None):
	"""Row list for drill-down dialogs. Always capped at DRILLDOWN_CAP rows."""
	scope = _check_access(depots)

	if block == "fg_depot":
		depot = next((d for d in scope if d.name == key), None)
		if not depot:
			frappe.throw(_("You do not have access to this depot"), frappe.PermissionError)
		item_groups = _descendant_item_groups(_settings().fg_item_group)
		rows = _bin_stock([depot.finished_good_warehouse], item_groups)
		rows.sort(key=lambda r: flt(r.value), reverse=True)
		return {
			"columns": [_("SKU"), _("Qty"), _("Value")],
			"rows": [[r.item_name or r.item_code, flt(r.qty), flt(r.value)] for r in rows[:DRILLDOWN_CAP]],
		}

	if block == "debtors_depot":
		if _settings().restrict_customer_drilldown and "System Manager" not in frappe.get_roles():
			frappe.throw(_("Customer drill-down is restricted"), frappe.PermissionError)
		if key not in [d.name for d in scope]:
			frappe.throw(_("You do not have access to this depot"), frappe.PermissionError)
		cache = frappe.cache().get_value(DEBTORS_CACHE_KEY, expires=True) or {"depots": {}}
		entry = cache["depots"].get(key) or {"customers": []}
		return {
			"columns": [_("Customer"), _("Outstanding"), _("Oldest Due Date")],
			"rows": [
				[c["customer"], c["outstanding"], c["oldest_due"]]
				for c in entry["customers"][:DRILLDOWN_CAP]
			],
		}

	frappe.throw(_("Unknown drill-down block: {0}").format(block))


# ---------------------------------------------------------------- ageing job

def _enqueue_job(job_id, method):
	from frappe.utils.background_jobs import is_job_enqueued

	if not is_job_enqueued(job_id):
		frappe.enqueue(
			f"agastya_agro.api.leadership_dashboard.{method}",
			queue="long",
			timeout=3600,
			job_id=job_id,
		)


def compute_ageing_cache():
	"""Precompute batch ageing + expiry value per FG warehouse. Runs on hourly_long.

	Reuses the BWBH Expiry Status report (one full scan) and values quantities
	with the item+warehouse average valuation rate from tabBin. Rows without a
	manufacturing date are reported separately (unknown_age_value), never
	folded into an ageing bucket.
	"""
	from agastya_agro.agastya_agro.report.bwbh_expiry_status.bwbh_expiry_status import (
		execute as bwbh_execute,
	)

	wh_map = _fg_warehouse_map(_all_depots())
	# BWBH expects string dates and full history for correct opening balances
	rows = bwbh_execute({"from_date": "2000-01-01", "to_date": str(nowdate())})[1]

	valuation = {}
	for b in frappe.get_all(
		"Bin",
		filters={"warehouse": ["in", list(wh_map)], "actual_qty": [">", 0]},
		fields=["item_code", "warehouse", "actual_qty", "stock_value"],
	):
		if flt(b.actual_qty):
			valuation[(b.item_code, b.warehouse)] = flt(b.stock_value) / flt(b.actual_qty)

	today = getdate(nowdate())
	near_limit = getdate(add_days(today, NEAR_EXPIRY_DAYS))
	warehouses = {}
	for row in rows:
		qty = flt(row.get("balance_qty"))
		warehouse = row.get("warehouse")
		if qty <= 0 or warehouse not in wh_map:
			continue
		entry = warehouses.setdefault(warehouse, {
			"ageing_value": dict.fromkeys(AGEING_BUCKETS, 0),
			"unknown_age_value": 0,
			"expiry_value": {"expired": 0, "near": 0, "regular": 0},
		})
		value = qty * valuation.get((row.get("item_code"), warehouse), 0)

		lapsed = row.get("lapsed_life")
		if lapsed is None:
			entry["unknown_age_value"] += value
		elif lapsed <= 30:
			entry["ageing_value"]["0-30"] += value
		elif lapsed <= 60:
			entry["ageing_value"]["31-60"] += value
		elif lapsed <= 90:
			entry["ageing_value"]["61-90"] += value
		elif lapsed <= 120:
			entry["ageing_value"]["91-120"] += value
		else:
			entry["ageing_value"]["120+"] += value

		expiry_date = getdate(row.get("expiry_date")) if row.get("expiry_date") else None
		if expiry_date and expiry_date < today:
			entry["expiry_value"]["expired"] += value
		elif expiry_date and expiry_date <= near_limit:
			entry["expiry_value"]["near"] += value
		else:
			entry["expiry_value"]["regular"] += value

	frappe.cache().set_value(
		AGEING_CACHE_KEY,
		{"computed_on": frappe.utils.now(), "warehouses": warehouses},
		expires_in_sec=PRECOMPUTE_TTL,
	)


def compute_debtors_cache():
	"""Precompute receivables ageing per depot from the accounting books.
	Runs on hourly_long.

	Uses ERPNext's Accounts Receivable engine (Payment Ledger based), so
	unreconciled payments, credit notes and advances are reflected — unlike
	Sales Invoice.outstanding_amount. Too slow for a request cycle, hence the
	cache. Rows are attributed to a depot via the source invoice's cost
	center; book entries without one (advances, journals) land in an
	"unmapped" bucket shown only on the unrestricted all-depot view.
	"""
	from erpnext.accounts.report.accounts_receivable.accounts_receivable import (
		execute as ar_execute,
	)

	settings = frappe.get_cached_doc("Leadership Dashboard Settings")
	rows = ar_execute(frappe._dict({
		"company": settings.company,
		"report_date": nowdate(),
		"party_type": "Customer",
		"ageing_based_on": settings.ageing_basis or "Due Date",
		"range1": 30, "range2": 60, "range3": 90, "range4": 120,
	}))[1]

	depot_labels = {d.name: d.cost_center_name for d in frappe.get_all(
		"Cost Center", filters={"company": settings.company}, fields=["name", "cost_center_name"]
	)}

	# book rows for invoices carry the invoice's cost center; fill any gaps
	# from Sales Invoice directly, everything else is unmapped
	si_rows = [r for r in rows if r.get("voucher_type") == "Sales Invoice" and not r.get("cost_center")]
	si_depots = {}
	if si_rows:
		names = list({r.get("voucher_no") for r in si_rows})
		si_depots = dict(frappe.get_all(
			"Sales Invoice", filters={"name": ["in", names]},
			fields=["name", "cost_center"], as_list=True,
		))

	depots = {}
	for row in rows:
		outstanding = flt(row.get("outstanding"))
		if abs(outstanding) < 0.005:
			continue
		depot = row.get("cost_center") or si_depots.get(row.get("voucher_no")) or UNMAPPED_DEPOT
		if depot not in depot_labels and depot != UNMAPPED_DEPOT:
			depot = UNMAPPED_DEPOT
		entry = depots.setdefault(depot, {
			"label": depot_labels.get(depot, _("Central / Unmapped")),
			"buckets": dict.fromkeys(DEBT_BUCKETS, 0),
			"outstanding": 0,
			"_customers": {},
		})
		entry["outstanding"] += outstanding
		# AR ranges: range1 0-30, range2 31-60, range3 61-90, range4 91-120, range5 120+
		entry["buckets"]["0-30"] += flt(row.get("range1"))
		entry["buckets"]["31-60"] += flt(row.get("range2"))
		entry["buckets"]["61-90"] += flt(row.get("range3"))
		entry["buckets"]["90+"] += flt(row.get("range4")) + flt(row.get("range5"))

		# the AR engine leaves every range at zero when the ageing date (due
		# date) is missing — true for crores of legacy imported vouchers here.
		# Age that remainder by posting date so buckets always sum to the book
		# total instead of silently dropping those rows from the donut.
		unaged = outstanding - sum(flt(row.get(f"range{i}")) for i in range(1, 6))
		if abs(unaged) > 0.005:
			age_days = date_diff(nowdate(), row.get("posting_date") or nowdate())
			if age_days <= 30:
				entry["buckets"]["0-30"] += unaged
			elif age_days <= 60:
				entry["buckets"]["31-60"] += unaged
			elif age_days <= 90:
				entry["buckets"]["61-90"] += unaged
			else:
				entry["buckets"]["90+"] += unaged
		cust = entry["_customers"].setdefault(
			row.get("party"), {"customer": row.get("party"), "outstanding": 0, "oldest_due": ""}
		)
		cust["outstanding"] += outstanding
		due = str(row.get("due_date") or "")
		if due and (not cust["oldest_due"] or due < cust["oldest_due"]):
			cust["oldest_due"] = due

	for entry in depots.values():
		entry["customers"] = sorted(
			entry.pop("_customers").values(), key=lambda c: c["outstanding"], reverse=True
		)[:DRILLDOWN_CAP]

	frappe.cache().set_value(
		DEBTORS_CACHE_KEY,
		{"computed_on": frappe.utils.now(), "depots": depots},
		expires_in_sec=PRECOMPUTE_TTL,
	)
