"""
Autenticação via token de sessão (não é JWT, não é cookie de sessão do
Flask — é um token opaco gerado no login, guardado na tabela `sessoes`,
enviado pelo frontend no header `Authorization: Bearer <token>`).

Isso é propositalmente simples (não Flask-Login, não JWT assinado) porque
resolve o problema real que tínhamos — rotas admin sem nenhuma checagem,
confiando cegamente no que o navegador dizia — sem introduzir dependência
nova. Se o projeto crescer, migrar para JWT ou Flask-Login é natural a
partir daqui, mas o modelo de dados (tabela `sessoes`) já suporta isso.
"""
from datetime import datetime
from functools import wraps

from flask import request, jsonify

from app.db import one


def usuario_da_requisicao():
    """Retorna {usuario_id, papel, email} se o token for válido e não
    expirado, ou None caso contrário. Aceita o token via header
    `Authorization: Bearer <token>` (padrão, usado pelo fetch() do
    frontend) ou via query string `?token=` (fallback para links <a href>
    diretos, como o download de exame, que não enviam headers custom)."""
    token = None
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[len("Bearer "):].strip()
    if not token:
        token = request.args.get("token", "").strip()
    if not token:
        return None

    row = one(
        """
        SELECT s.usuario_id, s.expira_em, u.papel, u.email
        FROM sessoes s JOIN usuarios u ON u.id = s.usuario_id
        WHERE s.token = ?
        """,
        (token,),
    )
    if not row:
        return None
    if datetime.fromisoformat(row["expira_em"]) < datetime.utcnow():
        return None
    return row


def requer_login(f):
    """Exige um token de sessão válido, de qualquer papel."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        usuario = usuario_da_requisicao()
        if not usuario:
            return jsonify({"erro": "Não autenticado. Faça login novamente."}), 401
        request.usuario_atual = usuario
        return f(*args, **kwargs)
    return wrapper


def requer_admin(f):
    """Exige um token de sessão válido pertencente a um usuário com papel='admin'."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        usuario = usuario_da_requisicao()
        if not usuario:
            return jsonify({"erro": "Não autenticado. Faça login novamente."}), 401
        if usuario["papel"] != "admin":
            return jsonify({"erro": "Acesso restrito a administradores."}), 403
        request.usuario_atual = usuario
        return f(*args, **kwargs)
    return wrapper


def exige_dono_ou_admin(usuario_atual: dict, usuario_id_alvo: str) -> bool:
    """True se usuario_atual pode acessar dados de usuario_id_alvo:
    é o próprio dono, ou é admin. Usado nas rotas que recebem um usuario_id
    (no path ou no corpo) para impedir que um cliente logado consulte ou
    manipule dados de outro cliente só por saber o UUID dele."""
    return usuario_atual["papel"] == "admin" or usuario_atual["usuario_id"] == usuario_id_alvo
