import os


def test_ui_pages_and_api_work_in_no_auth_mode():
    # Ensure NO-AUTH mode
    os.environ["DISABLE_AUTH"] = "1"

    from fastapi.testclient import TestClient
    from backend.main import app

    client = TestClient(app)

    # Required UI pages
    r = client.get("/ui/dashboard")
    assert r.status_code == 200

    r = client.get("/ui/departments")
    assert r.status_code == 200

    r = client.get("/ui/agents")
    assert r.status_code == 200

    r = client.get("/ui/council")
    assert r.status_code in (200, 302)

    r = client.get("/ui/memory")
    assert r.status_code == 200

    r = client.get("/ui/health")
    assert r.status_code == 200

    # Key APIs must not 401 in no-auth mode
    r = client.get("/api/v1/agents")
    assert r.status_code == 200
    assert isinstance(r.json(), dict)

    r = client.get("/api/v1/departments")
    assert r.status_code == 200
    assert isinstance(r.json(), dict)











