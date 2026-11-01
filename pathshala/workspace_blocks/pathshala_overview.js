// Runs inside Frappe's Custom HTML Block shadow DOM: `root_element` is the shadow root.
const $el = (name) => root_element.querySelector(`[data-el="${name}"]`);
const money = (v) => format_currency(v || 0, frappe.boot.sysdefaults.currency, 0);

function greet() {
	const h = new Date().getHours();
	const part = h < 12 ? __("Good morning") : h < 17 ? __("Good afternoon") : __("Good evening");
	const first = (frappe.boot.user.first_name || frappe.session.user_fullname || "").split(" ")[0];
	$el("hello").innerHTML = `${part}, <span>${frappe.utils.escape_html(first)}</span>`;
	$el("today").textContent =
		new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long", year: "numeric" }) +
		" · " + __("Library and Self Study Centre");
}

function load() {
	frappe.xcall("pathshala.api.dashboard_stats").then((s) => {
		$el("present_now").textContent = s.present_now;
		$el("checkins_today").innerHTML = __("{0} check-ins today", [`<b>${s.checkins_today}</b>`]);
		$el("occupancy").textContent = s.occupancy;
		$el("occupancy_bar").style.width = Math.min(s.occupancy, 100) + "%";
		$el("expiring_week").textContent = s.expiring_week;
		$el("active_students").innerHTML = __("{0} active students", [`<b>${s.active_students}</b>`]);
		$el("fees_due").textContent = money(s.fees_due);
		$el("collection_today").innerHTML = __("{0} collected today", [`<b>${money(s.collection_today)}</b>`]);
		$el("lockers_free").textContent = s.lockers_free;
		$el("lockers_total").textContent = ` / ${s.lockers_total}`;
		$el("lockers_overdue").innerHTML = s.lockers_overdue
			? `<b style="color:#d93636">${s.lockers_overdue}</b> ${__("overdue")}`
			: __("None overdue");
	});
}

const routes = {
	map: () => frappe.set_route("seat-map"),
	kiosk: () => window.open("/kiosk", "_blank"),
	attendance: () => frappe.set_route("List", "Attendance Log", { attendance_date: frappe.datetime.get_today() }),
	expiring: () => frappe.set_route("List", "Seat Booking", { status: "Active", docstatus: 1 }),
	dues: () => frappe.set_route("List", "Seat Booking", { docstatus: 1, outstanding_amount: [">", 0] }),
	lockers: () => frappe.set_route("seat-map"),
	new_student: () => frappe.new_doc("Student"),
	new_booking: () => frappe.new_doc("Seat Booking"),
	new_locker: () => frappe.new_doc("Locker Allocation"),
	new_payment: () => frappe.new_doc("Fee Payment"),
};
root_element.querySelectorAll("[data-action], [data-go]").forEach((node) =>
	node.addEventListener("click", () => {
		const fn = routes[node.dataset.action || node.dataset.go];
		fn && fn();
	})
);

greet();
load();
const timer = setInterval(() => {
	if (!root_element.host.isConnected) return clearInterval(timer);
	if (!document.hidden) load();
}, 60000);
