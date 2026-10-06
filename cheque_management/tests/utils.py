# Copyright (c) 2026, Vinay Mishra and contributors
# License: MIT. See LICENSE

"""Test data: one company with its own customer, supplier, bank and cheque accounts.

Everything is created on demand, so the tests run on a fresh CI site and on a site with
real data alike, on Frappe / ERPNext v15 and v16."""

import frappe
from frappe.utils import add_days, add_months, getdate, now_datetime, nowdate

COMPANY = "_Test Cheque Company"
ABBR = "_TCQ"
CUSTOMER = "_Test Cheque Customer"
USD_CUSTOMER = "_Test Cheque USD Customer"
SUPPLIER = "_Test Cheque Supplier"
ITEM = "_Test Cheque Service"


def before_tests():
	"""Complete the setup wizard on a fresh site so ERPNext masters (groups, UOMs, fiscal year) exist."""
	from frappe.desk.page.setup_wizard.setup_wizard import setup_complete

	frappe.clear_cache()
	if not frappe.get_all("Company", limit=1):
		year = now_datetime().year
		setup_complete(
			{
				"currency": "INR",
				"full_name": "Test User",
				"company_name": COMPANY,
				"timezone": "Asia/Kolkata",
				"company_abbr": ABBR,
				"industry": "Services",
				"country": "India",
				"fy_start_date": f"{year}-01-01",
				"fy_end_date": f"{year}-12-31",
				"language": "english",
				"company_tagline": "Testing",
				"email": "test@example.com",
				"password": "test",
				"chart_of_accounts": "Standard",
			}
		)
	frappe.db.commit()  # nosemgrep: setup data must survive the test transaction rollback


def base_date():
	"""One month into the fiscal year that contains today, so every test date (up to ~4 months
	later) falls in an open year whatever the site's year start (January, April, ...)."""
	from erpnext.accounts.utils import get_fiscal_year

	return getdate(add_months(get_fiscal_year(nowdate(), company=COMPANY)[1], 1))


def setup_test_data():
	make_company()
	ensure_fiscal_year()
	make_accounts()
	make_masters()
	configure_settings()


def ensure_fiscal_year():
	from erpnext.accounts.utils import FiscalYearError, get_fiscal_year

	try:
		get_fiscal_year(nowdate(), company=COMPANY)
	except FiscalYearError:
		year = now_datetime().year
		frappe.get_doc(
			{
				"doctype": "Fiscal Year",
				"year": f"_Test Cheque {year}",
				"year_start_date": f"{year}-01-01",
				"year_end_date": f"{year}-12-31",
				"companies": [{"company": COMPANY}],
			}
		).insert()


def make_company():
	if frappe.db.exists("Company", COMPANY):
		return
	# Company creation adds departments under this root; some sites have renamed or removed it.
	if not frappe.db.exists("Department", "All Departments"):
		frappe.get_doc({"doctype": "Department", "department_name": "All Departments", "is_group": 1}).insert(
			set_name="All Departments"
		)
	frappe.get_doc(
		{
			"doctype": "Company",
			"company_name": COMPANY,
			"abbr": ABBR,
			"default_currency": "INR",
			"country": "India",
			"chart_of_accounts": "Standard",
			"create_chart_of_accounts_based_on": "Standard Template",
		}
	).insert()


def account(name: str) -> str:
	return f"{name} - {ABBR}"


def make_account(account_name, parent, account_type=None, currency="INR"):
	name = account(account_name)
	if not frappe.db.exists("Account", name):
		frappe.get_doc(
			{
				"doctype": "Account",
				"account_name": account_name,
				"company": COMPANY,
				"parent_account": parent,
				"account_type": account_type,
				"account_currency": currency,
			}
		).insert()
	return name


def make_accounts():
	bank_group = frappe.db.get_value(
		"Account", {"company": COMPANY, "account_type": "Bank", "is_group": 1}, "name"
	) or frappe.db.get_value("Account", {"company": COMPANY, "account_name": "Bank Accounts"}, "name")
	make_account("_Test Cheque Bank", bank_group, "Bank")
	make_account("_Test Cheque Bank 2", bank_group, "Bank")
	make_account("_Test Cheque USD Bank", bank_group, "Bank", "USD")
	receivable_group = frappe.db.get_value(
		"Account", {"company": COMPANY, "account_name": "Accounts Receivable", "is_group": 1}, "name"
	)
	make_account("_Test Debtors USD", receivable_group, "Receivable", "USD")


