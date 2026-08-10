import secrets
from datetime import datetime

from flask import Blueprint, request, jsonify, current_app

from app.db import execute, one, all_rows, new_id
from app import notifications
from app.authz import requer_admin

from app.records.prontuario_routes import montar_registro_completo

bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@bp.route("/clientes", methods=["GET"])
@requer_admin
def listar_clientes():
    """Para o admin buscar um paciente e abrir o prontuário dele."""
    termo = request.args.get("busca", "").strip()
    if termo:
        return jsonify(all_rows(
            "SELECT id, nome, cpf, email FROM usuarios "
            "WHERE papel = 'cliente' AND (nome LIKE ? OR cpf LIKE ? OR email LIKE ?) "
            "ORDER BY nome LIMIT 30",
            (f"%{termo}%", f"%{termo}%", f"%{termo}%"),
        ))
    return jsonify(all_rows(
        "SELECT id, nome, cpf, email FROM usuarios WHERE papel = 'cliente' ORDER BY nome LIMIT 50"
    ))


@bp.route("/clientes/<usuario_id>/prontuario", methods=["GET"])
@requer_admin
def prontuario_paciente(usuario_id):
    cliente = one("SELECT id, nome, cpf, email, whatsapp FROM usuarios WHERE id = ?", (usuario_id,))
    if not cliente:
        return jsonify({"erro": "Cliente não encontrado."}), 404
    registro = montar_registro_completo(usuario_id)
    registro["cliente"] = cliente
    return jsonify(registro)


@bp.route("/agendamentos/<agendamento_id>/cancelar", methods=["POST"])
@requer_admin
def cancelar_agendamento_admin(agendamento_id):
    """Admin pode cancelar o agendamento de qualquer cliente (diferente da
    rota do cliente, que só cancela o próprio)."""
    row = one("SELECT id FROM agendamentos WHERE id = ?", (agendamento_id,))
    if not row:
        return jsonify({"erro": "Agendamento não encontrado."}), 404
    execute("UPDATE agendamentos SET status = 'cancelado' WHERE id = ?", (agendamento_id,))
    return jsonify({"mensagem": "Agendamento cancelado."})

@bp.route("/clientes", methods=["POST"])
@requer_admin
def cadastrar_cliente_manual():
    """
    Admin cadastra cliente sem definir senha. O sistema gera um token de
    primeiro acesso e envia por e-mail — a senha do admin nunca é exposta
    nem reaproveitada.
    """
    dados = request.get_json(force=True)
    obrigatorios = ["nome", "cpf", "email", "whatsapp"]
    faltando = [c for c in obrigatorios if not dados.get(c)]
    if faltando:
        return jsonify({"erro": f"Campos obrigatórios ausentes: {faltando}"}), 400

    if one("SELECT id FROM usuarios WHERE cpf = ?", (dados["cpf"],)):
        return jsonify({"erro": "CPF já cadastrado."}), 409

    usuario_id = new_id()
    token_primeiro_acesso = secrets.token_urlsafe(32)

    execute(
        """
        INSERT INTO usuarios (
            id, nome, cpf, email, senha_hash, whatsapp, papel, ativo,
            token_reset_senha, consentimento_lgpd_aceito
        ) VALUES (?, ?, ?, ?, NULL, ?, 'cliente', 0, ?, 0)
        """,
        (usuario_id, dados["nome"], dados["cpf"], dados["email"], dados["whatsapp"],
         token_primeiro_acesso),
    )
    # Consentimento LGPD só pode ser dado pelo próprio cliente em
    # /api/auth/primeiro-acesso — nunca marcado aqui pelo admin.
    notifications.enviar_primeiro_acesso(dados["email"], dados["nome"], token_primeiro_acesso)

    return jsonify({"mensagem": "Cliente cadastrado. E-mail de primeiro acesso enviado.",
                     "usuario_id": usuario_id}), 201


@bp.route("/agendamentos", methods=["GET"])
@requer_admin
def listar_agendamentos():
    data = request.args.get("data")
    query = """
        SELECT a.*, u.nome as cliente_nome, p.nome as profissional_nome, s.nome as sala_nome
        FROM agendamentos a
        JOIN usuarios u ON u.id = a.usuario_id
        JOIN profissionais p ON p.id = a.profissional_id
        JOIN salas s ON s.id = a.sala_id
        WHERE (? IS NULL OR a.data = ?)
        ORDER BY a.data, a.hora_inicio
    """
    return jsonify(all_rows(query, (data, data)))


@bp.route("/configuracoes", methods=["GET"])
@requer_admin
def obter_configuracoes():
    cfg = one("SELECT * FROM configuracoes WHERE id = 'default'")
    if not cfg:
        return jsonify({"erro": "Configurações não encontradas."}), 404
    return jsonify(cfg)


@bp.route("/configuracoes", methods=["PUT"])
@requer_admin
def atualizar_configuracoes():
    dados = request.get_json(force=True)
    campos = ["capacidade_max_dia", "hora_abertura", "hora_fechamento",
              "dias_funcionamento", "duracao_padrao_min"]
    sets, valores = [], []
    for c in campos:
        if c in dados:
            sets.append(f"{c} = ?")
            valores.append(dados[c])
    if not sets:
        return jsonify({"erro": "Nada para atualizar."}), 400

    execute(f"UPDATE configuracoes SET {', '.join(sets)} WHERE id = 'default'", valores)
    return jsonify({"mensagem": "Configurações atualizadas."})


@bp.route("/salas", methods=["GET"])
@requer_admin
def listar_salas():
    return jsonify(all_rows("SELECT * FROM salas ORDER BY nome"))


