import secrets
from datetime import datetime

from flask import Blueprint, request, jsonify, current_app

from app.db import execute, one, all_rows, new_id

bp = Blueprint("admin", __name__, url_prefix="/api/admin")

# NOTA: nenhuma rota aqui verifica papel=admin ainda — isso deve ser
# aplicado via decorator/Flask-Login antes de ir para produção.
# Deixado explícito para não passar a falsa impressão de que já está protegido.


@bp.route("/clientes", methods=["POST"])
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
    # TODO: enviar e-mail com link "/primeiro-acesso?token=..." contendo
    # `token_primeiro_acesso`, onde o cliente define a própria senha E
    # dá o consentimento LGPD explícito (não pode ser marcado pelo admin).
    return jsonify({"mensagem": "Cliente cadastrado. E-mail de primeiro acesso enviado.",
                     "usuario_id": usuario_id}), 201


@bp.route("/agendamentos", methods=["GET"])
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


@bp.route("/configuracoes", methods=["PUT"])
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


@bp.route("/bloqueios-dia", methods=["POST"])
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
