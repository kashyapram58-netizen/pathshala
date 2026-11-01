// Copyright (c) 2026, Ram and contributors
// For license information, please see license.txt

frappe.ui.form.on("Fee Payment", {
	setup(frm) {
		frm.set_query("reference_name", () => ({
			filters: { docstatus: 1, outstanding_amount: [">", 0] },
		}));
	},

	reference_doctype(frm) {
		frm.set_value("reference_name", null);
	},

	reference_name(frm) {
		if (!frm.doc.reference_name) return;
		frappe.db
			.get_value(frm.doc.reference_doctype, frm.doc.reference_name, ["outstanding_amount", "student"])
			.then((r) => {
				frm.set_value("student", r.message.student);
				frm.set_value("outstanding_amount", r.message.outstanding_amount);
				if (!frm.doc.amount) frm.set_value("amount", r.message.outstanding_amount);
			});
	},
});
