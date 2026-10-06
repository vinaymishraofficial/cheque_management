# User Guide

A step-by-step tutorial for accountants and finance teams. No technical knowledge needed.

**Who can do what**

| Role | Can |
| --- | --- |
| Accounts User | Create and submit cheques; deposit, clear, bounce, return and replace them |
| Accounts Manager | Everything above, plus cancel cheques, undo a step, and change Cheque Settings |

---

## 1. One-time setup

1. Search for **Cheque Settings** in the awesome bar (or open the **Cheques** workspace → *Cheque Settings*).
2. Click **Create Missing Accounts**, select your company, and click **Create**.
   This adds three accounts to your chart of accounts and fills the row:
   - **Cheques in Hand**: received cheques wait here until they clear.
   - **Cheques Issued**: cheques you gave suppliers wait here until your bank pays them.
   - **Cheque Bounce Charges**: bank charges on bounced cheques.

   Already have such accounts? Select them in the row instead.
3. Review the rules:
   - **Cheque Validity (Months)**: default 3. Older cheques are treated as stale and cannot be deposited.
   - **Allow Unallocated Amount**: lets a cheque be bigger than the invoices it pays; the extra is kept as an advance.
   - **Block Duplicate Cheque Numbers**: recommended on.
   - **Send Daily Digest** to a role (default Accounts Manager), looking ahead 7 days.
4. **Save**.

> Using several companies? Add one row per company.

---

## 2. Record a cheque you received

**Fastest way: from the invoice**

1. Open the submitted **Sales Invoice**.
2. Click **Create → Cheque**. The customer, amount and invoice are filled in.
3. Enter the **Cheque No**, **Cheque Date** (the date written on the cheque) and **Drawee Bank**.
4. **Save** and **Submit**.

**One cheque for several invoices**

1. **Cheque → + Add Cheque**.
2. **Cheque Type**: Received. Select the **Customer** and enter the **Amount**.
3. Click **Get Outstanding Invoices**. The amount is allocated to the oldest due invoices first. Adjust the *Allocated* column if needed.
4. Fill in the cheque number, date and bank, then **Submit**.

After submitting, the status is **In Hand** and the invoices show as paid. The money sits in *Cheques in Hand* until the cheque clears. Print a **Cheque Acknowledgement** for the customer from **Print**.

> A cheque dated later than today is marked **Post-dated** automatically.

---

## 3. Deposit it in the bank

On or after the cheque date:

1. Open the cheque → **Actions → Deposit**.
2. Choose the **Deposit Date** and the bank account you deposited it in.
3. **Deposit**. Status: **Deposited**. Nothing is posted to the books yet.

You cannot deposit a post-dated cheque before its date, or a stale cheque.

---

## 4. When the bank credits the money: Clear

1. **Actions → Clear**.
2. **Clearance Date**: the date on the bank statement.
3. **Clear**. Status: **Cleared**. The amount moves from *Cheques in Hand* to the bank, and the entry is already marked as reconciled in Bank Reconciliation.

You can also clear straight from *In Hand* if you skip the deposit step.

---

## 5. If the cheque bounces

1. **Actions → Bounce** (available once deposited, and even after clearing if the bank reverses it later).
2. Enter the **Bounce Date** and the **Reason** (Insufficient Funds, Signature Mismatch, ...).
3. **Bank Charges**: what your bank deducted, if anything. Tick **Recover Charges from customer** to add them to what the customer owes.
4. **Mark as Bounced**. Status: **Bounced**. The invoices are open again on the bounce date.

---

## 6. Replace a bounced cheque (or present it again)

1. On the bounced cheque: **Actions → Replace**.
2. A new cheque opens with the same customer and the invoices that are still open. To re-present the same cheque, keep the number. For a new cheque, change the number.
3. Set the new **Cheque Date**, **Save**, **Submit**.

The old cheque becomes **Replaced** and links to the new one.

---

## 7. Give a cheque back (Return)

The customer paid another way, or asked for the cheque back before you deposited it:

**Actions → Return to Party** → date → **Confirm**. Status: **Returned**. The invoices are open again.

---

## 8. Cheques you issue to suppliers

Same flow, from a **Purchase Invoice → Create → Cheque**, or a new cheque with **Cheque Type: Issued**.

- **Bank Account** is required: the account the cheque is drawn on.
- On submit the bill is paid and the amount waits in *Cheques Issued*.
- When it appears in your bank statement: **Clear**.
- If your bank returns it: **Bounce** (the bill reopens).
- Cancelled the cheque with the supplier or stopped payment: **Stop / Take Back**.

---

## 9. Fix a mistake

- **Undo Last Step** (Accounts Manager): takes back the last deposit, clearance, bounce or return and cancels its entry. You can undo several steps one at a time.
- **Cancel**: only while the cheque is still *In Hand* / *Issued*. To cancel later, undo the steps first.
- The journal entries a cheque creates cannot be cancelled on their own. Use the cheque.

---

## 10. Stay on top of it

- **Cheques workspace**: cheques in hand, due this week, issued outstanding, bounced this month, and charts.
- **List view**: cheques due for deposit are shown in red as *Due for Deposit*.
- **Calendar**: every cheque on its cheque date.
- **Daily digest email**: overdue and due cheques, cheques about to go stale, and issued cheques your bank may soon pay.

## 11. Reports

| Report | Use it to |
| --- | --- |
| **Cheque Register** | List cheques by type, status, party, cheque or posting date, with totals per status. |
| **Cheque Maturity** | See open cheques by how soon they are due (overdue, 0-7, 8-30, ... days), per cheque or per party. |
| **Cheque Bounce Analysis** | See each customer's bounce rate, bounced amount, charges and most common reason before accepting another post-dated cheque. |

---

## Common messages

| Message | What to do |
| --- | --- |
| *Set the cheque accounts for ... in Cheque Settings* | Do step 1 for that company. |
| *A post-dated cheque cannot be deposited before its cheque date* | Wait for the date on the cheque. |
| *The cheque is ... stale* | The cheque is older than the validity period. Return it and ask for a new one. |
| *Cheque ... is already recorded* | The same number from the same party already exists. To present a bounced cheque again, use **Replace** on it. |
| *... is settled by cheque ...* (when cancelling an invoice) | Bounce, return or cancel the cheque first. |
| *This entry belongs to cheque ...* | Change it through the cheque, not the journal entry. |
