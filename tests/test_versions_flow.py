"""Integration tests for tailored-resume version history + revert."""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.models import (
    CompatibilityAnalysis,
    CompatibilityScore,
    KeywordOverlap,
    TailoredBullet,
    TailoredExperience,
    TailoredResume,
    ValidationResult,
)


CANNED_ANALYSIS = CompatibilityAnalysis(
    keyword_overlap=KeywordOverlap(matched=["python"], missing=[], match_pct=100.0),
    compatibility_score=CompatibilityScore(
        overall_fit_score=8, strengths=["python"], gaps=[], recommendations=[],
    ),
)
CANNED_HASH = "abc123"
CANNED_USAGE = {"cost_cents": 0.10, "model": "claude-sonnet-4-6"}


@pytest.fixture
def client(tmp_path):
    from backend.db import get_connection, get_db, run_migrations
    from backend.main import app

    db_path = tmp_path / "test.db"
    run_migrations(db_path)

    conn = get_connection(db_path)
    conn.execute("UPDATE profile SET full_name=?, summary=? WHERE id=1", ("Jane", "x"))
    conn.commit()
    conn.close()

    def override_get_db():
        c = get_connection(db_path)
        try:
            yield c
        finally:
            c.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app, follow_redirects=False), db_path
    app.dependency_overrides.clear()


def _seed_app_with_versions(client_fixture, n_versions: int = 3) -> tuple[str, list[int]]:
    """Returns (app_id, [tailored_id, ...]) in chronological order."""
    tc, db_path = client_fixture
    from backend.db import get_connection
    from backend.services import tailored_repo

    with patch(
        "backend.routes.applications.run_analysis",
        return_value=(CANNED_ANALYSIS, CANNED_HASH, CANNED_USAGE),
    ):
        resp = tc.post(
            "/applications",
            data={"job_title": "Eng", "company": "Co", "jd_text": "JD"},
        )
    app_id = resp.headers["location"].split("/")[-1].split("?")[0]

    conn = get_connection(db_path)
    tids = []
    for i in range(n_versions):
        tailored = TailoredResume(
            summary=f"Summary v{i + 1}",
            experience=[
                TailoredExperience(
                    company="Acme", title="SWE",
                    bullets=[TailoredBullet(text=f"bullet v{i + 1}")],
                )
            ],
            skills=[f"skill-v{i + 1}"],
            selected_projects=[],
        )
        source = "generated" if i == 0 else "chat-edit"
        parent = None if i == 0 else i  # Phase 4 lineage: chat-edit's parent_version
        tid = tailored_repo.create_tailored(
            conn,
            application_id=app_id,
            content=tailored,
            validation=ValidationResult(),
            profile_hash=CANNED_HASH,
            model="claude-sonnet-4-6",
            cost_cents=0.5,
            source=source,
            parent_version=parent,
        )
        tids.append(tid)
    conn.close()
    return app_id, tids


class TestVersionsListPage:
    def test_renders_all_versions_newest_first(self, client):
        tc, _ = client
        app_id, tids = _seed_app_with_versions(client, n_versions=3)
        resp = tc.get(f"/applications/{app_id}/tailored/versions")
        assert resp.status_code == 200
        # All three versions referenced
        for v in (1, 2, 3):
            assert f"v{v}" in resp.text
        # Newest first: v3 appears before v1 in HTML
        assert resp.text.index("v3") < resp.text.index("v1")

    def test_latest_marked_with_tag(self, client):
        tc, _ = client
        app_id, _ = _seed_app_with_versions(client, n_versions=2)
        resp = tc.get(f"/applications/{app_id}/tailored/versions")
        assert "Latest" in resp.text

    def test_source_labels_rendered(self, client):
        tc, _ = client
        app_id, _ = _seed_app_with_versions(client, n_versions=2)
        resp = tc.get(f"/applications/{app_id}/tailored/versions")
        assert "Generated" in resp.text
        assert "Chat edit" in resp.text

    def test_unknown_app_404(self, client):
        tc, _ = client
        resp = tc.get("/applications/doesnotexist/tailored/versions")
        assert resp.status_code == 404

    def test_empty_state_when_no_versions(self, client):
        tc, _ = client
        with patch(
            "backend.routes.applications.run_analysis",
            return_value=(CANNED_ANALYSIS, CANNED_HASH, CANNED_USAGE),
        ):
            resp = tc.post(
                "/applications",
                data={"job_title": "Eng", "company": "Co", "jd_text": "JD"},
            )
        app_id = resp.headers["location"].split("/")[-1].split("?")[0]
        resp = tc.get(f"/applications/{app_id}/tailored/versions")
        assert resp.status_code == 200
        assert "No tailored resume versions yet" in resp.text


