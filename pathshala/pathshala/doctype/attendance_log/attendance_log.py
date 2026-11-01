# Copyright (c) 2026, Ram and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, get_datetime, getdate

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
		self.validate_seat()
		self.set_daily_usage()

	def on_update(self):
		if self.booking and (self.has_value_changed("extra_amount") or self.has_value_changed("booking")):
			self.update_booking_charges()

	def on_trash(self):
		if self.booking and flt(self.extra_amount):
			self.extra_amount = 0
			frappe.db.set_value("Attendance Log", self.name, "extra_amount", 0)
			self.update_booking_charges()

	def validate_single_open_log(self):
		open_log = frappe.db.get_value(
			"Attendance Log",
			{"student": self.student, "check_out": ("is", "not set"), "name": ("!=", self.name or "")},
		)
		if open_log:
			frappe.throw(_("{0} is already checked in ({1}).").format(self.student_name or self.student, open_log))

	def validate_seat(self):
		"""While a student is in, nobody else may sit on that seat."""
		if not self.seat or self.check_out:
			return
		taken = frappe.db.get_value(
			"Attendance Log",
			{"seat": self.seat, "check_out": ("is", "not set"), "name": ("!=", self.name or "")},
			"student_name",
		)
		if taken:
			frappe.throw(_("Seat {0} is currently occupied by {1}.").format(self.seat, taken))

	def set_daily_usage(self):
		"""Daily Hours plans: visits in a day add up; time beyond the allowance (+ grace) is charged."""
		hours = flt(frappe.db.get_value("Seat Booking", self.booking, "hours_per_day")) if self.booking else 0
		if not hours:
			self.allowance_minutes = self.used_before_minutes = self.extra_minutes = 0
			self.extra_amount = 0
			return
		self.allowance_minutes = int(hours * 60)
		self.used_before_minutes = cint(
			frappe.db.sql(
				"""select sum(duration_minutes) from `tabAttendance Log`
				where booking = %s and attendance_date = %s and name != %s and check_in < %s""",
				(self.booking, self.attendance_date, self.name or "", self.check_in),
			)[0][0]
		)
		if not self.check_out:
			self.extra_minutes, self.extra_amount = 0, 0
			return

		grace = cint(frappe.db.get_single_value("Pathshala Settings", "overstay_grace_minutes"))

		def billable(total):
			return max(0, total - self.allowance_minutes - grace)

		self.extra_minutes = billable(self.used_before_minutes + self.duration_minutes) - billable(
			self.used_before_minutes
		)
		self.extra_amount = flt(self.extra_minutes / 60 * get_overstay_rate(self.booking), 0)

	def update_booking_charges(self):
		from pathshala.pathshala.doctype.seat_booking.seat_booking import update_extra_charges

		update_extra_charges(self.booking)
		previous = self.get_doc_before_save()
		if previous and previous.booking and previous.booking != self.booking:
			update_extra_charges(previous.booking)


def get_overstay_rate(booking: str) -> float:
	plan = frappe.db.get_value("Seat Booking", booking, "plan")
	rate = flt(frappe.db.get_value("Seat Plan", plan, "extra_hour_rate")) if plan else 0
	return rate or flt(frappe.db.get_single_value("Pathshala Settings", "extra_hour_rate"))
