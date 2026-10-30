def _add(client, headers, type_, amount, category="General"):
    res = client.post(
        "/transactions/",
        json={"type": type_, "category": category, "amount": amount, "description": "test"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()


def test_requires_auth(client):
    assert client.get("/transactions/").status_code in (401, 403)


def test_create_and_list(client, user):
    created = _add(client, user["headers"], "income", 5000, "Salary")
    listed = client.get("/transactions/", headers=user["headers"]).json()
    assert [t["id"] for t in listed] == [created["id"]]


def test_summary_math(client, user):
    _add(client, user["headers"], "income", 1000)
    _add(client, user["headers"], "expense", 250.5)
    _add(client, user["headers"], "expense", 100)
    summary = client.get("/transactions/summary", headers=user["headers"]).json()
    assert summary == {
        "total_income": 1000.0,
        "total_expense": 350.5,
        "balance": 649.5,
        "transaction_count": 3,
    }


def test_filter_by_type(client, user):
    _add(client, user["headers"], "income", 10)
    _add(client, user["headers"], "expense", 5)
    expenses = client.get("/transactions/?transaction_type=expense", headers=user["headers"]).json()
    assert len(expenses) == 1 and expenses[0]["type"] == "expense"
    assert client.get("/transactions/?transaction_type=bogus", headers=user["headers"]).status_code == 400


def test_validation_rejects_bad_input(client, user):
    bad_amount = {"type": "income", "category": "Salary", "amount": -5}
    bad_type = {"type": "gift", "category": "Salary", "amount": 5}
    assert client.post("/transactions/", json=bad_amount, headers=user["headers"]).status_code == 422
    assert client.post("/transactions/", json=bad_type, headers=user["headers"]).status_code == 422


def test_delete(client, user):
    created = _add(client, user["headers"], "expense", 42)
    assert client.delete(f"/transactions/{created['id']}", headers=user["headers"]).status_code == 200
    assert client.get(f"/transactions/{created['id']}", headers=user["headers"]).status_code == 404


def test_users_cannot_see_each_others_data(client, user, other_user):
    mine = _add(client, user["headers"], "income", 999)
    theirs = client.get("/transactions/", headers=other_user["headers"]).json()
    assert theirs == []
    assert client.get(f"/transactions/{mine['id']}", headers=other_user["headers"]).status_code == 404
    assert client.delete(f"/transactions/{mine['id']}", headers=other_user["headers"]).status_code == 404
