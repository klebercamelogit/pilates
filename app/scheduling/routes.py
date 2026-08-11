from flask import Blueprint, request, jsonify

from app.scheduling.rules import (
    criar_agendamento, cancelar_agendamento, listar_dias_disponiveis, IndisponivelError,
    carregar_configuracoes,
)
from app.db import all_rows, one
from app.authz import requer_login, exige_dono_ou_admin

bp = Blueprint("scheduling", __name__, url_prefix="/api/agendamentos")


@bp.route("/opcoes", methods=["GET"])
def opcoes():
    """Salas, profissionais e configurações — o frontend usa isso para montar
    o seletor de horários (a API não expõe ocupação por horário individual;
    conflitos de horário são resolvidos no momento da criação, via a UNIQUE
    constraint do banco — ver app/scheduling/rules.py). Não é dado sensível,
    fica público (necessário antes mesmo do login, na tela de cadastro)."""
    cfg = carregar_configuracoes()
    return jsonify({
        "salas": all_rows("SELECT id, nome FROM salas WHERE ativa = 1"),
        "profissionais": all_rows(
            "SELECT id, nome, duracao_padrao_min, crefito FROM profissionais WHERE ativo = 1"
        ),
        "hora_abertura": cfg["hora_abertura"],
        "hora_fechamento": cfg["hora_fechamento"],
        "duracao_padrao_min": cfg["duracao_padrao_min"],
    })


@bp.route("/minhas/<usuario_id>", methods=["GET"])
@requer_login
def minhas(usuario_id):
    """Histórico/agendamentos do cliente logado. Exige token; só o próprio
    dono do usuario_id (ou um admin) pode consultar."""
    if not exige_dono_ou_admin(request.usuario_atual, usuario_id):
        return jsonify({"erro": "Acesso negado."}), 403

    query = """
        SELECT a.*, p.nome as profissional_nome, s.nome as sala_nome
        FROM agendamentos a
        JOIN profissionais p ON p.id = a.profissional_id
        JOIN salas s ON s.id = a.sala_id
        WHERE a.usuario_id = ?
        ORDER BY a.data DESC, a.hora_inicio DESC
    """
    return jsonify(all_rows(query, (usuario_id,)))


@bp.route("/calendario/<int:ano>/<int:mes>", methods=["GET"])
def calendario(ano, mes):
    """Disponibilidade não é dado sensível — fica pública (necessário antes
    do login, para o cliente ver a agenda antes de decidir se cadastra).
    Aceita ?profissional_id= opcional para refletir bloqueios específicos
    daquele profissional; sem isso, mostra só bloqueios globais."""
    profissional_id = request.args.get("profissional_id")
    return jsonify(listar_dias_disponiveis(ano, mes, profissional_id))


@bp.route("", methods=["POST"])
@requer_login
def criar():
    dados = request.get_json(force=True)
    obrigatorios = ["usuario_id", "profissional_id", "sala_id", "data", "hora_inicio", "hora_fim"]
    faltando = [c for c in obrigatorios if not dados.get(c)]
    if faltando:
        return jsonify({"erro": f"Campos obrigatórios ausentes: {faltando}"}), 400

    if not exige_dono_ou_admin(request.usuario_atual, dados["usuario_id"]):
        return jsonify({"erro": "Você só pode agendar para a própria conta."}), 403

    try:
        agendamento_id = criar_agendamento(
            dados["usuario_id"], dados["profissional_id"], dados["sala_id"],
            dados["data"], dados["hora_inicio"], dados["hora_fim"],
        )
    except IndisponivelError as e:
        return jsonify({"erro": str(e)}), 409

    return jsonify({"mensagem": "Agendamento confirmado.", "agendamento_id": agendamento_id}), 201


@bp.route("/<agendamento_id>/cancelar", methods=["POST"])
@requer_login
def cancelar(agendamento_id):
    dados = request.get_json(force=True)
    usuario_id = dados.get("usuario_id")
    if not usuario_id:
        return jsonify({"erro": "usuario_id obrigatório."}), 400
    if not exige_dono_ou_admin(request.usuario_atual, usuario_id):
        return jsonify({"erro": "Você só pode cancelar os próprios agendamentos."}), 403
    try:
        cancelar_agendamento(agendamento_id, usuario_id)
    except ValueError as e:
        return jsonify({"erro": str(e)}), 404
    return jsonify({"mensagem": "Agendamento cancelado."})
