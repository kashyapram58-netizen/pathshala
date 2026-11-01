# Copyright (c) 2026, Ram and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class SeatPlan(Document):
	def validate(self):
		if self.booking_type == "Hourly":
			self.shift = None
			self.duration_months = 0
		else:
			if self.booking_type != "Shift":
				self.shift = None
			if (self.duration_months or 0) < 1:
				frappe.throw(_("Duration must be at least 1 month."))
		if (self.rate or 0) <= 0:
			frappe.throw(_("Price must be greater than zero."))
