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
