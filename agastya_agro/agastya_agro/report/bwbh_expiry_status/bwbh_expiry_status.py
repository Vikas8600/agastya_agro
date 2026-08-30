# Copyright (c) 2025, Dexciss and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cint, flt, formatdate, getdate

AGEING_BUCKETS = [
	(0, 30, "0-30"),
	(31, 60, "31-60"),
	(61, 90, "61-90"),
	(91, 120, "91-120"),
	(121, 150, "121-150"),
	(151, 180, "151-180"),
	(181, 200, "181-200"),
	(201, 300, "201-300"),
	(301, 400, "301-400"),
	(401, 500, "401-500"),
	(501, 600, "501-600"),
	(601, 700, "601-700"),
	(701, 800, "701-800"),
	(801, 900, "801-900"),
	(901, 1000, "901-1000"),
	(1001, 1100, "1001-1100"),
]
AGEING_ORDER = [b[2] for b in AGEING_BUCKETS] + [">1100", "Expired", "No Expiry Date"]

NEAR_EXPIRY_DAYS = 120

LINK_FILTERS = (
	("company", "Company"),
	("item", "Item"),
	("batch_no", "Batch"),
	("warehouse", "Warehouse"),
	("brand", "Brand"),
	("transfer_price_list", "Price List"),
)


def get_ageing_bucket(days):
	if days is None:
		return "No Expiry Date"
	if days < 0:
		return "Expired"
	for lo, hi, label in AGEING_BUCKETS:
		if lo <= days <= hi:
			return label
	return ">1100"


def filter_by_ageing(rows, filters):
	# Two independent range filters, ANDed together. Either can be blank.
	lapsed_range = filters.get("lapsed_range")
	balance_range = filters.get("balance_range")
	if not lapsed_range and not balance_range:
		return rows

	out = []
	for r in rows:
		if lapsed_range and r.get("lapsed_ageing") != lapsed_range:
			continue
		if balance_range and r.get("balance_ageing") != balance_range:
			continue
		out.append(r)
	return out


def get_chart(rows, filters):
	# Overview: both ageing distributions side by side, over the full result set.
	lapsed_counts = {label: 0 for label in AGEING_ORDER}
	balance_counts = {label: 0 for label in AGEING_ORDER}
	for r in rows:
		if r.get("lapsed_ageing") in lapsed_counts:
			lapsed_counts[r["lapsed_ageing"]] += 1
		if r.get("balance_ageing") in balance_counts:
			balance_counts[r["balance_ageing"]] += 1

	labels = [label for label in AGEING_ORDER if lapsed_counts[label] or balance_counts[label]]

	chart_type = (filters.get("chart_type") or "Line").lower()

	return {
		"data": {
			"labels": labels,
			"datasets": [
				{"name": "Lapsed Days", "values": [lapsed_counts[label] for label in labels]},
				{"name": "Balance Days", "values": [balance_counts[label] for label in labels]},
			],
		},
		"type": chart_type,
		"height": 300,
		"lineOptions": {"hideDots": 0, "regionFill": 0},
	}


def get_report_summary(rows):
	total_lines = len(rows)
	item_count = len({r.get("item_code") for r in rows})
	total_qty = sum(flt(r.get("balance_qty")) for r in rows)
	total_value = sum(flt(r.get("transfer_value")) for r in rows)

	return [
		{"value": item_count, "label": "Items", "datatype": "Int"},
		{"value": total_lines, "label": "Batch Lines", "datatype": "Int"},
		{"value": total_qty, "label": "Balance Qty", "datatype": "Float"},
		{"value": total_value, "label": "Stock Transfer Value", "datatype": "Currency"},
	]


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)

	columns = get_columns(filters)
	all_rows = get_data(filters)
	data = filter_by_ageing(all_rows, filters)
	chart = get_chart(all_rows, filters)
	report_summary = get_report_summary(data)
	return columns, data, None, chart, report_summary


