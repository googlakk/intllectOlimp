async def test_healthz(client):
    response = await client.get("/api/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_database_starts_empty(client):
    response = await client.get("/api/auth/users")
    assert response.status_code == 200
    assert response.json() == {"students": [], "teachers": []}
