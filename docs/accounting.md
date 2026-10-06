# Accounting design

This page explains, for accountants and implementers, what PDC Management posts and why.

## Accounts

| Account | Type | Purpose |
| --- | --- | --- |
| Cheques in Hand | Asset (not Receivable) | Received cheques that have not cleared. |
| Cheques Issued | Liability (not Payable) | Issued cheques that the bank has not paid yet. |
| Cheque Bounce Charges | Expense | Charges your bank levies on a returned cheque. |

They are set per company in **Cheque Settings**. Receivable / Payable / Bank / Cash accounts are rejected as holding accounts: a party-type holding account would show every cheque in hand as an open receivable in the AR report, and a bank-type one would inflate the bank balance.

## Entries

All entries are Journal Entries with `cheque` set to the cheque, the cheque number and date as the reference, and the cheque's cost center and accounting dimensions on every row.

### Received cheque

| Step | Debit | Credit | Date |
| --- | --- | --- | --- |
| Submit | Cheques in Hand | Customer, one row per invoice + an advance row for any unallocated amount | Posting date |
| Deposit | - | - | (recorded only) |
| Clear | Bank | Cheques in Hand | Clearance date; the entry's clearance date is set for bank reconciliation |
| Bounce, not cleared | Customer, against the same invoices | Cheques in Hand | Bounce date |
| Bounce, cleared | Customer, against the same invoices | Bank | Bounce date |
| Bounce charges | Bounce Charges, or Customer when recovered | Bank | Bounce date (same entry as the bounce) |
| Return | reverses the submit entry | | Return date |

### Issued cheque

| Step | Debit | Credit | Date |
| --- | --- | --- | --- |
| Submit | Supplier, one row per bill + advance | Cheques Issued | Posting date |
| Clear | Cheques Issued | Bank | Clearance date |
| Bounce, not cleared | Cheques Issued | Supplier, against the same bills | Bounce date |
| Bounce, cleared | Bank | Supplier, against the same bills | Bounce date |
| Stop / take back | reverses the submit entry | | Return date |

### Refunds

An issued cheque to a customer settles a credit note (negative outstanding on a Sales Invoice return). A received cheque from a supplier settles a debit note. The same entries apply with the party sides swapped.

## Why reversals and not cancellation

Bounce and return post a new reversing entry on their own date. Cancelling the receipt entry would rewrite the books on the original date, which fails once that period is closed or frozen, and hides when the bounce actually happened. Reversals read the receipt entry's current rows, so allocations made later by Payment Reconciliation are reversed exactly as they now stand.

**Undo Last Step** is different: it is for correcting a mistake, so it cancels the step's entry. It needs the cancel permission.

## Multi-currency

- The cheque is in the party account's currency. Its exchange rate converts it to company currency, and the holding account is always in company currency.
- Clearing into a company-currency bank moves the company-currency amount. Clearing into a bank in the cheque's currency uses the clearing exchange rate; the difference from the holding amount goes to the company's Exchange Gain / Loss account.
- As with any ERPNext journal entry against an invoice, the difference between the invoice rate and the cheque rate stays in the receivable / payable until Exchange Rate Revaluation is run.

## Concurrency and integrity

- Submitting re-reads every invoice with a row lock, so two cheques cannot over-allocate one invoice.
- Every action locks the cheque row and checks that nobody changed it meanwhile.
- A Journal Entry that belongs to a cheque cannot be cancelled directly; use the cheque's actions.
- An invoice that an active cheque settles cannot be cancelled until the cheque is bounced, returned or cancelled.
