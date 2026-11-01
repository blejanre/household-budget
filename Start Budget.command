#!/bin/bash
cd "$(dirname "$0")"

pause() {
  read -r -p "Press Enter to close."
}

if ! command -v python3 >/dev/null 2>&1; then
  echo "This Mac needs Python 3. Install it from https://www.python.org/downloads/ and run this again."
  pause
  exit 1
fi

if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/python -m pip install -r requirements.txt
fi

if [ ! -f .env ]; then
  secret=$(python3 -c "import secrets; print(secrets.token_hex(32))")
  printf '%s\n' \
    "APP_PASSWORD=replace-with-a-shared-password" \
    "SESSION_SECRET=${secret}" \
    "BUDGET_DB=data/budget.db" \
    > .env
  echo "A file named .env was created in this folder."
  echo "Open it, replace the sample password with the password you both will type, save, and run this again."
  pause
  exit 1
fi

echo "The budget will open at http://127.0.0.1:8000"
echo "Leave this window open while you use it. Close the window when you are done."

.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 &
server_pid=$!

opened=0
for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
  if curl -sf "http://127.0.0.1:8000/health" >/dev/null; then
    open "http://127.0.0.1:8000"
    opened=1
    break
  fi
  if ! kill -0 "$server_pid" 2>/dev/null; then
    break
  fi
  sleep 0.3
done

if [ "$opened" -eq 0 ]; then
  echo "The budget did not start. If .env still has the sample password, replace it and run this again."
fi

wait "$server_pid"
