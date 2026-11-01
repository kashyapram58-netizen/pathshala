"""Data for the Student ID card print format (exposed to Jinja via hooks)."""

import base64
import mimetypes

import frappe
from frappe.utils import getdate, nowdate

from pathshala.pathshala.doctype.student.student import qr_data_uri
from pathshala.utils import fmt_time


def get_id_card_data(student: str) -> dict:
	doc = frappe.get_doc("Student", student)
	today = getdate(nowdate())
	booking = frappe.db.get_value(
		"Seat Booking",
		{"student": student, "docstatus": 1, "status": "Active", "to_date": (">=", today)},
		["branch", "zone", "seat", "booking_type", "shift", "from_time", "to_time", "to_date"],
		as_dict=True,
		order_by="to_date desc",
	)
	locker = frappe.db.get_value(
		"Locker Allocation",
		{"student": student, "docstatus": 1, "status": ("in", ("Active", "Overdue"))},
		["locker"],
		as_dict=True,
	)
	data = {
		"logo": app_image_uri("pathshala-icon-transparent.png"),
		"photo": file_data_uri(doc.photo),
		"initials": "".join(w[0] for w in (doc.full_name or "?").split()[:2]).upper(),
		"qr": qr_data_uri(doc.qr_token),
		"branch": None,
		"seat": None,
		"zone": None,
		"slot": None,
		"valid_till": None,
		"locker": frappe.db.get_value("Locker", locker.locker, "locker_no") if locker else None,
		"girls_only": False,
	}
	if booking:
		zone = frappe.db.get_value("Study Zone", booking.zone, ["zone_name", "gender_policy"], as_dict=True)
		data.update(
			branch=booking.branch,
			seat=frappe.db.get_value("Seat", booking.seat, "seat_no"),
			zone=zone.zone_name,
			girls_only=zone.gender_policy == "Girls Only",
			slot=f"{booking.shift or booking.booking_type} · {fmt_time(booking.from_time)}–{fmt_time(booking.to_time)}",
			valid_till=booking.to_date,
		)
	return data


def app_image_uri(filename: str) -> str:
	path = frappe.get_app_path("pathshala", "public", "images", filename)
	with open(path, "rb") as f:
		return "data:image/png;base64," + base64.b64encode(f.read()).decode()


def file_data_uri(file_url: str | None) -> str:
	"""Embed an attached image so it renders in PDFs even when the file is private."""
	if not file_url:
		return ""
	name = frappe.db.get_value("File", {"file_url": file_url}, "name")
	if not name:
		return ""
	try:
		content = frappe.get_doc("File", name).get_content()
	except Exception:
		return ""
	if isinstance(content, str):
		content = content.encode()
	mime = mimetypes.guess_type(file_url)[0] or "image/jpeg"
	return f"data:{mime};base64,{base64.b64encode(content).decode()}"
