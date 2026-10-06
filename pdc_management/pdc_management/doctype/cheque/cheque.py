# Copyright (c) 2026, Vinay Mishra and contributors
# License: MIT. See LICENSE

"""A cheque received from or issued to a party, from receipt to clearance or bounce.

Received: Dr Cheques in Hand / Cr party (against invoices) on receipt, then Dr Bank / Cr
Cheques in Hand on clearance. Issued mirrors it with Cheques Issued and the supplier.
Bounce and return post a reversing entry on their own date; nothing earlier is cancelled.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_months, flt, get_link_to_form, getdate, nowdate

from pdc_management import accounting
from pdc_management.accounting import Line
from pdc_management.utils import get_company_accounts, get_settings

INVOICE_OF_PARTY = {"Customer": "Sales Invoice", "Supplier": "Purchase Invoice"}
PARTY_FIELD = {"Sales Invoice": "customer", "Purchase Invoice": "supplier"}
PARTY_ACCOUNT_FIELD = {"Sales Invoice": "debit_to", "Purchase Invoice": "credit_to"}

# Statuses a cheque can be in for each action, by cheque type.
ACTION_STATUSES = {
	"deposit": {"Received": ("In Hand",)},
	"clear": {"Received": ("In Hand", "Deposited"), "Issued": ("Issued",)},
	"bounce": {"Received": ("Deposited", "Cleared"), "Issued": ("Issued", "Cleared")},
	"return": {"Received": ("In Hand",), "Issued": ("Issued",)},
	"replace": {"Received": ("Bounced", "Returned"), "Issued": ("Bounced", "Returned")},
}
OPEN_STATUS = {"Received": "In Hand", "Issued": "Issued"}


class Cheque(Document):
	def validate(self):
		self.set_missing_values()
		self.validate_dates()
		self.set_references()
		self.set_totals()
		self.validate_bank_account(self.bank_account)
		self.validate_duplicate()
		self.status = "Draft"

	def before_submit(self):
		# Re-read invoices under a row lock so two cheques cannot over-allocate one invoice.
		self.set_references(for_update=True)
		self.set_totals()

	def on_submit(self):
		self.journal_entry = accounting.post(
			self,
			self.posting_date,
			self.receipt_lines(),
			self.remark(_("{0} cheque").format(_(self.cheque_type))),
		)
		self.status = OPEN_STATUS[self.cheque_type]
		self.append_event(self.cheque_type, self.posting_date, self.journal_entry)
		self.db_set("journal_entry", self.journal_entry, update_modified=False)
		self.db_set("status", self.status, update_modified=False)
		self.save_events()
		if self.replacement_of:
			self.mark_original_replaced()

	def before_cancel(self):
		if self.status != OPEN_STATUS[self.cheque_type]:
			frappe.throw(
				_("A cheque that is {0} cannot be cancelled. Undo its last step first.").format(
					frappe.bold(_(self.status))
				),
				title=_("Cannot Cancel"),
			)

	def on_cancel(self):
		if self.journal_entry:
			accounting.cancel(self.journal_entry)
		self.db_set("status", "Cancelled", update_modified=False)
		if self.replacement_of:
			self.restore_original()

	# ---------------------------------------------------------------- validation

	def set_missing_values(self):
		from erpnext.accounts.doctype.account.account import get_account_currency
		from erpnext.accounts.party import get_party_account

		self.company_currency = frappe.get_cached_value("Company", self.company, "default_currency")
		self.party_name = frappe.get_cached_value(
			self.party_type, self.party, "customer_name" if self.party_type == "Customer" else "supplier_name"
		)
		self.party_account = get_party_account(self.party_type, self.party, self.company)
		self.party_account_currency = get_account_currency(self.party_account) or self.company_currency
		if self.party_account_currency == self.company_currency:
			self.exchange_rate = 1
		if flt(self.exchange_rate) <= 0:
			frappe.throw(_("Exchange Rate must be greater than 0."))
		if flt(self.amount) <= 0:
			frappe.throw(_("Amount must be greater than 0."))
		self.base_amount = flt(flt(self.amount) * flt(self.exchange_rate), self.precision("base_amount"))
		self.is_post_dated = int(getdate(self.cheque_date) > getdate(self.posting_date))

		accounts = get_company_accounts(self.company)
		self.holding_account = (
			accounts.cheques_in_hand_account
			if self.cheque_type == "Received"
			else accounts.cheques_issued_account
		)
		if not self.holding_account:
			frappe.throw(
				_("Set the {0} for {1} in Cheque Settings.").format(
					_("Cheques in Hand Account")
					if self.cheque_type == "Received"
					else _("Cheques Issued Account"),
					frappe.bold(self.company),
				)
			)

		if not self.bank_account and self.mode_of_payment:
			self.bank_account = self.default_bank_account()
		self.set_dimension_defaults()

	def set_dimension_defaults(self):
		"""Company cost center and default dimensions, so mandatory dimensions do not block posting."""
		from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
			get_checks_for_pl_and_bs_accounts,
		)

		if not self.cost_center:
			self.cost_center = frappe.get_cached_value("Company", self.company, "cost_center")
		for dimension in get_checks_for_pl_and_bs_accounts():
			if (
				dimension.company == self.company
				and dimension.default_dimension
				and not self.get(dimension.fieldname)
			):
				self.set(dimension.fieldname, dimension.default_dimension)

	def default_bank_account(self) -> str | None:
		account = frappe.db.get_value(
			"Mode of Payment Account",
			{"parent": self.mode_of_payment, "company": self.company},
			"default_account",
		)
		if account and frappe.get_cached_value("Account", account, "account_type") == "Bank":
			return account
		return None

	def validate_dates(self):
		validity = get_settings().cheque_validity_months
		if validity and getdate(self.cheque_date) < getdate(add_months(self.posting_date, -validity)):
			frappe.throw(
				_("The cheque is dated more than {0} months before the posting date and is stale.").format(
					validity
				),
				title=_("Stale Cheque"),
			)

	def set_references(self, for_update: bool = False):
		expected = INVOICE_OF_PARTY[self.party_type]
		seen = set()
		for row in self.references:
			row.reference_doctype = expected
			if row.reference_name in seen:
				frappe.throw(_("Row {0}: Invoice {1} is listed twice.").format(row.idx, row.reference_name))
			seen.add(row.reference_name)
			self.set_reference(row, for_update)

	def set_reference(self, row, for_update: bool):
		party_field = PARTY_FIELD[row.reference_doctype]
		account_field = PARTY_ACCOUNT_FIELD[row.reference_doctype]
		invoice = frappe.db.get_value(
			row.reference_doctype,
			row.reference_name,
			[
				"docstatus",
				"company",
				party_field,
				account_field,
				"posting_date",
				"due_date",
				"grand_total",
				"outstanding_amount",
				"party_account_currency",
			],
			as_dict=True,
			for_update=for_update,
		)
		label = _("Row {0}: {1} {2}").format(row.idx, _(row.reference_doctype), row.reference_name)
		if not invoice or invoice.docstatus != 1:
			frappe.throw(_("{0} is not submitted.").format(label))
		if invoice.company != self.company:
			frappe.throw(_("{0} belongs to another company.").format(label))
		if invoice[party_field] != self.party:
			frappe.throw(_("{0} is not billed to {1}.").format(label, self.party))
		currency = invoice.party_account_currency or self.company_currency
		if currency != self.party_account_currency:
			frappe.throw(
				_("{0} is in {1}, the cheque is in {2}.").format(label, currency, self.party_account_currency)
			)

		outstanding = flt(invoice.outstanding_amount)
		# A received cheque settles what the party owes us; an issued one what we owe them.
		# Against a return (credit / debit note) the outstanding is negative and the cheque is a refund.
		owes_us = self.party_type == "Customer"
		expects_positive = (self.cheque_type == "Received") == owes_us
		open_amount = outstanding if expects_positive else -outstanding
		if open_amount <= 0:
			frappe.throw(
				_("{0} has nothing outstanding to settle with a {1} cheque.").format(
					label, _(self.cheque_type)
				)
			)
		if flt(row.allocated_amount) <= 0:
			frappe.throw(_("{0}: Allocated amount must be greater than 0.").format(label))
		if flt(row.allocated_amount) - open_amount > 0.005:
			frappe.throw(
				_("{0}: Allocated {1} is more than the outstanding {2}.").format(
					label,
					frappe.format(row.allocated_amount, {"fieldtype": "Currency", "options": currency}),
					frappe.format(open_amount, {"fieldtype": "Currency", "options": currency}),
				)
			)

		row.update(
			{
				"account": invoice[account_field],
				"posting_date": invoice.posting_date,
				"due_date": invoice.due_date,
				"grand_total": invoice.grand_total,
				"outstanding_amount": outstanding,
			}
		)

	def set_totals(self):
		self.total_allocated_amount = flt(
			sum(flt(row.allocated_amount) for row in self.references),
			self.precision("total_allocated_amount"),
		)
		self.unallocated_amount = flt(
			self.amount - self.total_allocated_amount, self.precision("unallocated_amount")
		)
		if self.unallocated_amount < 0:
			frappe.throw(_("Allocated amount is more than the cheque amount."))
		if self.unallocated_amount and not get_settings().allow_on_account:
			frappe.throw(
				_(
					"Allocate the full cheque amount to invoices. Unallocated amounts are disabled in Cheque Settings."
				)
			)

	def validate_bank_account(self, account: str | None):
		if not account:
			return
		details = frappe.get_cached_value(
			"Account", account, ["account_type", "company", "is_group", "account_currency"], as_dict=True
		)
		if (
			not details
			or details.account_type != "Bank"
			or details.is_group
			or details.company != self.company
		):
			frappe.throw(
				_("{0} is not a bank account of {1}.").format(frappe.bold(account), frappe.bold(self.company))
			)
		if details.account_currency not in (self.company_currency, self.party_account_currency):
			frappe.throw(
				_("Bank account {0} is in {1}. Use one in {2} or {3}.").format(
					account, details.account_currency, self.company_currency, self.party_account_currency
				)
			)

	def validate_duplicate(self):
		if not get_settings().block_duplicate_cheque:
			return
		filters = {
			"cheque_no": self.cheque_no,
			"party_type": self.party_type,
			"party": self.party,
			"docstatus": 1,
			"name": ("!=", self.name),
		}
		if self.bank_name:
			filters["bank_name"] = self.bank_name
		if self.replacement_of:
			filters["name"] = ("not in", [self.name, self.replacement_of])
		duplicate = frappe.db.get_value("Cheque", filters, "name")
		if duplicate:
			frappe.throw(
				_(
					"Cheque {0} of {1} is already recorded in {2}. To present it again, use Replace on that cheque."
				).format(frappe.bold(self.cheque_no), self.party, get_link_to_form("Cheque", duplicate)),
				title=_("Duplicate Cheque"),
			)

	# ---------------------------------------------------------------- entries

	def receipt_lines(self) -> list[Line]:
		"""Received: Cr party per invoice (+ on account), Dr holding. Issued: the opposite."""
		received = self.cheque_type == "Received"
		party_lines = [
			self.party_line(
				row.account, row.allocated_amount, received, row.reference_doctype, row.reference_name
			)
			for row in self.references
		]
		if self.unallocated_amount:
			line = self.party_line(self.party_account, self.unallocated_amount, received)
			line.is_advance = "Yes"
			party_lines.append(line)

		precision = frappe.get_precision("Journal Entry Account", "debit")
		base = flt(
			sum(flt(flt(line.debit or line.credit) * self.exchange_rate, precision) for line in party_lines),
			precision,
		)
		holding = Line(self.holding_account, debit=base if received else 0, credit=0 if received else base)
		return [holding, *party_lines]

	def party_line(self, account, amount, received, reference_type=None, reference_name=None) -> Line:
		return Line(
			account=account,
			debit=0 if received else flt(amount),
			credit=flt(amount) if received else 0,
			exchange_rate=self.exchange_rate,
			party_type=self.party_type,
			party=self.party,
			reference_type=reference_type,
			reference_name=reference_name,
		)

	def holding_base(self) -> float:
		line = accounting.lines_of(self.journal_entry, {self.holding_account})[0]
		return line.debit or line.credit

	def bank_line(self, bank_account, base, exchange_rate, into_bank: bool) -> Line:
		"""The bank side of a clearance in the bank account's own currency."""
		in_company_currency = (
			frappe.get_cached_value("Account", bank_account, "account_currency") == self.company_currency
		)
		amount = base if in_company_currency else flt(self.amount)
		rate = 1 if in_company_currency else flt(exchange_rate or self.exchange_rate)
		return Line(
			bank_account,
			debit=amount if into_bank else 0,
			credit=0 if into_bank else amount,
			exchange_rate=rate,
		)

	def remark(self, event: str) -> str:
		return _("{0}: cheque {1} dated {2} of {3} ({4})").format(
			event,
			self.cheque_no,
			frappe.format(self.cheque_date, {"fieldtype": "Date"}),
			self.party_name or self.party,
			self.name,
		)

	# ---------------------------------------------------------------- actions

	@frappe.whitelist()
	def deposit(self, deposit_date=None, bank_account=None):
		"""Record that a received cheque was handed to the bank. No ledger entry."""
		self.begin("deposit")
		deposit_date = getdate(deposit_date or nowdate())
		bank_account = bank_account or self.bank_account
		if not bank_account:
			frappe.throw(_("Select the bank account the cheque is deposited into."))
		self.validate_bank_account(bank_account)
		self.validate_action_date(deposit_date, _("Deposit date"))
		if deposit_date < getdate(self.cheque_date):
			frappe.throw(
				_("A post-dated cheque cannot be deposited before its cheque date {0}.").format(
					frappe.format(self.cheque_date, {"fieldtype": "Date"})
				)
			)
		self.validate_not_stale(deposit_date)

		self.deposit_date = deposit_date
		self.deposit_bank_account = bank_account
		self.finish("Deposited", deposit_date, bank_account=bank_account)

	@frappe.whitelist()
	def clear(self, clearance_date=None, bank_account=None, exchange_rate=None):
		"""The bank honoured the cheque: move it from the holding account to the bank."""
		self.begin("clear")
		clearance_date = getdate(clearance_date or nowdate())
		bank_account = (
			bank_account
			or (self.deposit_bank_account if self.cheque_type == "Received" else None)
			or self.bank_account
		)
		if not bank_account:
			frappe.throw(_("Select the bank account."))
		self.validate_bank_account(bank_account)
		self.validate_action_date(clearance_date, _("Clearance date"))
		if clearance_date < getdate(self.cheque_date):
			frappe.throw(_("A cheque cannot clear before its cheque date."))
		if self.cheque_type == "Received" and not self.deposit_date:
			self.validate_not_stale(clearance_date)

		received = self.cheque_type == "Received"
		base = self.holding_base()
		lines = [
			self.bank_line(bank_account, base, exchange_rate, into_bank=received),
			Line(self.holding_account, debit=0 if received else base, credit=base if received else 0),
		]
		entry = accounting.post(
			self, clearance_date, lines, self.remark(_("Cleared")), clearance_date=clearance_date
		)
		self.clearance_date = clearance_date
		if received and not self.deposit_bank_account:
			self.deposit_bank_account = bank_account
		self.finish("Cleared", clearance_date, entry, bank_account)

	@frappe.whitelist()
	def bounce(self, bounce_date=None, reason=None, charges=0, recover_charges=0, remarks=None):
		"""The bank returned the cheque unpaid: the party owes / is owed again, on the bounce date."""
		self.begin("bounce")
		bounce_date = getdate(bounce_date or nowdate())
		self.validate_action_date(bounce_date, _("Bounce date"))
		charges = flt(charges)
		if charges < 0:
			frappe.throw(_("Charges cannot be negative."))

		bank_account = self.presented_bank_account()
		party_lines = [
			line.reversed()
			for line in accounting.lines_of(self.journal_entry)
			if line.account != self.holding_account
		]
		if self.status == "Cleared":
			clearance = self.last_event("Cleared").journal_entry
			lines = [
				*party_lines,
				*(line.reversed() for line in accounting.lines_of(clearance, {bank_account})),
			]
		else:
			lines = [
				*party_lines,
				*(
					line.reversed()
					for line in accounting.lines_of(self.journal_entry, {self.holding_account})
				),
			]

		if charges:
			if not bank_account:
				frappe.throw(_("Bounce charges need the bank account the cheque was presented through."))
			lines += self.charge_lines(bank_account, charges, cint_bool(recover_charges))

		entry = accounting.post(
			self, bounce_date, lines, self.remark(_("Bounced") + (f" ({reason})" if reason else ""))
		)
		self.bounce_date = bounce_date
		self.bounce_reason = reason
		self.bank_charges = charges
		self.finish("Bounced", bounce_date, entry, bank_account, remarks or reason)

	@frappe.whitelist()
	def return_cheque(self, return_date=None, remarks=None):
		"""Hand an undeposited cheque back to the party (or stop an issued one): reverse the receipt."""
		self.begin("return")
		return_date = getdate(return_date or nowdate())
		self.validate_action_date(return_date, _("Return date"))
		lines = [line.reversed() for line in accounting.lines_of(self.journal_entry)]
		entry = accounting.post(self, return_date, lines, self.remark(_("Returned")))
		self.return_date = return_date
		self.finish("Returned", return_date, entry, remarks=remarks)

	@frappe.whitelist()
	def undo_last_step(self):
		"""Take back the last deposit, clearance, bounce or return, cancelling its entry."""
		self.check_permission("cancel")
		self.lock()
		if self.docstatus != 1 or not self.events:
			frappe.throw(_("Nothing to undo."))
		last = self.events[-1]
		if last.event in ("Received", "Issued"):
			frappe.throw(_("Cancel the cheque to undo its receipt."))
		if last.event == "Replaced":
			frappe.throw(
				_("Cancel the replacement cheque {0} to undo the replacement.").format(self.replaced_by)
			)
		if last.journal_entry:
			accounting.cancel(last.journal_entry)

		clear_fields = {
			"Deposited": ("deposit_date", "deposit_bank_account"),
			"Cleared": ("clearance_date",),
			"Bounced": ("bounce_date", "bounce_reason", "bank_charges"),
			"Returned": ("return_date",),
		}[last.event]
		for fieldname in clear_fields:
			self.set(fieldname, None)
		if last.event == "Cleared" and not self.deposit_date:
			self.deposit_bank_account = None
		self.remove(last)
		self.status = EVENT_STATUS.get(self.events[-1].event, self.events[-1].event)
		self.save_after_action()

	def charge_lines(self, bank_account, charges, recover: bool) -> list[Line]:
		if frappe.get_cached_value("Account", bank_account, "account_currency") != self.company_currency:
			frappe.throw(
				_("Bounce charges can only be posted to a bank account in {0}.").format(self.company_currency)
			)
		if recover:
			if self.party_account_currency != self.company_currency:
				frappe.throw(
					_("Charges can only be recovered from a party billed in {0}.").format(
						self.company_currency
					)
				)
			debit = Line(self.party_account, debit=charges, party_type=self.party_type, party=self.party)
		else:
			account = get_company_accounts(self.company).bank_charges_account
			if not account:
				frappe.throw(
					_("Set the Bounce Charges Account for {0} in Cheque Settings.").format(
						frappe.bold(self.company)
					)
				)
			debit = Line(account, debit=charges)
		return [debit, Line(bank_account, credit=charges)]

	# ---------------------------------------------------------------- action plumbing

	def begin(self, action: str):
		"""Check permission and state under a row lock, so two users cannot act at once."""
		self.check_permission("submit")
		self.lock()
		if self.docstatus != 1:
			frappe.throw(_("Submit the cheque first."))
		allowed = ACTION_STATUSES[action].get(self.cheque_type, ())
		if self.status not in allowed:
			frappe.throw(
				_("A {0} cheque that is {1} cannot be {2}.").format(
					_(self.cheque_type).lower(), frappe.bold(_(self.status)), _(ACTION_LABELS[action])
				),
				title=_("Not Allowed"),
			)

	def lock(self):
		current = frappe.db.get_value(
			"Cheque", self.name, ["status", "modified"], as_dict=True, for_update=True
		)
		if current.status != self.status or str(current.modified) != str(self.modified):
			frappe.throw(_("The cheque was changed by someone else. Reload and try again."))

	def validate_action_date(self, date, label):
		last = (
			max(getdate(event.event_date) for event in self.events)
			if self.events
			else getdate(self.posting_date)
		)
		if getdate(date) < last:
			frappe.throw(
				_("{0} cannot be before {1}, the date of the previous step.").format(
					label, frappe.format(last, {"fieldtype": "Date"})
				)
			)

	def validate_not_stale(self, on_date):
		validity = get_settings().cheque_validity_months
		if validity and getdate(on_date) > getdate(add_months(self.cheque_date, validity)):
			frappe.throw(
				_(
					"The cheque is older than {0} months on {1} and is stale. Return it or ask for a replacement."
				).format(validity, frappe.format(on_date, {"fieldtype": "Date"})),
				title=_("Stale Cheque"),
			)

	def last_event(self, event: str):
		return next(row for row in reversed(self.events) if row.event == event)

	def presented_bank_account(self) -> str | None:
		"""The bank the cheque went through: the clearing bank once cleared, else where it was deposited."""
		if self.status == "Cleared":
			return self.last_event("Cleared").bank_account
		return self.deposit_bank_account if self.cheque_type == "Received" else self.bank_account

	def append_event(self, event, date, journal_entry=None, bank_account=None, remarks=None):
		self.append(
			"events",
			{
				"event": event,
				"event_date": date,
				"journal_entry": journal_entry,
				"bank_account": bank_account,
				"remarks": remarks,
				"user": frappe.session.user,
			},
		)

	def save_events(self):
		"""Event rows added in on_submit, after the document's children were already written."""
		for row in self.events:
			if row.is_new():
				row.db_insert()

	def finish(self, status, date, journal_entry=None, bank_account=None, remarks=None):
		self.append_event(status, date, journal_entry, bank_account, remarks)
		self.status = status
		self.save_after_action()

	def save_after_action(self):
		self.flags.ignore_permissions = True
		self.save()
		self.notify_update()

	# ---------------------------------------------------------------- replacement

	def mark_original_replaced(self):
		original = frappe.get_doc("Cheque", self.replacement_of)
		if original.status not in ACTION_STATUSES["replace"][original.cheque_type]:
			frappe.throw(
				_("Cheque {0} is {1} and cannot be replaced.").format(original.name, _(original.status))
			)
		if original.replaced_by:
			frappe.throw(
				_("Cheque {0} is already replaced by {1}.").format(original.name, original.replaced_by)
			)
		original.replaced_by = self.name
		original.append_event("Replaced", self.posting_date, remarks=_("Replaced by {0}").format(self.name))
		original.status = "Replaced"
		original.save_after_action()

	def restore_original(self):
		original = frappe.get_doc("Cheque", self.replacement_of)
		if original.replaced_by != self.name:
			return
		original.replaced_by = None
		for row in reversed(original.events):
			if row.event == "Replaced":
				original.remove(row)
				break
		original.status = original.events[-1].event
		original.save_after_action()


