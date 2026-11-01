# Copyright (c) 2026, Ram and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from pathshala.utils import to_time


class StudyShift(Document):
	def validate(self):
		if to_time(self.end_time) <= to_time(self.start_time):
			frappe.throw(_("End Time must be after Start Time. Overnight shifts are not supported."))