def make_masters():
	if not frappe.db.exists("Customer", CUSTOMER):
		frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": CUSTOMER,
				"customer_group": root("Customer Group"),
				"territory": root("Territory"),
			}
		).insert(set_name=CUSTOMER)
	if not frappe.db.exists("Customer", USD_CUSTOMER):
		frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": USD_CUSTOMER,
				"customer_group": root("Customer Group"),
				"territory": root("Territory"),
				"default_currency": "USD",
				"accounts": [{"company": COMPANY, "account": account("_Test Debtors USD")}],
			}
		).insert(set_name=USD_CUSTOMER)
	if not frappe.db.exists("Supplier", SUPPLIER):
		frappe.get_doc(
			{"doctype": "Supplier", "supplier_name": SUPPLIER, "supplier_group": root("Supplier Group")}
		).insert(set_name=SUPPLIER)
	if not frappe.db.exists("Item", ITEM):
		item = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": ITEM,
				"item_group": root("Item Group"),
				"stock_uom": frappe.db.get_value("UOM", {}, "name") or "Nos",
				"is_stock_item": 0,
			}
		)
		# Regional apps (e.g. India Compliance) make an HSN / SAC code mandatory.
		if item.meta.has_field("gst_hsn_code"):
			if not frappe.db.exists("GST HSN Code", "998311"):
				frappe.get_doc({"doctype": "GST HSN Code", "hsn_code": "998311"}).insert()
			item.gst_hsn_code = "998311"
		# Masters get fixed names even on sites that name them by series.
		item.insert(set_name=ITEM)
	if not frappe.db.get_value("Currency Exchange", {"from_currency": "USD", "to_currency": "INR"}):
		frappe.get_doc(
			{
				"doctype": "Currency Exchange",
				"date": "2000-01-01",
				"from_currency": "USD",
				"to_currency": "INR",
				"exchange_rate": 80,
			}
		).insert()


def root(doctype: str) -> str:
	"""A non-group record of a tree doctype (v16 rejects groups on parties), created if none exists."""
	name = f"_Test Cheque {doctype}"
	if not frappe.db.exists(doctype, name):
		parent_field = "parent_" + frappe.scrub(doctype)
		top = frappe.db.get_value(doctype, {"is_group": 1, parent_field: ("in", ("", None))}, "name")
		frappe.get_doc(
			{"doctype": doctype, frappe.scrub(doctype) + "_name": name, parent_field: top, "is_group": 0}
		).insert()
	return name


def configure_settings(**values):
	settings = frappe.get_single("Cheque Settings")
	if not any(row.company == COMPANY and row.cheques_in_hand_account for row in settings.company_accounts):
		settings.create_missing_accounts(COMPANY)
		settings.reload()
	settings.update(
		{
			"allow_on_account": 1,
			"block_duplicate_cheque": 1,
			"cheque_validity_months": 3,
			"send_daily_digest": 1,
			"digest_days_ahead": 7,
			**values,
		}
	)
	settings.save()


def make_invoice(
	doctype="Sales Invoice",
	rate=1000,
	party=None,
	posting_date=None,
	is_return=0,
	return_against=None,
	currency=None,
	conversion_rate=1,
):
	posting_date = posting_date or base_date()
	party_field = "customer" if doctype == "Sales Invoice" else "supplier"
	invoice = frappe.get_doc(
		{
			"doctype": doctype,
			"company": COMPANY,
			party_field: party or (CUSTOMER if doctype == "Sales Invoice" else SUPPLIER),
			"posting_date": posting_date,
			"set_posting_time": 1,
			"due_date": add_days(posting_date, 30) if not is_return else posting_date,
			"currency": currency or "INR",
			"conversion_rate": conversion_rate,
			"is_return": is_return,
			"return_against": return_against,
			"update_stock": 0,
			"items": [
				{
					"item_code": ITEM,
					"qty": -1 if is_return else 1,
					"rate": rate,
					"cost_center": frappe.get_cached_value("Company", COMPANY, "cost_center"),
					"item_tax_template": item_tax_template(),
				}
			],
		}
	)
	invoice.set(
		"selling_price_list" if doctype == "Sales Invoice" else "buying_price_list",
		price_list(doctype == "Sales Invoice"),
	)
	if doctype == "Purchase Invoice":
		invoice.bill_no = frappe.generate_hash(length=8)
	if currency == "USD":
		invoice.debit_to = account("_Test Debtors USD")
	invoice.insert()
	invoice.submit()
	return invoice


