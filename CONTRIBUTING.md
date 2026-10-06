# Contributing

Thanks for helping. Bug reports, fixes, translations and docs are all welcome.

## Reporting a bug

Open an issue with the steps to reproduce, what you expected, what happened, and the output of `bench version`. If money is posted wrongly, include the cheque's journal entries (General Ledger view) with amounts and account names; leave out real party names.

## Making a change

1. Fork the repo and branch from `develop`.
2. Set up a bench as described in the [Developer Guide](docs/developer-guide.md) and run `pre-commit install`.
3. Make the change with a test that fails without it.
4. Run `bench --site <site> run-tests --app pdc_management` and `pre-commit run --all-files`.
5. Open a pull request against `develop` that explains what changed and why.

## Guidelines

- Keep it working on Frappe / ERPNext v15 and v16.
- Never cancel or rewrite past entries for a business event. Post a new entry on the event's date.
- Every user-facing string goes through `_()` / `__()`.
- Match the surrounding code: small methods, clear names, comments only where the reason is not obvious.

## Translations

Add or improve translations with the standard Frappe translation workflow (`bench generate-pot-file --app pdc_management`, then `.po` files under `pdc_management/locale`).
