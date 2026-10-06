// Copyright (c) 2026, Vinay Mishra and contributors
// License: MIT. See LICENSE

frappe.query_reports["Cheque Maturity"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "as_on_date",
			label: __("As On"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "cheque_type",
			label: __("Cheque Type"),
			fieldtype: "Select",
			options: ["", "Received", "Issued"],
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
			fieldname: "group_by",
			label: __("Group By"),
			fieldtype: "Select",
			options: [
				{ value: "Cheque", label: __("Cheque") },
				{ value: "Party", label: __("Party") },
			],
			default: "Cheque",
		},
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "overdue" && data?.overdue) {
			value = `<span class="text-danger">${value}</span>`;
		}
		return value;
	},
};
