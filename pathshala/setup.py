import frappe

ROLES = {
	"Pathshala Manager": 1,
	"Pathshala Staff": 1,
	"Pathshala Kiosk": 0,  # tablet login, no desk access
}

# Custom HTML Blocks have no module, so they can't be exported as files; keep their source in
# pathshala/workspace_blocks/<scrubbed name>.{html,css,js} and sync it on every migrate.
CUSTOM_BLOCKS = ["Pathshala Overview"]


LOGO = "/assets/pathshala/images/pathshala-icon-transparent.png"


def after_migrate():
	create_roles()
	sync_custom_blocks()
	set_default_app()
	set_navbar_logo()


def create_roles():
	for role, desk_access in ROLES.items():
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": desk_access}).insert(
				ignore_permissions=True
			)


def sync_custom_blocks():
	for name in CUSTOM_BLOCKS:
		base = frappe.get_app_path("pathshala", "workspace_blocks", frappe.scrub(name))
		source = {}
		for field, ext in (("html", "html"), ("style", "css"), ("script", "js")):
			with open(f"{base}.{ext}") as f:
				source[field] = f.read()
		if frappe.db.exists("Custom HTML Block", name):
			doc = frappe.get_doc("Custom HTML Block", name)
			doc.update(source)
			doc.save(ignore_permissions=True)
		else:
			doc = frappe.get_doc({"doctype": "Custom HTML Block", "private": 0, **source})
			doc.insert(ignore_permissions=True, set_name=name)


def set_default_app():
	"""Land users on the Pathshala workspace after login, unless an admin already chose a default app."""
	if not frappe.db.get_single_value("System Settings", "default_app"):
		frappe.db.set_single_value("System Settings", "default_app", "pathshala")


def set_navbar_logo():
	"""The app_logo_url hook is ignored when 3+ apps define one (Frappe then picks its own),
	so set Navbar Settings.app_logo instead, unless an admin already uploaded a logo."""
	if not frappe.db.get_single_value("Navbar Settings", "app_logo"):
		frappe.db.set_single_value("Navbar Settings", "app_logo", LOGO)
		frappe.clear_cache()
