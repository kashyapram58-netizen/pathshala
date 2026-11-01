# Copyright (c) 2026, Ram and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

PAYABLE_DOCTYPES = ("Seat Booking", "Locker Allocation")


class FeePayment(Document):
	def validate(self):
		if self.reference_doctype not in PAYABLE_DOCTYPES:
			frappe.throw(_("Payments can only be made against {0}.").format(", ".join(PAYABLE_DOCTYPES)))
		ref = frappe.db.get_value(
			self.reference_doctype,
			self.reference_name,
			["docstatus", "student", "outstanding_amount"],
			as_dict=True,
		)
		if not ref or ref.docstatus != 1:
			frappe.throw(
				_("{0} {1} must be submitted before taking payment.").format(
					_(self.reference_doctype), self.reference_name
				)
			)
		self.student = ref.student
		self.outstanding_amount = ref.outstanding_amount
		if flt(self.amount) <= 0:
			frappe.throw(_("Amount must be greater than zero."))
		if flt(self.amount) > flt(ref.outstanding_amount):
			frappe.throw(
				_("Amount cannot be more than the outstanding amount {0}.").format(
					frappe.format(ref.outstanding_amount, "Currency")
				)
			)
		if self.mode_of_payment != "Cash" and not self.reference_no:
			frappe.throw(_("Transaction Ref No is required for {0} payments.").format(self.mode_of_payment))

	def on_submit(self):
		self.update_reference()

	def on_cancel(self):
		self.update_reference()

	def update_reference(self):
		from pathshala.utils import set_payment_totals

		set_payment_totals(frappe.get_doc(self.reference_doctype, self.reference_name))
