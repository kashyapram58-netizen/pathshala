// Copyright (c) 2026, Ram and contributors
// For license information, please see license.txt

frappe.ui.form.on("Student", {
	refresh(frm) {
		frm.get_field("qr_code").$wrapper.empty();
		if (frm.is_new()) return;

		frappe
			.xcall("pathshala.pathshala.doctype.student.student.get_qr_code", { student: frm.doc.name })
			.then((uri) => {
				if (!uri) return;
				frm.get_field("qr_code").$wrapper.html(
					`<img src="${uri}" style="width:160px;height:160px" alt="QR">
					<div class="text-muted small">${__("Students can scan this at the kiosk")}</div>`
				);
			});

		frm.add_custom_button(__("Check In / Out"), () =>
			frappe
				.xcall("pathshala.api.staff_punch", { student: frm.doc.name })
				.then((r) => {
					const indicator = { success: "green", warning: "orange", info: "blue" }[r.status] || "red";
					frappe.msgprint({ title: r.action ? __("Checked {0}", [r.action]) : __("Not Allowed"), message: r.message, indicator });
				})
		);

		frm.add_custom_button(
			__("Reset Kiosk PIN"),
			() =>
				frappe.confirm(__("Generate a new kiosk PIN for {0}?", [frm.doc.full_name]), () =>
					frappe
						.xcall("pathshala.pathshala.doctype.student.student.reset_kiosk_pin", { student: frm.doc.name })
						.then((pin) => {
							frm.reload_doc();
							frappe.msgprint({
								title: __("New Kiosk PIN"),
								message: __("New PIN for {0} is <b>{1}</b>", [frm.doc.full_name, pin]),
								indicator: "green",
							});
						})
				),
			__("Actions")
		);

		frm.add_custom_button(
			__("New Booking"),
			() => frappe.new_doc("Seat Booking", { student: frm.doc.name }),
			__("Actions")
		);

		frm.add_custom_button(
			__("Rent a Locker"),
			() => frappe.new_doc("Locker Allocation", { student: frm.doc.name }),
			__("Actions")
		);
	},
});
