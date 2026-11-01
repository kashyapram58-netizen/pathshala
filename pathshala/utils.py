import re
from datetime import datetime, time, timedelta

import frappe
from frappe import _
from frappe.utils import flt, get_time


def normalize_mobile(mobile: str | None) -> str:
	"""Return the last 10 digits of a mobile number ("+91 98765-43210" -> "9876543210")."""
	digits = re.sub(r"\D", "", mobile or "")
	return digits[-10:]


def validate_mobile(mobile: str | None, label: str = "Mobile") -> str:
	normalized = normalize_mobile(mobile)
	if len(normalized) != 10:
		frappe.throw(_("{0} must be a 10-digit number.").format(_(label)))
	return normalized


def to_time(value) -> time | None:
	"""Normalise Time values coming as str / timedelta / time."""
	if value in (None, ""):
		return None
	return get_time(value)


def minutes_between(start, end) -> int:
	return max(int((end - start).total_seconds() // 60), 0)


def format_minutes(minutes: int) -> str:
	h, m = divmod(int(minutes or 0), 60)
	return f"{h}h {m}m" if h else f"{m}m"


def shift_time(t: time, minutes: int) -> time:
	"""Add (or subtract) minutes to a time, clamped to the same day."""
	seconds = t.hour * 3600 + t.minute * 60 + t.second + minutes * 60
	seconds = min(max(seconds, 0), 24 * 3600 - 1)
	return (datetime.min + timedelta(seconds=seconds)).time()


def get_fee_status(net_amount, paid_amount) -> str:
	if flt(paid_amount) <= 0 and flt(net_amount) > 0:
		return "Unpaid"
	if flt(paid_amount) < flt(net_amount):
		return "Partly Paid"
	return "Paid"


def set_payment_totals(doc):
	"""Recompute paid / outstanding / fee status of a payable doc from its submitted Fee Payments."""
	paid = flt(
		frappe.db.sql(
			"""select sum(amount) from `tabFee Payment`
			where reference_doctype = %s and reference_name = %s and docstatus = 1""",
			(doc.doctype, doc.name),
		)[0][0]
	)
	doc.db_set(
		{
			"paid_amount": paid,
			"outstanding_amount": flt(doc.net_amount) - paid,
			"fee_status": get_fee_status(doc.net_amount, paid),
		}
	)


def new_fee_payment(doc):
	"""Draft Fee Payment for the outstanding amount of a Seat Booking / Locker Allocation."""
	payment = frappe.new_doc("Fee Payment")
	payment.reference_doctype = doc.doctype
	payment.reference_name = doc.name
	payment.student = doc.student
	payment.student_name = doc.student_name
	payment.outstanding_amount = doc.outstanding_amount
	payment.amount = doc.outstanding_amount
	return payment


def validate_gender_policy(student: str, zone: str | None, what: str):
	"""Girls Only zones can only be booked by female students."""
	if not zone or frappe.db.get_value("Study Zone", zone, "gender_policy") != "Girls Only":
		return
	if frappe.db.get_value("Student", student, "gender") != "Female":
		frappe.throw(
			_("{0} is in a Girls Only zone ({1}) and can only be given to female students.").format(what, zone),
			title=_("Girls Only Zone"),
		)


def fmt_time(t) -> str:
	t = to_time(t)
	return t.strftime("%I:%M %p").lstrip("0") if t else ""
