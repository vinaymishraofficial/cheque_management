# Developer Guide

For developers who want to run, extend or contribute to PDC Management.

## Local setup

```bash
cd ~/frappe-bench
bench get-app https://github.com/vinaymishraofficial/pdc_management   # or your fork
bench new-site cheque.localhost --install-app erpnext --admin-password admin
bench --site cheque.localhost install-app pdc_management
bench --site cheque.localhost set-config developer_mode 1
bench --site cheque.localhost set-config allow_tests true
bench start
```

Install the git hooks once:

```bash
cd apps/pdc_management
pre-commit install
```

## Layout

```
pdc_management/
├── hooks.py                 # doc events, scheduler, dashboards, accounting dimensions
├── accounting.py            # builds and posts / cancels the cheque's Journal Entries
├── install.py               # custom field on Journal Entry, dimensions, settings rows
├── tasks.py                 # daily digest
├── utils.py                 # settings helpers, app permission
├── overrides/
│   ├── invoice.py           # block cancelling an invoice with an active cheque
│   ├── journal_entry.py     # block cancelling a cheque's entry directly
│   └── dashboards.py        # cheques in Customer / Supplier connections
├── pdc_management/       # the module
│   ├── doctype/cheque/      # controller, form, list, calendar, tests
│   ├── doctype/cheque_settings/ ...
│   ├── report/              # register, maturity, bounce analysis
│   ├── workspace/ number_card/ dashboard_chart/ print_format/
├── desktop_icon/ workspace_sidebar/   # v16 apps screen and sidebar (ignored on v15)
├── templates/emails/cheque_digest.html
└── tests/utils.py           # test data factory and the before_tests hook
```

## How it works

- **`Cheque`** is a submittable document. `on_submit` posts the receipt / issue entry; every later step is a whitelisted method on the document: `deposit`, `clear`, `bounce`, `return_cheque`, `undo_last_step`. Allowed statuses per action are in `ACTION_STATUSES` in `cheque.py`.
- Each action calls `begin()`: permission check, a `SELECT ... FOR UPDATE` on the cheque, and a check that the client's copy is current. It ends with `finish()`, which appends a **Cheque Event** row (date, entry, bank, user) and saves the document as an update-after-submit.
- **`accounting.post()`** takes a list of `Line`s in account currency and creates a submitted Journal Entry. It adds an Exchange Gain / Loss row when the company-currency sides differ, and copies the cost center and every accounting dimension from the cheque. It runs inside `in_cheque_action()`, which the Journal Entry guard checks.
- **Reversals** (`bounce`, `return_cheque`) read the receipt entry's current rows with `accounting.lines_of()` and flip them, so Payment Reconciliation changes are respected.
- **Replacement**: `make_replacement()` maps a draft; when it is submitted, the original is set to *Replaced*. Cancelling the replacement restores the original.

## Extending

All extension points are standard Frappe hooks in your own app.

**React to a cheque step**

```python
# your_app/hooks.py
doc_events = {
    "Cheque": {
        "on_submit": "your_app.cheques.notify_sales_rep",
        "on_update_after_submit": "your_app.cheques.on_step",  # runs after deposit / clear / bounce / ...
    }
}
```

```python
# your_app/cheques.py
def on_step(doc, method=None):
    if doc.status == "Bounced":
        ...  # e.g. put the customer on credit hold
```

**Add fields**: use Custom Fields on `Cheque`. Accounting dimensions are added automatically, because `Cheque` is listed in `accounting_dimension_doctypes`.

**Change the posting logic**: override the class with `override_doctype_class = {"Cheque": "your_app.overrides.CustomCheque"}` and subclass `Cheque`. For example, override `receipt_lines()` or `charge_lines()`.

**Call actions over REST**

```bash
curl -X POST https://site/api/method/run_doc_method \
  -H "Authorization: token <key>:<secret>" \
  -d 'dt=Cheque' -d 'dn=CHQ-2026-00001' -d 'method=clear' \
  -d 'args={"clearance_date": "2026-10-06", "bank_account": "HDFC - XYZ"}'
```

## Tests

```bash
bench --site cheque.localhost run-tests --app pdc_management
bench --site cheque.localhost run-tests --module pdc_management.pdc_management.doctype.cheque.test_cheque
```

- The tests create their own company, customer, supplier, item and bank accounts (`tests/utils.py`), and everything is rolled back after each class. They work on a fresh CI site and on a site with data.
- `IGNORE_TEST_RECORD_DEPENDENCIES` in `test_cheque.py` stops the runner from importing ERPNext's generic test records, which would be committed.
- The factory adapts to site rules it meets in the wild: April fiscal years, naming series on masters, India Compliance HSN codes and GST treatment, and mandatory accounting dimensions.
- Use `FrappeTestCase` from `frappe.tests.utils`, so the same tests run on v15 and v16.

CI (`.github/workflows/ci.yml`) runs the suite on Frappe / ERPNext `version-15` (Python 3.11) and `version-16` (Python 3.14). The linter workflow runs pre-commit, Frappe's Semgrep rules and pip-audit.

## Compatibility rules

- Python 3.10+ syntax only (v15 runs on 3.10 / 3.11).
- No v16-only APIs in Python or JS without a fallback.
- `desktop_icon/` and `workspace_sidebar/` are v16 features that v15 ignores safely.

## Releasing

1. Update `CHANGELOG.md` and bump `__version__` in `pdc_management/__init__.py`.
2. Merge to `develop`, then fast-forward `version-15` and `version-16`.
3. Tag `vX.Y.Z` and create a GitHub release.
4. Frappe Cloud Marketplace picks up the release from the `version-15` / `version-16` branches.

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md).
