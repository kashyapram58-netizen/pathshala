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

	zone(frm) {
		frm.set_value("seat", null);
	},
});
