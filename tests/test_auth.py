def test_login_page(client):
    res = client.get("/auth/login")
    assert res.status_code == 200