# Copyright (c) 2026, Vinay Mishra and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _

APP_ROLES = ("Accounts User", "Accounts Manager", "System Manager")


def has_app_permission() -> bool:
	"""Show the app on the apps screen only to users who can read cheques."""
	return frappe.has_permission("Cheque", "read")


def get_settings():
	return frappe.get_cached_doc("Cheque Settings")


def get_company_accounts(company: str):
	"""The Cheque Settings row of a company. Throws with a pointer to the settings when missing."""
	for row in get_settings().company_accounts:
		if row.company == company:
			return row

	frappe.throw(
		_("Set the cheque accounts for {0} in {1}.").format(
			frappe.bold(company), frappe.utils.get_link_to_form("Cheque Settings", "Cheque Settings")
		),
		title=_("Cheque Accounts Missing"),
	)
