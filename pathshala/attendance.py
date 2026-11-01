"""Check-in / check-out rules shared by the kiosk and staff."""

from datetime import datetime, timedelta

import frappe
from frappe import _
from frappe.utils import cint, date_diff, flt, get_datetime, getdate, now_datetime

from pathshala.utils import fmt_time, format_minutes, natural_key, shift_time, to_time


def punch(student: str, branch: str, source: str = "Kiosk") -> dict:
	"""Toggle a student's attendance at a branch and return a kiosk-friendly result."""
	settings = frappe.get_cached_doc("Pathshala Settings")
	now = now_datetime()
	stu = frappe.db.get_value("Student", student, ["name", "full_name", "photo", "status", "gender"], as_dict=True)
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
	result.update(action="OUT", seat=seat_label(log.seat))

	if log.allowance_minutes:
		used = cint(log.used_before_minutes) + cint(log.duration_minutes)
		message = _("Goodbye! You used {0} of your {1} today.").format(
			format_minutes(used), format_minutes(log.allowance_minutes)
		)
		if flt(log.extra_amount):
			message += " " + _("Overstay {0}: {1} added to your dues.").format(
				format_minutes(log.extra_minutes), frappe.format(log.extra_amount, "Currency")
			)
			return dict(result, status="warning", message=message)
		return dict(result, status="success", message=message)

	total_today = frappe.db.sql(
		"""select sum(duration_minutes) from `tabAttendance Log`
		where student = %s and attendance_date = %s""",
		(log.student, log.attendance_date),
	)[0][0]
	return dict(result, status="success", message=_("Goodbye! You studied {0} today.").format(format_minutes(total_today)))


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
		fields=[
			"name", "seat", "zone", "plan", "seat_mode", "hours_per_day",
			"from_time", "to_time", "to_date", "outstanding_amount",
		],
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

	if cint(settings.block_entry_if_fee_due) and flt(booking.outstanding_amount) > 0:
		return dict(
			result,
			status="error",
			message=_("Fee due: {0}. Please pay at the desk to enter.").format(
				frappe.format(booking.outstanding_amount, "Currency")
			),
		)

	seat, assignment = booking.seat, "Booking"
	if booking.seat_mode == "Flexi":
		free = free_seats(booking, stu, branch, now)
		if not free:
			return dict(result, status="error", message=_("Sorry, no seat is free right now. Please check with the desk."))
		seat, assignment = free[0]["name"], "Auto" if source == "Kiosk" else "Staff"

	log = frappe.get_doc(
		{
			"doctype": "Attendance Log",
			"student": stu.name,
			"booking": booking.name,
			"branch": branch,
			"seat": seat,
			"seat_assignment": assignment,
			"check_in": now,
			"source": source,
		}
	).insert(ignore_permissions=True)

	result["seat"] = seat_label(seat)
	result["zone"] = frappe.db.get_value("Study Zone", frappe.db.get_value("Seat", seat, "zone"), "zone_name") if seat else ""
	if booking.seat_mode == "Flexi":
		result["log"] = log.name
		result["can_change_seat"] = True

	first_name = (stu.full_name or "").split(" ")[0]
	notes, warn = [], False
	if log.allowance_minutes:
		left = log.allowance_minutes - cint(log.used_before_minutes)
		if left > 0:
			notes.append(_("{0} of your {1} left today.").format(format_minutes(left), format_minutes(log.allowance_minutes)))
		else:
			warn = True
			rate = frappe.format(get_overstay_rate(booking.name), "Currency")
			notes.append(_("Today's {0} are used up. Extra time is charged at {1}/hr.").format(
				format_minutes(log.allowance_minutes), rate
			))
	days_left = date_diff(booking.to_date, today)
	if days_left <= cint(settings.expiry_warning_days):
		warn = True
		when = _("today") if days_left == 0 else _("in {0} day(s)").format(days_left)
		notes.append(_("Your plan ends {0}. Please renew at the desk.").format(when))
	overdue_lockers = frappe.get_all(
		"Locker Allocation",
		filters={"student": stu.name, "docstatus": 1, "status": "Overdue"},
		pluck="locker",
	)
	if overdue_lockers:
		warn = True
		labels = ", ".join(frappe.db.get_value("Locker", l, "locker_no") for l in overdue_lockers)
		notes.append(_("Locker {0} rent is overdue. Please renew at the desk.").format(labels))

	message = _("Welcome {0}!").format(first_name) + " " + (" ".join(notes) or _("Happy studying."))
	return dict(result, status="warning" if warn else "success", action="IN", message=message)


