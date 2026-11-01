# Copyright (c) 2026, Ram and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class Locker(Document):
	def autoname(self):
		self.clean_locker_no()
		self.name = f"{self.branch}-{self.locker_no}"

	def validate(self):
		self.clean_locker_no()
		if self.zone and frappe.db.get_value("Study Zone", self.zone, "branch") != self.branch:
			frappe.throw(_("Zone {0} does not belong to branch {1}.").format(self.zone, self.branch))
		self.update(get_locker_status(self.name, self.under_maintenance))

	def clean_locker_no(self):
		self.locker_no = (self.locker_no or "").strip().upper()


def get_locker_status(locker: str, under_maintenance: int = 0) -> dict:
	current = frappe.db.get_value(
		"Locker Allocation",
		{"locker": locker, "docstatus": 1, "status": ("in", ("Active", "Overdue"))},
		["name", "student_name", "status"],
		as_dict=True,
		order_by="from_date desc",
	)
	if current:
		return {
			"status": "Overdue" if current.status == "Overdue" else "Occupied",
			"current_allocation": current.name,
			"current_student": current.student_name,
		}
	return {
		"status": "Maintenance" if under_maintenance else "Available",
		"current_allocation": None,
		"current_student": None,
	}


def refresh_locker_status(locker: str):
	under_maintenance = frappe.db.get_value("Locker", locker, "under_maintenance")
	frappe.db.set_value("Locker", locker, get_locker_status(locker, under_maintenance), update_modified=False)
