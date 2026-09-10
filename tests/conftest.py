"""Provide an isolated default database for tests on a fresh checkout.

Individual tests can still override DB_PATH with their own fixtures.
"""
import pytest


@pytest.fixture(scope="session", autouse=True)
def session_database(tmp_path_factory):
    import config
    import database

    path = tmp_path_factory.mktemp("default_db") / "test.db"
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(config, "DB_PATH", path)
        patch.setattr(database, "DB_PATH", path)
        database.init_db()
        database.run_migrations()
        yield path
