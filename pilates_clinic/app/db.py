"""
Camada de acesso ao banco. Dois modos, controlados por DB_MODE:

- DB_MODE=local  -> SQLite puro (arquivo local, zero dependência externa).
                    Uso: rodar no localhost sem conta Turso.
- DB_MODE=cloud  -> Turso (libSQL), via libsql-client. Uso: produção/Vercel.

Ambos expõem a mesma interface (execute, execute_tx, one, all_rows, new_id),
então app/scheduling/rules.py, app/auth/routes.py etc. não sabem nem
precisam saber qual dos dois está rodando por baixo.
"""
import sqlite3
import uuid
from flask import current_app, g


# ---------------------------------------------------------------------
# Modo LOCAL (sqlite3 builtin, sem instalar nada além do Python padrão)
# ---------------------------------------------------------------------
class _LocalResultSet:
    def __init__(self, cursor):
        self.columns = [d[0] for d in cursor.description] if cursor.description else []
        self.rows = cursor.fetchall()


class _LocalSqliteClient:
    def __init__(self, path):
        self.conn = sqlite3.connect(path)
        self.conn.execute("PRAGMA foreign_keys = ON")

    def execute(self, sql, args=()):
        cur = self.conn.cursor()
        cur.execute(sql, list(args))
        self.conn.commit()
        return _LocalResultSet(cur)

    def batch(self, statements):
        """statements: lista de tuplas (sql, args)."""
        cur = self.conn.cursor()
        results = []
        try:
            for sql, args in statements:
                cur.execute(sql, list(args))
                results.append(_LocalResultSet(cur))
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return results

    def close(self):
        self.conn.close()


# ---------------------------------------------------------------------
# Modo CLOUD (Turso / libSQL) — importado só quando necessário, para o
# modo local não depender do pacote libsql-client instalado.
# ---------------------------------------------------------------------
def _create_cloud_client():
    import libsql_client
    return libsql_client.create_client_sync(
        url=current_app.config["TURSO_DATABASE_URL"],
        auth_token=current_app.config["TURSO_AUTH_TOKEN"],
    )


def get_db():
    if "db_client" not in g:
        if current_app.config["DB_MODE"] == "local":
            g.db_client = _LocalSqliteClient(current_app.config["LOCAL_DB_PATH"])
        else:
            g.db_client = _create_cloud_client()
    return g.db_client


def close_db(e=None):
    client = g.pop("db_client", None)
    if client is not None:
        client.close()


def init_app(app):
    app.teardown_appcontext(close_db)


def new_id() -> str:
    return str(uuid.uuid4())


def execute(sql: str, args=()):
    """Executa um único statement e retorna o ResultSet."""
    db = get_db()
    return db.execute(sql, args)


def execute_tx(statements: list):
    """
    Executa múltiplos statements em uma única transação (batch).
    `statements` é uma lista de tuplas (sql, args) nos dois modos —
    a conversão para o formato específico do libsql-client (modo cloud)
    acontece aqui dentro, não em quem chama.
    """
    db = get_db()
    if current_app.config["DB_MODE"] == "local":
        return db.batch(statements)

    import libsql_client
    return db.batch([libsql_client.Statement(sql, args) for sql, args in statements])


def one(sql: str, args=()):
    rs = execute(sql, args)
    if not rs.rows:
        return None
    return dict(zip(rs.columns, rs.rows[0]))


def all_rows(sql: str, args=()):
    rs = execute(sql, args)
    return [dict(zip(rs.columns, row)) for row in rs.rows]
