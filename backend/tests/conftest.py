import os
import shutil
import sys
from pathlib import Path

os.environ["WL_DISABLE_CLAUDE"] = "1"       # tests are deterministic and offline
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

import config  # noqa: E402
import db  # noqa: E402


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


@pytest.fixture()
def db_copy(built_db, tmp_path):
    p = tmp_path / "copy.db"
    shutil.copy(built_db, p)
    c = db.connect(p)
    yield c
    c.close()
