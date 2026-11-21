import os
import shutil
import sys
import tempfile
from pathlib import Path

os.environ["WL_DISABLE_CLAUDE"] = "1"       # tests are deterministic and offline
os.environ["WL_OVERDUE_CHECK_MIN"] = "0"    # no background deadline thread in tests (they call the check directly)
os.environ.pop("WL_SMTP_HOST", None)        # never send real mail from tests: messages are logged in email_outbox
os.environ["WL_INSTANCE_DIR"] = tempfile.mkdtemp(prefix="wl-test-instance-")   # uploads + signing secret, never the dev ones
os.environ["WL_SECRET"] = "test-only-signing-secret"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

import config  # noqa: E402
import db  # noqa: E402


TEST_PW = "test-pass-123"


def _have_data():
    return all((config.DATA_DIR / f"{n}.csv").exists() for n in config.SOURCE_FILES)


@pytest.fixture(scope="session")
def built_db(tmp_path_factory):
    """Run the full pipeline once into a temp database; every integration test shares it."""
    if not _have_data():
        pytest.skip("data/ missing: run scripts/fetch_data.sh")
    path = tmp_path_factory.mktemp("wl") / "test.db"
    old = config.DB_PATH
    config.DB_PATH = path
    from pipeline import run
    conn = db.connect(path)
    run.run(force=True, conn=conn, quiet=True)
    from live.seed import seed_accounts
    seed_accounts(conn, TEST_PW)
    conn.close()
    yield path
    config.DB_PATH = old


@pytest.fixture()
def conn(built_db):
    c = db.connect(built_db)
    yield c
    c.close()


@pytest.fixture(scope="session")
def client(built_db):
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


@pytest.fixture(scope="session")
def tokens(client):
    """Bearer headers for the seeded accounts, one login per account per test session."""
    def login(role, login_id):
        r = client.post(f"/api/auth/{role}/login", json={"login": login_id, "password": TEST_PW})
        assert r.status_code == 200, r.text
        return {"Authorization": "Bearer " + r.json()["token"]}
    return {"officer": login("officer", "ae-4471"), "officer_hw": login("officer", "ae-3310"), "ee": login("officer", "ee-1001"),
            "auditor": login("officer", "audit-01"), "ct05": login("contractor", "ct05"), "ct07": login("contractor", "ct07"),
            "citizen": login("citizen", "9800000001")}


@pytest.fixture()
def db_copy(built_db, tmp_path):
    p = tmp_path / "copy.db"
    shutil.copy(built_db, p)
    c = db.connect(p)
    yield c
    c.close()
