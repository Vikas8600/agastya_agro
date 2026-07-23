# Copyright (c) 2026, Dexciss and contributors
# See license.txt

"""Integration checks for the reconciliation mismatch scan.

Builds real vouchers, submits them, and asserts the scan reports exactly the
allocations a human would work out on paper. Every case is small enough to
verify by hand from the docstring.

Run:
    bench --site <site> run-tests --module \
        agastya_agro.agastya_agro.doctype.payment_reconciliation_mismatch.test_payment_reconciliation_mismatch
"""

import unittest

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from agastya_agro.agastya_agro.reconciliation.desired_allocations import (
	as_pair_map,
	get_actual_allocations,
	get_desired_allocations,
)
from agastya_agro.agastya_agro.reconciliation.mismatch_scan import diff_allocations


def _fill_mandatory(doc):
	"""Populate whatever mandatory fields this site has customised onto the doc.

	Agastya makes sales_person, gst_category and delivery_warehouse compulsory on
	Customer. Discovering those from meta rather than hardcoding them keeps the
	test working on a vanilla site, and stops a future custom field from breaking
	it.
	"""
	for field in doc.meta.get("fields"):
		if not field.reqd or doc.get(field.fieldname):
			continue

		if field.fieldtype == "Link" and field.options:
			filters = {}
			if frappe.get_meta(field.options).has_field("is_group"):
				filters["is_group"] = 0
			value = frappe.db.get_value(field.options, filters, "name")
			if value:
				doc.set(field.fieldname, value)

		elif field.fieldtype == "Select" and field.options:
			choice = next((o for o in field.options.split("\n") if o.strip()), None)
			if choice:
				doc.set(field.fieldname, choice)

		elif field.fieldtype in ("Data", "Small Text", "Text"):
			doc.set(field.fieldname, "Test")


def _pick_company():
	"""A company with the accounts needed to post a receivable and a receipt.

	A cost center is part of that set: the income leg is a P&L account, and
	ERPNext refuses to write a P&L GL entry without one.
	"""
	for company in frappe.get_all("Company", pluck="name"):
		receivable = frappe.db.get_value(
			"Account", {"company": company, "account_type": "Receivable", "is_group": 0}, "name"
		)
		income = frappe.db.get_value(
			"Account", {"company": company, "root_type": "Income", "is_group": 0}, "name"
		)
		bank = frappe.db.get_value(
			"Account", {"company": company, "account_type": "Bank", "is_group": 0}, "name"
		)
		cost_center = frappe.db.get_value(
			"Cost Center", {"company": company, "is_group": 0}, "name"
		)
		if receivable and income and bank and cost_center:
			return company, receivable, income, bank, cost_center
	return None, None, None, None, None


