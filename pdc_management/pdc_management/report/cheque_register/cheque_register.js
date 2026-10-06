// Copyright (c) 2026, Vinay Mishra and contributors
// License: MIT. See LICENSE

frappe.query_reports["Cheque Register"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "cheque_type",
			label: __("Cheque Type"),
			fieldtype: "Select",
			options: ["", "Received", "Issued"],
		},
		{
			fieldname: "date_based_on",
			label: __("Date Based On"),
			fieldtype: "Select",
			options: [
				{ value: "cheque_date", label: __("Cheque Date") },
				{ value: "posting_date", label: __("Posting Date") },
			],
			default: "cheque_date",
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), 1),
		},
		{
			fieldname: "party_type",
			label: __("Party Type"),
			fieldtype: "Select",
			options: ["", "Customer", "Supplier"],
			on_change() {
				frappe.query_report.set_filter_value("party", []);
			},
		},
		{
			fieldname: "party",
			label: __("Party"),
			fieldtype: "MultiSelectList",
			get_data(txt) {
				const party_type = frappe.query_report.get_filter_value("party_type");
				if (!party_type) return [];
				return frappe.db.get_link_options(party_type, txt);
			},
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "MultiSelectList",
			get_data() {
				return [
					"In Hand",
					"Issued",
					"Deposited",
					"Cleared",
					"Bounced",
					"Returned",
					"Replaced",
				].map((value) => ({ value, description: __(value) }));
			},
		},
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "status" && data?.status) {
			const colors = {
				"In Hand": "orange",
				Issued: "orange",
				Deposited: "blue",
				Cleared: "green",
				Bounced: "red",
				Returned: "gray",
				Replaced: "purple",
			};
			value = `<span class="indicator-pill ${colors[data.status] || "gray"}">${__(
				data.status
			)}</span>`;
		}
		if (column.fieldname === "days_to_date" && data?.days_to_date < 0) {
			value = `<span class="text-danger">${value}</span>`;
		}
		return value;
	},
};
