# Copyright (c) 2026, Vinay Mishra and contributors
# License: MIT. See LICENSE

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, add_months, flt

from pdc_management.pdc_management.doctype.cheque.cheque import (
	get_outstanding_invoices,
	make_cheque_from_invoice,
	make_replacement,
)
from pdc_management.tests.utils import (
	COMPANY,
	CUSTOMER,
	SUPPLIER,
	USD_CUSTOMER,
	account,
	balance,
	base_date,
	configure_settings,
	make_cheque,
	make_invoice,
	outstanding,
	party_balance,
	setup_test_data,
)


def _linked_doctypes() -> list[str]:
	"""Every doctype Cheque links to, including accounting dimension fields added on the site."""
	meta = frappe.get_meta("Cheque")
	linked = {df.options for df in meta.get_link_fields()}
	for table in meta.get_table_fields():
		linked |= {df.options for df in frappe.get_meta(table.options).get_link_fields()}
	return sorted(linked)


# The tests build their own company and masters (tests/utils.py). Without this the runner would
# import ERPNext's test modules for every linked doctype, which create and commit generic test data.
IGNORE_TEST_RECORD_DEPENDENCIES = _linked_doctypes()
test_ignore = IGNORE_TEST_RECORD_DEPENDENCIES  # Frappe v15 name

IN_HAND = account("Cheques in Hand")
ISSUED = account("Cheques Issued")
CHARGES = account("Cheque Bounce Charges")
BANK = account("_Test Cheque Bank")
BANK_2 = account("_Test Cheque Bank 2")
USD_BANK = account("_Test Cheque USD Bank")


