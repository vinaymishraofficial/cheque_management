app_name = "pdc_management"
app_title = "PDC Management"
app_publisher = "Vinay Mishra"
app_description = "Post-dated and current cheque lifecycle for ERPNext: receive, issue, deposit, clear, bounce, replace, with correct accounting."
app_email = "vinaymishraofficial@users.noreply.github.com"
app_license = "mit"
app_logo_url = "/assets/pdc_management/images/logo.svg"

required_apps = ["erpnext"]

add_to_apps_screen = [
	{
		"name": "pdc_management",
		"logo": "/assets/pdc_management/images/logo.svg",
		"title": "Cheques",
		"route": "/app/cheques",
		"has_permission": "pdc_management.utils.has_app_permission",
	}
]

after_install = "pdc_management.install.after_install"
after_migrate = "pdc_management.install.after_migrate"
before_uninstall = "pdc_management.install.before_uninstall"
before_tests = "pdc_management.tests.utils.before_tests"

doctype_js = {
	"Sales Invoice": "public/js/invoice.js",
	"Purchase Invoice": "public/js/invoice.js",
}

calendars = ["Cheque"]

# ERPNext adds every accounting dimension (Branch, Project, ...) to these doctypes.
accounting_dimension_doctypes = ["Cheque"]

doc_events = {
	"Sales Invoice": {
		"before_cancel": "pdc_management.overrides.invoice.prevent_cancel_with_active_cheques",
	},
	"Purchase Invoice": {
		"before_cancel": "pdc_management.overrides.invoice.prevent_cancel_with_active_cheques",
	},
	"Journal Entry": {
		"before_cancel": "pdc_management.overrides.journal_entry.prevent_direct_cancel",
	},
}

override_doctype_dashboards = {
	"Customer": "pdc_management.overrides.dashboards.add_cheques_to_party",
	"Supplier": "pdc_management.overrides.dashboards.add_cheques_to_party",
}

scheduler_events = {
	"daily": [
		"pdc_management.tasks.send_daily_digest",
	],
}

export_python_type_annotations = True
