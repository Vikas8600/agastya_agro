# Copyright (c) 2026, Dexciss and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cint, date_diff, flt, formatdate, getdate

NEAR_EXPIRY_DAYS = 120


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)
	return get_columns(), get_data(filters)


def validate_filters(filters):
	if not filters.company:
		frappe.throw(_("Please select a Company."))

	if not filters.from_date or not filters.to_date:
		frappe.throw(_("Please select both From Date and To Date."))

	if getdate(filters.from_date) > getdate(filters.to_date):
		frappe.throw(
			_("From Date {0} is after To Date {1}. No production falls in that range.").format(
				formatdate(filters.from_date), formatdate(filters.to_date)
			)
		)

	# Life is measured against this date, so it only makes sense at or after the
	# production being reported.
	if not filters.as_on_date:
		filters.as_on_date = filters.to_date
	elif getdate(filters.as_on_date) < getdate(filters.from_date):
		frappe.throw(
			_("Life As On {0} is before From Date {1}, so every batch would show negative age.").format(
				formatdate(filters.as_on_date), formatdate(filters.from_date)
			)
		)


def get_data(filters):
	fg_lines = get_fg_lines(filters)
	if not fg_lines:
		return []

	# Stage 2 -- everything the finished goods entries consumed, split into the
	# bulk (WIP) line and the packing lines.
	stage_two = get_consumed_lines([d.parent for d in fg_lines])

	# Stage 1 -- the entry that produced each bulk batch, and what it consumed.
	wip_batches = {c.batch_no for e in stage_two.values() for c in [e.wip] if c and c.batch_no}
	stage_one_entry = get_stage_one_entries(wip_batches)
	stage_one = get_consumed_lines(list(stage_one_entry.values()))

	refs = get_reference_maps(fg_lines, stage_two, stage_one, filters)

	data = []
	for fg in fg_lines:
		consumed = stage_two.get(fg.parent) or frappe._dict({"wip": None, "packing": []})
		wip = consumed.wip
		rm_lines = []
		if wip and wip.batch_no:
			source = stage_one_entry.get(wip.batch_no)
			if source:
				rm_lines = (stage_one.get(source) or frappe._dict({"packing": []})).packing

		data.extend(build_group(fg, wip, rm_lines, consumed.packing, refs, filters))

	return data


def build_group(fg, wip, rm_lines, packing_lines, refs, filters):
	"""One group per finished goods entry.

	The reference, the bulk block and the finished goods block are written on the
	first row only; raw material and packing lines run down independently, so the
	group is as tall as the longer of the two.
	"""
	height = max(len(rm_lines), len(packing_lines), 1)
	rows = []
	seen = set()

	for i in range(height):
		row = {}

		if i < len(rm_lines):
			row.update(build_rm_row(rm_lines[i], refs, seen))

		if i < len(packing_lines):
			row.update(build_packing_row(packing_lines[i], refs))

		if i == 0:
			row["reference_number"] = fg.parent
			if wip:
				row["wip_qty"] = flt(wip.qty)
				row["wip_batch"] = wip.batch_no
			row.update(build_fg_block(fg, refs, filters))

		rows.append(row)

	return rows


def build_rm_row(line, refs, seen):
	item = refs.item_docs.get(line.item_code) or frappe._dict()
	batch = refs.batches.get(line.batch_no) or frappe._dict()
	rate = flt(item.last_purchase_rate)

	# An item consumed from several batches occupies one row per batch, so the
	# BOM requirement is written against the first of them only.
	required = 0
	if line.item_code not in seen:
		seen.add(line.item_code)
		required = flt(refs.bom_required.get((line.parent, line.item_code)))

	return {
		"rm_item_code": line.item_code,
		"rm_item_name": item.item_name,
		"purity": flt(batch.custom_purity) or flt(item.custom_purity),
		"rm_batch": line.batch_no,
		"rm_mfg_date": batch.manufacturing_date,
		"rm_exp_date": batch.expiry_date,
		"rm_actual_qty": flt(line.qty),
		"rm_required_qty": required,
		"rm_price": rate,
		"rm_value": required * rate,
	}