EVENT_STATUS = {"Received": "In Hand", "Issued": "Issued"}
ACTION_LABELS = {
	"deposit": "deposited",
	"clear": "cleared",
	"bounce": "marked as bounced",
	"return": "returned",
	"replace": "replaced",
}


def cint_bool(value) -> bool:
	return bool(frappe.utils.cint(value))


# -------------------------------------------------------------------- whitelisted helpers


@frappe.whitelist()
def get_outstanding_invoices(company: str, party_type: str, party: str, cheque_type: str) -> list[dict]:
	"""Open invoices the cheque can settle, oldest due first, with the amount still open."""
	frappe.has_permission("Cheque", "create", throw=True)
	doctype = INVOICE_OF_PARTY.get(party_type)
	if not doctype:
		frappe.throw(_("Party Type must be Customer or Supplier."))
	frappe.has_permission(doctype, "read", throw=True)

	expects_positive = (cheque_type == "Received") == (party_type == "Customer")
	invoices = frappe.get_list(
		doctype,
		filters={
			"docstatus": 1,
			"company": company,
			PARTY_FIELD[doctype]: party,
			"outstanding_amount": (">", 0) if expects_positive else ("<", 0),
		},
		fields=["name", "posting_date", "due_date", "grand_total", "outstanding_amount"],
		order_by="due_date asc, posting_date asc, name asc",
	)
	for invoice in invoices:
		invoice.open_amount = abs(flt(invoice.outstanding_amount))
	return invoices


