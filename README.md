# Household budget

This ledger lives on one MacBook. Open it in the browser on that Mac. Amounts are Canadian dollars. You both use the same password.

The entries are stored in `data/budget.db` inside this folder on that Mac. Copy that file somewhere safe when you want a backup.

## Put it on the MacBook

On the Mac, download this zip:

https://github.com/blejanre/household-budget/archive/refs/heads/main.zip

Double-click the zip to unpack it. You will get a folder named `household-budget-main`. Move that folder somewhere you can find again, such as Documents.

## First time

1. If the Mac does not already have Python 3, install it from [python.org](https://www.python.org/downloads/).
2. In Finder, double-click `Start Budget.command` once. If the Mac says it cannot be opened, right-click that file, choose Open, then Open again.
3. The first run creates a settings file. Replace the sample password with the password you both will type, save, close the file, and click the Budget icon again.
4. Drag the Budget icon onto the Dock, the bar of icons at the bottom of the screen. Leave the folder where it is. The Dock icon points at that folder.

After that, click Budget on the Dock. The budget opens in the browser. You can close the browser when you are finished. The entries stay in `data/budget.db`. Click the Dock icon the next time you want to add something.

If the Dock icon does not open, double-click `Start Budget.command` once more, then try the Dock icon again.

## What you can do

- Add an entry with today's date already filled in, an amount, Income or Spending, a category, and an optional note.
- Add a category, or remove one from the dropdown. Older entries keep a category after it is removed. You can put it back later.
- See the month's entries, and click one to change or delete it.
- See income, spending, and the difference, with a bar for each category.
- Download a Markdown report or a JSON data file for that month.