def build_packing_row(line, refs):
	item = refs.item_docs.get(line.item_code) or frappe._dict()
	rate = flt(item.last_purchase_rate)

	return {
		"packing_item_code": line.item_code,
		"packing_item_name": item.item_name,
		"packing_required_qty": flt(line.qty),
		"packing_rate": rate,
		"packing_value": flt(line.qty) * rate,
	}


def build_fg_block(fg, refs, filters):
	item = refs.item_docs.get(fg.item_code) or frappe._dict()
	batch = refs.batches.get(fg.batch_no) or frappe._dict()
	position = refs.position.get((fg.item_code, fg.batch_no)) or frappe._dict()

	shelf_life = cint(item.shelf_life_in_days)
	mfg_date = batch.manufacturing_date
	lapsed = date_diff(filters.as_on_date, mfg_date) if (mfg_date and filters.as_on_date) else None
	balance_life = (shelf_life - lapsed) if lapsed is not None else None

	price = flt(refs.transfer_price.get(fg.item_code))
	opening_qty = flt(position.opening_qty)
	in_qty = flt(position.in_qty)
	out_qty = flt(position.out_qty)

	return {
		"fg_item_code": fg.item_code,
		"fg_item_name": item.item_name,
		"product_category": item.item_group,
		"product_group": item.item_class,
		"fg_qty": flt(fg.qty),
		"fg_mfg_date": mfg_date,
		"fg_exp_date": batch.expiry_date,
		"shelf_life": shelf_life,
		"lapsed_life": lapsed,
		"balance_life": balance_life,
		"status": get_status(balance_life),
		"fg_price": price,
		"opening_qty": opening_qty,
		"opening_value": opening_qty * price,
		"incoming_qty": in_qty,
		"incoming_value": in_qty * price,
		"sales_qty": out_qty,
		"sales_value": out_qty * price,
		"balance_qty": opening_qty + in_qty - out_qty,
		"balance_value": (opening_qty + in_qty - out_qty) * price,
	}


def get_status(balance_life):
	if balance_life is None:
		return ""
	if balance_life <= 0:
		return _("Already Expired")
	if balance_life <= NEAR_EXPIRY_DAYS:
		return _("Less than {0} days").format(NEAR_EXPIRY_DAYS)
	return _("Morethan {0} days").format(NEAR_EXPIRY_DAYS)


def get_fg_lines(filters):
	"""Finished goods produced in the period -- the driver of the report.

	Output landing in a WIP warehouse is bulk, which is stage one, so it is
	excluded here and picked up through the batch it produced.
	"""
	conditions = ""
	values = {
		"company": filters.company,
		"from_date": filters.from_date,
		"to_date": filters.to_date,
	}

	if filters.get("item_code"):
		conditions += " and sed.item_code = %(item_code)s"
		values["item_code"] = filters.item_code

	if filters.get("item_group"):
		conditions += " and item.item_group = %(item_group)s"
		values["item_group"] = filters.item_group

	if filters.get("warehouse"):
		conditions += " and sed.t_warehouse = %(warehouse)s"
		values["warehouse"] = filters.warehouse

	return frappe.db.sql(
		f"""
		select
			sed.parent, sed.item_code, sed.batch_no, sed.qty,
			sed.t_warehouse, se.posting_date
		from `tabStock Entry Detail` sed
		inner join `tabStock Entry` se on se.name = sed.parent
		inner join `tabItem` item on item.name = sed.item_code
		where se.docstatus = 1
			and se.purpose = 'Manufacture'
			and se.company = %(company)s
			and se.posting_date between %(from_date)s and %(to_date)s
			and sed.is_finished_item = 1
			and ifnull(sed.t_warehouse, '') not like '%%WIP%%'
			{conditions}
		order by se.posting_date, sed.parent, sed.idx
	""",
		values,
		as_dict=1,
	)


def get_consumed_lines(entries):
	"""Consumed lines per entry, with the bulk line separated from the rest."""
	result = {}
	if not entries:
		return result

	rows = frappe.db.sql(
		"""
		select parent, item_code, batch_no, serial_and_batch_bundle, qty, basic_rate, s_warehouse
		from `tabStock Entry Detail`
		where parent in %(entries)s
			and docstatus = 1
			and ifnull(s_warehouse, '') != ''
			and ifnull(is_finished_item, 0) = 0
		order by parent, idx
	""",
		{"entries": list(entries)},
		as_dict=1,
	)

	for row in rows:
		entry = result.setdefault(row.parent, frappe._dict({"wip": None, "packing": []}))
		if "WIP" in (row.s_warehouse or "") and not entry.wip:
			entry.wip = row
		else:
			entry.packing.append(row)

	fill_bundle_batches([r for r in rows if not r.batch_no and r.serial_and_batch_bundle])

	return result


