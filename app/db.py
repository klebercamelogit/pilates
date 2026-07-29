"""
Camada de acesso ao Turso (libSQL).

Por que não SQLAlchemy: o dialeto SQLAlchemy para libsql/Turso é limitado e
pouco mantido. Para um projeto que já usa SQL explícito no schema.sql (com
UNIQUE constraints fazendo o trabalho pesado de evitar overbooking), um
wrapper fino sobre libsql-client é mais previsível e mais fácil de debugar
em ambiente serverless (Vercel) do que um ORM completo.
"""
import uuid
import libsql_client
from flask import current_app, g


def get_db():
    if "db_client" not in g:
        g.db_client = libsql_client.create_client_sync(
            url=current_app.config["TURSO_DATABASE_URL"],
            auth_token=current_app.config["TURSO_AUTH_TOKEN"],
        )
    return g.db_client


def close_db(e=None):
    client = g.pop("db_client", None)
    if client is not None:
        client.close()


def init_app(app):
    app.teardown_appcontext(close_db)


def new_id() -> str:
    return str(uuid.uuid4())


def execute(sql: str, args: tuple | list = ()):
    """Executa um único statement e retorna o ResultSet."""
    db = get_db()
    return db.execute(sql, args)


def execute_tx(statements: list[tuple[str, tuple | list]]):
    """
    Executa múltiplos statements em uma única transação (batch).
    Usado onde a ordem/atomicidade importa, por exemplo:
    checar disponibilidade + inserir agendamento.
    """
    db = get_db()
    return db.batch([libsql_client.Statement(sql, args) for sql, args in statements])


def one(sql: str, args: tuple | list = ()):
    rs = execute(sql, args)
    if not rs.rows:
        return None
    return dict(zip(rs.columns, rs.rows[0]))


def all_rows(sql: str, args: tuple | list = ()):
    rs = execute(sql, args)
    return [dict(zip(rs.columns, row)) for row in rs.rows]
