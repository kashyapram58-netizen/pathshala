// Desk helpers shared by forms and list views.
frappe.provide("pathshala");

const BULK_METHOD = "pathshala.bulk";

// Number preview like "G1, G2, G3 … G40"
function preview_numbers(prefix, start, count, pad) {
	prefix = (prefix || "").trim().toUpperCase();
	start = cint(start);
	count = cint(count);
	if (count < 1) return "";
	const fmt = (n) => prefix + String(n).padStart(cint(pad), "0");
	const first = [...Array(Math.min(count, 3)).keys()].map((i) => fmt(start + i));
	return count > 3 ? `${first.join(", ")} … ${fmt(start + count - 1)}` : first.join(", ");
}

function bulk_dialog({ title, scope_field, scope_value, defaults, extra_fields, next_method, create_method, scope_arg, on_done }) {
	const d = new frappe.ui.Dialog({
		title,
		fields: [
			scope_field,
			{ fieldtype: "Section Break" },
			{ fieldname: "prefix", label: __("Prefix"), fieldtype: "Data", default: defaults.prefix, description: __("e.g. G for G1, G2…") },
			{ fieldname: "start", label: __("Start Number"), fieldtype: "Int", default: 1 },
			{ fieldtype: "Column Break" },
			{ fieldname: "count", label: __("How Many"), fieldtype: "Int", default: defaults.count || 10, reqd: 1 },
			{ fieldname: "pad", label: __("Zero Padding"), fieldtype: "Select", options: ["0", "2", "3"], default: "0", description: __("2 → G01, G02…") },
			{ fieldtype: "Section Break" },
			...extra_fields,
			{ fieldtype: "Section Break" },
			{ fieldname: "preview", fieldtype: "HTML" },
		],
		primary_action_label: __("Create"),
		primary_action(values) {
			const args = Object.assign({}, values, { [scope_arg]: values[scope_field.fieldname] });
			delete args.preview;
			frappe
				.xcall(`${BULK_METHOD}.${create_method}`, args, { freeze: true, freeze_message: __("Creating…") })
				.then((r) => {
					d.hide();
					let msg = __("{0} created.", [`<b>${r.created.length}</b>`]);
					if (r.skipped.length) msg += "<br>" + __("Skipped (already exist): {0}", [r.skipped.join(", ")]);
					frappe.msgprint({ title: __("Done"), message: msg, indicator: "green" });
					on_done && on_done(r);
				});
		},
	});

	const refresh_preview = () => {
		const v = d.get_values(true);
		const text = preview_numbers(v.prefix, v.start, v.count, v.pad);
		d.fields_dict.preview.$wrapper.html(
			text ? `<div class="text-muted small">${__("Will create")}: <b>${frappe.utils.escape_html(text)}</b></div>` : ""
		);
	};
	// Suggest the next free number for the chosen scope + prefix.
	const suggest_start = () => {
		const scope = d.get_value(scope_field.fieldname);
		if (!scope) return refresh_preview();
		frappe
			.xcall(`${BULK_METHOD}.${next_method}`, { [scope_arg]: scope, prefix: d.get_value("prefix") || "" })
			.then((n) => d.set_value("start", n).then(refresh_preview));
	};

	["start", "count", "pad"].forEach((f) => (d.fields_dict[f].df.onchange = refresh_preview));
	d.fields_dict.prefix.df.onchange = suggest_start;
	d.fields_dict[scope_field.fieldname].df.onchange = () => {
		if (scope_field.on_scope_change) scope_field.on_scope_change(d);
		suggest_start();
	};

	d.show();
	if (scope_value) d.set_value(scope_field.fieldname, scope_value);
	suggest_start();
	return d;
}

pathshala.bulk_seats = function ({ zone, on_done } = {}) {
	return bulk_dialog({
		title: __("Add Seats in Bulk"),
		scope_arg: "zone",
		scope_value: zone,
		scope_field: {
			fieldname: "zone", label: __("Zone"), fieldtype: "Link", options: "Study Zone", reqd: 1,
			on_scope_change: (d) => {
				const z = d.get_value("zone");
				if (z && !d.get_value("prefix")) d.set_value("prefix", z.trim()[0].toUpperCase());
			},
		},
		defaults: { prefix: zone ? zone.trim()[0].toUpperCase() : "", count: 40 },
		extra_fields: [
			{ fieldname: "seat_type", label: __("Seat Type"), fieldtype: "Select", options: ["Normal", "AC", "Cabin"], default: "Normal" },
		],
		next_method: "next_seat_number",
		create_method: "create_seats",
		on_done,
	});
};

pathshala.bulk_lockers = function ({ branch, on_done } = {}) {
	let dialog;
	dialog = bulk_dialog({
		title: __("Add Lockers in Bulk"),
		scope_arg: "branch",
		scope_value: branch,
		scope_field: { fieldname: "branch", label: __("Branch"), fieldtype: "Link", options: "Pathshala Branch", reqd: 1 },
		defaults: { prefix: "L", count: 20 },
		extra_fields: [
			{ fieldname: "size", label: __("Size"), fieldtype: "Select", options: ["Small", "Medium", "Large"], default: "Medium" },
			{ fieldtype: "Column Break" },
			{
				fieldname: "zone", label: __("Zone (optional)"), fieldtype: "Link", options: "Study Zone",
				description: __("Set for lockers inside a Girls Only zone."),
				get_query: () => ({ filters: { branch: dialog && dialog.get_value("branch") } }),
			},
		],
		next_method: "next_locker_number",
		create_method: "create_lockers",
		on_done,
	});
	return dialog;
};