def fill_bundle_batches(lines):
	"""Lines booked through a bundle carry no batch_no of their own."""
	if not lines:
		return

	bundles = {}
	for row in frappe.db.get_all(
		"Serial and Batch Entry",
		filters={"parent": ("in", list({r.serial_and_batch_bundle for r in lines}))},
		fields=["parent", "batch_no"],
	):
		bundles.setdefault(row.parent, row.batch_no)

	for row in lines:
		row.batch_no = bundles.get(row.serial_and_batch_bundle)


def get_stage_one_entries(batches):
	"""Map each bulk batch to the entry that produced it.

	Resolved through the stock ledger rather than Stock Entry Detail: batch_no is
	indexed there, while matching on the detail table forces a scan of every
	manufacturing entry. Batches booked through a bundle carry no batch_no on the
	ledger row, so those are picked up in a second pass.
	"""
	if not batches:
		return {}

	batches = set(batches)
	entries = {}

	for row in frappe.db.sql(
		"""
		select sle.batch_no, sle.voucher_no
		from `tabStock Ledger Entry` sle
		where sle.is_cancelled = 0
			and sle.voucher_type = 'Stock Entry'
			and sle.actual_qty > 0
			and sle.batch_no in %(batches)s
			and sle.warehouse like '%%WIP%%'
		order by sle.posting_date
	""",
		{"batches": list(batches)},
		as_dict=1,
	):
		entries[row.batch_no] = row.voucher_no

	missing = batches - set(entries)
	if missing:
		for row in frappe.db.sql(
			"""
			select sbe.batch_no, sbb.voucher_no
			from `tabSerial and Batch Entry` sbe
			inner join `tabSerial and Batch Bundle` sbb on sbb.name = sbe.parent
			where sbe.batch_no in %(batches)s
				and sbb.is_cancelled = 0
				and sbb.voucher_type = 'Stock Entry'
				and sbb.type_of_transaction = 'Inward'
		""",
			{"batches": list(missing)},
			as_dict=1,
		):
			entries.setdefault(row.batch_no, row.voucher_no)

	return entries


def get_reference_maps(fg_lines, stage_two, stage_one, filters):
	"""Batch every master and ledger lookup the rows need into one pass each."""
	item_codes = {d.item_code for d in fg_lines}
	batch_ids = {d.batch_no for d in fg_lines if d.batch_no}
	consumed_codes = set()

	for bucket in (stage_two, stage_one):
		for entry in bucket.values():
			lines = list(entry.packing)
			if entry.wip:
				lines.append(entry.wip)
			for line in lines:
				consumed_codes.add(line.item_code)
				if line.batch_no:
					batch_ids.add(line.batch_no)

	item_codes |= consumed_codes

	refs = frappe._dict(
		{
			"item_docs": {},
			"batches": {},
			"bom_required": {},
			"transfer_price": {},
			"position": {},
		}
	)

	if item_codes:
		# `class` needs quoting, so the item query stays raw SQL.
		for row in frappe.db.sql(
			"""
			select name, item_name, item_group, stock_uom, shelf_life_in_days,
				last_purchase_rate, custom_purity, `class` as item_class
			from `tabItem` where name in %(items)s
		""",
			{"items": list(item_codes)},
			as_dict=1,
		):
			refs.item_docs[row.name] = row

	if batch_ids:
		for row in frappe.db.get_all(
			"Batch",
			filters={"name": ("in", list(batch_ids))},
			fields=["name", "manufacturing_date", "expiry_date", "custom_purity"],
		):
			refs.batches[row.name] = row

	refs.bom_required = get_bom_requirements(set(stage_one))
	refs.transfer_price = get_transfer_prices({d.item_code for d in fg_lines}, filters)
	refs.position = get_stock_position({d.item_code for d in fg_lines}, filters)

	return refs


