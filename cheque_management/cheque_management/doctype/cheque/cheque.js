// Copyright (c) 2026, Vinay Mishra and contributors
// License: MIT. See LICENSE

const CHEQUE_STATUS_COLORS = {
	Draft: "red",
	"In Hand": "orange",
	Issued: "orange",
	Deposited: "blue",
	Cleared: "green",
	Bounced: "red",
	Returned: "gray",
	Replaced: "purple",
	Cancelled: "red",
};

const BOUNCE_REASONS = [
	"Insufficient Funds",
	"Signature Mismatch",
	"Payment Stopped by Drawer",
	"Account Closed",
	"Stale Cheque",
	"Post-dated Cheque Presented Early",
	"Amount in Words and Figures Differ",
	"Alteration on Cheque",
	"Drawer's Signature Missing",
	"Other",
];

frappe.ui.form.on("Cheque", {
	setup(frm) {
		// Cheque entries are cancelled by the cheque itself, never from the linked-documents dialog.
		frm.ignore_doctypes_on_cancel_all = ["Journal Entry"];

		frm.set_query("bank_account", () => bank_account_query(frm));
		frm.set_query("reference_name", "references", () => ({
			filters: {
				docstatus: 1,
				company: frm.doc.company,
				[frm.doc.party_type === "Customer" ? "customer" : "supplier"]: frm.doc.party,
				outstanding_amount: ["!=", 0],
			},
		}));
	},

	onload(frm) {
		erpnext.accounts.dimensions.setup_dimension_filters(frm, frm.doctype);
	},

	refresh(frm) {
		frm.page.set_indicator(__(frm.doc.status), CHEQUE_STATUS_COLORS[frm.doc.status] || "gray");
		show_overdue_banner(frm);
		if (frm.doc.docstatus === 1) {
			add_action_buttons(frm);
		}
		frm.toggle_display("references_section", !!frm.doc.party);
	},

	cheque_type(frm) {
		const party_type = frm.doc.cheque_type === "Issued" ? "Supplier" : "Customer";
		if (frm.doc.party_type !== party_type) {
			frm.set_value("party_type", party_type);
		}
		frm.set_df_property(
			"bank_name",
			"label",
			frm.doc.cheque_type === "Issued" ? __("Bank") : __("Drawee Bank")
		);
	},

	party_type(frm) {
		frm.set_value("party", null);
	},

	party(frm) {
		frm.clear_table("references");
		frm.refresh_field("references");
		frm.toggle_display("references_section", !!frm.doc.party);
		if (frm.doc.party && frm.doc.company) {
			set_party_details(frm);
		}
	},

	company(frm) {
		erpnext.accounts.dimensions.update_dimension(frm, frm.doctype);
		frm.set_value("bank_account", null);
		if (frm.doc.party) {
			set_party_details(frm);
		}
	},

	amount(frm) {
		set_totals(frm);
	},

	exchange_rate(frm) {
		set_totals(frm);
	},

	mode_of_payment(frm) {
		if (!frm.doc.mode_of_payment || !frm.doc.company) return;
		frappe.db
			.get_value(
				"Mode of Payment Account",
				{ parent: frm.doc.mode_of_payment, company: frm.doc.company },
				"default_account"
			)
			.then(({ message }) => {
				if (message?.default_account && !frm.doc.bank_account) {
					frm.set_value("bank_account", message.default_account);
				}
			});
	},

	get_outstanding_invoices(frm) {
		if (!frm.doc.amount) {
			frappe.msgprint(__("Enter the cheque amount first, so it can be allocated."));
			return;
		}
		frappe
			.call({
				method: "cheque_management.cheque_management.doctype.cheque.cheque.get_outstanding_invoices",
				args: {
					company: frm.doc.company,
					party_type: frm.doc.party_type,
					party: frm.doc.party,
					cheque_type: frm.doc.cheque_type,
				},
				freeze: true,
			})
			.then(({ message: invoices }) => {
				frm.clear_table("references");
				if (!invoices?.length) {
					frappe.show_alert({
						message: __("No outstanding invoices."),
						indicator: "orange",
					});
				}
				// Oldest due first, until the cheque amount runs out.
				let remaining = flt(frm.doc.amount);
				for (const invoice of invoices || []) {
					if (remaining <= 0) break;
					const allocated = Math.min(remaining, invoice.open_amount);
					frm.add_child("references", {
						reference_doctype:
							frm.doc.party_type === "Customer"
								? "Sales Invoice"
								: "Purchase Invoice",
						reference_name: invoice.name,
						posting_date: invoice.posting_date,
						due_date: invoice.due_date,
						grand_total: invoice.grand_total,
						outstanding_amount: invoice.outstanding_amount,
						allocated_amount: allocated,
					});
					remaining = flt(remaining - allocated, precision("amount"));
				}
				frm.refresh_field("references");
				set_totals(frm);
			});
	},
});

