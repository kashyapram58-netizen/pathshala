const MAP_METHOD = "pathshala.pathshala.page.seat_map.seat_map";

frappe.pages["seat-map"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Seat & Locker Map"),
		single_column: true,
	});
	wrapper.seat_map = new SeatMap(page);
};

frappe.pages["seat-map"].on_page_show = function (wrapper) {
	wrapper.seat_map && wrapper.seat_map.refresh();
};

class SeatMap {
	constructor(page) {
		this.page = page;
		this.$body = $(`<div class="psl-map"></div>`).appendTo(page.main);
		this.make_filters();
		this.page.set_primary_action(__("Refresh"), () => this.refresh(), "refresh");
		this.timer = setInterval(() => !document.hidden && this.refresh(), 60000);
		frappe.db.get_value("Pathshala Branch", { is_active: 1 }, "name").then((r) => {
			if (r.message && r.message.name && !this.branch.get_value()) this.branch.set_value(r.message.name);
		});
	}

	make_filters() {
		const refresh = () => this.refresh();
		this.view = this.page.add_field({
			fieldname: "view", label: __("View"), fieldtype: "Select",
			options: ["Seats", "Lockers"], default: "Seats",
			change: () => { this.toggle_time_filters(); refresh(); },
		});
		this.branch = this.page.add_field({
			fieldname: "branch", label: __("Branch"), fieldtype: "Link", options: "Pathshala Branch", change: refresh,
		});
		this.date = this.page.add_field({
			fieldname: "date", label: __("Date"), fieldtype: "Date", default: frappe.datetime.get_today(), change: refresh,
		});
		this.time = this.page.add_field({
			fieldname: "time", label: __("Time"), fieldtype: "Time",
			default: frappe.datetime.now_time().slice(0, 5) + ":00", change: refresh,
		});
	}

	toggle_time_filters() {
		const seats = this.view.get_value() === "Seats";
		this.date.$wrapper.toggle(seats);
		this.time.$wrapper.toggle(seats);
	}

	refresh() {
		const branch = this.branch.get_value();
		if (!branch) {
			this.$body.html(`<div class="psl-empty">${__("Select a branch to see the map.")}</div>`);
			return;
		}
		if (this.view.get_value() === "Lockers") {
			frappe.xcall(`${MAP_METHOD}.get_locker_map`, { branch }).then((d) => this.render_lockers(d));
		} else {
			frappe
				.xcall(`${MAP_METHOD}.get_seat_map`, { branch, date: this.date.get_value(), time: this.time.get_value() })
				.then((d) => this.render_seats(d));
		}
	}

	// ------------------------------------------------------------ seats
	render_seats(data) {
		const c = data.counts;
		const occupancy = data.total ? Math.round((c.occupied / (data.total - c.maintenance || 1)) * 100) : 0;
		let html = this.summary([
			[__("Occupancy"), `${occupancy}%`, "blue"],
			[__("Booked now"), c.occupied, "blue"],
			[__("Free now, booked other hours"), c.partial, "amber"],
			[__("Fully free"), c.free, "green"],
			[__("Maintenance"), c.maintenance, "gray"],
		]);
		html += this.legend([
			["free", __("Free")],
			["partial", __("Free now (sell hourly)")],
			["occupied", __("Booked")],
			["maintenance", __("Maintenance")],
		], true);

		if (!data.zones.length) html += `<div class="psl-empty">${__("No zones or seats yet for this branch.")}</div>`;
		for (const zone of data.zones) {
			const girls = zone.gender_policy === "Girls Only";
			html += `<div class="psl-zone ${girls ? "psl-zone-girls" : ""}">
				<div class="psl-zone-head">
					<span class="psl-zone-name">${frappe.utils.escape_html(zone.zone_name)}</span>
					<span class="psl-badge ${girls ? "psl-badge-girls" : ""}">${__(zone.gender_policy)}</span>
					<span class="text-muted small">${zone.seats.length} ${__("seats")}</span>
				</div>
				<div class="psl-grid">${zone.seats.map((s) => this.seat_tile(s)).join("") ||
					`<span class="text-muted small">${__("No seats")}</span>`}</div>
			</div>`;
		}
		this.$body.html(html);
		this.bind_seats(data);
	}

	seat_tile(s) {
		const who = s.current ? frappe.utils.escape_html(s.current.student_name.split(" ")[0]) : "";
		const sub = s.state === "partial" ? __("{0} slot(s)", [s.bookings.length]) : s.seat_type !== "Normal" ? s.seat_type : "";
		return `<button class="psl-tile psl-${s.state}" data-seat="${s.name}" title="${s.seat_no}">
			<span class="psl-tile-no">${s.seat_no}</span>
			<span class="psl-tile-who">${who || sub}</span>
			<span class="psl-flags">
				${s.present ? `<i class="psl-flag psl-flag-present" title="${__("Checked in")}"></i>` : ""}
				${s.expiring ? `<i class="psl-flag psl-flag-expiring" title="${__("Expiring soon")}"></i>` : ""}
				${s.fee_due ? `<i class="psl-flag psl-flag-due" title="${__("Fee due")}">₹</i>` : ""}
			</span>
		</button>`;
	}

