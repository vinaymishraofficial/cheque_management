# Copyright (c) 2026, Vinay Mishra and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.utils import date_diff, getdate, nowdate

from pdc_management.pdc_management.report.common import cheque_filters, date_range

DATE_FIELDS = ("cheque_date", "posting_date")


def execute(filters=None):
	filters = frappe._dict(filters or {})
	data = get_data(filters)
	return get_columns(), data, None, get_chart(data), get_summary(data)


def get_columns() -> list[dict]:
	return [
		{"label": _("Cheque"), "fieldname": "name", "fieldtype": "Link", "options": "Cheque", "width": 140},
		{"label": _("Type"), "fieldname": "cheque_type", "fieldtype": "Data", "width": 90},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
		{"label": _("Party Type"), "fieldname": "party_type", "fieldtype": "Data", "width": 90, "hidden": 1},
		{
			"label": _("Party"),
			"fieldname": "party",
			"fieldtype": "Dynamic Link",
			"options": "party_type",
			"width": 130,
		},
		{"label": _("Party Name"), "fieldname": "party_name", "fieldtype": "Data", "width": 170},
		{"label": _("Cheque No"), "fieldname": "cheque_no", "fieldtype": "Data", "width": 100},
		{"label": _("Cheque Date"), "fieldname": "cheque_date", "fieldtype": "Date", "width": 100},
		{"label": _("Drawee Bank"), "fieldname": "bank_name", "fieldtype": "Data", "width": 120},
		{
			"label": _("Currency"),
			"fieldname": "party_account_currency",
			"fieldtype": "Link",
			"options": "Currency",
			"width": 70,
			"hidden": 1,
		},
		{
			"label": _("Amount"),
			"fieldname": "amount",
			"fieldtype": "Currency",
			"options": "party_account_currency",
			"width": 120,
		},
		{
			"label": _("Amount (Company Currency)"),
			"fieldname": "base_amount",
			"fieldtype": "Currency",
			"width": 140,
		},
		{"label": _("Days to Cheque Date"), "fieldname": "days_to_date", "fieldtype": "Int", "width": 90},
		{"label": _("Deposited"), "fieldname": "deposit_date", "fieldtype": "Date", "width": 100},
		{"label": _("Cleared"), "fieldname": "clearance_date", "fieldtype": "Date", "width": 100},
		{"label": _("Bounced"), "fieldname": "bounce_date", "fieldtype": "Date", "width": 100},
		{"label": _("Bounce Reason"), "fieldname": "bounce_reason", "fieldtype": "Data", "width": 140},
		{
			"label": _("Company"),
			"fieldname": "company",
			"fieldtype": "Link",
			"options": "Company",
			"width": 120,
		},
	]


def get_data(filters) -> list[dict]:
	date_field = (
		filters.get("date_based_on") if filters.get("date_based_on") in DATE_FIELDS else "cheque_date"
	)
	conditions = date_range(filters, date_field, cheque_filters(filters))
	rows = frappe.get_list(
		"Cheque",
		filters=conditions,
		fields=[
			"name",
			"cheque_type",
			"status",
			"party_type",
			"party",
			"party_name",
			"cheque_no",
			"cheque_date",
			"bank_name",
			"party_account_currency",
			"amount",
			"base_amount",
			"deposit_date",
			"clearance_date",
			"bounce_date",
			"bounce_reason",
			"company",
		],
		order_by="cheque_date asc, name asc",
	)
	today = getdate(nowdate())
	for row in rows:
		if row.status in ("In Hand", "Issued", "Deposited"):
			row.days_to_date = date_diff(row.cheque_date, today)
	return rows


def get_chart(data) -> dict | None:
	if not data:
		return None
	totals: dict[str, float] = {}
	for row in data:
		totals[row.status] = totals.get(row.status, 0) + row.base_amount
	return {
		"data": {
			"labels": [_(status) for status in totals],
			"datasets": [{"name": _("Amount"), "values": list(totals.values())}],
		},
		"type": "bar",
		"fieldtype": "Currency",
		"colors": ["#4f9cf0"],
	}


def get_summary(data) -> list[dict]:
	def total(statuses):
		return sum(row.base_amount for row in data if row.status in statuses)

	return [
		{
			"label": _("In Hand / Issued"),
			"value": total(("In Hand", "Issued")),
			"datatype": "Currency",
			"indicator": "orange",
		},
		{
			"label": _("Deposited"),
			"value": total(("Deposited",)),
			"datatype": "Currency",
			"indicator": "blue",
		},
		{"label": _("Cleared"), "value": total(("Cleared",)), "datatype": "Currency", "indicator": "green"},
		{"label": _("Bounced"), "value": total(("Bounced",)), "datatype": "Currency", "indicator": "red"},
	]
