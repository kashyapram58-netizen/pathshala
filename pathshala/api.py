import secrets

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import cint, today

from pathshala.attendance import change_seat, free_seats, punch
from pathshala.pathshala.doctype.student.student import QR_PREFIX
from pathshala.utils import normalize_mobile

STAFF_ROLES = {"System Manager", "Pathshala Manager", "Pathshala Staff"}
MAX_PIN_FAILURES = 5
LOCKOUT_SECONDS = 10 * 60
SEAT_TOKEN_KEY = "pathshala:seat_token:"
SEAT_TOKEN_SECONDS = 3 * 60


def get_kiosk_branch(branch: str | None = None) -> str:
	"""Kiosk users are pinned to their device's branch; staff may pick any branch."""
	user = frappe.session.user
	if user == "Guest":
		raise frappe.PermissionError
	device_branch = frappe.db.get_value("Kiosk Device", {"user": user, "enabled": 1}, "branch")
	if device_branch:
		return device_branch
	if STAFF_ROLES & set(frappe.get_roles()):
		if not branch:
			branch = frappe.db.get_value("Pathshala Branch", {"is_active": 1}, "name", order_by="creation")
		if branch and frappe.db.exists("Pathshala Branch", branch):
			return branch
		frappe.throw(_("No branch found. Create a Pathshala Branch first."))
	frappe.throw(_("This login is not registered as a Kiosk Device."), frappe.PermissionError)


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=120, seconds=60)
def kiosk_punch(mobile: str | None = None, pin: str | None = None, qr: str | None = None, branch: str | None = None):
	branch = get_kiosk_branch(branch)
	student = student_from_qr(qr) if qr else student_from_pin(mobile, pin)
	if not student:
		return {"status": "error", "message": _("Invalid mobile number or PIN.")}
	if isinstance(student, dict):
		return student
	result = punch(student, branch, source="Kiosk")
	log = result.pop("log", None)
	if log:
		# Lets the kiosk offer "Choose another seat" for this visit only, for a short time.
		token = secrets.token_urlsafe(16)
		frappe.cache.set_value(f"{SEAT_TOKEN_KEY}{token}", log, expires_in_sec=SEAT_TOKEN_SECONDS)
		result["seat_token"] = token
	return result


def log_from_seat_token(token: str | None) -> str:
	log = frappe.cache.get_value(f"{SEAT_TOKEN_KEY}{token}", expires=True) if token else None
	if not log:
		frappe.throw(_("Seat change timed out. Please ask the desk."))
	return log


@frappe.whitelist()
def kiosk_free_seats(seat_token: str, branch: str | None = None):
	branch = get_kiosk_branch(branch)
	log = frappe.get_doc("Attendance Log", log_from_seat_token(seat_token))
	if log.branch != branch:
		raise frappe.PermissionError
	booking = frappe.db.get_value(
		"Seat Booking", log.booking, ["name", "plan", "zone", "hours_per_day", "seat_mode"], as_dict=True
	)
	stu = frappe.db.get_value("Student", log.student, ["name", "gender"], as_dict=True)
	seats = free_seats(booking, stu, branch, frappe.utils.now_datetime(), exclude_log=log.name)
	current = frappe.db.get_value("Seat", log.seat, ["name", "seat_no", "zone", "seat_type"], as_dict=True)
	if current:
		zone_name = frappe.db.get_value("Study Zone", current.zone, "zone_name")
		seats = [dict(current, zone_name=zone_name, current=1)] + [s for s in seats if s["name"] != current.name]
	return seats


@frappe.whitelist(methods=["POST"])
def kiosk_change_seat(seat_token: str, seat: str, branch: str | None = None):
	branch = get_kiosk_branch(branch)
	log_name = log_from_seat_token(seat_token)
	if frappe.db.get_value("Attendance Log", log_name, "branch") != branch:
		raise frappe.PermissionError
	return change_seat(log_name, seat, assignment="Student")