def make_cheque(cheque_type="Received", amount=1000, invoices=(), submit=True, **fields):
	party_type = fields.pop("party_type", "Customer" if cheque_type == "Received" else "Supplier")
	cheque = frappe.get_doc(
		{
			"doctype": "Cheque",
			"cheque_type": cheque_type,
			"company": COMPANY,
			"posting_date": base_date(),
			"party_type": party_type,
			"party": fields.pop("party", CUSTOMER if party_type == "Customer" else SUPPLIER),
			"cheque_no": fields.pop("cheque_no", frappe.generate_hash(length=6)),
			"cheque_date": fields.pop("cheque_date", base_date()),
			"bank_name": "_Test Drawee Bank",
			"amount": amount,
			"bank_account": fields.pop(
				"bank_account", account("_Test Cheque Bank") if cheque_type == "Issued" else None
			),
			**fields,
		}
	)
	for fieldname, value in mandatory_dimensions().items():
		if not cheque.get(fieldname):
			cheque.set(fieldname, value)
	for invoice, allocated in invoices:
		cheque.append(
			"references",
			{
				"reference_doctype": invoice.doctype,
				"reference_name": invoice.name,
				"allocated_amount": allocated,
			},
		)
	cheque.insert()
	if submit:
		cheque.submit()
	return cheque


def mandatory_dimensions() -> dict:
	"""Sites can make a dimension mandatory on journal rows; give the test cheques a value for it."""
	from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import get_accounting_dimensions

	meta = frappe.get_meta("Journal Entry Account")
	values = {}
	for dimension in get_accounting_dimensions(as_list=False):
		field = meta.get_field(dimension.fieldname)
		if field and field.reqd:
			values[dimension.fieldname] = frappe.db.get_value(dimension.document_type, {}, "name")
	return values


def price_list(selling: bool) -> str:
	name = "_Test Cheque Selling" if selling else "_Test Cheque Buying"
	if not frappe.db.exists("Price List", name):
		frappe.get_doc(
			{
				"doctype": "Price List",
				"price_list_name": name,
				"currency": "INR",
				"selling": int(selling),
				"buying": int(not selling),
				"enabled": 1,
			}
		).insert()
	return name


def item_tax_template() -> str | None:
	"""A zero-rate template, only when a site has made the item tax template mandatory."""
	field = frappe.get_meta("Sales Invoice Item").get_field("item_tax_template")
	if not (field and field.reqd):
		return None
	name = f"_Test Cheque Zero Tax - {ABBR}"
	if not frappe.db.exists("Item Tax Template", name):
		tax_group = frappe.db.get_value(
			"Account", {"company": COMPANY, "account_name": "Duties and Taxes", "is_group": 1}, "name"
		)
		tax_account = make_account("_Test Cheque Tax", tax_group, "Tax")
		template = frappe.get_doc(
			{
				"doctype": "Item Tax Template",
				"title": "_Test Cheque Zero Tax",
				"company": COMPANY,
				"taxes": [{"tax_type": tax_account, "tax_rate": 0}],
			}
		)
		if template.meta.has_field("gst_treatment"):
			template.gst_treatment = "Nil-Rated"  # India Compliance rejects 0% on taxable supplies
		template.insert()
	return name


def outstanding(invoice) -> float:
	return frappe.db.get_value(invoice.doctype, invoice.name, "outstanding_amount")


def balance(account_name: str) -> float:
	from erpnext.accounts.utils import get_balance_on

	return get_balance_on(account=account_name, company=COMPANY)


def party_balance(party_type: str, party: str) -> float:
	from erpnext.accounts.utils import get_balance_on

	return get_balance_on(party_type=party_type, party=party, company=COMPANY)
