// Copyright (c) 2026, Vinay Mishra and contributors
// License: MIT. See LICENSE

frappe.ui.form.on("Cheque Settings", {
	setup(frm) {
		const filters = {
			cheques_in_hand_account: { root_type: "Asset" },
			cheques_issued_account: { root_type: "Liability" },
			bank_charges_account: { root_type: "Expense" },
		};
		for (const [fieldname, extra] of Object.entries(filters)) {
			frm.set_query(fieldname, "company_accounts", (doc, cdt, cdn) => ({
				filters: { company: locals[cdt][cdn].company, is_group: 0, ...extra },
			}));
		}
	},

	create_accounts(frm) {
		const dialog = new frappe.ui.Dialog({
			title: __("Create Missing Accounts"),
			fields: [
				{
					fieldname: "company",
					fieldtype: "Link",
					options: "Company",
					label: __("Company"),
					reqd: 1,
					default: frappe.defaults.get_user_default("Company"),
				},
				{
					fieldtype: "HTML",
					options: `<p class="text-muted small">${__(
						"Adds Cheques in Hand (asset), Cheques Issued (liability) and Cheque Bounce Charges (expense) to the chart of accounts if they are missing, and fills the row."
					)}</p>`,
				},
			],
			primary_action_label: __("Create"),
			primary_action({ company }) {
				dialog.hide();
				frm.call({
					doc: frm.doc,
					method: "create_missing_accounts",
					args: { company },
					freeze: true,
				}).then(({ message: created }) => {
					frappe.show_alert({
						message: created?.length
							? __("Created {0}", [created.join(", ")])
							: __("Accounts were already set."),
						indicator: "green",
					});
					frm.reload_doc();
				});
			},
		});
		dialog.show();
	},
});
