# Copyright (c) 2026, Vinay Mishra and contributors
# License: MIT. See LICENSE

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate, nowdate

from cheque_management.cheque_management.report.cheque_bounce_analysis import cheque_bounce_analysis
from cheque_management.cheque_management.report.cheque_maturity import cheque_maturity
from cheque_management.cheque_management.report.cheque_register import cheque_register
from cheque_management.tasks import get_sections, send_daily_digest
from cheque_management.tests.utils import (
	COMPANY,
	CUSTOMER,
	account,
	base_date,
	configure_settings,
	make_cheque,
	setup_test_data,
)


class TestReports(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		setup_test_data()
		configure_settings()
		cls.open_cheque = make_cheque(amount=100, cheque_date=add_days(base_date(), 10))
		cls.bounced = make_cheque(amount=200)
		cls.bounced.deposit(base_date(), account("_Test Cheque Bank"))
		cls.bounced.bounce(base_date(), "Insufficient Funds")

	def test_register_filters_by_status_and_party(self):
		_columns, data, *_rest = cheque_register.execute(
			{"company": COMPANY, "status": ["Bounced"], "party_type": "Customer", "party": [CUSTOMER]}
		)
		names = {row.name for row in data}
		self.assertIn(self.bounced.name, names)
		self.assertNotIn(self.open_cheque.name, names)

	def test_register_ignores_unknown_date_field(self):
		cheque_register.execute(
			{"company": COMPANY, "date_based_on": "name; drop table", "from_date": base_date()}
		)

	def test_maturity_buckets(self):
		_columns, data, *_rest = cheque_maturity.execute({"company": COMPANY, "as_on_date": base_date()})
		row = next(row for row in data if row["name"] == self.open_cheque.name)
		self.assertEqual((row["days"], row["due_8_30"], row["overdue"]), (10, 100, 0))

		_columns, grouped, *_rest = cheque_maturity.execute(
			{"company": COMPANY, "as_on_date": base_date(), "group_by": "Party"}
		)
		self.assertTrue(any(row["party"] == CUSTOMER for row in grouped))

	def test_bounce_analysis(self):
		_columns, data, *_rest = cheque_bounce_analysis.execute(
			{"company": COMPANY, "from_date": add_days(base_date(), -1), "to_date": add_days(base_date(), 30)}
		)
		row = next(row for row in data if row.party == CUSTOMER)
		self.assertGreaterEqual(row.bounced, 1)
		self.assertGreater(row.bounce_rate, 0)
		self.assertEqual(row.top_reason, "Insufficient Funds")


class TestDigest(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		setup_test_data()

	def test_sections_pick_due_and_overdue_cheques(self):
		configure_settings()
		today = getdate(nowdate())
		due = make_cheque(amount=100, posting_date=today, cheque_date=add_days(today, 3))
		overdue = make_cheque(amount=100, posting_date=add_days(today, -5), cheque_date=add_days(today, -2))

		sections = dict(get_sections(today, 7, 3))
		names = {label: {row.name for row in rows} for label, rows in sections.items()}
		self.assertIn(overdue.name, next(iter(names.values())))
		self.assertTrue(any(due.name in found for found in names.values()))

	def test_digest_is_sent_to_role_holders(self):
		configure_settings(digest_role="Accounts Manager")
		today = getdate(nowdate())
		cheque = make_cheque(amount=100, posting_date=today, cheque_date=today)
		user = make_user("cheque.digest@example.com", "Accounts Manager")

		with (
			patch("cheque_management.tasks.has_outgoing_email", return_value=True),
			patch("cheque_management.tasks.frappe.sendmail") as sendmail,
		):
			send_daily_digest()

		sent = {call.kwargs["recipients"][0]: call.kwargs for call in sendmail.call_args_list}
		self.assertIn(user, sent)
		rows = [row.name for _label, rows in sent[user]["args"]["sections"] for row in rows]
		self.assertIn(cheque.name, rows)

	def test_digest_skipped_without_outgoing_email_account(self):
		configure_settings()
		make_cheque(amount=100, posting_date=getdate(nowdate()), cheque_date=getdate(nowdate()))
		with (
			patch("cheque_management.tasks.has_outgoing_email", return_value=False),
			patch("cheque_management.tasks.frappe.sendmail") as sendmail,
		):
			send_daily_digest()
		sendmail.assert_not_called()

	def test_digest_off(self):
		configure_settings(send_daily_digest=0)
		before = frappe.db.count("Email Queue")
		send_daily_digest()
		self.assertEqual(frappe.db.count("Email Queue"), before)


def make_user(email: str, role: str) -> str:
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Digest",
				"send_welcome_email": 0,
				"roles": [{"role": role}],
			}
		).insert(ignore_permissions=True)
	return email
