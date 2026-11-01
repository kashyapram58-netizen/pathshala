# Copyright (c) 2026, Ram and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class StudyZone(Document):
	def autoname(self):
		self.name = f"{self.zone_name} - {self.branch}"