# ------------------------------------------------------------------ flexi seats
def allowed_zones(branch: str, gender: str | None, plan_policy: str | None) -> list[str]:
	"""Girls may sit in Girls Only and Co-ed zones; everyone else in Co-ed only."""
	policies = {"Co-ed", "Girls Only"} if gender == "Female" else {"Co-ed"}
	if plan_policy:
		policies &= {plan_policy}
	return frappe.get_all(
		"Study Zone", filters={"branch": branch, "gender_policy": ("in", list(policies) or [""])}, pluck="name"
	)


def free_seats(booking, stu, branch: str, now: datetime, exclude_log: str | None = None) -> list[dict]:
	"""Seats a Flexi student may take right now, best first.

	A seat is free when nobody is sitting on it and no fixed booking reserves it for the
	time the student is likely to stay (their remaining hours today, at least one hour).
	"""
	plan = frappe.db.get_value("Seat Plan", booking.plan, ["gender_policy", "seat_type"], as_dict=True)
	zones = allowed_zones(branch, stu.gender, plan.gender_policy)
	if not zones:
		return []
	filters = {"zone": ("in", zones), "is_active": 1}
	if plan.seat_type:
		filters["seat_type"] = plan.seat_type
	seats = frappe.get_all("Seat", filters=filters, fields=["name", "seat_no", "zone", "seat_type"])

	occupied = set(
		frappe.get_all(
			"Attendance Log",
			filters={"check_out": ("is", "not set"), "seat": ("is", "set"), "name": ("!=", exclude_log or "")},
			pluck="seat",
		)
	)

	used = cint(
		frappe.db.sql(
			"select sum(duration_minutes) from `tabAttendance Log` where booking = %s and attendance_date = %s",
			(booking.name, now.date()),
		)[0][0]
	)
	stay = max(int(flt(booking.hours_per_day) * 60) - used, 60)
	closing = to_time(frappe.db.get_value("Pathshala Branch", branch, "closing_time"))
	leave_by = now + timedelta(minutes=stay)
	window_end = min(leave_by.time(), closing) if leave_by.date() == now.date() else closing
	reserved = set(
		frappe.db.sql_list(
			"""select seat from `tabSeat Booking`
			where docstatus = 1 and status = 'Active' and ifnull(seat, '') != '' and name != %s
				and from_date <= %s and to_date >= %s and from_time < %s and to_time > %s""",
			(booking.name, now.date(), now.date(), window_end, now.time()),
		)
	)

	last_seat = frappe.db.get_value(
		"Attendance Log", {"student": stu.name, "seat": ("is", "set")}, "seat", order_by="check_in desc"
	)
	zone_info = {
		z.name: z
		for z in frappe.get_all("Study Zone", filters={"name": ("in", zones)}, fields=["name", "zone_name", "gender_policy"])
	}
	zone_names = {name: z.zone_name for name, z in zone_info.items()}

	# Girls are seated in Girls Only zones first, keeping Co-ed seats for everyone else.
	free = [s for s in seats if s.name not in occupied and s.name not in reserved]
	free.sort(
		key=lambda s: (
			s.name != last_seat,
			s.zone != booking.zone,
			zone_info[s.zone].gender_policy != "Girls Only",
			zone_names[s.zone] or "",
			natural_key(s.seat_no),
		)
	)
	return [dict(s, zone_name=zone_names.get(s.zone)) for s in free]


def change_seat(log_name: str, seat: str, assignment: str = "Student") -> dict:
	log = frappe.get_doc("Attendance Log", log_name)
	if log.check_out:
		frappe.throw(_("This visit is already closed."))
	booking = frappe.db.get_value(
		"Seat Booking", log.booking, ["name", "plan", "zone", "hours_per_day", "seat_mode"], as_dict=True
	)
	if not booking or booking.seat_mode != "Flexi":
		frappe.throw(_("Seat can only be changed for Flexi plans."))
	stu = frappe.db.get_value("Student", log.student, ["name", "gender"], as_dict=True)
	if seat not in {s["name"] for s in free_seats(booking, stu, log.branch, now_datetime(), exclude_log=log.name)}:
		frappe.throw(_("Seat {0} is not available.").format(seat_label(seat) or seat))
	log.seat = seat
	log.seat_assignment = assignment
	log.save(ignore_permissions=True)
	zone = frappe.db.get_value("Seat", seat, "zone")
	return {"seat": seat_label(seat), "zone": frappe.db.get_value("Study Zone", zone, "zone_name")}


def get_overstay_rate(booking: str) -> float:
	from pathshala.pathshala.doctype.attendance_log.attendance_log import get_overstay_rate as rate

	return rate(booking)


# ------------------------------------------------------------------ helpers
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
