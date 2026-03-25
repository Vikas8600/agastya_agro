# Copyright (c) 2026, Dexciss and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import get_time, today, date_diff, getdate, cint


JOB_NAME = "auto_payment_reconciliation.process_auto_reconciliation"
METHOD_PATH = "agastya_agro.agastya_agro.doctype.auto_payment_reconciliation.auto_payment_reconciliation.process_auto_reconciliation"


class AutoPaymentReconciliation(Document):

	def on_update(self):
		self.sync_scheduled_job()

	@frappe.whitelist()
	def run_reconciliation(self):
		"""Manually trigger reconciliation from the form"""
		frappe.enqueue(
			process_auto_reconciliation,
			queue="long",
			timeout=3600,
		)
		frappe.msgprint("Payment Reconciliation has been queued. Check Process Payment Reconciliation list for progress.")

	def sync_scheduled_job(self):
		"""Create or update Scheduled Job Type based on run_time"""
		time = get_time(self.run_time or "00:00")
		cron = f"{time.minute} {time.hour} * * *"

		if frappe.db.exists("Scheduled Job Type", JOB_NAME):
			job = frappe.get_doc("Scheduled Job Type", JOB_NAME)
			job.cron_format = cron
			job.stopped = not self.enabled
			job.save(ignore_permissions=True)
		else:
			frappe.get_doc({
				"doctype": "Scheduled Job Type",
				"name": JOB_NAME,
				"method": METHOD_PATH,
				"frequency": "Cron",
				"cron_format": cron,
				"stopped": not self.enabled,
			}).insert(ignore_permissions=True)


def get_customers_to_reconcile(config):
	"""Get list of customers to reconcile based on config"""
	if not config.reconcile_all_customers and config.customers:
		return [row.customer for row in config.customers]

	parties = frappe.db.sql("""
		SELECT DISTINCT ple.party
		FROM `tabPayment Ledger Entry` ple
		WHERE ple.company = %s
		AND ple.party_type = 'Customer'
		AND ple.delinked = 0
		AND ple.party IS NOT NULL
		AND ple.party != ''
	""", config.company, as_dict=True)

	return [p.party for p in parties]


def process_auto_reconciliation():
	"""Main function - creates Process Payment Reconciliation docs for each customer"""
	config = frappe.get_single("Auto Payment Reconciliation")

	if not config.enabled:
		return

	# Check interval - skip if not enough days since last run
	interval = cint(config.interval_days) or 1
	if config.last_run_date:
		days_since = date_diff(today(), config.last_run_date)
		if days_since < interval:
			return

	customers = get_customers_to_reconcile(config)

	if not customers:
		return

	created = 0
	skipped = 0

	for customer in customers:
		# Skip if there's already a queued/running doc for this customer
		existing = frappe.db.exists("Process Payment Reconciliation", {
			"party": customer,
			"company": config.company,
			"docstatus": 1,
			"status": ("in", ["Queued", "Running"]),
		})

		if existing:
			skipped += 1
			continue

		try:
			doc = frappe.new_doc("Process Payment Reconciliation")
			doc.company = config.company
			doc.party_type = config.party_type or "Customer"
			doc.party = customer
			doc.receivable_payable_account = config.receivable_payable_account

			if config.from_invoice_date:
				doc.from_invoice_date = config.from_invoice_date
			if config.to_invoice_date:
				doc.to_invoice_date = config.to_invoice_date
			if config.from_payment_date:
				doc.from_payment_date = config.from_payment_date
			if config.to_payment_date:
				doc.to_payment_date = config.to_payment_date
			if config.cost_center:
				doc.cost_center = config.cost_center
			if config.bank_cash_account:
				doc.bank_cash_account = config.bank_cash_account

			doc.insert(ignore_permissions=True)
			doc.submit()
			created += 1
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(
				title=f"Auto Payment Reconciliation failed for {customer}",
			)

	# Update last run date
	frappe.db.set_single_value("Auto Payment Reconciliation", "last_run_date", today())
	frappe.db.commit()
