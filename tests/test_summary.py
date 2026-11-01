import json

import pytest
from fastapi.testclient import TestClient

INCOME = ["Carly Sky", "Carly Teaching", "Ben Elm", "Other Income"]
SPENDING = [
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
]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "household-test")
    monkeypatch.setenv("SESSION_SECRET", "test-secret-value-123")
    monkeypatch.setenv("BUDGET_DB", str(tmp_path / "budget.db"))
    monkeypatch.setenv("COOKIE_SECURE", "0")
    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client


def login(client: TestClient) -> None:
    response = client.post("/api/login", json={"password": "household-test"})
    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie


def category_id(client: TestClient, name: str, kind: str = "spending") -> int:
    rows = client.get("/api/categories").json()
    for row in rows:
        if row["name"] == name and row["kind"] == kind:
            return row["id"]
    raise AssertionError(name)


def test_refuses_to_start_without_password(tmp_path, monkeypatch):
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    monkeypatch.delenv("SESSION_SECRET", raising=False)
    monkeypatch.setenv("BUDGET_DB", str(tmp_path / "budget.db"))
    from app.main import create_app

    with pytest.raises(RuntimeError, match="APP_PASSWORD"):
        with TestClient(create_app()):
            pass


def test_refuses_sample_password(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "replace-with-a-shared-password")
    monkeypatch.setenv("SESSION_SECRET", "test-secret-value-123")
    monkeypatch.setenv("BUDGET_DB", str(tmp_path / "budget.db"))
    from app.main import create_app

    with pytest.raises(RuntimeError, match="sample"):
        with TestClient(create_app()):
            pass


def test_requires_login(client):
    assert client.get("/api/summary", params={"month": "2026-11"}).status_code == 401
    assert client.get("/api/export", params={"month": "2026-11", "format": "md"}).status_code == 401
    assert client.post("/api/login", json={"password": "nope"}).status_code == 401
    assert client.get("/health").json() == {"ok": True}


def test_starter_categories(client):
    login(client)
    rows = client.get("/api/categories").json()
    income = [row["name"] for row in rows if row["kind"] == "income"]
    spending = [row["name"] for row in rows if row["kind"] == "spending"]
    assert income == INCOME
    assert spending == SPENDING
    assert all(row["hidden"] is False for row in rows)

    duplicate = client.post("/api/categories", json={"name": "groceries", "kind": "spending"})
    assert duplicate.status_code == 409
    created = client.post("/api/categories", json={"name": "Coffee", "kind": "spending"})
    assert created.status_code == 201
    assert created.json()["name"] == "Coffee"
    assert created.json()["hidden"] is False


def test_summary_net_and_export(client):
    login(client)
    income = category_id(client, "Ben Elm", "income")
    groceries = category_id(client, "Groceries")
    assert client.post(
        "/api/transactions",
        json={
            "date": "2026-11-02",
            "amount": "100.00",
            "kind": "income",
            "category_id": income,
            "notes": "",
        },
    ).status_code == 201
    noted = client.post(
        "/api/transactions",
        json={
            "date": "2026-11-03",
            "amount": "0.10",
            "kind": "spending",
            "category_id": groceries,
            "notes": "a|b\nline",
        },
    )
    assert noted.status_code == 201
    assert client.post(
        "/api/transactions",
        json={
            "date": "2026-11-04",
            "amount": "0.20",
            "kind": "spending",
            "category_id": groceries,
            "notes": "",
        },
    ).status_code == 201

    summary = client.get("/api/summary", params={"month": "2026-11"}).json()
    assert summary["currency"] == "CAD"
    assert summary["totals"] == {"income": "100.00", "spending": "0.30", "net": "99.70"}
    assert summary["income_by_category"] == [{"category": "Ben Elm", "total": "100.00", "count": 1}]
    assert summary["spending_by_category"] == [{"category": "Groceries", "total": "0.30", "count": 2}]

    other = client.get("/api/summary", params={"month": "2026-10"}).json()
    assert other["totals"] == {"income": "0.00", "spending": "0.00", "net": "0.00"}
    assert client.get("/api/summary", params={"month": "2026-13"}).status_code == 400

    markdown = client.get("/api/export", params={"month": "2026-11", "format": "md"})
    assert markdown.status_code == 200
    assert "budget-2026-11.md" in markdown.headers["content-disposition"]
    text = markdown.text
    assert "schema: budget-report/v1" in text
    assert "currency: CAD" in text
    assert "income_total: 100.00" in text
    assert "spending_total: 0.30" in text
    assert "net: 99.70" in text
    assert "- Ben Elm: 100.00 (1)" in text
    assert "- Groceries: 0.30 (2)" in text
    assert "a/b line" in text

    payload = json.loads(client.get("/api/export", params={"month": "2026-11", "format": "json"}).text)
    assert payload["schema"] == "budget-report/v1"
    assert payload["currency"] == "CAD"
    assert payload["totals"]["net"] == "99.70"
    assert payload["transactions"][1]["notes"] == "a|b\nline"
    assert payload["transactions"][1]["amount"] == "0.10"
    assert [row["date"] for row in payload["transactions"]] == [
        "2026-11-02",
        "2026-11-03",
        "2026-11-04",
    ]


