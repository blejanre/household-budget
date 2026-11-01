#!/bin/bash
cd "$(dirname "$0")"
xattr -dr com.apple.quarantine . 2>/dev/null || true
chmod +x "Budget.app/Contents/MacOS/launcher"
open "./Budget.app"
echo "Budget is starting."
echo "Drag the Budget icon onto the Dock at the bottom of the screen."
echo "After that, click the Dock icon. You can close this window."
read -r -p "Press Enter to close."