@frappe.whitelist()
def make_cheque_from_invoice(source_name: str, args: str | dict | None = None):
	"""A draft cheque settling what is still open on the invoice. `args.source_doctype` names the invoice type."""
	source_doctype = frappe.parse_json(args or {}).get("source_doctype")
	if source_doctype not in PARTY_FIELD:
		frappe.throw(_("Cheques can be created only from Sales or Purchase Invoices."))
	invoice = frappe.get_doc(source_doctype, source_name)
	invoice.check_permission("read")
	if invoice.docstatus != 1 or not flt(invoice.outstanding_amount):
		frappe.throw(_("{0} has nothing outstanding.").format(source_name))

	party_type = "Customer" if source_doctype == "Sales Invoice" else "Supplier"
	outstanding = flt(invoice.outstanding_amount)
	# Positive outstanding on a Sales Invoice is collected; on a Purchase Invoice it is paid.
	is_refund = outstanding < 0
	cheque_type = (
		("Received" if party_type == "Customer" else "Issued")
		if not is_refund
		else ("Issued" if party_type == "Customer" else "Received")
	)

	cheque = frappe.new_doc("Cheque")
	cheque.update(
		{
			"cheque_type": cheque_type,
			"company": invoice.company,
			"party_type": party_type,
			"party": invoice.get(PARTY_FIELD[source_doctype]),
			"amount": abs(outstanding),
			"exchange_rate": invoice.get("conversion_rate") or 1,
		}
	)
	cheque.append(
		"references",
		{
			"reference_doctype": source_doctype,
			"reference_name": source_name,
			"due_date": invoice.due_date,
			"outstanding_amount": outstanding,
			"allocated_amount": abs(outstanding),
		},
	)
	return cheque


