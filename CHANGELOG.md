# Changelog

## 1.1.0

- Renamed from `cheque_management` to `pdc_management` (module *PDC Management*), because the old name is taken on Frappe Cloud Marketplace. DocType names are unchanged. Sites that had the old app: uninstall it, then install this one; existing holding accounts are picked up again by name.

## 1.0.1

- The daily digest no longer fails on sites without an outgoing Email Account; it is skipped.
- CI runs the full test suite on Frappe / ERPNext v15 and v16.

## 1.0.0

First release.

- Received and issued cheques against Sales / Purchase Invoices, credit / debit notes and on account.
- Deposit, clear, bounce (before or after clearance), return / stop, replace / re-present, and undo last step.
- Cheques in Hand and Cheques Issued holding accounts, with one-click account creation.
- Bounce charges to expense or recovered from the customer.
- Multi-currency with exchange difference on clearance, cost center and accounting dimensions.
- Guards: cheque date, stale cheques, duplicates, step dates, invoice cancellation, direct entry cancellation.
- Daily digest email.
- Cheque Register, Cheque Maturity and Cheque Bounce Analysis reports, workspace, number cards, charts, calendar and print format.
- Frappe / ERPNext v15 and v16.
