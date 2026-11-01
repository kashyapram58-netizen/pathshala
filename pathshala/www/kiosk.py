import frappe
from frappe.utils import cint

from pathshala.api import get_kiosk_branch

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/kiosk"
		raise frappe.Redirect

	context.branch = get_kiosk_branch(frappe.form_dict.get("branch"))
	settings = frappe.get_cached_doc("Pathshala Settings")
	context.reset_seconds = cint(settings.kiosk_reset_seconds) or 4
	context.title = f"Pathshala Check-in · {context.branch}"
	context.no_header = 1
	context.no_breadcrumbs = 1
	return context
