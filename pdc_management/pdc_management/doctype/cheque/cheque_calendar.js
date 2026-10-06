// Copyright (c) 2026, Vinay Mishra and contributors
// License: MIT. See LICENSE

frappe.views.calendar["Cheque"] = {
	field_map: {
		start: "cheque_date",
		end: "cheque_date",
		id: "name",
		title: "party_name",
		allDay: "allDay",
		status: "status",
	},
	filters: [
		{
			fieldtype: "Select",
			fieldname: "cheque_type",
			options: "\nReceived\nIssued",
			label: __("Cheque Type"),
		},
		{ fieldtype: "Link", fieldname: "company", options: "Company", label: __("Company") },
	],
	style_map: {
		"In Hand": "warning",
		Issued: "warning",
		Deposited: "info",
		Cleared: "success",
		Bounced: "danger",
	},
	get_events_method: "frappe.desk.calendar.get_events",
};
