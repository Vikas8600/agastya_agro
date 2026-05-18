# Copyright (c) 2026, Dexciss and contributors
# For license information, please see license.txt

import traceback

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, date_diff, flt, getdate, now_datetime


WORKER_PATH = "agastya_agro.agastya_agro.doctype.payment_reconciliation_redo.payment_reconciliation_redo.run_redo"


class PaymentReconciliationRedo(Document):

	def validate(self):
		if not self.party_type:
			self.party_type = "Customer"

		if not self.from_date or not self.to_date:
			frappe.throw(_("From Date and To Date are required"))

		if getdate(self.from_date) > getdate(self.to_date):
			frappe.throw(_("From Date cannot be after To Date"))

		max_days = cint(
			frappe.db.get_single_value("Auto Payment Reconciliation", "redo_max_days")
		) or 62

		span = date_diff(self.to_date, self.from_date) + 1
		if span > max_days:
			frappe.throw(
				_("Date range ({0} days) exceeds the configured limit of {1} days. Reduce the range or increase 'Redo Max Days' on Auto Payment Reconciliation.").format(
					span, max_days
				)
			)

		if self.is_new() or self.docstatus == 0:
			self.status = "Draft"
			self.unreconciled_count = 0
			self.error_log = None
			self.reconciliation_doc = None
			self.affected_vouchers = []

	def on_submit(self):
		self.db_set("status", "Queued", update_modified=False)
		frappe.enqueue(
			WORKER_PATH,
			queue="long",
			timeout=3600,
			doc_name=self.name,
			enqueue_after_commit=True,
		)

	def before_cancel(self):
		# Once we've started touching ledger entries (or finished), cancellation
		# is a record-only no-op that misleads users into thinking allocations
		# were restored. Block it. Users should fix mistakes with a new Redo run.
		allowed = ("Queued", "Failed")
		if self.status not in allowed:
			frappe.throw(
				_(
					"Cannot cancel a run in status <b>{0}</b>. "
					"Cancel is only allowed when status is <b>Queued</b> (before the worker started) "
					"or <b>Failed</b> (when nothing was changed on the ledger). "
					"For Completed / Partially Failed runs, create a new Payment Reconciliation Redo "
					"to fix any allocation issues — cancelling here would NOT re-link the "
					"{1} payment(s) already unreconciled."
				).format(self.status, self.unreconciled_count or 0)
			)

	def on_cancel(self):
		self.db_set("status", "Cancelled", update_modified=False)

	@frappe.whitelist()
	def preview_allocations(self):
		"""Return the list of reconciled allocations that would be reversed,
		without actually touching anything. For UI preview before submit."""
		missing = [
			label
			for label, value in (
				("Company", self.company),
				("Party Type", self.party_type),
				("Party", self.party),
				("From Date", self.from_date),
				("To Date", self.to_date),
			)
			if not value
		]
		if missing:
			frappe.throw(_("Fill these fields first: {0}").format(", ".join(missing)))

		if getdate(self.from_date) > getdate(self.to_date):
			frappe.throw(_("From Date cannot be after To Date"))

		return _get_allocations(self)

	@frappe.whitelist()
	def retry(self):
		if self.docstatus != 1:
			frappe.throw(_("Only submitted documents can be retried"))

		if self.status not in ("Failed", "Partially Failed"):
			frappe.throw(_("Retry is only available for Failed or Partially Failed runs"))

		self.db_set("status", "Queued", update_modified=False)
		self.db_set("error_log", None, update_modified=False)
		frappe.enqueue(
			WORKER_PATH,
			queue="long",
			timeout=3600,
			doc_name=self.name,
			enqueue_after_commit=True,
		)
		return "Queued"


def _append_error(doc, message):
	stamp = now_datetime().strftime("%Y-%m-%d %H:%M:%S")
	line = f"[{stamp}] {message}"
	existing = doc.error_log or ""
	doc.db_set(
		"error_log",
		(existing + "\n" + line).strip() if existing else line,
		update_modified=False,
	)


def _get_allocations(doc):
	"""All reconciled PLE rows for the party in the date window."""
	return frappe.db.sql(
		"""
		SELECT DISTINCT
			voucher_type,
			voucher_no,
			against_voucher_type,
			against_voucher_no,
			SUM(ABS(amount)) AS allocated_amount
		FROM `tabPayment Ledger Entry`
		WHERE company = %(company)s
			AND party_type = %(party_type)s
			AND party = %(party)s
			AND posting_date BETWEEN %(from_date)s AND %(to_date)s
			AND delinked = 0
			AND against_voucher_no IS NOT NULL
			AND against_voucher_no != ''
			AND voucher_no != against_voucher_no
		GROUP BY voucher_type, voucher_no, against_voucher_type, against_voucher_no
		""",
		{
			"company": doc.company,
			"party_type": doc.party_type,
			"party": doc.party,
			"from_date": doc.from_date,
			"to_date": doc.to_date,
		},
		as_dict=True,
	)


def _processed_keys(doc):
	"""Set of (voucher_no, against_voucher_no) already marked Success — for Retry skip."""
	return {
		(row.voucher_no, row.against_voucher_no)
		for row in (doc.affected_vouchers or [])
		if row.status == "Success"
	}


