// Copyright (c) 2026, Vinay Mishra and contributors
// License: MIT. See LICENSE

frappe.query_reports["Cheque Bounce Analysis"] = {
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
			options: ["Received", "Issued"],
			default: "Received",
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -12),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
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
			fieldname: "only_bounced",
			label: __("Only Parties With Bounces"),
			fieldtype: "Check",
			default: 1,
		},
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "bounce_rate" && data?.bounce_rate >= 20) {
			value = `<span class="text-danger bold">${value}</span>`;
		}
		return value;
	},
};
