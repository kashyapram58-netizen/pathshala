# Copyright (c) 2026, Ram and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, add_months, flt, getdate, today

from pathshala.utils import (
	fmt_time,
	get_fee_status,
	new_fee_payment,
	set_payment_totals,
	to_time,
	validate_gender_policy,
)


class SeatBooking(Document):
	def validate(self):
		self.plan_doc = frappe.get_cached_doc("Seat Plan", self.plan)
		self.set_seat_mode()
		self.validate_seat()
		self.validate_gender_policy()
		self.validate_plan()
		self.set_timing()
		self.set_amounts()
		self.validate_conflicts()

	def set_seat_mode(self):
		"""Daily Hours plans without a reserved seat are Flexi: a free seat is given at each check-in."""
		plan = self.plan_doc
		shift_type, hours = (
			frappe.db.get_value("Study Shift", plan.shift, ["shift_type", "hours_per_day"])
			if plan.booking_type == "Shift" and plan.shift
			else (None, 0)
		)
		self.hours_per_day = flt(hours) if shift_type == "Daily Hours" else 0
		self.seat_mode = "Flexi" if shift_type == "Daily Hours" and not plan.fixed_seat else "Fixed"
		if self.seat_mode == "Flexi":
			self.seat = None

	def before_submit(self):
		self.status = "Active" if getdate(self.to_date) >= getdate(today()) else "Expired"

	def on_cancel(self):
		self.db_set("status", "Cancelled")

	# ------------------------------------------------------------ validations
	def validate_seat(self):
		if self.zone and frappe.db.get_value("Study Zone", self.zone, "branch") != self.branch:
			frappe.throw(_("Zone {0} does not belong to branch {1}.").format(self.zone, self.branch))
		if self.seat_mode == "Flexi":
			return
		if not (self.zone and self.seat):
			frappe.throw(_("Zone and Seat are required for this plan."))
		seat = frappe.db.get_value("Seat", self.seat, ["zone", "branch", "is_active"], as_dict=True)
		if seat.zone != self.zone or seat.branch != self.branch:
			frappe.throw(_("Seat {0} does not belong to zone {1}.").format(self.seat, self.zone))
		if not seat.is_active and self.docstatus == 0:
			frappe.throw(_("Seat {0} is not active (under maintenance).").format(self.seat))

	def validate_gender_policy(self):
		self.gender = frappe.db.get_value("Student", self.student, "gender")
		self.gender_policy = frappe.db.get_value("Study Zone", self.zone, "gender_policy") if self.zone else None
		label = _("Seat {0}").format(self.seat) if self.seat else _("Zone {0}").format(self.zone)
		validate_gender_policy(self.student, self.zone, label)

	def validate_plan(self):
		plan = self.plan_doc
		if not plan.is_active and self.docstatus == 0:
			frappe.throw(_("Plan {0} is not active.").format(plan.name))
		if plan.branch and plan.branch != self.branch:
			frappe.throw(_("Plan {0} is only for branch {1}.").format(plan.name, plan.branch))
		if plan.gender_policy and self.zone and plan.gender_policy != self.gender_policy:
			frappe.throw(_("Plan {0} is only for {1} zones.").format(plan.name, plan.gender_policy))
		if plan.gender_policy == "Girls Only" and self.gender != "Female":
			frappe.throw(_("Plan {0} is only for Girls Only zones.").format(plan.name))
		seat_type = frappe.db.get_value("Seat", self.seat, "seat_type") if self.seat else None
		if plan.seat_type and seat_type and plan.seat_type != seat_type:
			frappe.throw(_("Plan {0} is only for {1} seats.").format(plan.name, plan.seat_type))

	def set_timing(self):
		plan = self.plan_doc
		self.booking_type = plan.booking_type
		self.shift = plan.shift
		opening, closing = frappe.db.get_value(
			"Pathshala Branch", self.branch, ["opening_time", "closing_time"]
		)

		if plan.booking_type == "Hourly":
			self.to_date = self.from_date
			if not (self.from_time and self.to_time):
				frappe.throw(_("From Time and To Time are required for hourly bookings."))
		elif plan.booking_type == "Shift" and not self.hours_per_day:
			self.from_time, self.to_time = frappe.db.get_value(
				"Study Shift", plan.shift, ["start_time", "end_time"]
			)
		else:  # Full Day, or Daily Hours (usable any time the branch is open)
			self.from_time, self.to_time = opening, closing

		if plan.booking_type != "Hourly":
			self.to_date = add_days(add_months(self.from_date, plan.duration_months), -1)

		start, end = to_time(self.from_time), to_time(self.to_time)
		if end <= start:
			frappe.throw(_("To Time must be after From Time."))
		if start < to_time(opening) or end > to_time(closing):
			frappe.throw(
				_("Booking time must be within branch hours ({0} - {1}).").format(
					fmt_time(opening), fmt_time(closing)
				)
			)

	def set_amounts(self):
		self.rate = flt(self.plan_doc.rate)
		if self.booking_type == "Hourly":
			start, end = to_time(self.from_time), to_time(self.to_time)
			self.hours = flt(
				((end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)) / 60, 2
			)
			self.amount = flt(self.rate * self.hours, 2)
		else:
			self.hours = 0
			self.amount = self.rate

		if flt(self.discount) < 0 or flt(self.discount) > flt(self.amount):
			frappe.throw(_("Discount must be between 0 and the booking amount."))
		self.extra_charges = flt(self.extra_charges)
		self.net_amount = flt(self.amount) - flt(self.discount) + self.extra_charges
		self.paid_amount = flt(self.paid_amount)
		self.outstanding_amount = flt(self.net_amount) - self.paid_amount
		self.fee_status = get_fee_status(self.net_amount, self.paid_amount)

	def validate_conflicts(self):
		"""A seat is double-booked only when both the date ranges and the time windows overlap."""
		overlap = dict(
			from_date=self.from_date,
			to_date=self.to_date,
			from_time=self.from_time,
			to_time=self.to_time,
			name=self.name or "",
		)
		# Flexi bookings hold no seat; seats are handed out at check-in.
		clash = self.seat and frappe.db.sql(
			"""
			select name, student_name, from_date, to_date, from_time, to_time
			from `tabSeat Booking`
			where seat = %(seat)s and docstatus = 1 and status = 'Active' and name != %(name)s
				and from_date <= %(to_date)s and to_date >= %(from_date)s
				and from_time < %(to_time)s and to_time > %(from_time)s
			limit 1
			""",
			dict(overlap, seat=self.seat),
			as_dict=True,
		)
		if clash:
			c = clash[0]
			frappe.throw(
				_("Seat {0} is already booked by {1} ({2}) from {3} to {4}, {5} - {6}.").format(
					self.seat,
					c.student_name,
					c.name,
					frappe.format(c.from_date, "Date"),
					frappe.format(c.to_date, "Date"),
					fmt_time(c.from_time),
					fmt_time(c.to_time),
				),
				title=_("Seat Not Available"),
			)

		same_student = frappe.db.sql(
			"""
			select name from `tabSeat Booking`
			where student = %(student)s and docstatus = 1 and status = 'Active' and name != %(name)s
				and from_date <= %(to_date)s and to_date >= %(from_date)s
				and from_time < %(to_time)s and to_time > %(from_time)s
			limit 1
			""",
			dict(overlap, student=self.student),
		)
		if same_student:
			frappe.throw(
				_("{0} already has booking {1} overlapping this time.").format(
					self.student_name, same_student[0][0]
				)
			)


