"""SQLite ledger. Hiding a category leaves the row so old entries keep the name."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.money import BudgetError, format_cents

INCOME_CATEGORIES = (
    "Carly Sky",
    "Carly Teaching",
    "Ben Elm",
    "Other Income",
)

SPENDING_CATEGORIES = (
    "Phones",
    "Electricity",
    "Water",
    "Car/Gas",
    "Hockey",
    "Synchro",
    "Violin",
    "Life Insurance",
    "Charity",
    "Subscriptions",
    "Gym",
    "Entertainment",
    "Groceries",
    "Braces",
    "Medication",
    "Pets",
    "Beauty appt.",
    "Ben Savings",
    "Carly Retirement",
)

TRANSACTION_SELECT = """
    SELECT t.id, t.date, t.amount_cents, t.kind, t.category_id, t.notes,
           c.name AS category, c.hidden AS category_hidden
    FROM transactions t
    JOIN categories c ON c.id = t.category_id
"""


def db_path() -> Path:
    return Path(os.environ.get("BUDGET_DB", "data/budget.db"))


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL").fetchone()
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
        except Exception:
            conn.execute("ROLLBACK")
            raise
        else:
            conn.execute("COMMIT")
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                kind TEXT NOT NULL CHECK (kind IN ('income', 'spending')),
                hidden INTEGER NOT NULL DEFAULT 0 CHECK (hidden IN (0, 1)),
                sort_order INTEGER NOT NULL,
                UNIQUE (name, kind)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY,
                date TEXT NOT NULL,
                amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
                kind TEXT NOT NULL CHECK (kind IN ('income', 'spending')),
                category_id INTEGER NOT NULL REFERENCES categories(id),
                notes TEXT NOT NULL DEFAULT ''
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date)"
        )
        seeded = conn.execute("SELECT 1 FROM meta WHERE key = 'seeded'").fetchone()
        if seeded is None:
            _seed_categories(conn)
            conn.execute("INSERT INTO meta (key, value) VALUES ('seeded', '1')")


def _seed_categories(conn: sqlite3.Connection) -> None:
    for kind, names in (("income", INCOME_CATEGORIES), ("spending", SPENDING_CATEGORIES)):
        for order, name in enumerate(names):
            conn.execute(
                """
                INSERT INTO categories (name, kind, hidden, sort_order)
                VALUES (?, ?, 0, ?)
                """,
                (name, kind, order),
            )


def public_category(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "kind": row["kind"],
        "hidden": bool(row["hidden"]),
    }


def public_transaction(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "date": row["date"],
        "amount": format_cents(row["amount_cents"]),
        "kind": row["kind"],
        "category_id": row["category_id"],
        "category": row["category"],
        "category_hidden": bool(row["category_hidden"]),
        "notes": row["notes"],
    }


def list_categories(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, name, kind, hidden, sort_order
        FROM categories
        ORDER BY CASE kind WHEN 'income' THEN 0 ELSE 1 END, sort_order, id
        """
    ).fetchall()
    return [public_category(row) for row in rows]


def create_category(conn: sqlite3.Connection, name: str, kind: str) -> dict:
    existing = conn.execute(
        """
        SELECT id, hidden FROM categories
        WHERE kind = ? AND lower(name) = lower(?)
        """,
        (kind, name),
    ).fetchone()
    if existing is not None:
        if existing["hidden"]:
            raise BudgetError("That category is hidden. Put it back on the dropdown.", 409)
        raise BudgetError("That category is already on the list.", 409)
    order = conn.execute(
        "SELECT COALESCE(MAX(sort_order), -1) + 1 AS next_order FROM categories WHERE kind = ?",
        (kind,),
    ).fetchone()["next_order"]
    cursor = conn.execute(
        """
        INSERT INTO categories (name, kind, hidden, sort_order)
        VALUES (?, ?, 0, ?)
        """,
        (name, kind, order),
    )
    row = conn.execute(
        "SELECT id, name, kind, hidden FROM categories WHERE id = ?",
        (cursor.lastrowid,),
    ).fetchone()
    return public_category(row)


def set_category_hidden(conn: sqlite3.Connection, category_id: int, hidden: bool) -> dict:
    row = conn.execute(
        "SELECT id, name, kind, hidden FROM categories WHERE id = ?",
        (category_id,),
    ).fetchone()
    if row is None:
        raise BudgetError("Category not found.", 404)
    conn.execute(
        "UPDATE categories SET hidden = ? WHERE id = ?",
        (1 if hidden else 0, category_id),
    )
    updated = conn.execute(
        "SELECT id, name, kind, hidden FROM categories WHERE id = ?",
        (category_id,),
    ).fetchone()
    return public_category(updated)


