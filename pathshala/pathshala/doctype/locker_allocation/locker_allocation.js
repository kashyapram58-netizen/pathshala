// Copyright (c) 2026, Ram and contributors
// For license information, please see license.txt

const LA_METHOD = "pathshala.pathshala.doctype.locker_allocation.locker_allocation";

frappe.ui.form.on("Locker Allocation", {
	setup(frm) {
		frm.set_query("locker", () => ({
			filters: frm.doc.renewed_from
				? { branch: frm.doc.branch }
				: { branch: frm.doc.branch, status: "Available" },
		}));
		frm.set_query("plan", () => ({ filters: { is_active: 1 } }));
		frm.set_query("student", () => ({ filters: { status: "Active" } }));
	},

	refresh(frm) {
		if (frm.doc.docstatus !== 1) return;
		const open = ["Active", "Overdue"].includes(frm.doc.status);

		if (frm.doc.outstanding_amount > 0) {
			frm.add_custom_button(__("Receive Payment"), () =>
				frappe.model.open_mapped_doc({ method: `${LA_METHOD}.make_payment`, frm })
			);
		}
		if (open) {
			frm.add_custom_button(__("Renew"), () =>
				frappe.model.open_mapped_doc({ method: `${LA_METHOD}.make_renewal`, frm })
			);
			frm.add_custom_button(__("Release Locker"), () => release(frm));
		}
		if (frm.doc.status === "Overdue") {
			frm.dashboard.set_headline_alert(
				__("This locker is overdue since {0}. Renew or release it.", [frappe.datetime.str_to_user(frm.doc.to_date)]),
				"red"
			);
		}
	},

	branch(frm) {
		frm.set_value("locker", null);
	},
});

function release(frm) {
	frappe.xcall(`${LA_METHOD}.get_release_details`, { name: frm.doc.name }).then((info) => {
		if (info.outstanding_amount > 0) {
			frappe.msgprint(
				__("Collect the outstanding {0} before releasing.", [format_currency(info.outstanding_amount)])
			);
			return;
		}
		const d = new frappe.ui.Dialog({
			title: __("Release Locker {0}", [frm.doc.locker]),
			fields: [
				{ fieldname: "key_returned", fieldtype: "Check", label: __("Key returned / lock cleared"), default: 1 },
				{
					fieldname: "deposit_refunded",
					fieldtype: "Currency",
					label: __("Deposit Refunded"),
					default: info.deposit_held,
					description: __("Deposit held: {0}. Deduct for damage or lost key.", [format_currency(info.deposit_held)]),
				},
				{ fieldname: "remarks", fieldtype: "Small Text", label: __("Remarks") },
			],
			primary_action_label: __("Release"),
			primary_action(values) {
				frappe.xcall(`${LA_METHOD}.release_locker`, Object.assign({ name: frm.doc.name }, values)).then(() => {
					d.hide();
					frappe.show_alert({ message: __("Locker released"), indicator: "green" });
					frm.reload_doc();
				});
			},
		});
		d.show();
	});
}
