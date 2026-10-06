# Copyright (c) 2026, Vinay Mishra and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document

# (field, root type, account types that are not allowed, label)
ACCOUNT_RULES = (
	(
		"cheques_in_hand_account",
		"Asset",
		("Receivable", "Payable", "Bank", "Cash"),
		"Cheques in Hand Account",
	),
	(
		"cheques_issued_account",
		"Liability",
		("Receivable", "Payable", "Bank", "Cash"),
		"Cheques Issued Account",
	),
	("bank_charges_account", "Expense", (), "Bounce Charges Account"),
)

NEW_ACCOUNTS = (
	# (field, account name, parent account names to try, root type)
	(
		"cheques_in_hand_account",
		"Cheques in Hand",
		("Current Assets", "Loans and Advances (Assets)"),
		"Asset",
	),
	("cheques_issued_account", "Cheques Issued", ("Current Liabilities",), "Liability"),
	("bank_charges_account", "Cheque Bounce Charges", ("Indirect Expenses", "Expenses"), "Expense"),
)


class ChequeSettings(Document):
	def validate(self):
		seen = set()
		for row in self.company_accounts:
			if row.company in seen:
				frappe.throw(_("Row {0}: {1} is listed twice.").format(row.idx, row.company))
			seen.add(row.company)
			validate_accounts(row)

	def on_update(self):
		frappe.clear_document_cache("Cheque Settings", "Cheque Settings")

	@frappe.whitelist()
	def create_missing_accounts(self, company: str):
		"""Add the holding and charges accounts to the company's chart and fill the row."""
		frappe.has_permission("Account", "create", throw=True)
		row = next((row for row in self.company_accounts if row.company == company), None)
		if not row:
			row = self.append("company_accounts", {"company": company})

		created = []
		for fieldname, account_name, parents, root_type in NEW_ACCOUNTS:
			if row.get(fieldname):
				continue
			existing = frappe.db.get_value(
				"Account", {"company": company, "account_name": account_name, "is_group": 0}, "name"
			)
			row.set(fieldname, existing or make_account(company, account_name, parents, root_type))
			if not existing:
				created.append(row.get(fieldname))

		self.save()
		return created


def validate_accounts(row):
	currency = frappe.get_cached_value("Company", row.company, "default_currency")
	for fieldname, root_type, blocked_types, label in ACCOUNT_RULES:
		account = row.get(fieldname)
		if not account:
			continue
		details = frappe.get_cached_value(
			"Account",
			account,
			["company", "is_group", "root_type", "account_type", "account_currency"],
			as_dict=True,
		)
		prefix = _("Row {0}: {1} {2}").format(row.idx, _(label), frappe.bold(account))
		if details.company != row.company:
			frappe.throw(_("{0} belongs to another company.").format(prefix))
		if details.is_group:
			frappe.throw(_("{0} is a group account.").format(prefix))
		if details.root_type != root_type:
			frappe.throw(_("{0} must be an {1} account.").format(prefix, _(root_type)))
		if details.account_type in blocked_types:
			frappe.throw(
				_(
					"{0} cannot be of type {1}. A party-type account would show cheques as open AR / AP."
				).format(prefix, _(details.account_type))
			)
		if details.account_currency and details.account_currency != currency:
			frappe.throw(_("{0} must be in the company currency {1}.").format(prefix, currency))


def make_account(company: str, account_name: str, parents: tuple, root_type: str) -> str:
	parent = None
	for name in parents:
		parent = frappe.db.get_value(
			"Account",
			{"company": company, "account_name": name, "is_group": 1, "root_type": root_type},
			"name",
		)
		if parent:
			break
	if not parent:
		# Charts of accounts differ by country: fall back to the first group under the root.
		root = frappe.db.get_value(
			"Account",
			{"company": company, "root_type": root_type, "is_group": 1, "parent_account": ("in", ("", None))},
			"name",
		)
		parent = (
			frappe.db.get_value(
				"Account", {"company": company, "is_group": 1, "parent_account": root}, "name", order_by="lft"
			)
			or root
		)
	if not parent:
		frappe.throw(
			_("No {0} group account found in {1}. Create {2} manually.").format(
				_(root_type), company, account_name
			)
		)

	account = frappe.get_doc(
		{
			"doctype": "Account",
			"account_name": account_name,
			"company": company,
			"parent_account": parent,
			"is_group": 0,
			"account_currency": frappe.get_cached_value("Company", company, "default_currency"),
		}
	)
	account.insert()
	return account.name
