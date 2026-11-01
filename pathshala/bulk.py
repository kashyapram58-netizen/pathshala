"""Create many Seats / Lockers at once (e.g. G1…G40 in a zone)."""

import re

import frappe
from frappe import _
from frappe.utils import cint

MAX_BULK = 500


def make_numbers(prefix: str, start: int, count: int, pad: int) -> list[str]:
	prefix = (prefix or "").strip().upper()
	start, count, pad = cint(start), cint(count), cint(pad)
	if count < 1 or count > MAX_BULK:
		frappe.throw(_("Count must be between 1 and {0}.").format(MAX_BULK))
	if start < 0:
		frappe.throw(_("Start number cannot be negative."))
	return [f"{prefix}{str(n).zfill(pad)}" for n in range(start, start + count)]


def next_number(doctype: str, field: str, filters: dict, prefix: str) -> int:
	"""Highest existing <prefix><number> + 1, so a zone can be topped up later."""
	prefix = (prefix or "").strip().upper()
	pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")
	numbers = [
		int(m.group(1))
		for value in frappe.get_all(doctype, filters=filters, pluck=field)
		if (m := pattern.match((value or "").upper()))
	]
	return max(numbers, default=0) + 1


# ------------------------------------------------------------------ seats
@frappe.whitelist()
def next_seat_number(zone: str, prefix: str = "") -> int:
	branch = frappe.db.get_value("Study Zone", zone, "branch")
	return next_number("Seat", "seat_no", {"branch": branch}, prefix)


@frappe.whitelist()
def create_seats(zone: str, prefix: str = "", start: int = 1, count: int = 1, pad: int = 0, seat_type: str = "Normal"):
	frappe.has_permission("Seat", "create", throw=True)
	branch = frappe.db.get_value("Study Zone", zone, "branch")
	if not branch:
		frappe.throw(_("Zone {0} not found.").format(zone))
	created, skipped = [], []
	for seat_no in make_numbers(prefix, start, count, pad):
		# Seat numbers are unique per branch (name = "<branch>-<seat_no>").
		if frappe.db.exists("Seat", f"{branch}-{seat_no}"):
			skipped.append(seat_no)
			continue
		frappe.get_doc({"doctype": "Seat", "seat_no": seat_no, "zone": zone, "seat_type": seat_type}).insert()
		created.append(seat_no)
	return {"created": created, "skipped": skipped}


# ------------------------------------------------------------------ lockers
@frappe.whitelist()
def next_locker_number(branch: str, prefix: str = "") -> int:
	return next_number("Locker", "locker_no", {"branch": branch}, prefix)


@frappe.whitelist()
def create_lockers(
	branch: str,
	prefix: str = "L",
	start: int = 1,
	count: int = 1,
	pad: int = 0,
	size: str = "Medium",
	zone: str | None = None,
):
	frappe.has_permission("Locker", "create", throw=True)
	created, skipped = [], []
	for locker_no in make_numbers(prefix, start, count, pad):
		if frappe.db.exists("Locker", f"{branch}-{locker_no}"):
			skipped.append(locker_no)
			continue
		frappe.get_doc(
			{"doctype": "Locker", "locker_no": locker_no, "branch": branch, "size": size, "zone": zone or None}
		).insert()
		created.append(locker_no)
	return {"created": created, "skipped": skipped}
