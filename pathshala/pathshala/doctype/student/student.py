# Copyright (c) 2026, Ram and contributors
# For license information, please see license.txt

import secrets

import frappe
from frappe import _
from frappe.model.document import Document

from pathshala.utils import validate_mobile

QR_PREFIX = "PSL:"


class Student(Document):
	def validate(self):
		self.full_name = (self.full_name or "").strip()
		self.mobile = validate_mobile(self.mobile)
		if self.guardian_mobile:
			self.guardian_mobile = validate_mobile(self.guardian_mobile, "Guardian Mobile")
		self.validate_pin()
		self.validate_gender_change()
		if not self.qr_token:
			self.qr_token = secrets.token_urlsafe(16)

	def validate_pin(self):
		if not self.kiosk_pin:
			if self.is_new():
				self._generated_pin = generate_pin()
				self.kiosk_pin = self._generated_pin
			return
		if self.is_dummy_password(self.kiosk_pin):
			return
		if not (self.kiosk_pin.isdigit() and len(self.kiosk_pin) == 4):
			frappe.throw(_("Kiosk PIN must be exactly 4 digits."))

	def validate_gender_change(self):
		"""Changing gender must not leave a non-female student in a Girls Only seat."""
		if self.is_new() or self.gender == "Female" or not self.has_value_changed("gender"):
			return
		if frappe.db.exists(
			"Seat Booking",
			{"student": self.name, "docstatus": 1, "status": "Active", "gender_policy": "Girls Only"},
		):
			frappe.throw(_("This student has an active booking in a Girls Only zone."))

	def after_insert(self):
		if getattr(self, "_generated_pin", None):
			frappe.msgprint(
				_("Kiosk PIN for {0} is <b>{1}</b>. Share it with the student.").format(
					self.full_name, self._generated_pin
				),
				title=_("Kiosk PIN"),
			)


def generate_pin() -> str:
	return f"{secrets.randbelow(10000):04d}"


@frappe.whitelist()
def reset_kiosk_pin(student: str) -> str:
	doc = frappe.get_doc("Student", student)
	doc.check_permission("write")
	pin = generate_pin()
	doc.kiosk_pin = pin
	doc.save()
	return pin


@frappe.whitelist()
def get_qr_code(student: str) -> str:
	doc = frappe.get_doc("Student", student)
	doc.check_permission("read")
	return qr_data_uri(doc.qr_token)


def qr_data_uri(token: str | None) -> str:
	"""Return the student's QR code as a PNG data URI (also usable from print formats)."""
	if not token:
		return ""
	from pyqrcode import create as qrcreate

	return "data:image/png;base64," + qrcreate(QR_PREFIX + token).png_as_base64_str(scale=6, quiet_zone=2)
