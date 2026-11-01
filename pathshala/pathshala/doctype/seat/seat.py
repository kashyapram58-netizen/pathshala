# Copyright (c) 2026, Ram and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Seat(Document):
	def autoname(self):
		self.clean_seat_no()
		branch = frappe.db.get_value("Study Zone", self.zone, "branch")
		self.name = f"{branch}-{self.seat_no}"

	def validate(self):
		self.clean_seat_no()

	def clean_seat_no(self):
		self.seat_no = (self.seat_no or "").strip().upper()