def validate_filters(filters):
	if not filters.get("from_date"):
		frappe.throw(_("'From Date' is required"))

	if not filters.get("to_date"):
		frappe.throw(_("'To Date' is required"))

	if getdate(filters.get("from_date")) > getdate(filters.get("to_date")):
		frappe.throw(
			_("From Date {0} is after To Date {1}. No stock movement falls in that range.").format(
				formatdate(filters.get("from_date")), formatdate(filters.get("to_date"))
			)
		)

	# Prepared Report and API callers bypass the Link field's own lookup, so the
	# references are checked here rather than assumed valid.
	for fieldname, doctype in LINK_FILTERS:
		value = filters.get(fieldname)
		if value and not frappe.db.exists(doctype, value):
			frappe.throw(_("{0} {1} does not exist.").format(_(doctype), frappe.bold(value)))


def get_columns(filters):
	return [
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 150},
		{"label": _("Brand"), "fieldname": "brand", "fieldtype": "Data", "width": 150},
		{"label": _("Class"), "fieldname": "class", "fieldtype": "Data", "width": 150},
		{"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 150},
		{"label": _("Manufacturing Date"), "fieldname": "mfg_date", "fieldtype": "Date", "width": 120},
		{"label": _("Expiry Date"), "fieldname": "expiry_date", "fieldtype": "Date", "width": 120},
		{"label": _("Batch No"), "fieldname": "batch_no", "fieldtype": "Link", "options": "Batch", "width": 120},
		{"label": _("Old Batch No"), "fieldname": "old_batch_no", "fieldtype": "Data", "width": 150},
		{"label": _("Opening Qty"), "fieldname": "opening_qty", "fieldtype": "Float", "width": 120},
		{"label": _("In Qty"), "fieldname": "in_qty", "fieldtype": "Float", "width": 120},
		{"label": _("Out Qty"), "fieldname": "out_qty", "fieldtype": "Float", "width": 120},
		{"label": _("Balance Qty"), "fieldname": "balance_qty", "fieldtype": "Float", "width": 120},
		# Requested beside Balance Qty: the transfer rate and what the balance is
		# worth at it.
		{"label": _("Stock Transfer Price"), "fieldname": "transfer_price", "fieldtype": "Currency", "width": 150},
		{"label": _("Value"), "fieldname": "transfer_value", "fieldtype": "Currency", "width": 150},
		{"label": _("UOM"), "fieldname": "uom", "fieldtype": "Data", "width": 120},
		{"label": _("Cases"), "fieldname": "cases", "fieldtype": "Float", "width": 120},
		{"label": _("Weight"), "fieldname": "weight", "fieldtype": "Float", "width": 120},
		{"label": _("Shelf Life"), "fieldname": "shelf_life", "fieldtype": "Int", "width": 120},
		{"label": _("Lapsed Life"), "fieldname": "lapsed_life", "fieldtype": "Int", "width": 120},
		{"label": _("Lapsed Days Ageing"), "fieldname": "lapsed_ageing", "fieldtype": "Data", "width": 130},
		{"label": _("Balance Life"), "fieldname": "balance_life", "fieldtype": "Int", "width": 120},
		{"label": _("Balance Days Ageing"), "fieldname": "balance_ageing", "fieldtype": "Data", "width": 140},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 170},
	]


def get_conditions(filters, alias, warehouse_column, batch_column):
	"""Shared WHERE clauses for both halves of the ledger.

	Values are bound, never interpolated: an item or warehouse whose name holds
	an apostrophe would otherwise break the query outright.
	"""
	conditions = [
		"{0}.docstatus < 2".format(alias),
		"{0}.is_cancelled = 0".format(alias),
		"{0}.posting_datetime <= %(to_datetime)s".format(alias),
	]
	values = {}

	if filters.get("company"):
		conditions.append("{0}.company = %(company)s".format(alias))
		values["company"] = filters.get("company")

	if filters.get("item"):
		conditions.append("{0}.item_code = %(item)s".format(alias))
		values["item"] = filters.get("item")

	if filters.get("warehouse"):
		conditions.append("{0} = %(warehouse)s".format(warehouse_column))
		values["warehouse"] = filters.get("warehouse")

	if filters.get("batch_no"):
		conditions.append("{0} = %(batch_no)s".format(batch_column))
		values["batch_no"] = filters.get("batch_no")

	if filters.get("brand"):
		conditions.append("item.brand = %(brand)s")
		values["brand"] = filters.get("brand")

	return conditions, values


