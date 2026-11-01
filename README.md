# Household budget

This ledger lives on one MacBook. Open it in the browser on that Mac. Amounts are Canadian dollars. You both use the same password.

The entries are stored in `data/budget.db` inside this folder on that Mac. Copy that file somewhere safe when you want a backup.

## Put it on the MacBook

Copy this folder onto the MacBook with a USB stick or AirDrop. Leave the `.venv` folder behind. That copy was made for Windows and will not run on a Mac.

On the Mac, put the folder somewhere you can find again, such as Documents.

## First time

1. If the Mac does not already have Python 3, install it from [python.org](https://www.python.org/downloads/).
2. In Finder, double-click `Start Budget.command`.
3. If the Mac says it cannot be opened, right-click the file, choose Open, then Open again.
4. The first run creates a file named `.env`. Open that file, replace the sample password with the password you both will type, save it, and double-click `Start Budget.command` again.

The window that opens has to stay open while you use the budget. It will open http://127.0.0.1:8000 in the browser. That address works only on this MacBook.

Close the window when you are finished. The entries stay in `data/budget.db`.

## What you can do

- Add an entry with today's date already filled in, an amount, Income or Spending, a category, and an optional note.
- Add a category, or remove one from the dropdown. Older entries keep a category after it is removed. You can put it back later.
- See the month's entries, and click one to change or delete it.
- See income, spending, and the difference, with a bar for each category.
- Download a Markdown report or a JSON data file for that month.