@bp.route("/salas", methods=["POST"])
@requer_admin
def criar_sala():
    dados = request.get_json(force=True)
    if not dados.get("nome"):
        return jsonify({"erro": "nome é obrigatório."}), 400
    sala_id = new_id()
    execute("INSERT INTO salas (id, nome, ativa) VALUES (?, ?, 1)", (sala_id, dados["nome"]))
    return jsonify({"mensagem": "Sala criada.", "id": sala_id}), 201


@bp.route("/salas/<sala_id>", methods=["PUT"])
@requer_admin
def atualizar_sala(sala_id):
    dados = request.get_json(force=True)
    sets, valores = [], []
    if "nome" in dados:
        sets.append("nome = ?"); valores.append(dados["nome"])
    if "ativa" in dados:
        sets.append("ativa = ?"); valores.append(bool(dados["ativa"]))
    if not sets:
        return jsonify({"erro": "Nada para atualizar."}), 400
    valores.append(sala_id)
    execute(f"UPDATE salas SET {', '.join(sets)} WHERE id = ?", valores)
    return jsonify({"mensagem": "Sala atualizada."})


@bp.route("/profissionais", methods=["GET"])
@requer_admin
def listar_profissionais():
    return jsonify(all_rows("SELECT * FROM profissionais ORDER BY nome"))


@bp.route("/profissionais", methods=["POST"])
@requer_admin
def criar_profissional():
    """Quantidade de profissionais é gerenciável — cada um com sua própria
    duração de atendimento, negociável conforme a necessidade do paciente."""
    dados = request.get_json(force=True)
    if not dados.get("nome"):
        return jsonify({"erro": "nome é obrigatório."}), 400
    prof_id = new_id()
    execute(
        "INSERT INTO profissionais (id, nome, duracao_padrao_min, ativo) VALUES (?, ?, ?, 1)",
        (prof_id, dados["nome"], dados.get("duracao_padrao_min", 60)),
    )
    return jsonify({"mensagem": "Profissional cadastrado.", "id": prof_id}), 201


@bp.route("/profissionais/<prof_id>", methods=["PUT"])
@requer_admin
def atualizar_profissional(prof_id):
    dados = request.get_json(force=True)
    sets, valores = [], []
    if "nome" in dados:
        sets.append("nome = ?"); valores.append(dados["nome"])
    if "duracao_padrao_min" in dados:
        sets.append("duracao_padrao_min = ?"); valores.append(dados["duracao_padrao_min"])
    if "ativo" in dados:
        sets.append("ativo = ?"); valores.append(bool(dados["ativo"]))
    if not sets:
        return jsonify({"erro": "Nada para atualizar."}), 400
    valores.append(prof_id)
    execute(f"UPDATE profissionais SET {', '.join(sets)} WHERE id = ?", valores)
    return jsonify({"mensagem": "Profissional atualizado."})


@bp.route("/bloqueios-dia", methods=["GET"])
@requer_admin
def listar_bloqueios_dia():
    return jsonify(all_rows("SELECT * FROM bloqueios_dia ORDER BY data"))


@bp.route("/bloqueios-dia/<bloqueio_id>", methods=["DELETE"])
@requer_admin
def remover_bloqueio_dia(bloqueio_id):
    execute("DELETE FROM bloqueios_dia WHERE id = ?", (bloqueio_id,))
    return jsonify({"mensagem": "Bloqueio removido."})


@bp.route("/janelas-indisponiveis", methods=["GET"])
@requer_admin
def listar_janelas_indisponiveis():
    return jsonify(all_rows("SELECT * FROM janelas_indisponiveis ORDER BY hora_inicio"))


@bp.route("/janelas-indisponiveis/<janela_id>", methods=["DELETE"])
@requer_admin
def remover_janela_indisponivel(janela_id):
    execute("DELETE FROM janelas_indisponiveis WHERE id = ?", (janela_id,))
    return jsonify({"mensagem": "Janela indisponível removida."})


@bp.route("/bloqueios-dia", methods=["POST"])
@requer_admin
def criar_bloqueio_dia():
    """Feriado nacional/regional, jogo da Copa, ou força maior (enchente, decreto)."""
    dados = request.get_json(force=True)
    obrigatorios = ["data", "motivo", "tipo"]
    faltando = [c for c in obrigatorios if not dados.get(c)]
    if faltando:
        return jsonify({"erro": f"Campos obrigatórios ausentes: {faltando}"}), 400

    execute(
        "INSERT INTO bloqueios_dia (id, data, motivo, tipo) VALUES (?, ?, ?, ?)",
        (new_id(), dados["data"], dados["motivo"], dados["tipo"]),
    )
    return jsonify({"mensagem": "Bloqueio registrado."}), 201


@bp.route("/janelas-indisponiveis", methods=["POST"])
@requer_admin
def criar_janela_indisponivel():
    """Ex: almoço das 12h às 13h, recorrente (dia_semana) ou pontual (data_especifica)."""
    dados = request.get_json(force=True)
    if not dados.get("dia_semana") and not dados.get("data_especifica"):
        return jsonify({"erro": "Informe dia_semana (recorrente) ou data_especifica (pontual)."}), 400

    execute(
        """
        INSERT INTO janelas_indisponiveis (id, dia_semana, data_especifica, hora_inicio, hora_fim, motivo)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (new_id(), dados.get("dia_semana"), dados.get("data_especifica"),
         dados["hora_inicio"], dados["hora_fim"], dados.get("motivo")),
    )
    return jsonify({"mensagem": "Janela indisponível registrada."}), 201