@frappe.whitelist()
def kiosk_status(branch: str | None = None):
	branch = get_kiosk_branch(branch)
	rows = frappe.db.sql(
		"""
		select z.zone_name, z.gender_policy, count(distinct s.name) as seats, count(distinct a.name) as present
		from `tabStudy Zone` z
		left join `tabSeat` s on s.zone = z.name and s.is_active = 1
		left join `tabAttendance Log` a on a.seat = s.name and a.check_out is null and a.attendance_date = %s
		where z.branch = %s
		group by z.name order by z.zone_name
		""",
		(today(), branch),
		as_dict=True,
	)
	return {"branch": branch, "zones": rows}


@frappe.whitelist()
def staff_punch(student: str, branch: str | None = None):
	"""Manual check-in/out by desk staff (bypasses PIN)."""
	if not STAFF_ROLES & set(frappe.get_roles()):
		raise frappe.PermissionError
	branch = branch or get_kiosk_branch()
	return punch(student, branch, source="Staff")


@frappe.whitelist()
def dashboard_stats() -> dict:
	"""Live numbers for the Pathshala workspace overview."""
	if not STAFF_ROLES & set(frappe.get_roles()):
		raise frappe.PermissionError
	now = frappe.utils.now_datetime()
	date, time = now.date(), now.time().strftime("%H:%M:%S")

	def scalar(query, *args):
		return frappe.db.sql(query, args)[0][0] or 0

	seats_total = frappe.db.count("Seat", {"is_active": 1})
	# Seats reserved by fixed bookings right now, plus seats Flexi students are sitting on.
	seats_booked_now = scalar(
		"""select count(*) from (
			select seat from `tabSeat Booking`
			where docstatus = 1 and status = 'Active' and ifnull(seat, '') != ''
				and from_date <= %s and to_date >= %s and from_time <= %s and to_time > %s
			union
			select seat from `tabAttendance Log` where check_out is null and ifnull(seat, '') != ''
		) s""",
		date, date, time, time,
	)
	fees_due = sum(
		scalar(
			f"""select sum(outstanding_amount) from `tab{dt}`
			where docstatus = 1 and status != 'Cancelled' and outstanding_amount > 0"""
		)
		for dt in ("Seat Booking", "Locker Allocation")
	)
	return {
		"present_now": frappe.db.count("Attendance Log", {"attendance_date": date, "check_out": ("is", "not set")}),
		"checkins_today": frappe.db.count("Attendance Log", {"attendance_date": date}),
		"seats_total": seats_total,
		"seats_booked_now": seats_booked_now,
		"occupancy": round(seats_booked_now * 100 / seats_total) if seats_total else 0,
		"active_students": scalar(
			"select count(distinct student) from `tabSeat Booking` where docstatus = 1 and status = 'Active'"
		),
		"expiring_week": frappe.db.count(
			"Seat Booking",
			{"docstatus": 1, "status": "Active", "to_date": ("between", (date, frappe.utils.add_days(date, 7)))},
		),
		"fees_due": fees_due,
		"collection_today": scalar(
			"select sum(amount) from `tabFee Payment` where docstatus = 1 and posting_date = %s", date
		),
		"lockers_total": frappe.db.count("Locker"),
		"lockers_free": frappe.db.count("Locker", {"status": "Available"}),
		"lockers_overdue": frappe.db.count("Locker", {"status": "Overdue"}),
	}


def student_from_qr(qr: str) -> str | None:
	token = (qr or "").strip()
	if token.startswith(QR_PREFIX):
		token = token[len(QR_PREFIX) :]
	return frappe.db.get_value("Student", {"qr_token": token}, "name") if token else None


def student_from_pin(mobile: str | None, pin: str | None):
	mobile = normalize_mobile(mobile)
	if len(mobile) != 10 or not pin:
		return None
	student = frappe.db.get_value("Student", {"mobile": mobile}, "name")
	if not student:
		return None

	key = f"pathshala:pin_failures:{student}"
	failures = cint(frappe.cache.get_value(key, expires=True))
	if failures >= MAX_PIN_FAILURES:
		return {"status": "error", "message": _("Too many wrong PIN attempts. Try again in 10 minutes or contact the desk.")}

	from frappe.utils.password import get_decrypted_password

	saved_pin = get_decrypted_password("Student", student, "kiosk_pin", raise_exception=False)
	if not saved_pin or saved_pin != str(pin).strip():
		frappe.cache.set_value(key, failures + 1, expires_in_sec=LOCKOUT_SECONDS)
		return None
	frappe.cache.delete_value(key)
	return student
