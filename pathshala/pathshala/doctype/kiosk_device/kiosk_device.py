# Copyright (c) 2026, Ram and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class KioskDevice(Document):
	def validate(self):
		roles = frappe.get_roles(self.user)
		privileged = {"System Manager", "Administrator", "Pathshala Manager", "Pathshala Staff"} & set(roles)
		if privileged:
			frappe.msgprint(
				_("User {0} has roles {1}. A kiosk user should only have the Pathshala Kiosk role.").format(
					self.user, ", ".join(sorted(privileged))
				),
				indicator="orange",
				alert=True,
			)
