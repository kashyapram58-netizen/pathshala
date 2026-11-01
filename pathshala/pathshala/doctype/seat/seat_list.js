frappe.listview_settings["Seat"] = {
	onload(listview) {
		listview.page.add_inner_button(__("Add Seats in Bulk"), () =>
			pathshala.bulk_seats({
				zone: listview.filters.find((f) => f[1] === "zone")?.[3],
				on_done: () => listview.refresh(),
			})
		);
	},
};
