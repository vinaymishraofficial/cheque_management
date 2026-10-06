# Copyright (c) 2026, Vinay Mishra and contributors
# License: MIT. See LICENSE

"""Daily digest: what to deposit, what is overdue, what is about to go stale and which issued
cheques will be presented soon. One email per recipient, covering only companies they can see."""

import frappe
from frappe import _
from frappe.utils import add_days, add_months, getdate, nowdate

from cheque_management.utils import get_settings

FIELDS = [
	"name",
	"company",
	"party_name",
	"cheque_no",
	"cheque_date",
	"amount",
	"party_account_currency",
	"status",
]


def send_daily_digest():
	settings = get_settings()
	if not settings.send_daily_digest or not settings.digest_role:
		return

	sections = get_sections(
		getdate(nowdate()), settings.digest_days_ahead or 0, settings.cheque_validity_months
	)
	if not any(rows for _label, rows in sections):
		return

	for user in get_recipients(settings.digest_role):
		visible = filter_for_user(sections, user)
		if not any(rows for _label, rows in visible):
			continue
		frappe.sendmail(
			recipients=[user],
			subject=_("Cheques to act on today"),
			template="cheque_digest",
			args={"sections": visible, "site_url": frappe.utils.get_url()},
			header=[_("Cheque Digest"), "blue"],
			now=False,
		)


def get_sections(today, days_ahead: int, validity_months: int) -> list[tuple[str, list]]:
	horizon = add_days(today, days_ahead)
	received_in_hand = {"docstatus": 1, "cheque_type": "Received", "status": "In Hand"}
	sections = [
		(
			_("Overdue for deposit"),
			frappe.get_all(
				"Cheque",
				filters={**received_in_hand, "cheque_date": ("<", today)},
				fields=FIELDS,
				order_by="cheque_date",
			),
		),
		(
			_("Due for deposit (next {0} days)").format(days_ahead),
			frappe.get_all(
				"Cheque",
				filters={**received_in_hand, "cheque_date": ("between", (today, horizon))},
				fields=FIELDS,
				order_by="cheque_date",
			),
		),
		(
			_("Issued cheques that may be presented (next {0} days)").format(days_ahead),
			frappe.get_all(
				"Cheque",
				filters={
					"docstatus": 1,
					"cheque_type": "Issued",
					"status": "Issued",
					"cheque_date": ("<=", horizon),
				},
				fields=FIELDS,
				order_by="cheque_date",
			),
		),
	]
	if validity_months:
		# Cheques that go stale within the horizon: cheque date + validity falls in [today, horizon].
		sections.append(
			(
				_("Going stale soon"),
				frappe.get_all(
					"Cheque",
					filters={
						**received_in_hand,
						"cheque_date": (
							"between",
							(add_months(today, -validity_months), add_months(horizon, -validity_months)),
						),
					},
					fields=FIELDS,
					order_by="cheque_date",
				),
			)
		)
	return sections


def get_recipients(role: str) -> list[str]:
	users = frappe.get_all(
		"Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent", distinct=True
	)
	if not users:
		return []
	return frappe.get_all(
		"User",
		filters=[
			["name", "in", users],
			["name", "not in", ("Guest", "Administrator")],
			["enabled", "=", 1],
			["user_type", "=", "System User"],
		],
		pluck="name",
	)


def filter_for_user(sections, user: str):
	allowed = {}

	def can_see(company):
		if company not in allowed:
			allowed[company] = frappe.has_permission("Cheque", "read", user=user) and frappe.has_permission(
				"Company", "read", doc=company, user=user
			)
		return allowed[company]

	return [(label, [row for row in rows if can_see(row.company)]) for label, rows in sections]
