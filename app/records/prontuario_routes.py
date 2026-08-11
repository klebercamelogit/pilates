from flask import Blueprint, request, jsonify

from app.db import execute, one, all_rows, new_id
from app.authz import requer_login, exige_dono_ou_admin

bp = Blueprint("prontuario", __name__, url_prefix="/api/prontuarios")


@bp.route("", methods=["POST"])
@requer_login
def criar_ou_atualizar():
    """
    Upsert simples: se o cliente já tem um prontuário, atualiza; senão cria.
    Chamado pelo próprio cliente ao informar comorbidades.
    """
    dados = request.get_json(force=True)
    usuario_id = dados.get("usuario_id")
    if not usuario_id:
        return jsonify({"erro": "usuario_id é obrigatório."}), 400
    if not exige_dono_ou_admin(request.usuario_atual, usuario_id):
        return jsonify({"erro": "Você só pode editar o próprio prontuário."}), 403

    existente = one(
        "SELECT id FROM prontuarios WHERE usuario_id = ? ORDER BY criado_em DESC LIMIT 1",
        (usuario_id,),
    )

    if existente:
        execute(
            """
            UPDATE prontuarios
            SET possui_comorbidade = ?, descricao_comorbidade = ?,
                atualizado_em = datetime('now')
            WHERE id = ?
            """,
            (bool(dados.get("possui_comorbidade")), dados.get("descricao_comorbidade"),
             existente["id"]),
        )
        return jsonify({"mensagem": "Prontuário atualizado.", "prontuario_id": existente["id"]})

    prontuario_id = new_id()
    execute(
        """
        INSERT INTO prontuarios (id, usuario_id, possui_comorbidade, descricao_comorbidade)
        VALUES (?, ?, ?, ?)
        """,
        (prontuario_id, usuario_id, bool(dados.get("possui_comorbidade")),
         dados.get("descricao_comorbidade")),
    )
    return jsonify({"mensagem": "Prontuário criado.", "prontuario_id": prontuario_id}), 201


def montar_registro_completo(usuario_id: str):
    """Reaproveitado pelo cliente (visão própria) e pelo admin (visão de qualquer paciente)."""
    prontuario = one(
        "SELECT * FROM prontuarios WHERE usuario_id = ? ORDER BY criado_em DESC LIMIT 1",
        (usuario_id,),
    )
    exames = []
    if prontuario:
        exames = all_rows(
            "SELECT id, nome_original, content_type, tamanho_bytes, enviado_em "
            "FROM exames_arquivos WHERE prontuario_id = ? ORDER BY enviado_em DESC",
            (prontuario["id"],),
        )

    historico = all_rows(
        """
        SELECT a.id, a.data, a.hora_inicio, a.status, a.anotacoes_profissional,
               p.nome as profissional_nome, s.nome as sala_nome
        FROM agendamentos a
        JOIN profissionais p ON p.id = a.profissional_id
        JOIN salas s ON s.id = a.sala_id
        WHERE a.usuario_id = ?
        ORDER BY a.data DESC, a.hora_inicio DESC
        """,
        (usuario_id,),
    )

    return {"prontuario": prontuario, "exames": exames, "historico": historico}


@bp.route("/<usuario_id>", methods=["GET"])
@requer_login
def obter(usuario_id):
    """Visão do próprio cliente (ou admin). Agora exige token e verifica
    propriedade — antes era acessível por qualquer um que soubesse o UUID."""
    if not exige_dono_ou_admin(request.usuario_atual, usuario_id):
        return jsonify({"erro": "Acesso negado."}), 403
    return jsonify(montar_registro_completo(usuario_id))
