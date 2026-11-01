# Copyright (c) 2026, Ram and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_datetime, getdate

from pathshala.utils import minutes_between


class AttendanceLog(Document):
	def validate(self):
		self.attendance_date = getdate(self.check_in)
		if self.check_out:
			if get_datetime(self.check_out) < get_datetime(self.check_in):
				frappe.throw(_("Check Out cannot be before Check In."))
			self.duration_minutes = minutes_between(get_datetime(self.check_in), get_datetime(self.check_out))
		else:
			self.duration_minutes = 0
			self.validate_single_open_log()

	def validate_single_open_log(self):
		open_log = frappe.db.get_value(
			"Attendance Log",
			{"student": self.student, "check_out": ("is", "not set"), "name": ("!=", self.name or "")},
		)
		if open_log:
			frappe.throw(_("{0} is already checked in ({1}).").format(self.student_name or self.student, open_log))
