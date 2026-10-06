# Copyright (c) 2026, Vinay Mishra and contributors
# License: MIT. See LICENSE

"""Journal Entries posted by a cheque.

Every entry is built from Lines in account currency. When the company-currency totals of
the lines differ (a foreign-currency cheque cleared or reversed at another rate), the
difference goes to the company's Exchange Gain / Loss account so the entry balances.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import frappe
from frappe import _
from frappe.utils import flt

# Set while a cheque posts or cancels its own entries, so the Journal Entry guard lets them through.
IN_CHEQUE_ACTION = "pdc_management_in_action"


@dataclass
class Line:
	account: str
	debit: float = 0.0
	credit: float = 0.0
	exchange_rate: float = 1.0
	party_type: str | None = None
	party: str | None = None
	reference_type: str | None = None
	reference_name: str | None = None
	is_advance: str = "No"

	def reversed(self) -> Line:
		return replace(self, debit=self.credit, credit=self.debit, is_advance="No")


def post(cheque, posting_date, lines: list[Line], remark: str, clearance_date=None) -> str:
	"""Insert and submit a Journal Entry for the cheque and return its name."""
	je = frappe.new_doc("Journal Entry")
	has_bank_line = any(_account_type(line.account) == "Bank" for line in lines)
	je.update(
		{
			"voucher_type": "Bank Entry" if has_bank_line else "Journal Entry",
			"company": cheque.company,
			"posting_date": posting_date,
			"cheque_no": cheque.cheque_no,
			"cheque_date": cheque.cheque_date,
			"user_remark": remark,
			"cheque": cheque.name,
		}
	)

	company_currency = frappe.get_cached_value("Company", cheque.company, "default_currency")
	precision = frappe.get_precision("Journal Entry Account", "debit")
	dimensions = dimension_values(cheque)
	difference = 0.0
	for line in lines:
		currency = _account_currency(line.account) or company_currency
		rate = 1.0 if currency == company_currency else flt(line.exchange_rate)
		if currency != company_currency:
			je.multi_currency = 1
		je.append(
			"accounts",
			{
				"account": line.account,
				"party_type": line.party_type,
				"party": line.party,
				"reference_type": line.reference_type,
				"reference_name": line.reference_name,
				"is_advance": line.is_advance,
				"exchange_rate": rate,
				"debit_in_account_currency": flt(line.debit, precision),
				"credit_in_account_currency": flt(line.credit, precision),
				**dimensions,
			},
		)
		difference += flt(line.debit * rate, precision) - flt(line.credit * rate, precision)

	difference = flt(difference, precision)
	if difference:
		je.append("accounts", {**_exchange_difference_row(cheque.company, difference), **dimensions})

	je.flags.ignore_exchange_rate = True
	je.flags.ignore_permissions = True
	with in_cheque_action():
		je.insert()
		je.submit()
	if clearance_date:
		# Journal Entry clears this on validate; Bank Clearance sets it after submit the same way.
		je.db_set("clearance_date", clearance_date, update_modified=False)
	return je.name


def dimension_values(cheque) -> dict:
	"""Cost center and accounting dimensions of the cheque, copied to every entry row."""
	from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import get_accounting_dimensions

	values = {"cost_center": cheque.get("cost_center")}
	for fieldname in get_accounting_dimensions():
		if cheque.get(fieldname):
			values[fieldname] = cheque.get(fieldname)
	return values


def cancel(journal_entry: str) -> None:
	je = frappe.get_doc("Journal Entry", journal_entry)
	if je.docstatus != 1:
		return
	# The cheque's event history links to the entry; that link must not block undoing it.
	je.ignore_linked_doctypes = ("Cheque", "Cheque Event")
	je.flags.ignore_permissions = True
	with in_cheque_action():
		je.cancel()


def lines_of(journal_entry: str, accounts: set[str] | None = None) -> list[Line]:
	"""Current rows of a posted entry as Lines, optionally only for some accounts.

	Read at reversal time, so allocations made later by Payment Reconciliation are honoured."""
	rows = frappe.get_all(
		"Journal Entry Account",
		filters={"parent": journal_entry, "parenttype": "Journal Entry"},
		fields=[
			"account",
			"debit_in_account_currency",
			"credit_in_account_currency",
			"exchange_rate",
			"party_type",
			"party",
			"reference_type",
			"reference_name",
		],
		order_by="idx",
	)
	return [
		Line(
			account=row.account,
			debit=flt(row.debit_in_account_currency),
			credit=flt(row.credit_in_account_currency),
			exchange_rate=flt(row.exchange_rate) or 1.0,
			party_type=row.party_type,
			party=row.party,
			reference_type=row.reference_type,
			reference_name=row.reference_name,
		)
		for row in rows
		if accounts is None or row.account in accounts
	]


class in_cheque_action:
	"""Context manager marking cheque-owned Journal Entry writes."""

	def __enter__(self):
		self.previous = frappe.flags.get(IN_CHEQUE_ACTION)
		frappe.flags[IN_CHEQUE_ACTION] = True

	def __exit__(self, *exc):
		frappe.flags[IN_CHEQUE_ACTION] = self.previous


def _exchange_difference_row(company: str, difference: float) -> dict:
	account = frappe.get_cached_value("Company", company, "exchange_gain_loss_account")
	if not account:
		frappe.throw(
			_("Set the Exchange Gain / Loss Account in Company {0}.").format(frappe.bold(company)),
			title=_("Exchange Difference"),
		)
	return {
		"account": account,
		"exchange_rate": 1,
		"debit_in_account_currency": -difference if difference < 0 else 0,
		"credit_in_account_currency": difference if difference > 0 else 0,
	}


def _account_currency(account: str) -> str | None:
	return frappe.get_cached_value("Account", account, "account_currency")


def _account_type(account: str) -> str | None:
	return frappe.get_cached_value("Account", account, "account_type")
