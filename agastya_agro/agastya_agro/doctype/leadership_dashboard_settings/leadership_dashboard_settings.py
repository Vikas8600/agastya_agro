# Copyright (c) 2026, Dexciss and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class LeadershipDashboardSettings(Document):
	def validate(self):
		self.validate_thresholds()

	def validate_thresholds(self):
		seen = set()
		for row in self.thresholds:
			if row.red_below >= row.orange_below:
				frappe.throw(
					_("Row {0}: Red Below ({1}) must be less than Orange Below ({2})").format(
						row.idx, row.red_below, row.orange_below
					)
				)
			rule = (row.applies_to, (row.key or "").strip().lower())
			if rule in seen:
				frappe.throw(
					_("Row {0}: duplicate threshold rule for {1} / {2}").format(
						row.idx, row.applies_to, row.key or _("Default")
					)
				)
			seen.add(rule)

	def on_update(self):
		frappe.cache().delete_keys("leadership_dashboard:*")
