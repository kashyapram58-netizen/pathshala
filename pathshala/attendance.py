"""Check-in / check-out rules shared by the kiosk and staff."""

from datetime import datetime

import frappe
from frappe import _
from frappe.utils import cint, date_diff, flt, get_datetime, getdate, now_datetime

from pathshala.utils import fmt_time, format_minutes, shift_time, to_time


def punch(student: str, branch: str, source: str = "Kiosk") -> dict:
	"""Toggle a student's attendance at a branch and return a kiosk-friendly result."""
	settings = frappe.get_cached_doc("Pathshala Settings")
	now = now_datetime()
	stu = frappe.db.get_value("Student", student, ["name", "full_name", "photo", "status"], as_dict=True)
	result = {"student": stu.name, "student_name": stu.full_name, "photo": stu.photo, "time": fmt_time(now)}

	if stu.status != "Active":
		return dict(result, status="error", message=_("Your membership is inactive. Please contact the desk."))

	open_log = frappe.db.get_value(
		"Attendance Log",
		{"student": student, "check_out": ("is", "not set")},
		["name", "check_in", "branch", "seat"],
		as_dict=True,
	)

	if open_log:
		since = (now - get_datetime(open_log.check_in)).total_seconds()
		if since < cint(settings.duplicate_punch_seconds):
			return dict(
				result,
				status="info",
				action="IN",
				seat=seat_label(open_log.seat),
				message=_("Already checked in at {0}.").format(fmt_time(open_log.check_in)),
			)
		return check_out(open_log, now, result)

	return check_in(stu, branch, now, settings, source, result)


def check_out(open_log, now: datetime, result: dict) -> dict:
	log = frappe.get_doc("Attendance Log", open_log.name)
	log.check_out = now
	log.save(ignore_permissions=True)
	total_today = frappe.db.sql(
		"""select sum(duration_minutes) from `tabAttendance Log`
		where student = %s and attendance_date = %s""",
		(log.student, log.attendance_date),
	)[0][0]
	return dict(
		result,
		status="success",
		action="OUT",
		seat=seat_label(log.seat),
		message=_("Goodbye! You studied {0} today.").format(format_minutes(total_today)),
	)


def check_in(stu, branch: str, now: datetime, settings, source: str, result: dict) -> dict:
	today = now.date()
	bookings = frappe.get_all(
		"Seat Booking",
		filters={
			"student": stu.name,
			"branch": branch,
			"docstatus": 1,
			"status": "Active",
			"from_date": ("<=", today),
			"to_date": (">=", today),
		},
		fields=["name", "seat", "zone", "from_time", "to_time", "to_date", "outstanding_amount"],
		order_by="from_time asc",
	)

	if not bookings:
		return dict(result, status="error", message=no_booking_message(stu.name, branch, today))

	now_t = now.time()
	early = cint(settings.early_entry_minutes)
	booking = next(
		(b for b in bookings if shift_time(to_time(b.from_time), -early) <= now_t <= to_time(b.to_time)),
		None,
	)
	if not booking:
		if cint(settings.enforce_shift_timing):
			upcoming = next((b for b in bookings if to_time(b.from_time) > now_t), None)
			if upcoming:
				msg = _("Your slot is {0} - {1}. Entry opens at {2}.").format(
					fmt_time(upcoming.from_time),
					fmt_time(upcoming.to_time),
					fmt_time(shift_time(to_time(upcoming.from_time), -early)),
				)
			else:
				msg = _("Your slot for today has ended. Please book extra hours at the desk.")
			return dict(result, status="error", message=msg)
		booking = bookings[0]

	result["seat"] = seat_label(booking.seat)
	result["zone"] = frappe.db.get_value("Study Zone", booking.zone, "zone_name")

	if cint(settings.block_entry_if_fee_due) and flt(booking.outstanding_amount) > 0:
		return dict(
			result,
			status="error",
			message=_("Fee due: {0}. Please pay at the desk to enter.").format(
				frappe.format(booking.outstanding_amount, "Currency")
			),
		)

	frappe.get_doc(
		{
			"doctype": "Attendance Log",
			"student": stu.name,
			"booking": booking.name,
			"branch": branch,
			"seat": booking.seat,
			"check_in": now,
			"source": source,
		}
	).insert(ignore_permissions=True)

	first_name = (stu.full_name or "").split(" ")[0]
	notes = []
	days_left = date_diff(booking.to_date, today)
	if days_left <= cint(settings.expiry_warning_days):
		when = _("today") if days_left == 0 else _("in {0} day(s)").format(days_left)
		notes.append(_("Your plan ends {0}. Please renew at the desk.").format(when))
	overdue_lockers = frappe.get_all(
		"Locker Allocation",
		filters={"student": stu.name, "docstatus": 1, "status": "Overdue"},
		pluck="locker",
	)
	if overdue_lockers:
		labels = ", ".join(frappe.db.get_value("Locker", l, "locker_no") for l in overdue_lockers)
		notes.append(_("Locker {0} rent is overdue. Please renew at the desk.").format(labels))

	if notes:
		return dict(
			result,
			status="warning",
			action="IN",
			message=_("Welcome {0}!").format(first_name) + " " + " ".join(notes),
		)
	return dict(result, status="success", action="IN", message=_("Welcome {0}! Happy studying.").format(first_name))


def no_booking_message(student: str, branch: str, today) -> str:
	last = frappe.get_all(
		"Seat Booking",
		filters={"student": student, "branch": branch, "docstatus": 1, "to_date": ("<", today)},
		fields=["to_date"],
		order_by="to_date desc",
		limit=1,
	)
	if last:
		return _("Your plan expired on {0}. Please renew at the desk.").format(
			frappe.format(last[0].to_date, "Date")
		)
	return _("No active booking at this branch. Please contact the desk.")


def seat_label(seat: str | None) -> str:
	return frappe.db.get_value("Seat", seat, "seat_no") if seat else ""


def auto_check_out():
	"""Hourly: close attendance left open after the branch closed (or from previous days)."""
	now = now_datetime()
	open_logs = frappe.get_all(
		"Attendance Log",
		filters={"check_out": ("is", "not set")},
		fields=["name", "branch", "attendance_date", "check_in"],
	)
	closing = dict(frappe.get_all("Pathshala Branch", fields=["name", "closing_time"], as_list=True))
	for row in open_logs:
		close_at = datetime.combine(getdate(row.attendance_date), to_time(closing.get(row.branch)))
		if close_at > now:
			continue
		log = frappe.get_doc("Attendance Log", row.name)
		log.check_out = max(close_at, get_datetime(row.check_in))
		log.auto_checked_out = 1
		log.save(ignore_permissions=True)