def get_bom_requirements(entry_names):
	"""Required quantity per item, from the BOM each entry was produced against.

	The BOM is written for a fixed batch size, so each line is scaled by what the
	entry actually produced.
	"""
	requirements = {}
	if not entry_names:
		return requirements

	entries = frappe.db.sql(
		"""
		select se.name, se.bom_no, sed.qty as produced_qty
		from `tabStock Entry` se
		inner join `tabStock Entry Detail` sed
			on sed.parent = se.name and sed.is_finished_item = 1
		where se.name in %(entries)s
			and ifnull(se.bom_no, '') != ''
	""",
		{"entries": list(entry_names)},
		as_dict=1,
	)
	if not entries:
		return requirements

	per_unit = {}
	for row in frappe.db.sql(
		"""
		select bi.parent as bom, bi.item_code, bi.qty / bom.quantity as per_unit
		from `tabBOM Item` bi
		inner join `tabBOM` bom on bom.name = bi.parent
		where bi.parent in %(boms)s and bom.quantity > 0
	""",
		{"boms": list({e.bom_no for e in entries})},
		as_dict=1,
	):
		per_unit.setdefault(row.bom, {})[row.item_code] = flt(row.per_unit)

	for entry in entries:
		for item_code, factor in (per_unit.get(entry.bom_no) or {}).items():
			requirements[(entry.name, item_code)] = factor * flt(entry.produced_qty)

	return requirements


def get_transfer_prices(item_codes, filters):
	"""Stock transfer price, falling back to the last rate actually billed on a
	transfer delivery note when the price list has no entry for the item."""
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
		prices[row.item_code] = flt(row.price_list_rate)

	missing = [code for code in item_codes if code not in prices]
	if missing:
		for row in frappe.db.sql(
			"""
			select dni.item_code, dni.rate
			from `tabDelivery Note Item` dni
			inner join `tabDelivery Note` dn on dn.name = dni.parent
			where dn.docstatus = 1
				and dn.selling_price_list = %(price_list)s
				and dni.item_code in %(items)s
			order by dn.posting_date
		""",
			{"price_list": price_list, "items": missing},
			as_dict=1,
		):
			prices[row.item_code] = flt(row.rate)

	return prices


def get_stock_position(item_codes, filters):
	"""Opening, incoming and outward quantity per item and batch."""
	position = {}
	if not item_codes:
		return position

	conditions = ""
	values = {
		"items": list(item_codes),
		"company": filters.company,
		"from_date": filters.from_date,
		"to_date": filters.to_date,
	}

	if filters.get("warehouse"):
		conditions += " and sle.warehouse = %(warehouse)s"
		values["warehouse"] = filters.warehouse

	rows = frappe.db.sql(
		f"""
		select
			sle.item_code,
			coalesce(sle.batch_no, sbe.batch_no) as batch_no,
			sum(case when sle.posting_date < %(from_date)s
				then sle.actual_qty else 0 end) as opening_qty,
			sum(case when sle.posting_date >= %(from_date)s and sle.actual_qty > 0
				then sle.actual_qty else 0 end) as in_qty,
			sum(case when sle.posting_date >= %(from_date)s and sle.actual_qty < 0
				then -sle.actual_qty else 0 end) as out_qty
		from `tabStock Ledger Entry` sle
		left join `tabSerial and Batch Bundle` sbb on sbb.name = sle.serial_and_batch_bundle
		left join `tabSerial and Batch Entry` sbe on sbe.parent = sbb.name
		where sle.is_cancelled = 0
			and sle.company = %(company)s
			and sle.item_code in %(items)s
			and sle.posting_date <= %(to_date)s
			{conditions}
		group by sle.item_code, coalesce(sle.batch_no, sbe.batch_no)
	""",
		values,
		as_dict=1,
	)

	for row in rows:
		position[(row.item_code, row.batch_no)] = row

	return position


