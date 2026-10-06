// Copyright (c) 2026, Vinay Mishra and contributors
// License: MIT. See LICENSE

frappe.listview_settings["Cheque"] = {
	add_fields: ["status", "cheque_date", "cheque_type"],
	has_indicator_for_draft: true,

	get_indicator(doc) {
		const today = frappe.datetime.get_today();
		if (doc.status === "In Hand" && doc.cheque_date <= today) {
			return [__("Due for Deposit"), "red", "status,=,In Hand|cheque_date,<=,Today"];
		}
		const colors = {
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
		return [__(doc.status), colors[doc.status] || "gray", `status,=,${doc.status}`];
	},
};
