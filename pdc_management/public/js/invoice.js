// Copyright (c) 2026, Vinay Mishra and contributors
// License: MIT. See LICENSE

// Adds Create > Cheque to submitted Sales and Purchase Invoices that still have an outstanding.
for (const doctype of ["Sales Invoice", "Purchase Invoice"]) {
	frappe.ui.form.on(doctype, {
		refresh(frm) {
			if (
				frm.doc.docstatus !== 1 ||
				!flt(frm.doc.outstanding_amount) ||
				!frappe.model.can_create("Cheque")
			) {
				return;
			}
			frm.add_custom_button(
				__("Cheque"),
				() =>
					frappe.model.open_mapped_doc({
						method: "pdc_management.pdc_management.doctype.cheque.cheque.make_cheque_from_invoice",
						source_name: frm.doc.name,
						args: { source_doctype: frm.doctype },
					}),
				__("Create")
			);
		},
	});
}
