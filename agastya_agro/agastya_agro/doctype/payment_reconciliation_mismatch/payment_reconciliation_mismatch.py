# Copyright (c) 2026, Dexciss and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class PaymentReconciliationMismatch(Document):

	def validate(self):
		if self.status == "Ignored" and not self.ignore_reason:
			frappe.throw(_("Give a reason before ignoring a mismatch"))

		# Anything other than Ignored is decided by the scan, not by hand.
		if self.status != "Ignored":
			self.ignore_reason = None
