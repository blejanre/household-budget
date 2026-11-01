"""Monthly totals and the condensed Markdown and JSON reports."""

from __future__ import annotations

from app.money import format_cents


def summary_from(month: str, totals: dict[str, int], groups: list[dict]) -> dict:
    income = totals["income"]
    spending = totals["spending"]
    return {
        "month": month,
        "currency": "CAD",
        "totals": {
            "income": format_cents(income),
            "spending": format_cents(spending),
            "net": format_cents(income - spending),
        },
        "income_by_category": [_group_public(row) for row in groups if row["kind"] == "income"],
        "spending_by_category": [_group_public(row) for row in groups if row["kind"] == "spending"],
    }


def export_from(
    month: str,
    totals: dict[str, int],
    groups: list[dict],
    transactions: list[dict],
) -> dict:
    report = summary_from(month, totals, groups)
    report["schema"] = "budget-report/v1"
    report["transactions"] = [
        {
            "date": row["date"],
            "kind": row["kind"],
            "category": row["category"],
            "amount": format_cents(row["amount_cents"]),
            "notes": row["notes"],
        }
        for row in transactions
    ]
    return {
        "schema": report["schema"],
        "month": report["month"],
        "currency": report["currency"],
        "totals": report["totals"],
        "income_by_category": report["income_by_category"],
        "spending_by_category": report["spending_by_category"],
        "transactions": report["transactions"],
    }


def render_markdown(report: dict) -> str:
    totals = report["totals"]
    lines = [
        f"# Budget report {report['month']}",
        "",
        "schema: budget-report/v1",
        f"currency: {report['currency']}",
        f"income_total: {totals['income']}",
        f"spending_total: {totals['spending']}",
        f"net: {totals['net']}",
        "",
        "## Income by category",
        "",
        *_category_lines(report["income_by_category"]),
        "",
        "## Spending by category",
        "",
        *_category_lines(report["spending_by_category"]),
        "",
        "## Transactions",
        "",
        "date | kind | category | amount | notes",
    ]
    for row in report["transactions"]:
        lines.append(
            " | ".join(
                [
                    _cell(row["date"]),
                    _cell(row["kind"]),
                    _cell(row["category"]),
                    _cell(row["amount"]),
                    _cell(row["notes"]),
                ]
            )
        )
    return "\n".join(lines) + "\n"


def _group_public(row: dict) -> dict:
    return {
        "category": row["category"],
        "total": format_cents(row["total_cents"]),
        "count": row["count"],
    }


def _category_lines(rows: list[dict]) -> list[str]:
    if not rows:
        return ["- none"]
    return [f"- {row['category']}: {row['total']} ({row['count']})" for row in rows]


def _cell(value: str) -> str:
    return str(value).replace("|", "/").replace("\n", " ").strip()
