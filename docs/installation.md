# Installation

## Frappe Cloud

Open your site's dashboard → **Apps** → **Install App** and choose **PDC Management**.

## Self-hosted (Frappe / ERPNext v15 or v16)

```bash
cd ~/frappe-bench
bench get-app https://github.com/vinaymishraofficial/pdc_management --branch version-16   # or version-15
bench --site your-site install-app pdc_management
bench --site your-site migrate
bench restart   # production benches
```

ERPNext must already be installed on the site.

## After installing

Follow **One-time setup** in the [User Guide](user-guide.md): open **Cheque Settings** and click **Create Missing Accounts**.

## Uninstalling

```bash
bench --site your-site uninstall-app pdc_management
```

This removes the app's doctypes and their data. The holding accounts in your chart of accounts and the journal entries already posted are kept.

## Upgrading from `cheque_management`

Versions before 1.1.0 were called `cheque_management`. Uninstall that app, then install `pdc_management`. Existing *Cheques in Hand*, *Cheques Issued* and *Cheque Bounce Charges* accounts are linked again automatically.
