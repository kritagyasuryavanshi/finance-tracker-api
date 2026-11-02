import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _demo(client):
    res = client.post("/auth/demo")
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_login_is_case_insensitive(client):
    client.post("/auth/signup", json={"email": "Mixed.Case@Example.com", "password": "Secret123!"})
    res = client.post("/auth/login", json={"email": "  mixed.case@example.com ", "password": "Secret123!"})
    assert res.status_code == 200


def test_signup_rejects_invalid_email(client):
    assert client.post("/auth/signup", json={"email": "not-an-email", "password": "Secret123!"}).status_code == 422


def test_demo_account_is_seeded_and_private(client):
    a, b = _demo(client), _demo(client)
    me_a = client.get("/auth/me", headers=a).json()
    me_b = client.get("/auth/me", headers=b).json()
    assert me_a["id"] != me_b["id"]

    rows = client.get("/transactions/", headers=a).json()
    assert len(rows) >= 20
    summary = client.get("/transactions/summary", headers=a).json()
    assert summary["total_income"] == 185000.0
    assert summary["balance"] > 0

    # changes in one demo account never show up in another
    client.delete(f"/transactions/{rows[0]['id']}", headers=a)
    assert len(client.get("/transactions/", headers=b).json()) == len(rows)


def test_transactions_newest_first_with_iso_dates(client):
    rows = client.get("/transactions/", headers=_demo(client)).json()
    dates = [r["date"] for r in rows]
    assert dates == sorted(dates, reverse=True)
    assert all(d.endswith("Z") and "T" in d for d in dates)


def test_chat_drops_duplicated_latest_message(client, monkeypatch):
    import services.ai_service as ai_service

    seen = {}

    def fake_chat(user_message, transactions, summary, chat_history):
        seen["history"] = chat_history
        return "ok"

    monkeypatch.setattr(ai_service, "chat_with_ai", fake_chat)
    headers = _demo(client)
    body = {
        "message": "How much on rent?",
        "chat_history": [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
            {"role": "user", "content": "How much on rent?"},
        ],
    }
    res = client.post("/ai/chat", json=body, headers=headers)
    assert res.status_code == 200
    assert [m["content"] for m in seen["history"]] == ["hi", "hello"]


def test_upload_rejects_non_csv_and_large_files(client):
    headers = _demo(client)
    res = client.post("/ai/upload", files={"file": ("notes.txt", b"hello", "text/plain")}, headers=headers)
    assert res.status_code == 400
    big = b"a,b\n" + b"1,2\n" * (2 * 1024 * 1024)
    res = client.post("/ai/upload", files={"file": ("big.csv", big, "text/csv")}, headers=headers)
    assert res.status_code == 413


def test_csv_stats_layouts(tmp_path):
    from services.langchain_service import compute_csv_stats

    def stats(text):
        f = tmp_path / "s.csv"
        f.write_text(text)
        return compute_csv_stats(str(f))

    assert stats("Date,Description,Debit,Credit\n1,Rent,22000,\n2,Salary,,85000\n")["balance"] == 63000
    assert stats("date,type,amount\n1,income,1000\n2,expense,250.5\n")["total_expense"] == 250.5
    assert stats("Txn,Amount\nSalary,\"85,000\"\nRent,-22000\n")["total_income"] == 85000
    assert stats("a,b\nx,y\n") is None


def test_heavy_ai_libraries_are_not_loaded_at_startup():
    """The API must start without importing CrewAI, Chroma or LangChain (memory and cold start)."""
    env = {**os.environ, "DATABASE_URL": "sqlite://", "SECRET_KEY": "x"}
    code = (
        "import sys, main; heavy=[m for m in ('crewai','langchain_chroma','chromadb','langgraph','langchain_google_genai') "
        "if m in sys.modules]; print(','.join(heavy))"
    )
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == ""


def test_database_outage_returns_clear_503(client, monkeypatch):
    import database
    from sqlalchemy.exc import OperationalError

    def broken(*args, **kwargs):
        raise OperationalError("SELECT 1", {}, Exception("could not connect to server"))

    monkeypatch.setattr(database, "get_user_by_email", broken)
    res = client.post("/auth/login", json={"email": "a@example.com", "password": "x"})
    assert res.status_code == 503
    assert "database is unavailable" in res.json()["detail"]
