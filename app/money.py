"""Amount, date, and category text checks. Amounts are integer cents."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

TWOPLACES = Decimal("0.01")
MAX_CENTS = 10_000_000_00


class BudgetError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


def format_cents(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    cents = abs(int(cents))
    return f"{sign}{cents // 100}.{cents % 100:02d}"


def parse_amount_cents(value: str) -> int:
    text = str(value).strip().replace("$", "").replace("CA$", "").replace(" ", "")
    if text.count(",") == 1 and "." not in text:
        text = text.replace(",", ".")
    else:
        text = text.replace(",", "")
    if not re.fullmatch(r"\d+(\.\d+)?", text or ""):
        raise BudgetError("Enter an amount like 12.50.")
    try:
        amount = Decimal(text)
    except InvalidOperation as exc:
        raise BudgetError("Enter an amount like 12.50.") from exc
    if amount <= 0:
        raise BudgetError("Amount must be greater than zero.")
    quantized = amount.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    if quantized != amount:
        raise BudgetError("Use at most two decimal places.")
    cents = int((quantized * 100).to_integral_value(rounding=ROUND_HALF_UP))
    if cents > MAX_CENTS:
        raise BudgetError("Amount is too large.")
    return cents


def parse_date(value: str) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value or ""):
        raise BudgetError("Enter a valid date.")
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise BudgetError("Enter a valid date.") from exc


def parse_month(value: str) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}", value or ""):
        raise BudgetError("Month must look like 2026-11.")
    year, month = int(value[:4]), int(value[5:])
    if month < 1 or month > 12:
        raise BudgetError("Month must look like 2026-11.")
    return f"{year:04d}-{month:02d}"


def clean_notes(value: str) -> str:
    text = str(value or "").replace("\r\n", "\n").strip()
    if len(text) > 500:
        raise BudgetError("Notes must be 500 characters or fewer.")
    return text


def clean_name(value: str) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        raise BudgetError("Enter a category name.")
    if len(text) > 40:
        raise BudgetError("Category name must be 40 characters or fewer.")
    return text
