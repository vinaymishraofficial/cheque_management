# Copyright (c) 2026, Vinay Mishra and contributors
# License: MIT. See LICENSE

from frappe import _


def get_data():
	return {
		"fieldname": "cheque",
		"non_standard_fieldnames": {"Cheque": "replacement_of"},
		"transactions": [
			{"label": _("Accounting"), "items": ["Journal Entry"]},
			{"label": _("Replacement"), "items": ["Cheque"]},
		],
	}
