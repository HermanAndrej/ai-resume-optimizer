from backend.db import get_connection, run_migrations
from backend.paths import get_db_path, get_data_dir

get_data_dir().mkdir(parents=True, exist_ok=True)
run_migrations(get_db_path())

conn = get_connection(get_db_path())
tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
print("Tables:", tables)
print("Count:", len(tables))

row = dict(conn.execute("SELECT * FROM profile WHERE id=1").fetchone())
print("Seed profile row:", row)

conn.execute("INSERT OR IGNORE INTO schema_version (version) VALUES (1)")
run_migrations(get_db_path())
print("Double migration: OK")
