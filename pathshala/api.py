import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import cint, today

from pathshala.attendance import punch
from pathshala.pathshala.doctype.student.student import QR_PREFIX
from pathshala.utils import normalize_mobile

STAFF_ROLES = {"System Manager", "Pathshala Manager", "Pathshala Staff"}
MAX_PIN_FAILURES = 5
LOCKOUT_SECONDS = 10 * 60


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
	return punch(student, branch, source="Kiosk")


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