class TestPaymentReconciliationMismatch(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company, cls.receivable, cls.income, cls.bank, cls.cost_center = _pick_company()

	def setUp(self):
		if not self.company:
			raise unittest.SkipTest("no company with receivable/income/bank accounts on this site")

		doc = frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": f"_Test Recon {frappe.generate_hash(length=8)}",
				"customer_type": "Company",
				"customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}, "name"),
				"territory": frappe.db.get_value("Territory", {"is_group": 0}, "name"),
			}
		)
		_fill_mandatory(doc)
		doc.insert(ignore_permissions=True)

		# Agastya names customers by series, so the record name is not the
		# customer_name. Party links resolve against the name.
		self.customer = doc.name

	def receivable_entry(self, posting_date, amount):
		"""Manual JV debiting the customer -- stands in for an invoice."""
		jv = frappe.get_doc(
			{
				"doctype": "Journal Entry",
				"voucher_type": "Journal Entry",
				"company": self.company,
				"posting_date": posting_date,
				"accounts": [
					{
						"account": self.receivable,
						"party_type": "Customer",
						"party": self.customer,
						"debit_in_account_currency": amount,
						"debit": amount,
					},
					{
						"account": self.income,
						"credit_in_account_currency": amount,
						"credit": amount,
						"cost_center": self.cost_center,
					},
				],
			}
		)
		jv.insert(ignore_permissions=True)
		jv.submit()
		return jv.name

	def payment(self, posting_date, amount, allocations=None):
		"""Receipt from the customer, optionally allocated to given receivables.

		`allocations` is a list of (journal_entry, amount). Passing None leaves
		the payment entirely unallocated.
		"""
		pe = frappe.get_doc(
			{
				"doctype": "Payment Entry",
				"payment_type": "Receive",
				"company": self.company,
				"posting_date": posting_date,
				"party_type": "Customer",
				"party": self.customer,
				"paid_from": self.receivable,
				"paid_to": self.bank,
				"paid_amount": amount,
				"received_amount": amount,
				"source_exchange_rate": 1,
				"target_exchange_rate": 1,
				"cost_center": self.cost_center,
				# A receipt into a bank account is a bank transaction, and
				# ERPNext will not submit one without an instrument reference.
				"reference_no": "TEST-REF",
				"reference_date": posting_date,
				"references": [
					{
						"reference_doctype": "Journal Entry",
						"reference_name": name,
						"allocated_amount": allocated,
					}
					for name, allocated in (allocations or [])
				],
			}
		)
		pe.insert(ignore_permissions=True)
		pe.submit()
		return pe.name

	def scan(self):
		desired = as_pair_map(get_desired_allocations(self.customer, self.company))
		actual, _meta = get_actual_allocations(self.customer, self.company)
		return desired, actual, diff_allocations(desired, actual)

	def assert_pairs(self, pairs, expected, label):
		got = {key: flt(value, 2) for key, value in pairs.items()}
		self.assertEqual(got, expected, f"{label} allocation mismatch")

	def test_backdated_invoice_is_detected(self):
		"""The ticket's scenario.

		    JV_OLD  05-Jan  Dr 5,000   <- back-dated, entered after the payment
		    JV_NEW  10-Feb  Dr 7,000
		    PE      20-Feb  Cr 7,000   -> all 7,000 landed on JV_NEW

		FIFO must clear the oldest first, so the scan has to report the payment
		is 5,000 short on JV_OLD and 5,000 over on JV_NEW.
		"""
		jv_old = self.receivable_entry("2026-01-05", 5000)
		jv_new = self.receivable_entry("2026-02-10", 7000)
		pe = self.payment("2026-02-20", 7000, [(jv_new, 7000)])

		desired, actual, mismatches = self.scan()

		self.assert_pairs(actual, {(pe, jv_new): 7000.0}, "actual")
		self.assert_pairs(desired, {(pe, jv_old): 5000.0, (pe, jv_new): 2000.0}, "desired")

		by_pair = {(m["credit_voucher"], m["debit_voucher"]): m for m in mismatches}
		self.assertEqual(len(mismatches), 2, "expected exactly two mismatches")

		short = by_pair[(pe, jv_old)]
		self.assertEqual(short["mismatch_type"], "Missing Allocation")
		self.assertEqual(flt(short["desired_allocated"], 2), 5000.0)
		self.assertEqual(flt(short["actual_allocated"], 2), 0.0)
		self.assertEqual(flt(short["difference"], 2), 5000.0)

		over = by_pair[(pe, jv_new)]
		self.assertEqual(over["mismatch_type"], "Amount Mismatch")
		self.assertEqual(flt(over["desired_allocated"], 2), 2000.0)
		self.assertEqual(flt(over["actual_allocated"], 2), 7000.0)
		self.assertEqual(flt(over["difference"], 2), -5000.0)

	def test_correctly_reconciled_customer_is_silent(self):
		"""Allocation already in FIFO order must raise nothing at all.

		This is the case that keeps the report trustworthy -- a scan that flags
		correct work is worse than no scan.
		"""
		jv_old = self.receivable_entry("2026-01-05", 5000)
		jv_new = self.receivable_entry("2026-02-10", 7000)
		self.payment("2026-02-20", 7000, [(jv_old, 5000), (jv_new, 2000)])

		desired, actual, mismatches = self.scan()

		self.assertEqual(desired, actual, "FIFO and ledger should agree exactly")
		self.assertEqual(mismatches, [], f"expected no mismatches, got {mismatches}")

	def test_unallocated_payment_is_reported(self):
		"""A receipt left sitting unapplied while an invoice is open."""
		jv = self.receivable_entry("2026-01-05", 5000)
		pe = self.payment("2026-02-20", 5000)

		desired, actual, mismatches = self.scan()

		self.assertEqual(actual, {}, "ledger should hold no allocation")
		self.assert_pairs(desired, {(pe, jv): 5000.0}, "desired")

		self.assertEqual(len(mismatches), 1)
		self.assertEqual(mismatches[0]["mismatch_type"], "Unallocated Payment")
		self.assertEqual(flt(mismatches[0]["difference"], 2), 5000.0)

	def test_payment_on_wrong_invoice_entirely(self):
		"""Two equal invoices, payment put on the newer one.

		Nothing is back-dated here -- this is plain operator error, and FIFO
		still has to catch it.
		"""
		jv_old = self.receivable_entry("2026-01-05", 3000)
		jv_new = self.receivable_entry("2026-02-10", 3000)
		pe = self.payment("2026-02-20", 3000, [(jv_new, 3000)])

		_desired, _actual, mismatches = self.scan()

		by_pair = {(m["credit_voucher"], m["debit_voucher"]): m for m in mismatches}
		self.assertEqual(by_pair[(pe, jv_old)]["mismatch_type"], "Missing Allocation")
		self.assertEqual(by_pair[(pe, jv_new)]["mismatch_type"], "Wrong Pairing")
		self.assertEqual(flt(by_pair[(pe, jv_new)]["difference"], 2), -3000.0)