def get_ledger_balances(filters):
	"""Opening, in and out per item / warehouse / batch, aggregated in the database.

	The opening balance is every movement before From Date, so the ledger has to
	be read from the beginning of time either way. What it does not have to do is
	hand a row per voucher back to Python — the split is done here, so the result
	is one row per batch rather than a million.

	Item is joined only when a brand filter is set. That join is what holds a
	metadata lock on the Item table, and holding it for the length of this scan
	is enough to block a schema change on the whole site.
	"""
	to_datetime = "{0} 23:59:59".format(getdate(filters.get("to_date")))

	# A voucher is netted before it is called a receipt or an issue, the way
	# Batch-Wise Balance History does it: a reconciliation that writes +110 and
	# -80 against one batch is a receipt of 30, not both at once.
	aggregate = """
		sum(case when v.posting_date < %(from_date)s then v.qty else 0 end) as opening_qty,
		sum(case when v.posting_date >= %(from_date)s and v.qty > 0 then v.qty else 0 end) as in_qty,
		sum(case when v.posting_date >= %(from_date)s and v.qty < 0 then -v.qty else 0 end) as out_qty
	"""

	base_values = {
		"from_date": getdate(filters.get("from_date")),
		"to_datetime": to_datetime,
	}

	balances = {}

	# Batches recorded straight on the ledger row.
	conditions, values = get_conditions(filters, "sle", "sle.warehouse", "sle.batch_no")
	conditions.append("ifnull(sle.batch_no, '') != ''")
	values.update(base_values)

	collect(
		balances,
		"""
		select v.item_code, v.warehouse, v.batch_no, {aggregate}
		from (
			select sle.item_code, sle.warehouse, sle.batch_no, sle.voucher_no,
				max(sle.posting_date) as posting_date, sum(sle.actual_qty) as qty
			from `tabStock Ledger Entry` sle
			{brand_join}
			where {conditions}
			group by sle.item_code, sle.warehouse, sle.batch_no, sle.voucher_no
		) v
		group by v.item_code, v.warehouse, v.batch_no
	""".format(
			aggregate=aggregate,
			brand_join=brand_join(filters),
			conditions=" and ".join(conditions),
		),
		values,
	)

	# Batches recorded through a Serial and Batch Bundle instead.
	conditions, values = get_conditions(
		filters, "sle", "batch_package.warehouse", "batch_package.batch_no"
	)
	conditions.append("sle.has_batch_no = 1")
	values.update(base_values)

	collect(
		balances,
		"""
		select v.item_code, v.warehouse, v.batch_no, {aggregate}
		from (
			select sle.item_code, batch_package.warehouse, batch_package.batch_no, sle.voucher_no,
				max(sle.posting_date) as posting_date, sum(batch_package.qty) as qty
			from `tabStock Ledger Entry` sle
			inner join `tabSerial and Batch Entry` batch_package
				on batch_package.parent = sle.serial_and_batch_bundle
			{brand_join}
			where {conditions}
			group by sle.item_code, batch_package.warehouse, batch_package.batch_no, sle.voucher_no
		) v
		group by v.item_code, v.warehouse, v.batch_no
	""".format(
			aggregate=aggregate,
			brand_join=brand_join(filters),
			conditions=" and ".join(conditions),
		),
		values,
	)

	return balances


def brand_join(filters):
	return "inner join `tabItem` item on item.name = sle.item_code" if filters.get("brand") else ""


def collect(balances, query, values):
	"""Fold one half of the ledger into the running per-batch totals."""
	for row in frappe.db.sql(query, values, as_dict=1):
		key = (row.item_code, row.warehouse, row.batch_no or "")
		entry = balances.setdefault(
			key, frappe._dict(opening_qty=0.0, in_qty=0.0, out_qty=0.0)
		)
		entry.opening_qty += flt(row.opening_qty)
		entry.in_qty += flt(row.in_qty)
		entry.out_qty += flt(row.out_qty)


def get_transfer_prices(item_codes, filters):
	"""Rate per item on the stock transfer price list.

	The list is rotated monthly and only one is ever enabled, so the enabled one
	is the current one. Its rows carry validity dates that lapse with the month;
	they are deliberately not applied, because a rate that has just lapsed is
	still the rate the stock moved at, and filtering on them would empty the
	column until the next list is loaded.
	"""
	prices = {}
	if not item_codes:
		return prices

	price_list = filters.get("transfer_price_list") or frappe.db.get_value(
		"Price List", {"enabled": 1, "name": ("like", "%STOCK-TRANSFER%")}, "name"
	)
	if not price_list:
		return prices

	for row in frappe.db.get_all(
		"Item Price",
		filters={"price_list": price_list, "item_code": ("in", list(item_codes))},
		fields=["item_code", "price_list_rate"],
	):
		prices.setdefault(row.item_code, flt(row.price_list_rate))

	return prices


