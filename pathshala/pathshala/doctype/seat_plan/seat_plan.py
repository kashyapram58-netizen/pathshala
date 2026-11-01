# Copyright (c) 2026, Ram and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


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

		shift = frappe.db.get_value("Study Shift", self.shift, ["shift_type", "hours_per_day"], as_dict=True) if self.shift else None
		self.shift_type = shift.shift_type if shift else None
		self.hours_per_day = shift.hours_per_day if shift else 0
		if self.shift_type != "Daily Hours":
			self.fixed_seat = 0
			self.extra_hour_rate = 0
		if flt(self.extra_hour_rate) < 0:
			frappe.throw(_("Overstay rate cannot be negative."))

	@property
	def is_flexi(self) -> bool:
		return self.shift_type == "Daily Hours" and not self.fixed_seat
