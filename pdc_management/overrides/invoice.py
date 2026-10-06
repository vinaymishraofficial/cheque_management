# Copyright (c) 2026, Vinay Mishra and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _

# A cheque in these states still settles the invoice in the books.
ACTIVE_STATUSES = ("In Hand", "Issued", "Deposited", "Cleared")


def prevent_cancel_with_active_cheques(doc, method=None):
	"""Stop cancelling an invoice that an active cheque settles; it would leave the cheque dangling."""
	cheques = frappe.get_all(
		"Cheque Reference",
		filters={"reference_doctype": doc.doctype, "reference_name": doc.name, "docstatus": 1},
		pluck="parent",
		distinct=True,
	)
	active = (
		frappe.get_all(
			"Cheque", filters={"name": ("in", cheques), "status": ("in", ACTIVE_STATUSES)}, pluck="name"
		)
		if cheques
		else []
	)
	if active:
		frappe.throw(
			_("{0} is settled by cheque {1}. Bounce, return or cancel the cheque first.").format(
				doc.name, ", ".join(frappe.utils.get_link_to_form("Cheque", name) for name in active)
			),
			title=_("Active Cheque"),
		)