def test_negative_net(client):
    login(client)
    client.post(
        "/api/transactions",
        json={
            "date": "2026-12-01",
            "amount": "10.00",
            "kind": "income",
            "category_id": category_id(client, "Other Income", "income"),
            "notes": "",
        },
    )
    client.post(
        "/api/transactions",
        json={
            "date": "2026-12-02",
            "amount": "25.00",
            "kind": "spending",
            "category_id": category_id(client, "Hockey"),
            "notes": "",
        },
    )
    summary = client.get("/api/summary", params={"month": "2026-12"}).json()
    assert summary["totals"]["net"] == "-15.00"
    text = client.get("/api/export", params={"month": "2026-12", "format": "md"}).text
    assert "net: -15.00" in text


def test_hidden_category_stays_on_old_entries(client):
    login(client)
    groceries = category_id(client, "Groceries")
    created = client.post(
        "/api/transactions",
        json={
            "date": "2026-11-05",
            "amount": "12.50",
            "kind": "spending",
            "category_id": groceries,
            "notes": "milk",
        },
    )
    assert created.status_code == 201
    tx_id = created.json()["id"]

    hidden = client.patch(f"/api/categories/{groceries}", json={"hidden": True})
    assert hidden.status_code == 200
    assert hidden.json()["hidden"] is True
    assert hidden.json()["name"] == "Groceries"

    blocked = client.post(
        "/api/transactions",
        json={
            "date": "2026-11-06",
            "amount": "1.00",
            "kind": "spending",
            "category_id": groceries,
            "notes": "",
        },
    )
    assert blocked.status_code == 400

    updated = client.patch(
        f"/api/transactions/{tx_id}",
        json={
            "date": "2026-11-05",
            "amount": "12.50",
            "kind": "spending",
            "category_id": groceries,
            "notes": "milk and bread",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["category"] == "Groceries"
    assert updated.json()["category_hidden"] is True
    assert updated.json()["notes"] == "milk and bread"

    listed = client.get("/api/transactions", params={"month": "2026-11"}).json()
    assert listed[0]["category"] == "Groceries"

    summary = client.get("/api/summary", params={"month": "2026-11"}).json()
    assert summary["spending_by_category"] == [{"category": "Groceries", "total": "12.50", "count": 1}]
    report = json.loads(client.get("/api/export", params={"month": "2026-11", "format": "json"}).text)
    assert report["transactions"][0]["category"] == "Groceries"
    assert "Groceries" in client.get("/api/export", params={"month": "2026-11", "format": "md"}).text

    restored = client.patch(f"/api/categories/{groceries}", json={"hidden": False})
    assert restored.json()["hidden"] is False
    assert (
        client.post(
            "/api/transactions",
            json={
                "date": "2026-11-06",
                "amount": "1.00",
                "kind": "spending",
                "category_id": groceries,
                "notes": "",
            },
        ).status_code
        == 201
    )


def test_rejects_bad_amounts_and_mismatched_kind(client):
    login(client)
    pets = category_id(client, "Pets")

    def post(amount, kind="spending", category=pets, day="2026-11-01"):
        return client.post(
            "/api/transactions",
            json={
                "date": day,
                "amount": amount,
                "kind": kind,
                "category_id": category,
                "notes": "",
            },
        )

    assert post("0").status_code == 400
    assert post("-5").status_code == 400
    assert post("1.234").status_code == 400
    assert post("12,50").status_code == 201
    assert post("12,50").json()["amount"] == "12.50"
    large = post("1,234.56")
    assert large.status_code == 201
    assert large.json()["amount"] == "1234.56"
    assert post("10.00", kind="income", category=pets).status_code == 400


def test_edit_and_delete_entry(client):
    login(client)
    created = client.post(
        "/api/transactions",
        json={
            "date": "2026-11-08",
            "amount": "8.00",
            "kind": "spending",
            "category_id": category_id(client, "Violin"),
            "notes": "strings",
        },
    )
    tx_id = created.json()["id"]
    edited = client.patch(
        f"/api/transactions/{tx_id}",
        json={
            "date": "2026-11-09",
            "amount": "9.25",
            "kind": "spending",
            "category_id": category_id(client, "Synchro"),
            "notes": "meet",
        },
    )
    assert edited.status_code == 200
    assert edited.json()["amount"] == "9.25"
    assert edited.json()["category"] == "Synchro"
    assert client.delete(f"/api/transactions/{tx_id}").status_code == 204
    summary = client.get("/api/summary", params={"month": "2026-11"}).json()
    assert summary["totals"]["spending"] == "0.00"
    assert client.delete(f"/api/transactions/{tx_id}").status_code == 404
