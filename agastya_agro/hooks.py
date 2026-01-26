from . import __version__ as app_version

app_name = "agastya_agro"
app_title = "Agastya Agro"
app_publisher = "Dexciss"
app_description = "Agastya Agro"
app_icon = "octicon octicon-file-directory"
app_color = "grey"
app_email = "vsolanke@dexciss.com"
app_license = "MIT"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/agastya_agro/css/agastya_agro.css"
app_include_js = "/assets/agastya_agro/js/query_report_overrides.js"

fixtures = fixtures = [
		{"dt":"Custom Field", "filters": [["name", "in",(
           "Sales Invoice-additional_discount",
        )]]}
]



# include js, css files in header of web template
# web_include_css = "/assets/agastya_agro/css/agastya_agro.css"
# web_include_js = "/assets/agastya_agro/js/agastya_agro.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "agastya_agro/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {"Delivery Note" : "public/js/delivery_note.js",
				"Sales Invoice" : "public/js/sales_invoice.js",
				"Purchase Receipt": "public/js/purchase_receipt.js",
				"Purchase Invoice": "public/js/purchase_invoice.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "agastya_agro.install.before_install"
# after_install = "agastya_agro.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "agastya_agro.uninstall.before_uninstall"
# after_uninstall = "agastya_agro.uninstall.after_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "agastya_agro.notifications.get_notification_config"

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
# 	"Delivery Note": "agastya_agro.overrides.CustomDeliveryNote",
# 	"Sales Invoice": "agastya_agro.overrides.CustomSalesInvoice"
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Sales Order": {
		"validate": "agastya_agro.agastya_agro.custom_sales_order.custom_validate",
		
	},
	"Sales Invoice":{
		"validate":"agastya_agro.agastya_agro.custom_sales_invoice.custom_validate",
		"before_insert":"agastya_agro.public.py.sales_invoice.before_insert"
	},
	"Delivery Note":{
		"validate":"agastya_agro.agastya_agro.custom_delivery_notes.custom_validate"
	},
	"Purchase Invoice":{
		"validate":"agastya_agro.public.py.purchase_invoice.validate"
	}
}
# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"agastya_agro.tasks.all"
# 	],
# 	"daily": [
# 		"agastya_agro.tasks.daily"
# 	],
# 	"hourly": [
# 		"agastya_agro.tasks.hourly"
# 	],
# 	"weekly": [
# 		"agastya_agro.tasks.weekly"
# 	]
# 	"monthly": [
# 		"agastya_agro.tasks.monthly"
# 	]
# }

# Testing
# -------

# before_tests = "agastya_agro.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.utils.print_format.report_to_pdf": "agastya_agro.overrides.report_to_pdf"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "agastya_agro.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]


# User Data Protection
# --------------------

user_data_fields = [
	{
		"doctype": "{doctype_1}",
		"filter_by": "{filter_by}",
		"redact_fields": ["{field_1}", "{field_2}"],
		"partial": 1,
	},
	{
		"doctype": "{doctype_2}",
		"filter_by": "{filter_by}",
		"partial": 1,
	},
	{
		"doctype": "{doctype_3}",
		"strict": False,
	},
	{
		"doctype": "{doctype_4}"
	}
]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"agastya_agro.auth.validate"
# ]
