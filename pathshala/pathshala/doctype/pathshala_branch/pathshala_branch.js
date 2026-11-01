// Copyright (c) 2026, Ram and contributors
// For license information, please see license.txt

frappe.ui.form.on("Pathshala Branch", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(
			__("Add Zone"),
			() => frappe.new_doc("Study Zone", { branch: frm.doc.name }),
			__("Setup")
		);
		frm.add_custom_button(__("Add Seats"), () => pathshala.bulk_seats(), __("Setup"));
		frm.add_custom_button(__("Add Lockers"), () => pathshala.bulk_lockers({ branch: frm.doc.name }), __("Setup"));
		frm.add_custom_button(__("Seat & Locker Map"), () => frappe.set_route("seat-map"));
	},
});