def _unreconcile_one(company, voucher_type, voucher_no, against_voucher_type, against_voucher_no):
	"""Replicates erpnext.accounts.doctype.unreconcile_payment.create_unreconcile_doc_for_selection
	for a single allocation, but returns the created doc so we can record its name."""
	unrecon = frappe.new_doc("Unreconcile Payment")
	unrecon.company = company
	unrecon.voucher_type = voucher_type
	unrecon.voucher_no = voucher_no
	unrecon.add_references()
	unrecon.allocations = [
		row
		for row in unrecon.allocations
		if row.reference_doctype == against_voucher_type
		and row.reference_name == against_voucher_no
	]
	if not unrecon.allocations:
		frappe.throw(
			_("No matching allocation found on {0} {1} against {2} {3}").format(
				voucher_type, voucher_no, against_voucher_type, against_voucher_no
			)
		)
	unrecon.save()
	unrecon.submit()
	return unrecon


def _trigger_reconciliation(doc):
	recon = frappe.new_doc("Process Payment Reconciliation")
	recon.company = doc.company
	recon.party_type = doc.party_type
	recon.party = doc.party
	recon.receivable_payable_account = doc.receivable_payable_account
	recon.from_payment_date = doc.from_date
	recon.to_payment_date = doc.to_date
	if doc.cost_center:
		recon.cost_center = doc.cost_center
	if doc.bank_cash_account:
		recon.bank_cash_account = doc.bank_cash_account
	recon.insert(ignore_permissions=True)
	recon.submit()

	# Leave a trail on the recon doc so anyone opening it knows it was created
	# by a Payment Reconciliation Redo run (and which one).
	try:
		redo_link = frappe.utils.get_link_to_form("Payment Reconciliation Redo", doc.name)
		recon.add_comment(
			"Info",
			_("Created by Payment Reconciliation Redo {0}").format(redo_link),
		)
	except Exception:
		pass

	# Process Payment Reconciliation on_submit only sets status=Queued; the actual
	# job is fired by an hourly scheduler. Trigger it immediately so the user does
	# not have to click "Start / Resume" on the recon doc.
	try:
		from erpnext.accounts.doctype.process_payment_reconciliation.process_payment_reconciliation import (
			trigger_job_for_doc,
		)

		trigger_job_for_doc(recon.name)
	except Exception:
		frappe.log_error(
			title=f"Payment Reconciliation Redo: failed to auto-start {recon.name}",
		)

	return recon.name


def run_redo(doc_name):
	"""Background worker — unreconciles allocations then triggers re-reconciliation."""
	doc = frappe.get_doc("Payment Reconciliation Redo", doc_name)

	if doc.docstatus != 1 or doc.status not in ("Queued",):
		return

	doc.db_set("status", "Unreconciling", update_modified=False)
	frappe.db.commit()

	try:
		allocations = _get_allocations(doc)
	except Exception:
		_append_error(doc, f"Failed to fetch allocations: {traceback.format_exc()}")
		doc.db_set("status", "Failed", update_modified=False)
		frappe.db.commit()
		return

	already_done = _processed_keys(doc)
	failure_count = 0
	new_success = 0

	for alloc in allocations:
		key = (alloc.voucher_no, alloc.against_voucher_no)
		if key in already_done:
			continue

		row = doc.append(
			"affected_vouchers",
			{
				"voucher_type": alloc.voucher_type,
				"voucher_no": alloc.voucher_no,
				"against_voucher_type": alloc.against_voucher_type,
				"against_voucher_no": alloc.against_voucher_no,
				"allocated_amount": flt(alloc.allocated_amount),
				"status": "Pending",
			},
		)
		row.db_insert()

		try:
			unrecon = _unreconcile_one(
				doc.company,
				alloc.voucher_type,
				alloc.voucher_no,
				alloc.against_voucher_type,
				alloc.against_voucher_no,
			)
			row.db_set("unreconcile_doc", unrecon.name, update_modified=False)
			row.db_set("status", "Success", update_modified=False)
			new_success += 1
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			# After rollback the child row insert is gone — re-insert with Failed state.
			err = traceback.format_exc()
			doc.reload()
			failed_row = doc.append(
				"affected_vouchers",
				{
					"voucher_type": alloc.voucher_type,
					"voucher_no": alloc.voucher_no,
					"against_voucher_type": alloc.against_voucher_type,
					"against_voucher_no": alloc.against_voucher_no,
					"allocated_amount": flt(alloc.allocated_amount),
					"status": "Failed",
					"error": (err[-200:] if err else "Unknown error"),
				},
			)
			failed_row.db_insert()
			_append_error(
				doc,
				f"Failed to unreconcile {alloc.voucher_type} {alloc.voucher_no} -> "
				f"{alloc.against_voucher_type} {alloc.against_voucher_no}: {err.splitlines()[-1] if err else ''}",
			)
			failure_count += 1
			frappe.db.commit()

	doc.reload()
	doc.db_set(
		"unreconciled_count",
		len(already_done) + new_success,
		update_modified=False,
	)
	doc.db_set("status", "Re-Reconciling", update_modified=False)
	frappe.db.commit()

	recon_failed = False
	try:
		recon_name = _trigger_reconciliation(doc)
		doc.db_set("reconciliation_doc", recon_name, update_modified=False)
		frappe.db.commit()
	except Exception:
		frappe.db.rollback()
		_append_error(doc, f"Failed to trigger Process Payment Reconciliation: {traceback.format_exc()}")
		recon_failed = True
		frappe.db.commit()

	if recon_failed and new_success == 0 and failure_count > 0:
		final = "Failed"
	elif recon_failed:
		final = "Partially Failed"
	elif failure_count > 0:
		final = "Partially Failed"
	else:
		final = "Completed"

	doc.db_set("status", final, update_modified=False)
	frappe.db.commit()