class ChequeTestCase(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		setup_test_data()

	def setUp(self):
		configure_settings()

	def gl(self, journal_entry: str) -> dict[str, float]:
		"""Net debit per account of a journal entry, in company currency."""
		rows = frappe.get_all(
			"GL Entry",
			filters={"voucher_no": journal_entry, "is_cancelled": 0},
			fields=["account", "debit", "credit"],
		)
		net: dict[str, float] = {}
		for row in rows:
			net[row.account] = flt(net.get(row.account, 0) + row.debit - row.credit, 2)
		return net


class TestReceivedCheque(ChequeTestCase):
	def test_receipt_settles_invoice_into_cheques_in_hand(self):
		invoice = make_invoice(rate=1000)
		before = balance(IN_HAND)
		cheque = make_cheque(amount=1000, invoices=[(invoice, 1000)])

		self.assertEqual(cheque.status, "In Hand")
		self.assertEqual(outstanding(invoice), 0)
		self.assertEqual(balance(IN_HAND) - before, 1000)
		self.assertEqual(cheque.events[0].event, "Received")
		self.assertEqual(frappe.db.get_value("Journal Entry", cheque.journal_entry, "cheque"), cheque.name)

	def test_deposit_then_clear_moves_amount_to_bank(self):
		invoice = make_invoice(rate=700)
		cheque = make_cheque(amount=700, invoices=[(invoice, 700)], cheque_date=add_days(base_date(), 10))
		in_hand_before, bank_before = balance(IN_HAND), balance(BANK)

		cheque.deposit(add_days(base_date(), 10), BANK)
		self.assertEqual(cheque.status, "Deposited")
		self.assertEqual(balance(IN_HAND), in_hand_before, "deposit posts nothing")

		cheque.clear(add_days(base_date(), 12))
		self.assertEqual(cheque.status, "Cleared")
		entry = cheque.events[-1].journal_entry
		self.assertEqual(self.gl(entry), {BANK: 700, IN_HAND: -700})
		self.assertEqual(
			frappe.db.get_value("Journal Entry", entry, "clearance_date"), add_days(base_date(), 12)
		)
		self.assertEqual(balance(BANK) - bank_before, 700)
		self.assertEqual(balance(IN_HAND), in_hand_before - 700)

	def test_bounce_after_deposit_reopens_invoice_and_books_charges(self):
		invoice = make_invoice(rate=500)
		cheque = make_cheque(amount=500, invoices=[(invoice, 500)])
		cheque.deposit(base_date(), BANK)
		cheque.bounce(add_days(base_date(), 3), "Insufficient Funds", charges=50)

		self.assertEqual(cheque.status, "Bounced")
		self.assertEqual(outstanding(invoice), 500)
		self.assertEqual(
			self.gl(cheque.events[-1].journal_entry),
			{account("Debtors"): 500, IN_HAND: -500, CHARGES: 50, BANK: -50},
		)
		self.assertEqual(cheque.bounce_reason, "Insufficient Funds")

	def test_bounce_charges_recovered_from_customer(self):
		invoice = make_invoice(rate=300)
		cheque = make_cheque(amount=300, invoices=[(invoice, 300)])
		cheque.deposit(base_date(), BANK)
		before = party_balance("Customer", CUSTOMER)
		cheque.bounce(base_date(), "Signature Mismatch", charges=25, recover_charges=1)

		self.assertEqual(party_balance("Customer", CUSTOMER) - before, 325)

	def test_bounce_after_clearance_takes_money_back_from_bank(self):
		invoice = make_invoice(rate=400)
		cheque = make_cheque(amount=400, invoices=[(invoice, 400)])
		cheque.clear(base_date(), BANK_2)
		cheque.bounce(add_days(base_date(), 2), "Payment Stopped by Drawer")

		self.assertEqual(outstanding(invoice), 400)
		self.assertEqual(self.gl(cheque.events[-1].journal_entry), {account("Debtors"): 400, BANK_2: -400})

	def test_return_in_hand_cheque(self):
		invoice = make_invoice(rate=200)
		cheque = make_cheque(amount=200, invoices=[(invoice, 200)])
		cheque.return_cheque(add_days(base_date(), 1), "Customer paid in cash instead")

		self.assertEqual(cheque.status, "Returned")
		self.assertEqual(outstanding(invoice), 200)

	def test_unallocated_amount_is_an_advance(self):
		invoice = make_invoice(rate=600)
		before = party_balance("Customer", CUSTOMER)
		cheque = make_cheque(amount=1000, invoices=[(invoice, 600)])

		self.assertEqual(cheque.unallocated_amount, 400)
		self.assertEqual(party_balance("Customer", CUSTOMER) - before, -1000)
		advance = frappe.get_all(
			"Journal Entry Account",
			filters={"parent": cheque.journal_entry, "is_advance": "Yes"},
			pluck="credit_in_account_currency",
		)
		self.assertEqual(advance, [400])

	def test_unallocated_amount_blocked_when_disabled(self):
		configure_settings(allow_on_account=0)
		invoice = make_invoice(rate=600)
		with self.assertRaisesRegex(frappe.ValidationError, "Allocate the full cheque amount"):
			make_cheque(amount=1000, invoices=[(invoice, 600)])

	def test_cheque_settles_several_invoices(self):
		first, second = make_invoice(rate=300), make_invoice(rate=500)
		make_cheque(amount=800, invoices=[(first, 300), (second, 500)])
		self.assertEqual((outstanding(first), outstanding(second)), (0, 0))

	def test_partial_cheques_cannot_overpay_invoice(self):
		invoice = make_invoice(rate=1000)
		make_cheque(amount=600, invoices=[(invoice, 600)])
		with self.assertRaisesRegex(frappe.ValidationError, "more than the outstanding"):
			make_cheque(amount=600, invoices=[(invoice, 600)])

	def test_invoice_of_another_party_rejected(self):
		invoice = make_invoice(rate=100, party=USD_CUSTOMER, currency="USD", conversion_rate=80)
		with self.assertRaisesRegex(frappe.ValidationError, "not billed to"):
			make_cheque(amount=100, invoices=[(invoice, 100)])


class TestChequeRules(ChequeTestCase):
	def test_duplicate_cheque_number_blocked(self):
		cheque = make_cheque(amount=100)
		with self.assertRaisesRegex(frappe.ValidationError, "already recorded"):
			make_cheque(amount=100, cheque_no=cheque.cheque_no)

	def test_duplicate_allowed_when_disabled(self):
		configure_settings(block_duplicate_cheque=0)
		cheque = make_cheque(amount=100)
		make_cheque(amount=100, cheque_no=cheque.cheque_no)

	def test_post_dated_cheque_cannot_be_deposited_early(self):
		cheque = make_cheque(amount=100, cheque_date=add_days(base_date(), 15))
		self.assertTrue(cheque.is_post_dated)
		with self.assertRaisesRegex(frappe.ValidationError, "before its cheque date"):
			cheque.deposit(add_days(base_date(), 5), BANK)

	def test_cheque_cannot_clear_before_its_date(self):
		cheque = make_cheque(amount=100, cheque_date=add_days(base_date(), 15))
		with self.assertRaisesRegex(frappe.ValidationError, "cannot clear before"):
			cheque.clear(add_days(base_date(), 5), BANK)

	def test_stale_cheque_cannot_be_received(self):
		with self.assertRaisesRegex(frappe.ValidationError, "stale"):
			make_cheque(amount=100, cheque_date=add_months(base_date(), -4))

	def test_stale_cheque_cannot_be_deposited(self):
		cheque = make_cheque(amount=100)
		with self.assertRaisesRegex(frappe.ValidationError, "stale"):
			cheque.deposit(add_days(add_months(base_date(), 3), 1), BANK)

	def test_step_cannot_be_dated_before_previous_step(self):
		cheque = make_cheque(amount=100)
		cheque.deposit(add_days(base_date(), 5), BANK)
		with self.assertRaisesRegex(frappe.ValidationError, "previous step"):
			cheque.clear(add_days(base_date(), 4))

	def test_actions_follow_status(self):
		cheque = make_cheque(amount=100)
		with self.assertRaisesRegex(frappe.ValidationError, "cannot be"):
			cheque.bounce(base_date(), "Other")

	def test_bank_account_must_be_a_bank(self):
		cheque = make_cheque(amount=100)
		with self.assertRaisesRegex(frappe.ValidationError, "not a bank account"):
			cheque.deposit(base_date(), IN_HAND)

	def test_settings_reject_party_type_holding_account(self):
		settings = frappe.get_single("Cheque Settings")
		row = next(row for row in settings.company_accounts if row.company == COMPANY)
		row.cheques_in_hand_account = account("Debtors")
		with self.assertRaisesRegex(frappe.ValidationError, "cannot be of type"):
			settings.save()


class TestCancelAndUndo(ChequeTestCase):
	def test_cancel_in_hand_cheque_reverses_receipt(self):
		invoice = make_invoice(rate=250)
		cheque = make_cheque(amount=250, invoices=[(invoice, 250)])
		cheque.cancel()

		self.assertEqual(cheque.status, "Cancelled")
		self.assertEqual(frappe.db.get_value("Journal Entry", cheque.journal_entry, "docstatus"), 2)
		self.assertEqual(outstanding(invoice), 250)

	def test_cancel_blocked_after_deposit(self):
		cheque = make_cheque(amount=100)
		cheque.deposit(base_date(), BANK)
		with self.assertRaisesRegex(frappe.ValidationError, "cannot be cancelled"):
			cheque.cancel()

	def test_undo_clearance(self):
		cheque = make_cheque(amount=100)
		cheque.deposit(base_date(), BANK)
		cheque.clear(base_date())
		clearance = cheque.events[-1].journal_entry

		cheque.undo_last_step()
		self.assertEqual(cheque.status, "Deposited")
		self.assertIsNone(cheque.clearance_date)
		self.assertEqual(frappe.db.get_value("Journal Entry", clearance, "docstatus"), 2)

		cheque.undo_last_step()
		self.assertEqual(cheque.status, "In Hand")
		self.assertIsNone(cheque.deposit_bank_account)

	def test_undo_bounce_restores_settlement(self):
		invoice = make_invoice(rate=100)
		cheque = make_cheque(amount=100, invoices=[(invoice, 100)])
		cheque.deposit(base_date(), BANK)
		cheque.bounce(base_date(), "Other")
		cheque.undo_last_step()

		self.assertEqual(cheque.status, "Deposited")
		self.assertEqual(outstanding(invoice), 0)

	def test_cheque_entry_cannot_be_cancelled_directly(self):
		cheque = make_cheque(amount=100)
		entry = frappe.get_doc("Journal Entry", cheque.journal_entry)
		with self.assertRaisesRegex(frappe.ValidationError, "belongs to cheque"):
			entry.cancel()

	def test_invoice_with_active_cheque_cannot_be_cancelled(self):
		invoice = make_invoice(rate=100)
		make_cheque(amount=100, invoices=[(invoice, 100)])
		invoice.reload()
		with self.assertRaises(frappe.ValidationError):
			invoice.cancel()


class TestReplacement(ChequeTestCase):
	def test_replace_bounced_cheque(self):
		invoice = make_invoice(rate=900)
		original = make_cheque(amount=900, invoices=[(invoice, 900)])
		original.deposit(base_date(), BANK)
		original.bounce(base_date(), "Insufficient Funds")

		replacement = make_replacement(original.name)
		self.assertEqual(replacement.references[0].allocated_amount, 900)
		self.assertEqual(
			replacement.cheque_no, original.cheque_no, "re-presenting the same cheque is allowed"
		)
		replacement.posting_date = base_date()
		replacement.cheque_date = add_days(base_date(), 7)
		replacement.insert()
		replacement.submit()

		original.reload()
		self.assertEqual((original.status, original.replaced_by), ("Replaced", replacement.name))
		self.assertEqual(outstanding(invoice), 0)

		replacement.reload()
		replacement.cancel()
		original.reload()
		self.assertEqual((original.status, original.replaced_by), ("Bounced", None))

	def test_cheque_in_hand_cannot_be_replaced(self):
		cheque = make_cheque(amount=100)
		with self.assertRaisesRegex(frappe.ValidationError, "bounced or returned"):
			make_replacement(cheque.name)


class TestIssuedCheque(ChequeTestCase):
	def test_issue_and_clear(self):
		invoice = make_invoice("Purchase Invoice", rate=800)
		cheque = make_cheque(
			"Issued", amount=800, invoices=[(invoice, 800)], cheque_date=add_days(base_date(), 20)
		)

		self.assertEqual(cheque.status, "Issued")
		self.assertEqual(outstanding(invoice), 0)
		self.assertEqual(self.gl(cheque.journal_entry), {account("Creditors"): 800, ISSUED: -800})

		cheque.clear(add_days(base_date(), 21))
		self.assertEqual(self.gl(cheque.events[-1].journal_entry), {ISSUED: 800, BANK: -800})

	def test_issued_cheque_bounce_reopens_bill(self):
		invoice = make_invoice("Purchase Invoice", rate=350)
		cheque = make_cheque("Issued", amount=350, invoices=[(invoice, 350)])
		cheque.bounce(base_date(), "Insufficient Funds")
		self.assertEqual(outstanding(invoice), 350)

	def test_stop_issued_cheque(self):
		invoice = make_invoice("Purchase Invoice", rate=150)
		cheque = make_cheque("Issued", amount=150, invoices=[(invoice, 150)])
		cheque.return_cheque(base_date())
		self.assertEqual((cheque.status, outstanding(invoice)), ("Returned", 150))

	def test_refund_cheque_to_customer_against_credit_note(self):
		invoice = make_invoice(rate=500)
		credit_note = make_invoice(rate=500, is_return=1, return_against=invoice.name)
		# The credit note leaves the original paid and itself at -500: the customer is owed a refund.
		self.assertEqual(outstanding(credit_note), -500)

		make_cheque(
			"Issued", party_type="Customer", party=CUSTOMER, amount=500, invoices=[(credit_note, 500)]
		)
		self.assertEqual(outstanding(credit_note), 0)


class TestMultiCurrency(ChequeTestCase):
	def test_usd_cheque_cleared_into_inr_bank(self):
		invoice = make_invoice(rate=100, party=USD_CUSTOMER, currency="USD", conversion_rate=80)
		cheque = make_cheque(amount=100, party=USD_CUSTOMER, exchange_rate=82, invoices=[(invoice, 100)])

		self.assertEqual((cheque.party_account_currency, cheque.base_amount), ("USD", 8200))
		self.assertEqual(outstanding(invoice), 0)
		self.assertEqual(self.gl(cheque.journal_entry)[IN_HAND], 8200)

		cheque.clear(base_date(), BANK)
		self.assertEqual(self.gl(cheque.events[-1].journal_entry), {BANK: 8200, IN_HAND: -8200})

	def test_usd_cheque_cleared_into_usd_bank_books_exchange_difference(self):
		invoice = make_invoice(rate=100, party=USD_CUSTOMER, currency="USD", conversion_rate=80)
		cheque = make_cheque(amount=100, party=USD_CUSTOMER, exchange_rate=80, invoices=[(invoice, 100)])
		cheque.clear(base_date(), USD_BANK, exchange_rate=83)

		gl = self.gl(cheque.events[-1].journal_entry)
		gain_loss = frappe.get_cached_value("Company", COMPANY, "exchange_gain_loss_account")
		self.assertEqual(gl[USD_BANK], 8300)
		self.assertEqual(gl[IN_HAND], -8000)
		self.assertEqual(gl[gain_loss], -300)


class TestHelpers(ChequeTestCase):
	def test_outstanding_invoices_oldest_first(self):
		later = make_invoice(rate=100, posting_date=add_days(base_date(), 5))
		earlier = make_invoice(rate=100, posting_date=base_date())
		names = [row.name for row in get_outstanding_invoices(COMPANY, "Customer", CUSTOMER, "Received")]
		self.assertLess(names.index(earlier.name), names.index(later.name))

	def test_make_cheque_from_invoice(self):
		invoice = make_invoice("Purchase Invoice", rate=450)
		cheque = make_cheque_from_invoice(invoice.name, {"source_doctype": "Purchase Invoice"})
		self.assertEqual((cheque.cheque_type, cheque.party, cheque.amount), ("Issued", SUPPLIER, 450))
		self.assertEqual(cheque.references[0].allocated_amount, 450)

	def test_permission_needed_for_actions(self):
		cheque = make_cheque(amount=100)
		frappe.set_user("Guest")
		try:
			with self.assertRaises(frappe.PermissionError):
				cheque.deposit(base_date(), BANK)
		finally:
			frappe.set_user("Administrator")
