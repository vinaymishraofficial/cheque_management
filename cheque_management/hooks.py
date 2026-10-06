app_name = "cheque_management"
app_title = "Cheque Management"
app_publisher = "Vinay Mishra"
app_description = "Post-dated and current cheque lifecycle for ERPNext: receive, issue, deposit, clear, bounce, replace, with correct accounting."
app_email = "vinaymishraofficial@users.noreply.github.com"
app_license = "mit"
app_logo_url = "/assets/cheque_management/images/logo.svg"

required_apps = ["erpnext"]

add_to_apps_screen = [
	{
		"name": "cheque_management",
		"logo": "/assets/cheque_management/images/logo.svg",
		"title": "Cheques",
		"route": "/app/cheques",
		"has_permission": "cheque_management.utils.has_app_permission",
	}
]

after_install = "cheque_management.install.after_install"
after_migrate = "cheque_management.install.after_migrate"
before_uninstall = "cheque_management.install.before_uninstall"
before_tests = "cheque_management.tests.utils.before_tests"

doctype_js = {
	"Sales Invoice": "public/js/invoice.js",
	"Purchase Invoice": "public/js/invoice.js",
}

calendars = ["Cheque"]

# ERPNext adds every accounting dimension (Branch, Project, ...) to these doctypes.
accounting_dimension_doctypes = ["Cheque"]

doc_events = {
	"Sales Invoice": {
		"before_cancel": "cheque_management.overrides.invoice.prevent_cancel_with_active_cheques",
	},
	"Purchase Invoice": {
		"before_cancel": "cheque_management.overrides.invoice.prevent_cancel_with_active_cheques",
	},
	"Journal Entry": {
		"before_cancel": "cheque_management.overrides.journal_entry.prevent_direct_cancel",
	},
}

override_doctype_dashboards = {
	"Customer": "cheque_management.overrides.dashboards.add_cheques_to_party",
	"Supplier": "cheque_management.overrides.dashboards.add_cheques_to_party",
}

scheduler_events = {
	"daily": [
		"cheque_management.tasks.send_daily_digest",
	],
}

export_python_type_annotations = True
