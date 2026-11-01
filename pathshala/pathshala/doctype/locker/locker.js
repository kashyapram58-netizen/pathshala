// Copyright (c) 2026, Ram and contributors
// For license information, please see license.txt

frappe.ui.form.on("Locker", {
	setup(frm) {
		frm.set_query("zone", () => ({ filters: { branch: frm.doc.branch } }));
	},

	refresh(frm) {
		if (frm.is_new()) return;
		if (frm.doc.status === "Available") {
			frm.add_custom_button(__("Allocate"), () =>
				frappe.new_doc("Locker Allocation", { branch: frm.doc.branch, locker: frm.doc.name })
			);
		} else if (frm.doc.current_allocation) {
			frm.add_custom_button(__("View Allocation"), () =>
				frappe.set_route("Form", "Locker Allocation", frm.doc.current_allocation)
			);
		}
	},
});
