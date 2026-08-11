from flask import Blueprint, request, jsonify

from app.db import execute, one, new_id

bp = Blueprint("chatbot", __name__, url_prefix="/api/chatbot")


@bp.route("/verificar-email", methods=["POST"])
def verificar_email():
    """
    Pública, sem login — mas retorna só o nome (para o chatbot cumprimentar
    a pessoa), nunca outros dados. Isso não é uma rota de autenticação:
    não prova que quem está digitando é o dono do e-mail, só evita pedir
    de novo informações que já temos.
    """
    dados = request.get_json(force=True)
    email = dados.get("email")
    if not email:
        return jsonify({"erro": "email é obrigatório."}), 400

    usuario = one(
        "SELECT nome FROM usuarios WHERE email = ? AND papel = 'cliente' AND ativo = 1",
        (email,),
    )
    if usuario:
        return jsonify({"existe": True, "nome": usuario["nome"]})
    return jsonify({"existe": False, "nome": None})


@bp.route("/solicitacao", methods=["POST"])
def criar_solicitacao():
    """
    Registra a solicitação coletada pelo chatbot como um lead — não cria
    agendamento nem mexe no prontuário diretamente. Um admin revisa e dá
    sequência (confirma o agendamento manualmente ou entra em contato).
    Isso é proposital: sem exigir senha no meio da conversa do chatbot,
    não dá pra provar quem está do outro lado, então não é seguro deixar
    o chatbot gravar direto em dados de um cliente existente.
    """
    dados = request.get_json(force=True)
    obrigatorios = ["tipo_atendimento", "nome", "email"]
    faltando = [c for c in obrigatorios if not dados.get(c)]
    if faltando:
        return jsonify({"erro": f"Campos obrigatórios ausentes: {faltando}"}), 400

    ja_cadastrado = one(
        "SELECT id FROM usuarios WHERE email = ? AND papel = 'cliente'", (dados["email"],)
    ) is not None

    solicitacao_id = new_id()
    execute(
        """
        INSERT INTO chatbot_solicitacoes (
            id, tipo_atendimento, nome, email, telefone, comorbidade,
            sala_desejada, profissional_desejado, data_desejada, horario_desejado,
            mensagem, cliente_ja_cadastrado
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            solicitacao_id, dados["tipo_atendimento"], dados["nome"], dados["email"],
            dados.get("telefone"), dados.get("comorbidade"), dados.get("sala_desejada"),
            dados.get("profissional_desejado"), dados.get("data_desejada"),
            dados.get("horario_desejado"), dados.get("mensagem"), ja_cadastrado,
        ),
    )
    return jsonify({
        "mensagem": "Solicitação recebida! A clínica vai entrar em contato em breve.",
        "solicitacao_id": solicitacao_id,
    }), 201
