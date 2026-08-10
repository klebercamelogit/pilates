"""
Cria (ou recria) o banco SQLite local a partir de schema.sql + seed.sql.
Uso: python scripts/init_local_db.py
"""
import os
import sqlite3

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.environ.get("LOCAL_DB_PATH", os.path.join(RAIZ, "local.db"))
SCHEMA_PATH = os.path.join(RAIZ, "schema", "schema.sql")
SEED_PATH = os.path.join(RAIZ, "schema", "seed.sql")


def main():
    recriar = os.path.exists(DB_PATH)
    if recriar:
        print(f"Banco local já existe em {DB_PATH} — aplicando schema/seed (idempotente).")
    conn = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        conn.executescript(f.read())
    with open(SEED_PATH, encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    print(f"Banco local pronto em: {DB_PATH}")


if __name__ == "__main__":
    main()
