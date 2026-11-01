frappe.listview_settings["Locker"] = {
	onload(listview) {
		listview.page.add_inner_button(__("Add Lockers in Bulk"), () =>
			pathshala.bulk_lockers({
				branch: listview.filters.find((f) => f[1] === "branch")?.[3],
				on_done: () => listview.refresh(),
			})
		);
	},
};
