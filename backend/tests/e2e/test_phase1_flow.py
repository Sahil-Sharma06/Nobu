"""End-to-end Phase 1 flow over HTTP, with the stub LLM and fake web: offline and free."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from nobu.api.app import app
from nobu.api.deps import get_deps
from nobu.pipeline.core import Deps


@pytest.fixture
def client(deps: Deps) -> Iterator[TestClient]:
    app.dependency_overrides[get_deps] = lambda: deps
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_full_text_flow(client: TestClient, deps: Deps) -> None:
    # 1. one-time resume upload builds the fact bank and prefills the profile
    r = client.post("/resume", files={"file": ("cv.txt", b"Sahil Sharma resume", "text/plain")})
    assert r.status_code == 200 and r.json()["facts"] == 3
    assert (
        client.post("/resume", files={"file": ("cv.txt", b"again", "text/plain")}).status_code
        == 409
    )
    assert client.get("/profile").json()["name"] == "Sahil Sharma"

    # 2. command -> structured request, confirmed before any research is spent
    parsed = client.post("/outreach/parse", json={"text": "reach out to acme for backend intern"})
    assert parsed.json()["issues"] == []

    # 3. research -> match -> contact -> draft -> critic, producing a review card
    card = client.post("/outreach", json={"request": parsed.json()["parsed"]}).json()
    oid = card["id"]
    assert card["state"] == "drafted"
    assert card["contact"]["email"] == "priya@acme.dev"
    assert card["highlighted"][0]["rationale"]
    assert card["flags"] == []
    assert "https://acme.dev/careers" in card["sources"]
    assert any("approved" in p for p in card["send_problems"])

    # 4. can't send before approval, nor without explicit confirmation
    assert client.post(f"/outreach/{oid}/send", json={"confirm": True}).status_code == 409
    assert client.post(f"/outreach/{oid}/approve").json()["state"] == "approved"
    assert client.post(f"/outreach/{oid}/send", json={}).status_code == 400

    # 5. dry-run send: .eml written, nothing leaves the machine
    sent = client.post(f"/outreach/{oid}/send", json={"confirm": True}).json()
    assert sent["state"] == "sent" and sent["dry_run"] is True
    assert (deps.settings.data_dir / "outbox" / f"outreach-{oid}.eml").exists()

    # 6. dedupe: a second outreach to the same company is blocked at send time
    card2 = client.post("/outreach", json={"request": parsed.json()["parsed"]}).json()
    client.post(f"/outreach/{card2['id']}/approve")
    blocked = client.post(f"/outreach/{card2['id']}/send", json={"confirm": True})
    assert blocked.status_code == 409
    assert any("Already emailed" in p for p in blocked.json()["problems"])

    # 7. delete all my data
    assert client.post("/data/delete-all", json={"confirm": "nope"}).status_code == 400
    assert client.post("/data/delete-all", json={"confirm": "DELETE"}).json() == {"ok": True}
    assert client.get("/outreach").json() == []
    assert client.get("/facts").json() == []
    assert not any(deps.settings.data_dir.rglob("*"))


def test_flagged_draft_cannot_be_approved_or_sent(client: TestClient, deps: Deps) -> None:
    client.post("/resume", files={"file": ("cv.txt", b"cv", "text/plain")})
    assert isinstance(deps.llm, object)
    from nobu.llm.stub import StubLLM

    assert isinstance(deps.llm, StubLLM)
    deps.llm.set("critic", {"flags": [{"code": "flattery", "message": "huge fan"}]})
    req = {"company": "Acme", "role": "backend intern", "company_domain": "acme.dev"}
    card = client.post("/outreach", json={"request": req}).json()
    assert card["unresolved_flags"] == 1
    assert client.post(f"/outreach/{card['id']}/approve").status_code == 422

    # editing re-runs the critic; once the user resolves the flag it can go out
    deps.llm.set("critic", {"flags": []})
    edited = client.patch(
        f"/outreach/{card['id']}", json={"subject": card["subject"], "body": card["body"]}
    ).json()
    assert edited["flags"] == []
    assert client.post(f"/outreach/{card['id']}/approve").status_code == 200


def test_suppressed_contact_blocked(client: TestClient) -> None:
    client.post("/resume", files={"file": ("cv.txt", b"cv", "text/plain")})
    client.post("/suppression", json={"value": "ACME.dev", "reason": "asked not to"})
    req = {"company": "Acme", "role": "backend intern", "company_domain": "acme.dev"}
    card = client.post("/outreach", json={"request": req}).json()
    client.post(f"/outreach/{card['id']}/approve")
    r = client.post(f"/outreach/{card['id']}/send", json={"confirm": True})
    assert r.status_code == 409 and "suppression" in r.json()["detail"]
