# Copyright (c) 2026, Vinay Mishra and contributors
# License: MIT. See LICENSE

from frappe import _


def add_cheques_to_party(data):
	"""Show a party's cheques under Connections on Customer and Supplier."""
	data.setdefault("non_standard_fieldnames", {})["Cheque"] = "party"
	transactions = data.setdefault("transactions", [])
	group = next((row for row in transactions if row.get("label") == _("Payments")), None)
	if group:
		group["items"].append("Cheque")
	else:
		transactions.append({"label": _("Cheques"), "items": ["Cheque"]})
	return data