frappe.ui.form.on("Cheque Reference", {
	reference_name(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		row.reference_doctype =
			frm.doc.party_type === "Customer" ? "Sales Invoice" : "Purchase Invoice";
		if (!row.reference_name) return;
		frappe.db
			.get_value(row.reference_doctype, row.reference_name, [
				"posting_date",
				"due_date",
				"grand_total",
				"outstanding_amount",
			])
			.then(({ message }) => {
				if (!message) return;
				const unallocated = flt(frm.doc.amount) - flt(frm.doc.total_allocated_amount);
				frappe.model.set_value(cdt, cdn, {
					posting_date: message.posting_date,
					due_date: message.due_date,
					grand_total: message.grand_total,
					outstanding_amount: message.outstanding_amount,
					allocated_amount: Math.max(
						0,
						Math.min(Math.abs(message.outstanding_amount), unallocated)
					),
				});
			});
	},

	allocated_amount(frm) {
		set_totals(frm);
	},

	references_remove(frm) {
		set_totals(frm);
	},
});

function bank_account_query(frm) {
	return {
		filters: {
			company: frm.doc.company,
			account_type: "Bank",
			is_group: 0,
		},
	};
}

function set_party_details(frm) {
	frappe
		.call({
			method: "erpnext.accounts.party.get_party_account",
			args: {
				party_type: frm.doc.party_type,
				party: frm.doc.party,
				company: frm.doc.company,
			},
		})
		.then(({ message: account }) => {
			frm.set_value("party_account", account);
			return frappe.db.get_value("Account", account, "account_currency");
		})
		.then(({ message }) => {
			const company_currency = erpnext.get_currency(frm.doc.company);
			const currency = message?.account_currency || company_currency;
			frm.set_value("party_account_currency", currency);
			frm.set_value("company_currency", company_currency);
			if (currency === company_currency) {
				frm.set_value("exchange_rate", 1);
				return;
			}
			return frappe
				.call({
					method: "erpnext.setup.utils.get_exchange_rate",
					args: {
						from_currency: currency,
						to_currency: company_currency,
						transaction_date: frm.doc.posting_date,
					},
				})
				.then(({ message: rate }) => frm.set_value("exchange_rate", rate || 1));
		});
}

function set_totals(frm) {
	const allocated = (frm.doc.references || []).reduce(
		(sum, row) => sum + flt(row.allocated_amount),
		0
	);
	frm.set_value("total_allocated_amount", flt(allocated, precision("total_allocated_amount")));
	frm.set_value(
		"unallocated_amount",
		flt(flt(frm.doc.amount) - allocated, precision("unallocated_amount"))
	);
	frm.set_value(
		"base_amount",
		flt(flt(frm.doc.amount) * flt(frm.doc.exchange_rate || 1), precision("base_amount"))
	);
}

function show_overdue_banner(frm) {
	const today = frappe.datetime.get_today();
	if (frm.doc.docstatus === 1 && frm.doc.status === "In Hand" && frm.doc.cheque_date <= today) {
		const days = frappe.datetime.get_day_diff(today, frm.doc.cheque_date);
		frm.dashboard.add_comment(
			days
				? __("This cheque was due for deposit {0} day(s) ago.", [days])
				: __("This cheque is due for deposit today."),
			days ? "red" : "orange",
			true
		);
	}
}

function add_action_buttons(frm) {
	const { status, cheque_type } = frm.doc;
	const received = cheque_type === "Received";
	const group = __("Actions");

	if (received && status === "In Hand") {
		frm.add_custom_button(__("Deposit"), () => deposit_dialog(frm), group);
	}
	if (
		(received && ["In Hand", "Deposited"].includes(status)) ||
		(!received && status === "Issued")
	) {
		frm.add_custom_button(__("Clear"), () => clear_dialog(frm), group);
	}
	if (
		(received && ["Deposited", "Cleared"].includes(status)) ||
		(!received && ["Issued", "Cleared"].includes(status))
	) {
		frm.add_custom_button(__("Bounce"), () => bounce_dialog(frm), group);
	}
	if ((received && status === "In Hand") || (!received && status === "Issued")) {
		frm.add_custom_button(
			received ? __("Return to Party") : __("Stop / Take Back"),
			() => return_dialog(frm),
			group
		);
	}
	if (["Bounced", "Returned"].includes(status) && !frm.doc.replaced_by) {
		frm.add_custom_button(__("Replace"), () => make_replacement(frm), group);
	}
	if ((frm.doc.events || []).length > 1 && status !== "Replaced" && frm.perm[0]?.cancel) {
		frm.add_custom_button(__("Undo Last Step"), () => undo_last_step(frm), group);
	}

	if (["Deposited", "In Hand", "Issued"].includes(status)) {
		frm.page.set_inner_btn_group_as_primary(group);
	}
}

function run_action(frm, method, args, message) {
	return frm
		.call({ doc: frm.doc, method, args, freeze: true, freeze_message: __("Posting...") })
		.then(() => {
			frappe.show_alert({ message, indicator: "green" });
			frm.reload_doc();
		});
}