class TestViewSpecificVersion:
    def test_view_old_version_renders_old_content(self, client):
        tc, _ = client
        app_id, tids = _seed_app_with_versions(client, n_versions=3)
        # tids[0] is v1 (oldest)
        resp = tc.get(f"/applications/{app_id}/tailored/{tids[0]}")
        assert resp.status_code == 200
        assert "Summary v1" in resp.text
        # Should NOT show v3 content
        assert "Summary v3" not in resp.text

    def test_view_old_shows_banner(self, client):
        tc, _ = client
        app_id, tids = _seed_app_with_versions(client, n_versions=3)
        resp = tc.get(f"/applications/{app_id}/tailored/{tids[0]}")
        assert "newer version exists" in resp.text

    def test_view_latest_version_no_banner(self, client):
        tc, _ = client
        app_id, tids = _seed_app_with_versions(client, n_versions=3)
        resp = tc.get(f"/applications/{app_id}/tailored/{tids[-1]}")
        assert resp.status_code == 200
        assert "newer version exists" not in resp.text

    def test_unknown_tailored_id_404(self, client):
        tc, _ = client
        app_id, _ = _seed_app_with_versions(client)
        resp = tc.get(f"/applications/{app_id}/tailored/99999")
        assert resp.status_code == 404

    def test_tailored_belonging_to_other_app_404(self, client):
        tc, db_path = client
        app1_id, tids1 = _seed_app_with_versions(client)
        app2_id, _ = _seed_app_with_versions(client)
        # app2 trying to view app1's tailored row
        resp = tc.get(f"/applications/{app2_id}/tailored/{tids1[0]}")
        assert resp.status_code == 404


class TestRevert:
    def test_revert_creates_new_latest(self, client):
        tc, db_path = client
        app_id, tids = _seed_app_with_versions(client, n_versions=3)

        resp = tc.post(f"/applications/{app_id}/tailored/{tids[0]}/revert")
        assert resp.status_code == 303
        assert resp.headers["location"] == f"/applications/{app_id}/tailored"

        from backend.db import get_connection
        from backend.services import tailored_repo
        conn = get_connection(db_path)
        rows = tailored_repo.list_for_application(conn, app_id)
        latest = tailored_repo.get_latest_for_application(conn, app_id)
        conn.close()

        assert len(rows) == 4  # 3 + 1 reverted
        assert latest.source == "reverted"
        assert latest.parent_version == 1  # tids[0] is v1
        assert latest.content.summary == "Summary v1"

    def test_revert_redirects_to_tailored_page(self, client):
        tc, _ = client
        app_id, tids = _seed_app_with_versions(client)
        resp = tc.post(f"/applications/{app_id}/tailored/{tids[0]}/revert")
        assert resp.headers["location"] == f"/applications/{app_id}/tailored"

    def test_revert_unknown_app_redirects_to_list(self, client):
        tc, _ = client
        resp = tc.post("/applications/doesnotexist/tailored/1/revert")
        assert resp.status_code == 303
        assert resp.headers["location"] == "/applications"

    def test_revert_unknown_tailored_redirects_to_versions(self, client):
        tc, _ = client
        app_id, _ = _seed_app_with_versions(client)
        resp = tc.post(f"/applications/{app_id}/tailored/99999/revert")
        assert resp.status_code == 303
        assert resp.headers["location"] == f"/applications/{app_id}/tailored/versions"

    def test_revert_then_view_shows_old_content(self, client):
        tc, _ = client
        app_id, tids = _seed_app_with_versions(client, n_versions=3)
        tc.post(f"/applications/{app_id}/tailored/{tids[0]}/revert")
        resp = tc.get(f"/applications/{app_id}/tailored")
        assert resp.status_code == 200
        assert "Summary v1" in resp.text


class TestVersionsLink:
    def test_tailored_page_shows_versions_link_with_count(self, client):
        tc, _ = client
        app_id, _ = _seed_app_with_versions(client, n_versions=3)
        resp = tc.get(f"/applications/{app_id}/tailored")
        assert "Versions" in resp.text
        assert "(3)" in resp.text
        assert f"/applications/{app_id}/tailored/versions" in resp.text
