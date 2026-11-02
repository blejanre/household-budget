# Household budget

This ledger lives on one MacBook. Open it in the browser on that Mac. Amounts are Canadian dollars. You both use the same password.

The entries are stored in `data/budget.db` inside this folder on that Mac. Copy that file somewhere safe when you want a backup.

## Put it on the MacBook

A zip downloaded in the browser will not open. The Mac shows a warning that Apple could not verify the file, and right-click Open does not get past it. Download it from Terminal instead.

1. Press Command (⌘) and the space bar together. Type Terminal and press Return.
2. Click in the Terminal window, paste this, and press Return:

```bash
curl -L -o "$HOME/Documents/household-budget.zip" https://github.com/blejanre/household-budget/archive/refs/heads/main.zip
unzip -o "$HOME/Documents/household-budget.zip" -d "$HOME/Documents"
xattr -dr com.apple.quarantine "$HOME/Documents/household-budget-main"
mkdir -p "$HOME/Applications"
cat > /tmp/BudgetLauncher.applescript <<'EOF'
do shell script "nohup /bin/bash " & quoted form of ((POSIX path of (path to home folder)) & "Documents/household-budget-main/Budget.app/Contents/MacOS/launcher") & " >/tmp/household-budget-launch.log 2>&1 &"
EOF
osacompile -o "$HOME/Applications/Budget.app" /tmp/BudgetLauncher.applescript
cp "$HOME/Documents/household-budget-main/Budget.app/Contents/Resources/AppIcon.icns" "$HOME/Applications/Budget.app/Contents/Resources/applet.icns"
bash "$HOME/Documents/household-budget-main/Budget.app/Contents/MacOS/launcher"
open "$HOME/Applications"
```

The program folder is in Documents and is named `household-budget-main`. The icon you drag to the Dock is the Budget icon in the Applications window that opens. You can trash the copy that the browser downloaded.

## First time

1. If a message says the Mac needs Python 3, install it from [python.org](https://www.python.org/downloads/), then click the Budget icon again.
2. A settings file opens. Replace the sample password with the password you both will type, save, close the file, and click the Budget icon again.
3. An Applications window opens. Drag the Budget icon from that window onto the Dock. Leave the `household-budget-main` folder in Documents. The Dock icon uses that folder.

After that, click Budget on the Dock. The budget opens in the browser. You can close the browser when you are finished. The entries stay in `data/budget.db`. Click the Dock icon the next time you want to add something.

## What you can do

- Add an entry with today's date already filled in, an amount, Income or Spending, a category, and an optional note.
- Add a category, or remove one from the dropdown. Older entries keep a category after it is removed. You can put it back later.
- See the month's entries, and click one to change or delete it.
- See income, spending, and the difference, with a bar for each category.
- Download a Markdown report or a JSON data file for that month.