@frappe.whitelist()
def make_replacement(source_name: str):
	"""A draft cheque for the same party, settling what the bounced / returned one left open."""
	original = frappe.get_doc("Cheque", source_name)
	original.check_permission("read")
	frappe.has_permission("Cheque", "create", throw=True)
	if original.status not in ACTION_STATUSES["replace"].get(original.cheque_type, ()):
		frappe.throw(_("Only a bounced or returned cheque can be replaced."))
	if original.replaced_by:
		frappe.throw(_("Cheque {0} is already replaced by {1}.").format(original.name, original.replaced_by))

	cheque = frappe.new_doc("Cheque")
	for fieldname in (
		"cheque_type", "company", "party_type", "party", "bank_name", "bank_branch",
		"mode_of_payment", "bank_account", "amount", "exchange_rate", "cheque_no",
	):  # fmt: skip
		cheque.set(fieldname, original.get(fieldname))
	for fieldname in accounting.dimension_values(original):
		cheque.set(fieldname, original.get(fieldname))
	cheque.replacement_of = original.name
	cheque.remarks = _("Replacement for {0}").format(original.name)

	open_invoices = {
		row.name: row
		for row in get_outstanding_invoices(
			original.company, original.party_type, original.party, original.cheque_type
		)
	}
	for row in original.references:
		invoice = open_invoices.get(row.reference_name)
		if invoice:
			cheque.append(
				"references",
				{
					"reference_doctype": row.reference_doctype,
					"reference_name": row.reference_name,
					"due_date": invoice.due_date,
					"outstanding_amount": invoice.outstanding_amount,
					"allocated_amount": min(flt(row.allocated_amount), invoice.open_amount),
				},
			)
	return cheque
