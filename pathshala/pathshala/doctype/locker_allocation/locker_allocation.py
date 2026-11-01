# Copyright (c) 2026, Ram and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, add_months, flt, getdate, today

from pathshala.pathshala.doctype.locker.locker import refresh_locker_status
from pathshala.utils import get_fee_status, new_fee_payment, validate_gender_policy


class LockerAllocation(Document):
	def validate(self):
		self.plan_doc = frappe.get_cached_doc("Locker Plan", self.plan)
		self.validate_locker()
		self.validate_plan()
		self.set_dates()
		self.set_amounts()
		self.validate_conflicts()

	def before_submit(self):
		self.status = "Active" if getdate(self.to_date) >= getdate(today()) else "Overdue"

	def on_submit(self):
		if self.renewed_from:
			frappe.db.set_value("Locker Allocation", self.renewed_from, "status", "Renewed")
		refresh_locker_status(self.locker)

	def on_cancel(self):
		self.db_set("status", "Cancelled")
		if self.renewed_from and frappe.db.get_value("Locker Allocation", self.renewed_from, "status") == "Renewed":
			source_to = frappe.db.get_value("Locker Allocation", self.renewed_from, "to_date")
			status = "Active" if getdate(source_to) >= getdate(today()) else "Overdue"
			frappe.db.set_value("Locker Allocation", self.renewed_from, "status", status)
		refresh_locker_status(self.locker)

	# ------------------------------------------------------------ validations
	def validate_locker(self):
		locker = frappe.db.get_value("Locker", self.locker, ["branch", "zone", "size", "under_maintenance"], as_dict=True)
		if locker.branch != self.branch:
			frappe.throw(_("Locker {0} does not belong to branch {1}.").format(self.locker, self.branch))
		if locker.under_maintenance and self.docstatus == 0:
			frappe.throw(_("Locker {0} is under maintenance.").format(self.locker))
		self.size = locker.size
		validate_gender_policy(self.student, locker.zone, _("Locker {0}").format(self.locker))

	def validate_plan(self):
		plan = self.plan_doc
		if not plan.is_active and self.docstatus == 0:
			frappe.throw(_("Plan {0} is not active.").format(plan.name))
		if plan.branch and plan.branch != self.branch:
			frappe.throw(_("Plan {0} is only for branch {1}.").format(plan.name, plan.branch))
		if plan.size and plan.size != self.size:
			frappe.throw(_("Plan {0} is only for {1} lockers.").format(plan.name, plan.size))

	def set_dates(self):
		self.to_date = add_days(add_months(self.from_date, self.plan_doc.duration_months), -1)

	def set_amounts(self):
		self.rent = flt(self.plan_doc.rate)
		# The deposit is collected once; renewals carry it forward.
		self.security_deposit = 0 if self.renewed_from else flt(self.plan_doc.security_deposit)
		if flt(self.discount) < 0 or flt(self.discount) > self.rent:
			frappe.throw(_("Discount must be between 0 and the rent."))
		self.net_amount = self.rent + self.security_deposit - flt(self.discount)
		self.paid_amount = flt(self.paid_amount)
		self.outstanding_amount = self.net_amount - self.paid_amount
		self.fee_status = get_fee_status(self.net_amount, self.paid_amount)

	def validate_conflicts(self):
		"""An Overdue allocation still holds the student's things, so it blocks the locker until released."""
		clash = frappe.db.sql(
			"""
			select name, student_name, status, to_date from `tabLocker Allocation`
			where locker = %(locker)s and docstatus = 1 and name not in (%(name)s, %(renewed_from)s)
				and (status = 'Overdue'
					or (status = 'Active' and from_date <= %(to_date)s and to_date >= %(from_date)s))
			limit 1
			""",
			dict(
				locker=self.locker,
				name=self.name or "",
				renewed_from=self.renewed_from or "",
				from_date=self.from_date,
				to_date=self.to_date,
			),
			as_dict=True,
		)
		if clash:
			c = clash[0]
			frappe.throw(
				_("Locker {0} is held by {1} ({2}, {3} until {4}).").format(
					self.locker, c.student_name, c.name, _(c.status), frappe.format(c.to_date, "Date")
				),
				title=_("Locker Not Available"),
			)

	# ------------------------------------------------------------ release
	def get_deposit_held(self) -> float:
		"""Deposit collected on this allocation or the first one in its renewal chain."""
		deposit, name, seen = 0.0, self.name, set()
		while name and name not in seen:
			seen.add(name)
			row = frappe.db.get_value("Locker Allocation", name, ["security_deposit", "renewed_from"], as_dict=True)
			deposit += flt(row.security_deposit)
			name = row.renewed_from
		return deposit


@frappe.whitelist()
def get_release_details(name: str) -> dict:
	doc = frappe.get_doc("Locker Allocation", name)
	doc.check_permission("read")
	return {"deposit_held": doc.get_deposit_held(), "outstanding_amount": doc.outstanding_amount}


@frappe.whitelist()
def release_locker(name: str, key_returned: int = 0, deposit_refunded: float = 0, remarks: str | None = None):
	doc = frappe.get_doc("Locker Allocation", name)
	doc.check_permission("write")
	if doc.docstatus != 1 or doc.status not in ("Active", "Overdue"):
		frappe.throw(_("Only Active or Overdue allocations can be released."))
	if flt(doc.outstanding_amount) > 0:
		frappe.throw(
			_("Collect the outstanding {0} before releasing the locker.").format(
				frappe.format(doc.outstanding_amount, "Currency")
			)
		)
	deposit_held = doc.get_deposit_held()
	if flt(deposit_refunded) < 0 or flt(deposit_refunded) > deposit_held:
		frappe.throw(
			_("Deposit refund must be between 0 and {0}.").format(frappe.format(deposit_held, "Currency"))
		)
	doc.db_set(
		{
			"status": "Released",
			"released_on": today(),
			"key_returned": frappe.utils.cint(key_returned),
			"deposit_refunded": flt(deposit_refunded),
			"release_remarks": remarks,
		}
	)
	doc.add_comment(
		"Info",
		_("Locker released. Deposit refunded: {0}").format(frappe.format(deposit_refunded, "Currency")),
	)
	refresh_locker_status(doc.locker)
	return doc.status


@frappe.whitelist()
def make_renewal(source_name: str):
	source = frappe.get_doc("Locker Allocation", source_name)
	source.check_permission("read")
	if source.status not in ("Active", "Overdue"):
		frappe.throw(_("Only Active or Overdue allocations can be renewed."))
	doc = frappe.new_doc("Locker Allocation")
	for field in ("student", "branch", "locker", "plan", "key_no", "key_issued", "remarks"):
		doc.set(field, source.get(field))
	doc.from_date = add_days(source.to_date, 1)
	doc.renewed_from = source.name
	return doc


@frappe.whitelist()
def make_payment(source_name: str):
	source = frappe.get_doc("Locker Allocation", source_name)
	source.check_permission("read")
	return new_fee_payment(source)


def mark_overdue():
	"""Daily: allocations past their end date that were not renewed or released."""
	rows = frappe.get_all(
		"Locker Allocation",
		filters={"docstatus": 1, "status": "Active", "to_date": ("<", today())},
		fields=["name", "locker"],
	)
	for row in rows:
		frappe.db.set_value("Locker Allocation", row.name, "status", "Overdue")
		refresh_locker_status(row.locker)
