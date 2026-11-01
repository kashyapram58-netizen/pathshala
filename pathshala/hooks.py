app_name = "pathshala"
app_title = "Pathshala"
app_publisher = "Ram"
app_description = "A commercial app for library management"
app_email = "kashyap.ram58@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

app_logo_url = "/assets/pathshala/images/pathshala-icon-transparent.png"

website_context = {
	"favicon": "/assets/pathshala/images/pathshala-icon.png",
	"splash_image": "/assets/pathshala/images/pathshala-logo-transparent.png",
}

add_to_apps_screen = [
	{
		"name": "pathshala",
		"logo": "/assets/pathshala/images/pathshala-icon-transparent.png",
		"title": "Pathshala",
		"route": "/app/pathshala",
	}
]

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "pathshala",
# 		"logo": "/assets/pathshala/logo.png",
# 		"title": "Pathshala",
# 		"route": "/pathshala",
# 		"has_permission": "pathshala.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_css = "/assets/pathshala/css/desk.css"
app_include_js = "/assets/pathshala/js/pathshala.js"

# include js, css files in header of web template
# web_include_css = "/assets/pathshala/css/pathshala.css"
# web_include_js = "/assets/pathshala/js/pathshala.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "pathshala/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "pathshala/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "pathshala.utils.jinja_methods",
# 	"filters": "pathshala.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "pathshala.install.before_install"
# after_install = "pathshala.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "pathshala.uninstall.before_uninstall"
# after_uninstall = "pathshala.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "pathshala.utils.before_app_install"
# after_app_install = "pathshala.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "pathshala.utils.before_app_uninstall"
# after_app_uninstall = "pathshala.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "pathshala.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

scheduler_events = {
	"daily": [
		"pathshala.pathshala.doctype.seat_booking.seat_booking.expire_bookings",
		"pathshala.pathshala.doctype.locker_allocation.locker_allocation.mark_overdue",
	],
	"hourly": ["pathshala.attendance.auto_check_out"],
}

after_migrate = "pathshala.setup.after_migrate"

jinja = {
	"methods": [
		"pathshala.pathshala.doctype.student.student.qr_data_uri",
		"pathshala.id_card.get_id_card_data",
	]
}

# scheduler_events = {
# 	"all": [
# 		"pathshala.tasks.all"
# 	],
# 	"daily": [
# 		"pathshala.tasks.daily"
# 	],
# 	"hourly": [
# 		"pathshala.tasks.hourly"
# 	],
# 	"weekly": [
# 		"pathshala.tasks.weekly"
# 	],
# 	"monthly": [
# 		"pathshala.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "pathshala.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "pathshala.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "pathshala.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["pathshala.utils.before_request"]
# after_request = ["pathshala.utils.after_request"]

# Job Events
# ----------
# before_job = ["pathshala.utils.before_job"]
# after_job = ["pathshala.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"pathshala.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

