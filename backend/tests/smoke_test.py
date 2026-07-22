import os

os.environ["DATABASE_URL"] = "sqlite:///./smoke_test.db"
# Replicate the docker-compose environment: empty string, not unset.
os.environ["OPENAI_BASE_URL"] = ""
os.environ["SECRET_KEY"] = "smoke-test-secret"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "test123"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

with TestClient(app) as client:  # context manager triggers lifespan (bootstrap + scheduler)
    r = client.get("/api/health")
    assert r.status_code == 200, r.text
    print("health:", r.json())

    r = client.get("/api/mailboxes")
    assert r.status_code == 401, "expected 401 without token, got " + str(r.status_code)
    print("unauthenticated /api/mailboxes correctly rejected (401)")

    r = client.post("/api/auth/login", data={"username": "admin", "password": "test123"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    print("login: ok")
    headers = {"Authorization": f"Bearer {token}"}

    r = client.get("/api/mailboxes", headers=headers)
    assert r.status_code == 200, r.text
    print("mailboxes:", r.json())

    payload = {
        "name": "Test box",
        "email_address": "support@example.com",
        "imap_host": "imap.example.com",
        "imap_username": "support@example.com",
        "imap_password": "pw1",
        "smtp_host": "smtp.example.com",
        "smtp_username": "support@example.com",
        "smtp_password": "pw2",
    }
    r = client.post("/api/mailboxes", headers=headers, json=payload)
    assert r.status_code == 201, r.text
    mb = r.json()
    assert "imap_password" not in mb and "imap_password_enc" not in mb
    print("mailbox created:", mb["id"], mb["name"])

    r = client.get(f"/api/mailboxes/{mb['id']}/agent", headers=headers)
    assert r.status_code == 200, r.text
    print("agent auto-created:", r.json()["enabled"], r.json()["interval_minutes"])

    r = client.put(
        f"/api/mailboxes/{mb['id']}/agent",
        headers=headers,
        json={"enabled": True, "interval_minutes": 60, "product_context": "A CLI tool"},
    )
    assert r.status_code == 200, r.text
    print("agent updated: enabled =", r.json()["enabled"])

    r = client.post(
        f"/api/mailboxes/{mb['id']}/agent/documents",
        headers=headers,
        json={"title": "FAQ", "content": "Q: ...\nA: ..."},
    )
    assert r.status_code == 201, r.text
    print("document added")

    # knowledge items: playbooks (per-situation rules) + product facts
    r = client.post(
        f"/api/mailboxes/{mb['id']}/agent/knowledge",
        headers=headers,
        json={"kind": "playbook", "title": "SEO cold outreach", "body": "Ignore it."},
    )
    assert r.status_code == 201, r.text
    pb_id = r.json()["id"]
    r = client.post(
        f"/api/mailboxes/{mb['id']}/agent/knowledge",
        headers=headers,
        json={"kind": "fact", "title": "Free plan", "body": "5 exports/month."},
    )
    assert r.status_code == 201, r.text
    r = client.post(
        f"/api/mailboxes/{mb['id']}/agent/knowledge",
        headers=headers,
        json={"kind": "bogus", "title": "x", "body": "y"},
    )
    assert r.status_code == 422, "invalid knowledge kind must be rejected: " + str(r.status_code)
    r = client.get(
        f"/api/mailboxes/{mb['id']}/agent/knowledge",
        headers=headers,
        params={"kind": "playbook"},
    )
    assert r.status_code == 200 and len(r.json()) == 1, r.text
    r = client.put(
        f"/api/knowledge/{pb_id}",
        headers=headers,
        json={"title": "SEO cold outreach", "body": "Ignore it, do not reply."},
    )
    assert r.status_code == 200 and r.json()["body"].endswith("do not reply."), r.text
    r = client.get(f"/api/mailboxes/{mb['id']}/agent/knowledge", headers=headers)
    assert r.status_code == 200 and len(r.json()) == 2, r.text
    r = client.delete(f"/api/knowledge/{pb_id}", headers=headers)
    assert r.status_code == 204, r.text
    print("knowledge CRUD (playbook + fact): ok")

    r = client.get("/api/settings", headers=headers)
    assert r.status_code == 200, r.text
    print("settings:", r.json())

    r = client.put(
        "/api/settings",
        headers=headers,
        json={"openai_api_key": "sk-test-abcd", "openai_base_url": "", "default_model": "gpt-4o-mini"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["has_api_key"] is True
    assert r.json()["api_key_hint"] == "…abcd"
    print("settings saved with masked key:", r.json()["api_key_hint"])

    r = client.get("/api/providers", headers=headers)
    assert r.status_code == 200, r.text
    provider_ids = [p["id"] for p in r.json()]
    assert "openai" in provider_ids and "openai-compatible" in provider_ids
    print("providers:", provider_ids)

    r = client.get("/api/models", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["source"] == "curated"
    assert "gpt-5.6-terra" in r.json()["models"]
    print("models (curated):", len(r.json()["models"]), "models, first:", r.json()["models"][0])

    r = client.put(
        "/api/settings",
        headers=headers,
        json={"provider": "openai", "openai_api_key": "", "openai_base_url": "", "default_model": ""},
    )
    assert r.status_code == 200, r.text
    assert r.json()["default_model"] == "gpt-5.6-terra", r.json()
    print("empty default_model falls back to provider default:", r.json()["default_model"])

    # get_llm must return exactly (client, model).
    from app.database import SessionLocal
    from app.services import llm as llm_service

    _db = SessionLocal()
    llm_client, llm_model = llm_service.get_llm(_db)
    assert isinstance(llm_model, str) and llm_model, llm_model
    _db.close()
    print("get_llm unpacks to (client, model):", llm_model)

    # Assistant: with a fake key the LLM call must fail cleanly (502), not 500,
    # and the failure must come from the provider call, not our own code.
    r = client.post(
        f"/api/mailboxes/{mb['id']}/assistant",
        headers=headers,
        json={"messages": [{"role": "user", "content": "hello"}]},
    )
    assert r.status_code == 502, f"expected 502 with fake key, got {r.status_code}: {r.text}"
    detail = r.json()["detail"]
    assert "unpack" not in detail and "Error code" in detail or "api" in detail.lower(), detail
    print("assistant endpoint fails cleanly with invalid key (502):", detail[:80])

    r = client.post(
        f"/api/mailboxes/{mb['id']}/assistant",
        headers=headers,
        json={"messages": []},
    )
    assert r.status_code == 422, r.text
    print("assistant rejects empty message list (422)")

    r = client.get("/api/dashboard/stats", headers=headers)
    assert r.status_code == 200, r.text
    print("stats:", r.json())

    r = client.get("/api/emails", headers=headers)
    assert r.status_code == 200, r.text
    print("emails:", r.json())

    r = client.get("/api/replies", headers=headers)
    assert r.status_code == 200, r.text
    print("replies:", r.json())

    r = client.delete(f"/api/mailboxes/{mb['id']}", headers=headers)
    assert r.status_code == 204, r.text
    print("mailbox deleted (cascade)")

    paths = client.get("/openapi.json").json()["paths"]
    print("openapi paths:", len(paths))

print("SMOKE TEST PASSED")
