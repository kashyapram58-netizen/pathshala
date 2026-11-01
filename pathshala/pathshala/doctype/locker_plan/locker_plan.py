# Copyright (c) 2026, Ram and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class LockerPlan(Document):
	def validate(self):
		if (self.duration_months or 0) < 1:
			frappe.throw(_("Duration must be at least 1 month."))
		if flt(self.rate) <= 0:
			frappe.throw(_("Rent must be greater than zero."))
		if flt(self.security_deposit) < 0:
			frappe.throw(_("Security Deposit cannot be negative."))
