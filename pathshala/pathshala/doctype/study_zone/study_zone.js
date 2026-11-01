// Copyright (c) 2026, Ram and contributors
// For license information, please see license.txt

frappe.ui.form.on("Study Zone", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("Add Seats"), () =>
			pathshala.bulk_seats({ zone: frm.doc.name, on_done: () => frm.reload_doc() })
		);
		frm.add_custom_button(__("View Seats"), () => frappe.set_route("List", "Seat", { zone: frm.doc.name }));
	},
});