	bind_seats(data) {
		const seats = {};
		data.zones.forEach((z) => z.seats.forEach((s) => (seats[s.name] = Object.assign({ zone: z.name }, s))));
		this.$body.find(".psl-tile[data-seat]").on("click", (e) => this.seat_dialog(seats[e.currentTarget.dataset.seat]));
	}

	seat_dialog(s) {
		const rows = s.bookings.length
			? s.bookings
					.map(
						(b) => `<tr>
						<td><a href="/app/seat-booking/${b.name}">${b.name}</a></td>
						<td>${frappe.utils.escape_html(b.student_name)}</td>
						<td>${__(b.booking_type)}</td>
						<td>${b.slot}</td>
						<td>${frappe.datetime.str_to_user(b.to_date)}</td>
						<td>${b.fee_due ? `<span class="indicator-pill red">${__("Due")}</span>` : `<span class="indicator-pill green">${__("Paid")}</span>`}</td>
					</tr>`
					)
					.join("")
			: `<tr><td colspan="6" class="text-muted">${__("No bookings on this date.")}</td></tr>`;
		const d = new frappe.ui.Dialog({
			title: __("Seat {0}", [s.seat_no]),
			size: "large",
			fields: [{
				fieldtype: "HTML",
				options: `<table class="table table-sm"><thead><tr>
					<th>${__("Booking")}</th><th>${__("Student")}</th><th>${__("Type")}</th>
					<th>${__("Slot")}</th><th>${__("Until")}</th><th>${__("Fee")}</th></tr></thead>
					<tbody>${rows}</tbody></table>`,
			}],
			primary_action_label: s.state === "maintenance" ? null : __("New Booking"),
			primary_action: () => {
				d.hide();
				frappe.new_doc("Seat Booking", {
					branch: this.branch.get_value(), zone: s.zone, seat: s.name, from_date: this.date.get_value(),
				});
			},
		});
		d.show();
	}

	// ------------------------------------------------------------ lockers
	render_lockers(data) {
		const c = data.counts;
		let html = this.summary([
			[__("Available"), c.Available || 0, "green"],
			[__("Occupied"), c.Occupied || 0, "blue"],
			[__("Overdue"), c.Overdue || 0, "red"],
			[__("Maintenance"), c.Maintenance || 0, "gray"],
		]);
		html += this.legend([
			["free", __("Available")], ["occupied", __("Occupied")], ["overdue", __("Overdue")], ["maintenance", __("Maintenance")],
		]);
		if (!data.groups.length) html += `<div class="psl-empty">${__("No lockers yet for this branch.")}</div>`;
		const css = { Available: "free", Occupied: "occupied", Overdue: "overdue", Maintenance: "maintenance" };
		for (const g of data.groups) {
			html += `<div class="psl-zone"><div class="psl-zone-head">
				<span class="psl-zone-name">${__(g.size)} ${__("Lockers")}</span>
				<span class="text-muted small">${g.lockers.length}</span></div>
				<div class="psl-grid">${g.lockers
					.map((l) => `<button class="psl-tile psl-${css[l.status]}" data-locker="${l.name}" data-alloc="${l.current_allocation || ""}">
						<span class="psl-tile-no">${l.locker_no}</span>
						<span class="psl-tile-who">${l.current_student ? frappe.utils.escape_html(l.current_student.split(" ")[0]) : ""}</span>
						<span class="psl-flags">${l.fee_due ? `<i class="psl-flag psl-flag-due">₹</i>` : ""}</span>
					</button>`)
					.join("")}</div></div>`;
		}
		this.$body.html(html);
		this.$body.find(".psl-tile[data-locker]").on("click", (e) => {
			const { locker, alloc } = e.currentTarget.dataset;
			if (alloc) frappe.set_route("Form", "Locker Allocation", alloc);
			else if (e.currentTarget.classList.contains("psl-free"))
				frappe.new_doc("Locker Allocation", { branch: this.branch.get_value(), locker });
			else frappe.set_route("Form", "Locker", locker);
		});
	}

	// ------------------------------------------------------------ shared
	summary(items) {
		return `<div class="psl-summary">${items
			.map(([label, value, color]) => `<div class="psl-stat psl-stat-${color}"><div class="psl-stat-value">${value}</div><div class="psl-stat-label">${label}</div></div>`)
			.join("")}</div>`;
	}

	legend(items, flags) {
		let html = items.map(([cls, label]) => `<span><i class="psl-swatch psl-${cls}"></i>${label}</span>`).join("");
		if (flags) {
			html += `<span><i class="psl-flag psl-flag-present"></i>${__("Checked in")}</span>
				<span><i class="psl-flag psl-flag-expiring"></i>${__("Expiring soon")}</span>
				<span><i class="psl-flag psl-flag-due">₹</i>${__("Fee due")}</span>`;
		}
		return `<div class="psl-legend">${html}</div>`;
	}
}
