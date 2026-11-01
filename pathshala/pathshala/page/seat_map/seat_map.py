import frappe
from frappe.utils import cint, date_diff, flt, getdate, nowdate, nowtime

from pathshala.api import STAFF_ROLES
from pathshala.utils import fmt_time, natural_key, to_time


def check_access():
	if not STAFF_ROLES & set(frappe.get_roles()):
		raise frappe.PermissionError


@frappe.whitelist()
def get_seat_map(branch: str, date: str | None = None, time: str | None = None) -> dict:
	"""Seats of a branch grouped by zone, with their state at the given date and time."""
	check_access()
	date = getdate(date or nowdate())
	at = to_time(time or nowtime())
	expiry_days = cint(frappe.db.get_single_value("Pathshala Settings", "expiry_warning_days")) or 3

	seats = frappe.get_all(
		"Seat",
		filters={"branch": branch},
		fields=["name", "seat_no", "zone", "seat_type", "is_active"],
	)
	seats.sort(key=lambda s: natural_key(s.seat_no))
	bookings = frappe.get_all(
		"Seat Booking",
		filters={
			"branch": branch,
			"docstatus": 1,
			"status": ("!=", "Cancelled"),
			"from_date": ("<=", date),
			"to_date": (">=", date),
		},
		fields=[
			"name", "seat", "student", "student_name", "booking_type", "shift",
			"from_time", "to_time", "to_date", "outstanding_amount",
		],
		order_by="from_time asc",
	)
	# Who is sitting where right now (Flexi students get their seat at check-in).
	present = {}
	if date == getdate(nowdate()):
		for log in frappe.get_all(
			"Attendance Log",
			filters={"branch": branch, "check_out": ("is", "not set"), "seat": ("is", "set")},
			fields=["seat", "student", "student_name", "booking", "check_in"],
		):
			present[log.seat] = log

	by_seat = {}
	for b in bookings:
		if not b.seat:
			continue
		by_seat.setdefault(b.seat, []).append(
			{
				"name": b.name,
				"student": b.student,
				"student_name": b.student_name,
				"booking_type": b.booking_type,
				"slot": f"{fmt_time(b.from_time)} – {fmt_time(b.to_time)}",
				"active_now": to_time(b.from_time) <= at < to_time(b.to_time),
				"expiring": date_diff(b.to_date, date) <= expiry_days,
				"to_date": b.to_date,
				"fee_due": flt(b.outstanding_amount) > 0,
			}
		)

	zones = {
		z.name: dict(z, seats=[])
		for z in frappe.get_all(
			"Study Zone",
			filters={"branch": branch},
			fields=["name", "zone_name", "gender_policy"],
			order_by="zone_name asc",
		)
	}
	counts = {"free": 0, "partial": 0, "occupied": 0, "maintenance": 0}
	for seat in seats:
		seat_bookings = by_seat.get(seat.name, [])
		current = next((b for b in seat_bookings if b["active_now"]), None)
		walk_in = present.get(seat.name)
		if not current and walk_in:
			current = {
				"name": walk_in.booking,
				"student": walk_in.student,
				"student_name": walk_in.student_name,
				"booking_type": "Flexi",
				"slot": f"in since {fmt_time(walk_in.check_in)}",
				"active_now": True,
				"expiring": False,
				"to_date": None,
				"fee_due": False,
				"flexi": True,
			}
		if not seat.is_active:
			state = "maintenance"
		elif current:
			state = "occupied"
		elif seat_bookings:
			state = "partial"
		else:
			state = "free"
		counts[state] += 1
		if seat.zone in zones:
			zones[seat.zone]["seats"].append(
				{
					"name": seat.name,
					"seat_no": seat.seat_no,
					"seat_type": seat.seat_type,
					"state": state,
					"present": seat.name in present,
					"current": current,
					"bookings": seat_bookings + ([current] if current and current.get("flexi") else []),
					"expiring": bool(current and current["expiring"]),
					"fee_due": any(b["fee_due"] for b in seat_bookings),
				}
			)

	return {"zones": list(zones.values()), "counts": counts, "total": len(seats)}


@frappe.whitelist()
def get_locker_map(branch: str) -> dict:
	check_access()
	lockers = frappe.get_all(
		"Locker",
		filters={"branch": branch},
		fields=["name", "locker_no", "size", "zone", "status", "current_allocation", "current_student"],
	)
	lockers.sort(key=lambda l: natural_key(l.locker_no))
	allocations = {
		a.name: a
		for a in frappe.get_all(
			"Locker Allocation",
			filters={"name": ("in", [l.current_allocation for l in lockers if l.current_allocation] or [""])},
			fields=["name", "student", "to_date", "outstanding_amount", "key_no"],
		)
	}
	counts = {"Available": 0, "Occupied": 0, "Overdue": 0, "Maintenance": 0}
	sizes = {}
	for locker in lockers:
		alloc = allocations.get(locker.current_allocation)
		locker["allocation"] = alloc
		locker["fee_due"] = bool(alloc and flt(alloc.outstanding_amount) > 0)
		counts[locker.status] = counts.get(locker.status, 0) + 1
		sizes.setdefault(locker.size, []).append(locker)

	order = ["Small", "Medium", "Large"]
	groups = [{"size": s, "lockers": sizes[s]} for s in sorted(sizes, key=lambda s: order.index(s) if s in order else 9)]
	return {"groups": groups, "counts": counts, "total": len(lockers)}
