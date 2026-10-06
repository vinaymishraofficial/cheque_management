# Copyright (c) 2026, Vinay Mishra and contributors
# License: MIT. See LICENSE

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

CUSTOM_FIELDS = {
	"Journal Entry": [
		{
			"fieldname": "cheque",
			"fieldtype": "Link",
			"label": "Cheque",
			"options": "Cheque",
			"insert_after": "cheque_date",
			"read_only": 1,
			"no_copy": 1,
			"search_index": 1,
			"print_hide": 1,
			"description": "Posted by this cheque. Use the cheque's actions to change it.",
		}
	],
}


def after_install():
	create_custom_fields(CUSTOM_FIELDS, ignore_validate=True)
	add_accounting_dimensions()
	setup_companies()


def after_migrate():
	create_custom_fields(CUSTOM_FIELDS, ignore_validate=True)
	add_accounting_dimensions()


def add_accounting_dimensions():
	"""Dimensions created before the app was installed; ERPNext adds later ones itself."""
	from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
		create_accounting_dimensions_for_doctype,
	)

	create_accounting_dimensions_for_doctype("Cheque")


def before_uninstall():
	for doctype, fields in CUSTOM_FIELDS.items():
		for field in fields:
			name = frappe.db.get_value("Custom Field", {"dt": doctype, "fieldname": field["fieldname"]})
			if name:
				frappe.delete_doc("Custom Field", name, ignore_permissions=True)
	# Accounting dimension fields ERPNext added to the app's doctypes.
	for name in frappe.get_all("Custom Field", filters={"dt": "Cheque"}, pluck="name"):
		frappe.delete_doc("Custom Field", name, ignore_permissions=True)


def setup_companies():
	"""Add a settings row per existing company, reusing accounts that already exist by name."""
	settings = frappe.get_single("Cheque Settings")
	listed = {row.company for row in settings.company_accounts}
	for company in frappe.get_all("Company", pluck="name"):
		if company in listed:
			continue
		row = {"company": company}
		for fieldname, account_name in (
			("cheques_in_hand_account", "Cheques in Hand"),
			("cheques_issued_account", "Cheques Issued"),
			("bank_charges_account", "Cheque Bounce Charges"),
		):
			row[fieldname] = frappe.db.get_value(
				"Account", {"company": company, "account_name": account_name, "is_group": 0}, "name"
			)
		settings.append("company_accounts", row)
	settings.flags.ignore_permissions = True
	settings.save()