def get_columns():
	return [
		{"label": _("Reference Number"), "fieldname": "reference_number", "fieldtype": "Link", "options": "Stock Entry", "width": 170},
		{"label": _("RM Item Code"), "fieldname": "rm_item_code", "fieldtype": "Link", "options": "Item", "width": 150},
		{"label": _("RM Item Name"), "fieldname": "rm_item_name", "fieldtype": "Data", "width": 200},
		{"label": _("Purity %"), "fieldname": "purity", "fieldtype": "Percent", "width": 90},
		{"label": _("RM Batch Number"), "fieldname": "rm_batch", "fieldtype": "Link", "options": "Batch", "width": 150},
		{"label": _("MFG Date"), "fieldname": "rm_mfg_date", "fieldtype": "Date", "width": 100},
		{"label": _("Exp Date"), "fieldname": "rm_exp_date", "fieldtype": "Date", "width": 100},
		{"label": _("RM Actual Qty"), "fieldname": "rm_actual_qty", "fieldtype": "Float", "width": 120},
		{"label": _("RM Required Qty"), "fieldname": "rm_required_qty", "fieldtype": "Float", "width": 130},
		{"label": _("RM price"), "fieldname": "rm_price", "fieldtype": "Currency", "width": 110},
		{"label": _("RM Value"), "fieldname": "rm_value", "fieldtype": "Currency", "width": 120},
		{"label": _("WIP Qty (Convertion)"), "fieldname": "wip_qty", "fieldtype": "Float", "width": 150},
		{"label": _("WIP Batch Number"), "fieldname": "wip_batch", "fieldtype": "Link", "options": "Batch", "width": 150},
		{"label": _("Item Code"), "fieldname": "packing_item_code", "fieldtype": "Link", "options": "Item", "width": 170},
		{"label": _("Item Name"), "fieldname": "packing_item_name", "fieldtype": "Data", "width": 200},
		{"label": _("Required Qty"), "fieldname": "packing_required_qty", "fieldtype": "Float", "width": 120},
		{"label": _("Packing rate"), "fieldname": "packing_rate", "fieldtype": "Currency", "width": 120},
		{"label": _("Packing value"), "fieldname": "packing_value", "fieldtype": "Currency", "width": 120},
		{"label": _("FG Item Code"), "fieldname": "fg_item_code", "fieldtype": "Link", "options": "Item", "width": 200},
		{"label": _("FG Item Name"), "fieldname": "fg_item_name", "fieldtype": "Data", "width": 240},
		{"label": _("Product Category"), "fieldname": "product_category", "fieldtype": "Link", "options": "Item Group", "width": 140},
		{"label": _("Product Group"), "fieldname": "product_group", "fieldtype": "Link", "options": "Class", "width": 120},
		{"label": _("FG Qty"), "fieldname": "fg_qty", "fieldtype": "Float", "width": 100},
		{"label": _("Mfg Date"), "fieldname": "fg_mfg_date", "fieldtype": "Date", "width": 100},
		{"label": _("Exp Date"), "fieldname": "fg_exp_date", "fieldtype": "Date", "width": 100},
		{"label": _("Self Life"), "fieldname": "shelf_life", "fieldtype": "Int", "width": 90},
		{"label": _("Lapsed Life"), "fieldname": "lapsed_life", "fieldtype": "Int", "width": 100},
		{"label": _("Balance Life"), "fieldname": "balance_life", "fieldtype": "Int", "width": 110},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 150},
		{"label": _("FG price Stock Transfer.Price"), "fieldname": "fg_price", "fieldtype": "Currency", "width": 180},
		{"label": _("FG Opening Qy"), "fieldname": "opening_qty", "fieldtype": "Float", "width": 130},
		{"label": _("FG Opening Value"), "fieldname": "opening_value", "fieldtype": "Currency", "width": 150},
		{"label": _("FG Incoming Qy"), "fieldname": "incoming_qty", "fieldtype": "Float", "width": 140},
		{"label": _("FG Incoming Value"), "fieldname": "incoming_value", "fieldtype": "Currency", "width": 150},
		{"label": _("FG Sales Qy"), "fieldname": "sales_qty", "fieldtype": "Float", "width": 120},
		{"label": _("FG Sales Value"), "fieldname": "sales_value", "fieldtype": "Currency", "width": 140},
		{"label": _("FG Balance Qty"), "fieldname": "balance_qty", "fieldtype": "Float", "width": 130},
		{"label": _("FG Balance Value"), "fieldname": "balance_value", "fieldtype": "Currency", "width": 150},
	]
