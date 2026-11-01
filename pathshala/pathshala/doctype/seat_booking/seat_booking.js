// Copyright (c) 2026, Ram and contributors
// For license information, please see license.txt

frappe.ui.form.on("Seat Booking", {
	setup(frm) {
		frm.set_query("zone", () => ({ filters: { branch: frm.doc.branch } }));
		frm.set_query("seat", () => ({ filters: { zone: frm.doc.zone, is_active: 1 } }));
		frm.set_query("plan", () => ({ filters: { is_active: 1 } }));
		frm.set_query("student", () => ({ filters: { status: "Active" } }));
	},

	refresh(frm) {
		if (frm.doc.docstatus !== 1) return;
		if (frm.doc.outstanding_amount > 0) {
			frm.add_custom_button(__("Receive Payment"), () =>
				frappe.model.open_mapped_doc({
					method: "pathshala.pathshala.doctype.seat_booking.seat_booking.make_payment",
					frm,
				})
			);
		}
		if (frm.doc.booking_type !== "Hourly" && frm.doc.status !== "Cancelled") {
			frm.add_custom_button(__("Renew"), () =>
				frappe.model.open_mapped_doc({
					method: "pathshala.pathshala.doctype.seat_booking.seat_booking.make_renewal",
					frm,
				})
			);
		}
	},

	branch(frm) {
		frm.set_value("zone", null);
	},

	plan(frm) {
		if (!frm.doc.plan) return;
		frappe.db
			.get_value("Seat Plan", frm.doc.plan, ["booking_type", "shift_type", "fixed_seat", "hours_per_day"])
			.then(({ message: p }) => {
				// Daily Hours without a reserved seat = Flexi: a free seat is given at each check-in.
				const flexi = p.booking_type === "Shift" && p.shift_type === "Daily Hours" && !p.fixed_seat;
				frm.set_value("seat_mode", flexi ? "Flexi" : "Fixed");
				frm.set_value("hours_per_day", p.shift_type === "Daily Hours" ? p.hours_per_day : 0);
				if (flexi) frm.set_value("seat", null);
			});
	},

	zone(frm) {
		frm.set_value("seat", null);
	},
});
