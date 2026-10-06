# Copyright (c) 2026, Vinay Mishra and contributors
# License: MIT. See LICENSE

"""Per party: cheques presented, how many bounced, the bounce rate and the charges incurred.
A high rate is a credit-risk signal before accepting the next post-dated cheque."""

import frappe
from frappe import _
from frappe.utils import flt

from pdc_management.pdc_management.report.common import cheque_filters, date_range

# A cheque counts as presented once it reached the bank: cleared, bounced, or replaced after a bounce.
PRESENTED = ("Cleared", "Bounced", "Replaced")


def execute(filters=None):
	filters = frappe._dict(filters or {})
	data = get_data(filters)
	return get_columns(), data, None, get_chart(data)


def get_columns() -> list[dict]:
	return [
		{"label": _("Party Type"), "fieldname": "party_type", "fieldtype": "Data", "hidden": 1},
		{
			"label": _("Party"),
			"fieldname": "party",
			"fieldtype": "Dynamic Link",
			"options": "party_type",
			"width": 140,
		},
		{"label": _("Party Name"), "fieldname": "party_name", "fieldtype": "Data", "width": 180},
		{"label": _("Cheques"), "fieldname": "cheques", "fieldtype": "Int", "width": 80},
		{"label": _("Presented"), "fieldname": "presented", "fieldtype": "Int", "width": 90},
		{"label": _("Bounced"), "fieldname": "bounced", "fieldtype": "Int", "width": 80},
		{"label": _("Bounce Rate %"), "fieldname": "bounce_rate", "fieldtype": "Percent", "width": 110},
		{"label": _("Bounced Amount"), "fieldname": "bounced_amount", "fieldtype": "Currency", "width": 130},
		{"label": _("Bounce Charges"), "fieldname": "bank_charges", "fieldtype": "Currency", "width": 120},
		{"label": _("Last Bounce"), "fieldname": "last_bounce", "fieldtype": "Date", "width": 100},
		{"label": _("Most Common Reason"), "fieldname": "top_reason", "fieldtype": "Data", "width": 170},
	]


def get_data(filters) -> list[dict]:
	conditions = date_range(filters, "cheque_date", cheque_filters(filters))
	conditions.setdefault("cheque_type", "Received")
	cheques = frappe.get_list(
		"Cheque",
		filters=conditions,
		fields=[
			"party_type",
			"party",
			"party_name",
			"status",
			"base_amount",
			"bounce_date",
			"bounce_reason",
			"bank_charges",
		],
	)

	parties: dict[tuple, dict] = {}
	for cheque in cheques:
		row = parties.setdefault(
			(cheque.party_type, cheque.party),
			frappe._dict(
				party_type=cheque.party_type,
				party=cheque.party,
				party_name=cheque.party_name,
				cheques=0,
				presented=0,
				bounced=0,
				bounced_amount=0.0,
				bank_charges=0.0,
				last_bounce=None,
				reasons={},
			),
		)
		row.cheques += 1
		was_bounced = bool(cheque.bounce_date)
		if cheque.status in PRESENTED or was_bounced:
			row.presented += 1
		if was_bounced:
			row.bounced += 1
			row.bounced_amount += flt(cheque.base_amount)
			row.bank_charges += flt(cheque.bank_charges)
			if not row.last_bounce or cheque.bounce_date > row.last_bounce:
				row.last_bounce = cheque.bounce_date
			if cheque.bounce_reason:
				row.reasons[cheque.bounce_reason] = row.reasons.get(cheque.bounce_reason, 0) + 1

	rows = []
	for row in parties.values():
		row.bounce_rate = flt(row.bounced * 100 / row.presented, 2) if row.presented else 0
		row.top_reason = _(max(row.reasons, key=row.reasons.get)) if row.reasons else None
		del row["reasons"]
		if not filters.get("only_bounced") or row.bounced:
			rows.append(row)
	return sorted(rows, key=lambda row: (-row.bounce_rate, -row.bounced_amount))


def get_chart(data) -> dict | None:
	top = [row for row in data if row.bounced][:10]
	if not top:
		return None
	return {
		"data": {
			"labels": [row.party_name or row.party for row in top],
			"datasets": [{"name": _("Bounce Rate %"), "values": [row.bounce_rate for row in top]}],
		},
		"type": "bar",
		"colors": ["#e24c4c"],
	}
