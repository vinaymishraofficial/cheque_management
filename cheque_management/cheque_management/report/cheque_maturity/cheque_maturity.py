# Copyright (c) 2026, Vinay Mishra and contributors
# License: MIT. See LICENSE

"""Open cheques bucketed by how far their cheque date is from the report date."""

import frappe
from frappe import _
from frappe.utils import date_diff, getdate, nowdate

from cheque_management.cheque_management.report.common import cheque_filters

OPEN_STATUSES = ("In Hand", "Issued", "Deposited")
BUCKETS = (
	("overdue", "Overdue", None, -1),
	("due_0_7", "0-7 Days", 0, 7),
	("due_8_30", "8-30 Days", 8, 30),
	("due_31_60", "31-60 Days", 31, 60),
	("due_61_90", "61-90 Days", 61, 90),
	("due_90_plus", "90+ Days", 91, None),
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	data = get_data(filters)
	return get_columns(filters), data, None, get_chart(data)


def get_columns(filters) -> list[dict]:
	group = filters.get("group_by") or "Cheque"
	columns = []
	if group == "Cheque":
		columns += [
			{
				"label": _("Cheque"),
				"fieldname": "name",
				"fieldtype": "Link",
				"options": "Cheque",
				"width": 140,
			},
			{"label": _("Cheque No"), "fieldname": "cheque_no", "fieldtype": "Data", "width": 100},
			{"label": _("Cheque Date"), "fieldname": "cheque_date", "fieldtype": "Date", "width": 100},
			{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 90},
		]
	columns += [
		{"label": _("Type"), "fieldname": "cheque_type", "fieldtype": "Data", "width": 90},
		{"label": _("Party Type"), "fieldname": "party_type", "fieldtype": "Data", "hidden": 1},
		{
			"label": _("Party"),
			"fieldname": "party",
			"fieldtype": "Dynamic Link",
			"options": "party_type",
			"width": 130,
		},
		{"label": _("Party Name"), "fieldname": "party_name", "fieldtype": "Data", "width": 170},
	]
	if group == "Cheque":
		columns.append({"label": _("Days"), "fieldname": "days", "fieldtype": "Int", "width": 70})
	columns.append({"label": _("Total"), "fieldname": "total", "fieldtype": "Currency", "width": 130})
	columns += [
		{"label": _(label), "fieldname": key, "fieldtype": "Currency", "width": 120}
		for key, label, *_rest in BUCKETS
	]
	return columns


def get_data(filters) -> list[dict]:
	as_on = getdate(filters.get("as_on_date") or nowdate())
	conditions = cheque_filters(filters)
	conditions["status"] = ("in", OPEN_STATUSES)
	cheques = frappe.get_list(
		"Cheque",
		filters=conditions,
		fields=[
			"name",
			"cheque_no",
			"cheque_date",
			"status",
			"cheque_type",
			"party_type",
			"party",
			"party_name",
			"base_amount",
		],
		order_by="cheque_date asc",
	)

	rows = []
	for cheque in cheques:
		days = date_diff(cheque.cheque_date, as_on)
		row = {**cheque, "days": days, "total": cheque.base_amount}
		for key, _label, low, high in BUCKETS:
			row[key] = cheque.base_amount if in_bucket(days, low, high) else 0
		rows.append(row)

	if (filters.get("group_by") or "Cheque") == "Party":
		return group_by_party(rows)
	return rows


def in_bucket(days: int, low, high) -> bool:
	return (low is None or days >= low) and (high is None or days <= high)


def group_by_party(rows) -> list[dict]:
	grouped: dict[tuple, dict] = {}
	for row in rows:
		key = (row["cheque_type"], row["party_type"], row["party"])
		target = grouped.setdefault(
			key,
			{field: row[field] for field in ("cheque_type", "party_type", "party", "party_name")}
			| {"total": 0, **{bucket[0]: 0 for bucket in BUCKETS}},
		)
		target["total"] += row["total"]
		for key_name, *_rest in BUCKETS:
			target[key_name] += row[key_name]
	return sorted(grouped.values(), key=lambda row: -row["total"])


def get_chart(data) -> dict | None:
	if not data:
		return None
	values = [sum(row[key] for row in data) for key, *_rest in BUCKETS]
	return {
		"data": {
			"labels": [_(label) for _key, label, *_rest in BUCKETS],
			"datasets": [{"name": _("Amount"), "values": values}],
		},
		"type": "bar",
		"fieldtype": "Currency",
		"colors": ["#e24c4c"],
	}