def get_reference_maps(item_codes, batch_nos, filters):
	refs = frappe._dict(item_docs={}, batches={}, conv_factors={}, transfer_prices={})

	if item_codes:
		for row in frappe.db.sql(
			"""
			select name, item_name, brand, `class` as item_class,
				stock_uom, case_per_unit, weight_per_unit
			from `tabItem` where name in %(items)s
		""",
			{"items": list(item_codes)},
			as_dict=1,
		):
			refs.item_docs[row.name] = row

		# Alternate-UOM conversion factor per item. An item with more than one
		# alternate UOM keeps the first, matching what the single-value lookup
		# this replaced would have returned.
		for row in frappe.db.sql(
			"""
			select parent, conversion_factor
			from `tabUOM Conversion Detail`
			where is_alternate_uom = 1 and parent in %(items)s
			order by idx
		""",
			{"items": list(item_codes)},
			as_dict=1,
		):
			refs.conv_factors.setdefault(row.parent, row.conversion_factor)

		refs.transfer_prices = get_transfer_prices(item_codes, filters)

	if batch_nos:
		for row in frappe.db.sql(
			"""
			select name, manufacturing_date, expiry_date, old_batch_no
			from `tabBatch` where name in %(batches)s
		""",
			{"batches": list(batch_nos)},
			as_dict=1,
		):
			refs.batches[row.name] = row

	return refs


def get_data(filters):
	balances = get_ledger_balances(filters)
	if not balances:
		return []

	item_codes = {key[0] for key in balances}
	batch_nos = {key[2] for key in balances if key[2]}
	refs = get_reference_maps(item_codes, batch_nos, filters)

	today = getdate()
	data = []

	for key in sorted(balances):
		item_code, warehouse, batch_no = key
		qty = balances[key]

		opening_qty = qty.opening_qty
		in_qty = qty.in_qty
		out_qty = qty.out_qty
		balance_qty = opening_qty + in_qty - out_qty

		if not (opening_qty or in_qty or out_qty or balance_qty):
			continue

		item = refs.item_docs.get(item_code) or frappe._dict()
		batch = refs.batches.get(batch_no) or frappe._dict()

		shelf_life = lapsed_life = balance_life = None
		status = ""
		if batch.manufacturing_date and batch.expiry_date:
			shelf_life = (batch.expiry_date - batch.manufacturing_date).days
			lapsed_life = (today - batch.manufacturing_date).days
			balance_life = (batch.expiry_date - today).days

			if balance_life <= 0:
				status = "Expired"
			elif balance_life < NEAR_EXPIRY_DAYS:
				status = "Near Expiry"
			else:
				status = "More Than {0} Days".format(NEAR_EXPIRY_DAYS)

		conv_factor = refs.conv_factors.get(item_code)
		transfer_price = flt(refs.transfer_prices.get(item_code))

		data.append({
			"item_code": item_code,
			"item_name": item.item_name,
			"brand": item.brand,
			"class": item.item_class,
			"warehouse": warehouse,
			"batch_no": batch_no,
			"old_batch_no": batch.old_batch_no,
			"opening_qty": opening_qty,
			"in_qty": in_qty,
			"out_qty": out_qty,
			"balance_qty": balance_qty,
			"transfer_price": transfer_price,
			"transfer_value": transfer_price * balance_qty,
			"uom": item.stock_uom,
			"cases": (flt(balance_qty) / flt(conv_factor)) if conv_factor else 0,
			"weight": balance_qty * flt(item.weight_per_unit),
			"mfg_date": batch.manufacturing_date,
			"expiry_date": batch.expiry_date,
			"shelf_life": shelf_life,
			"lapsed_life": lapsed_life,
			"lapsed_ageing": get_ageing_bucket(lapsed_life),
			"balance_life": balance_life,
			"balance_ageing": get_ageing_bucket(balance_life),
			"status": status,
		})

	return data
