from flask import Blueprint, request, jsonify

from app.scheduling.rules import (
    criar_agendamento, cancelar_agendamento, listar_dias_disponiveis, IndisponivelError,
)

bp = Blueprint("scheduling", __name__, url_prefix="/api/agendamentos")


@bp.route("/calendario/<int:ano>/<int:mes>", methods=["GET"])
def calendario(ano, mes):
    return jsonify(listar_dias_disponiveis(ano, mes))


@bp.route("", methods=["POST"])
def criar():
    dados = request.get_json(force=True)
    obrigatorios = ["usuario_id", "profissional_id", "sala_id", "data", "hora_inicio", "hora_fim"]
    faltando = [c for c in obrigatorios if not dados.get(c)]
    if faltando:
        return jsonify({"erro": f"Campos obrigatórios ausentes: {faltando}"}), 400

    try:
        agendamento_id = criar_agendamento(
            dados["usuario_id"], dados["profissional_id"], dados["sala_id"],
            dados["data"], dados["hora_inicio"], dados["hora_fim"],
        )
    except IndisponivelError as e:
        return jsonify({"erro": str(e)}), 409

    return jsonify({"mensagem": "Agendamento confirmado.", "agendamento_id": agendamento_id}), 201


@bp.route("/<agendamento_id>/cancelar", methods=["POST"])
def cancelar(agendamento_id):
    dados = request.get_json(force=True)
    usuario_id = dados.get("usuario_id")
    if not usuario_id:
        return jsonify({"erro": "usuario_id obrigatório."}), 400
    try:
        cancelar_agendamento(agendamento_id, usuario_id)
    except ValueError as e:
        return jsonify({"erro": str(e)}), 404
    return jsonify({"mensagem": "Agendamento cancelado."})