def update_extra_charges(booking: str):
	"""Roll overstay charges from Attendance Logs into the booking's amount due."""
	doc = frappe.get_doc("Seat Booking", booking)
	extra = flt(
		frappe.db.sql(
			"select sum(extra_amount) from `tabAttendance Log` where booking = %s", booking
		)[0][0]
	)
	if extra == flt(doc.extra_charges):
		return
	doc.db_set({"extra_charges": extra, "net_amount": flt(doc.amount) - flt(doc.discount) + extra})
	set_payment_totals(doc)


@frappe.whitelist()
def make_renewal(source_name: str):
	"""Create a draft booking for the next period on the same seat and plan."""
	source = frappe.get_doc("Seat Booking", source_name)
	source.check_permission("read")
	if source.booking_type == "Hourly":
		frappe.throw(_("Hourly bookings cannot be renewed."))
	doc = frappe.new_doc("Seat Booking")
	for field in ("student", "branch", "zone", "seat", "plan", "discount", "remarks"):
		doc.set(field, source.get(field))
	doc.from_date = add_days(source.to_date, 1)
	doc.renewed_from = source.name
	return doc


@frappe.whitelist()
def make_payment(source_name: str):
	source = frappe.get_doc("Seat Booking", source_name)
	source.check_permission("read")
	return new_fee_payment(source)


def expire_bookings():
	"""Daily: mark bookings whose period has ended as Expired."""
	frappe.db.sql(
		"""update `tabSeat Booking` set status = 'Expired', modified = now()
		where docstatus = 1 and status = 'Active' and to_date < %s""",
		today(),
	)
