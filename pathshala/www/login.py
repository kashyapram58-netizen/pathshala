import os

import frappe
from frappe.www.login import get_context as frappe_login_context

no_cache = True

LOGO = "/assets/pathshala/images/pathshala-logo-transparent.png"
ICON = "/assets/pathshala/images/pathshala-icon-transparent.png"


def get_context(context):
	"""Reuse Frappe's login context (social login, LDAP, signup...) and only re-brand it."""
	frappe_login_context(context)
	context.app_name = "Pathshala"
	context.logo = ICON
	context.full_logo = LOGO
	context.body_class = "psl-login"
	context.title = "Login · Pathshala"
	# /assets are cached by browsers for 12h; bust it whenever the stylesheet changes.
	css = frappe.get_app_path("pathshala", "public", "css", "login.css")
	context.css_version = int(os.path.getmtime(css))
	return context
