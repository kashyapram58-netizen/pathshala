# Copyright (c) 2026, Ram and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from pathshala.utils import to_time


class PathshalaBranch(Document):
	def validate(self):
		if to_time(self.closing_time) <= to_time(self.opening_time):
			frappe.throw(_("Closing Time must be after Opening Time."))
