# Copyright (c) 2026, Ram and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from pathshala.utils import to_time


class StudyShift(Document):
	def validate(self):
		if self.shift_type == "Daily Hours":
			self.start_time = self.end_time = None
			if not (0 < flt(self.hours_per_day) <= 24):
				frappe.throw(_("Hours per Day must be between 0 and 24."))
		else:
			self.hours_per_day = 0
			if not (self.start_time and self.end_time):
				frappe.throw(_("Start Time and End Time are required for a Time Slot shift."))
			if to_time(self.end_time) <= to_time(self.start_time):
				frappe.throw(_("End Time must be after Start Time. Overnight shifts are not supported."))
