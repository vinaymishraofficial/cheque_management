# Copyright (c) 2026, Vinay Mishra and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _

from pdc_management.accounting import IN_CHEQUE_ACTION


def prevent_direct_cancel(doc, method=None):
	"""Entries of a cheque change only through the cheque, so its status and the books agree."""
	if doc.get("cheque") and not frappe.flags.get(IN_CHEQUE_ACTION):
		frappe.throw(
			_("This entry belongs to cheque {0}. Use Undo Last Step or Cancel on the cheque.").format(
				frappe.utils.get_link_to_form("Cheque", doc.cheque)
			),
			title=_("Posted by a Cheque"),
		)