function deposit_dialog(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __("Deposit Cheque {0}", [frm.doc.cheque_no]),
		fields: [
			{
				fieldname: "deposit_date",
				fieldtype: "Date",
				label: __("Deposit Date"),
				reqd: 1,
				default: frappe.datetime.get_today(),
			},
			{
				fieldname: "bank_account",
				fieldtype: "Link",
				label: __("Deposit Into"),
				options: "Account",
				reqd: 1,
				default: frm.doc.bank_account,
				get_query: () => bank_account_query(frm),
			},
		],
		primary_action_label: __("Deposit"),
		primary_action(values) {
			dialog.hide();
			run_action(frm, "deposit", values, __("Cheque deposited"));
		},
	});
	dialog.show();
}

function clear_dialog(frm) {
	const default_bank =
		frm.doc.cheque_type === "Received"
			? frm.doc.deposit_bank_account || frm.doc.bank_account
			: frm.doc.bank_account;
	const dialog = new frappe.ui.Dialog({
		title: __("Clear Cheque {0}", [frm.doc.cheque_no]),
		fields: [
			{
				fieldname: "clearance_date",
				fieldtype: "Date",
				label: __("Clearance Date"),
				reqd: 1,
				default: frappe.datetime.get_today(),
				description: __("Date the amount appears in the bank statement."),
			},
			{
				fieldname: "bank_account",
				fieldtype: "Link",
				label: __("Bank Account"),
				options: "Account",
				reqd: 1,
				default: default_bank,
				get_query: () => bank_account_query(frm),
			},
			{
				fieldname: "exchange_rate",
				fieldtype: "Float",
				label: __("Exchange Rate at Clearance"),
				precision: 9,
				default: frm.doc.exchange_rate,
				depends_on: `eval:${frm.doc.party_account_currency !== frm.doc.company_currency}`,
				description: __("Used only when the bank account is in {0}.", [
					frm.doc.party_account_currency,
				]),
			},
		],
		primary_action_label: __("Clear"),
		primary_action(values) {
			dialog.hide();
			run_action(frm, "clear", values, __("Cheque cleared"));
		},
	});
	dialog.show();
}

function bounce_dialog(frm) {
	const received = frm.doc.cheque_type === "Received";
	const dialog = new frappe.ui.Dialog({
		title: __("Bounce Cheque {0}", [frm.doc.cheque_no]),
		fields: [
			{
				fieldname: "bounce_date",
				fieldtype: "Date",
				label: __("Bounce Date"),
				reqd: 1,
				default: frappe.datetime.get_today(),
			},
			{
				fieldname: "reason",
				fieldtype: "Select",
				label: __("Reason"),
				reqd: 1,
				options: ["", ...BOUNCE_REASONS].map((value) => ({ value, label: __(value) })),
			},
			{ fieldtype: "Column Break" },
			{
				fieldname: "charges",
				fieldtype: "Currency",
				label: __("Bank Charges"),
				options: frm.doc.company_currency,
				description: __("Charged by your bank for the returned cheque."),
			},
			{
				fieldname: "recover_charges",
				fieldtype: "Check",
				label: __("Recover Charges from {0}", [frm.doc.party_name || frm.doc.party]),
				depends_on: "eval:doc.charges > 0",
				hidden: !received,
			},
			{ fieldtype: "Section Break" },
			{ fieldname: "remarks", fieldtype: "Small Text", label: __("Remarks") },
		],
		primary_action_label: __("Mark as Bounced"),
		primary_action(values) {
			dialog.hide();
			run_action(frm, "bounce", values, __("Cheque marked as bounced"));
		},
	});
	dialog.show();
}

function return_dialog(frm) {
	const dialog = new frappe.ui.Dialog({
		title:
			frm.doc.cheque_type === "Received"
				? __("Return Cheque {0} to Party", [frm.doc.cheque_no])
				: __("Stop / Take Back Cheque {0}", [frm.doc.cheque_no]),
		fields: [
			{
				fieldname: "return_date",
				fieldtype: "Date",
				label: __("Date"),
				reqd: 1,
				default: frappe.datetime.get_today(),
			},
			{ fieldname: "remarks", fieldtype: "Small Text", label: __("Remarks") },
		],
		primary_action_label: __("Confirm"),
		primary_action(values) {
			dialog.hide();
			run_action(frm, "return_cheque", values, __("Cheque returned"));
		},
	});
	dialog.show();
}

function make_replacement(frm) {
	frappe.model.open_mapped_doc({
		method: "cheque_management.cheque_management.doctype.cheque.cheque.make_replacement",
		source_name: frm.doc.name,
	});
}

function undo_last_step(frm) {
	const last = frm.doc.events[frm.doc.events.length - 1];
	frappe.confirm(
		__("Undo <b>{0}</b> on {1}? Its journal entry will be cancelled.", [
			__(last.event),
			frappe.datetime.str_to_user(last.event_date),
		]),
		() => run_action(frm, "undo_last_step", {}, __("Last step undone"))
	);
}
