import frappe

ROLES = {
	"Pathshala Manager": 1,
	"Pathshala Staff": 1,
	"Pathshala Kiosk": 0,  # tablet login, no desk access
}


def after_migrate():
	for role, desk_access in ROLES.items():
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": desk_access}).insert(
				ignore_permissions=True
			)
