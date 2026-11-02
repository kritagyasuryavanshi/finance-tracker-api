def test_health(client):
    assert client.get("/health").json() == {"status": "healthy"}


def test_signup_returns_token(client, user):
    me = client.get("/auth/me", headers=user["headers"])
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == user["email"]
    assert "password_hash" not in body


def test_duplicate_signup_rejected(client, user):
    res = client.post("/auth/signup", json={"email": user["email"], "password": "Another1!pass"})
    assert res.status_code >= 400


def test_login_with_correct_password(client, user):
    res = client.post("/auth/login", json={"email": user["email"], "password": user["password"]})
    assert res.status_code == 200
    assert res.json()["access_token"]


def test_login_with_wrong_password(client, user):
    res = client.post("/auth/login", json={"email": user["email"], "password": "wrong-password"})
    assert res.status_code in (400, 401)
    assert "access_token" not in res.json()


def test_invalid_token_rejected(client):
    res = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert res.status_code == 401


def test_ai_endpoints_require_auth(client):
    """Every AI endpoint reads user data, so none may be called anonymously."""
    calls = [
        ("get", "/ai/insights", None),
        ("post", "/ai/chat", {"message": "hi"}),
        ("post", "/ai/advice", {"category": "Food", "amount": 10}),
        ("post", "/ai/query-documents", {"question": "hi"}),
        ("post", "/ai/hybrid-search", {"question": "hi"}),
        ("get", "/ai/deep-analysis", None),
        ("get", "/ai/crew-analysis", None),
    ]
    for method, path, body in calls:
        res = getattr(client, method)(path, json=body) if body else getattr(client, method)(path)
        assert res.status_code in (401, 403), f"{path} returned {res.status_code}"
