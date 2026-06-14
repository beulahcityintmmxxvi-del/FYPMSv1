def test_student_registration_page_loads(client):
    response = client.get("/auth/register")
    assert response.status_code == 200


def test_supervisor_registration_page_loads(client):
    response = client.get("/auth/supervisor-register")
    assert response.status_code == 200