def _load_category(conn: sqlite3.Connection, category_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
    if row is None:
        raise BudgetError("Choose a category.", 400)
    return row


def _ensure_category(row: sqlite3.Row, kind: str, *, allow_hidden: bool) -> None:
    if row["kind"] != kind:
        raise BudgetError("Choose a category that matches income or spending.", 400)
    if row["hidden"] and not allow_hidden:
        raise BudgetError("That category is hidden. Put it back to use it on a new entry.", 400)


def _transaction_row(conn: sqlite3.Connection, tx_id: int) -> sqlite3.Row:
    row = conn.execute(
        TRANSACTION_SELECT + " WHERE t.id = ?",
        (tx_id,),
    ).fetchone()
    if row is None:
        raise BudgetError("Entry not found.", 404)
    return row


def list_transactions(conn: sqlite3.Connection, month: str) -> list[dict]:
    rows = conn.execute(
        TRANSACTION_SELECT + " WHERE substr(t.date, 1, 7) = ? ORDER BY t.date DESC, t.id DESC",
        (month,),
    ).fetchall()
    return [public_transaction(row) for row in rows]


def create_transaction(
    conn: sqlite3.Connection,
    *,
    day: str,
    amount_cents: int,
    kind: str,
    category_id: int,
    notes: str,
) -> dict:
    category = _load_category(conn, category_id)
    _ensure_category(category, kind, allow_hidden=False)
    cursor = conn.execute(
        """
        INSERT INTO transactions (date, amount_cents, kind, category_id, notes)
        VALUES (?, ?, ?, ?, ?)
        """,
        (day, amount_cents, kind, category_id, notes),
    )
    return public_transaction(_transaction_row(conn, int(cursor.lastrowid)))


def update_transaction(
    conn: sqlite3.Connection,
    tx_id: int,
    *,
    day: str,
    amount_cents: int,
    kind: str,
    category_id: int,
    notes: str,
) -> dict:
    existing = _transaction_row(conn, tx_id)
    category = _load_category(conn, category_id)
    _ensure_category(category, kind, allow_hidden=category["id"] == existing["category_id"])
    conn.execute(
        """
        UPDATE transactions
        SET date = ?, amount_cents = ?, kind = ?, category_id = ?, notes = ?
        WHERE id = ?
        """,
        (day, amount_cents, kind, category_id, notes, tx_id),
    )
    return public_transaction(_transaction_row(conn, tx_id))


def delete_transaction(conn: sqlite3.Connection, tx_id: int) -> None:
    _transaction_row(conn, tx_id)
    conn.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))


def month_totals(conn: sqlite3.Connection, month: str) -> dict[str, int]:
    totals = {"income": 0, "spending": 0}
    rows = conn.execute(
        """
        SELECT kind, COALESCE(SUM(amount_cents), 0) AS total
        FROM transactions
        WHERE substr(date, 1, 7) = ?
        GROUP BY kind
        """,
        (month,),
    ).fetchall()
    for row in rows:
        totals[row["kind"]] = int(row["total"])
    return totals


def month_groups(conn: sqlite3.Connection, month: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT c.name AS category, t.kind AS kind,
               SUM(t.amount_cents) AS total_cents, COUNT(*) AS count
        FROM transactions t
        JOIN categories c ON c.id = t.category_id
        WHERE substr(t.date, 1, 7) = ?
        GROUP BY t.category_id, t.kind
        ORDER BY total_cents DESC, c.name COLLATE NOCASE ASC
        """,
        (month,),
    ).fetchall()
    return [
        {
            "category": row["category"],
            "kind": row["kind"],
            "total_cents": int(row["total_cents"]),
            "count": int(row["count"]),
        }
        for row in rows
    ]


def month_export_rows(conn: sqlite3.Connection, month: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT t.date, t.kind, c.name AS category, t.amount_cents, t.notes
        FROM transactions t
        JOIN categories c ON c.id = t.category_id
        WHERE substr(t.date, 1, 7) = ?
        ORDER BY t.date ASC, t.id ASC
        """,
        (month,),
    ).fetchall()
    return [
        {
            "date": row["date"],
            "kind": row["kind"],
            "category": row["category"],
            "amount_cents": int(row["amount_cents"]),
            "notes": row["notes"],
        }
        for row in rows
    ]
