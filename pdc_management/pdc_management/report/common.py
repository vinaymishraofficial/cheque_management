# Copyright (c) 2026, Vinay Mishra and contributors
# License: MIT. See LICENSE

"""Filters shared by the cheque reports."""

import frappe

STATUSES = ["In Hand", "Issued", "Deposited", "Cleared", "Bounced", "Returned", "Replaced"]


def cheque_filters(filters) -> dict:
	"""Submitted cheques matching the report filters. Multi-select values arrive as lists or JSON."""
	conditions = {"docstatus": 1}
	if filters.get("company"):
		conditions["company"] = filters.company
	if filters.get("cheque_type"):
		conditions["cheque_type"] = filters.cheque_type
	if filters.get("party_type"):
		conditions["party_type"] = filters.party_type
	for fieldname in ("party", "status"):
		values = frappe.parse_json(filters.get(fieldname)) if filters.get(fieldname) else None
		if values:
			conditions[fieldname] = ("in", values if isinstance(values, list) else [values])
	return conditions


def date_range(filters, fieldname: str, conditions: dict) -> dict:
	if filters.get("from_date") and filters.get("to_date"):
		conditions[fieldname] = ("between", (filters.from_date, filters.to_date))
	elif filters.get("from_date"):
		conditions[fieldname] = (">=", filters.from_date)
	elif filters.get("to_date"):
		conditions[fieldname] = ("<=", filters.to_date)
	return conditions
