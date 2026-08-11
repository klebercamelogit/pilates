import secrets
from datetime import datetime

from flask import Blueprint, request, jsonify, current_app

from app.db import execute, one, all_rows, new_id
from app import notifications
from app.authz import requer_admin

from app.records.prontuario_routes import montar_registro_completo

bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@bp.route("/administradores", methods=["GET"])
@requer_admin
def listar_administradores():
    return jsonify(all_rows(
        "SELECT id, nome, email, whatsapp FROM usuarios WHERE papel = 'admin' ORDER BY nome"
    ))


@bp.route("/administradores", methods=["POST"])
@requer_admin
def criar_administrador():
    """
    Cria um novo administrador. Mesmo fluxo de segurança do cadastro manual
    de cliente: a senha nunca é definida aqui, o novo admin recebe um
    e-mail de primeiro acesso e define a própria senha.
    """
    dados = request.get_json(force=True)
    obrigatorios = ["nome", "email", "whatsapp"]
    faltando = [c for c in obrigatorios if not dados.get(c)]
    if faltando:
        return jsonify({"erro": f"Campos obrigatórios ausentes: {faltando}"}), 400

    if one("SELECT id FROM usuarios WHERE email = ?", (dados["email"],)):
        return jsonify({"erro": "E-mail já cadastrado."}), 409

    usuario_id = new_id()
    token_primeiro_acesso = secrets.token_urlsafe(32)
    cpf_interno = f"sem-cpf-{new_id()}"

    execute(
        """
        INSERT INTO usuarios (
            id, nome, cpf, email, senha_hash, whatsapp, papel, ativo,
            token_reset_senha, consentimento_lgpd_aceito
        ) VALUES (?, ?, ?, ?, NULL, ?, 'admin', 0, ?, 0)
        """,
        (usuario_id, dados["nome"], cpf_interno, dados["email"], dados["whatsapp"],
         token_primeiro_acesso),
    )
    notifications.enviar_primeiro_acesso(dados["email"], dados["nome"], token_primeiro_acesso)

    return jsonify({"mensagem": "Administrador cadastrado. E-mail de primeiro acesso enviado.",
                     "usuario_id": usuario_id}), 201


@bp.route("/administradores/<usuario_id>/revogar", methods=["POST"])
@requer_admin
def revogar_administrador(usuario_id):
    """Rebaixa um admin para cliente comum. Bloqueado contra auto-revogação
    para evitar que o sistema fique sem nenhum admin com acesso."""
    if usuario_id == request.usuario_atual["usuario_id"]:
        return jsonify({"erro": "Você não pode revogar o próprio acesso de administrador."}), 400

    alvo = one("SELECT id FROM usuarios WHERE id = ? AND papel = 'admin'", (usuario_id,))
    if not alvo:
        return jsonify({"erro": "Administrador não encontrado."}), 404

    execute("UPDATE usuarios SET papel = 'cliente' WHERE id = ?", (usuario_id,))
    return jsonify({"mensagem": "Acesso de administrador revogado."})


@bp.route("/prontuarios", methods=["GET"])
@requer_admin
def listar_prontuarios():
    """Lista só pacientes que já enviaram algo ao prontuário (comorbidade
    preenchida ou exame anexado) — não a lista geral de clientes."""
    nome = request.args.get("nome", "").strip()
    email = request.args.get("email", "").strip()

    condicoes = []
    parametros = []
    if nome:
        condicoes.append("u.nome LIKE ?")
        parametros.append(f"%{nome}%")
    if email:
        condicoes.append("u.email LIKE ?")
        parametros.append(f"%{email}%")
    where_extra = f"AND {' AND '.join(condicoes)}" if condicoes else ""

    query = f"""
        SELECT u.id as usuario_id, u.nome, u.email,
               p.id as prontuario_id, p.possui_comorbidade,
               (SELECT COUNT(*) FROM exames_arquivos e WHERE e.prontuario_id = p.id) as qtd_exames
        FROM prontuarios p
        JOIN usuarios u ON u.id = p.usuario_id
        WHERE 1=1 {where_extra}
        GROUP BY u.id
        ORDER BY u.nome
        LIMIT 100
    """
    return jsonify(all_rows(query, parametros))


@bp.route("/chatbot-solicitacoes", methods=["GET"])
@requer_admin
def listar_solicitacoes_chatbot():
    apenas_pendentes = request.args.get("pendentes") == "1"
    where = "WHERE atendido = 0" if apenas_pendentes else ""
    return jsonify(all_rows(f"SELECT * FROM chatbot_solicitacoes {where} ORDER BY criado_em DESC"))


@bp.route("/chatbot-solicitacoes/<solicitacao_id>/atender", methods=["POST"])
@requer_admin
def marcar_solicitacao_atendida(solicitacao_id):
    execute("UPDATE chatbot_solicitacoes SET atendido = 1 WHERE id = ?", (solicitacao_id,))
    return jsonify({"mensagem": "Solicitação marcada como atendida."})


@bp.route("/clientes", methods=["GET"])
@requer_admin
def listar_clientes():
    """Para o admin buscar um paciente e abrir o prontuário dele."""
    termo = request.args.get("busca", "").strip()
    if termo:
        return jsonify(all_rows(
            "SELECT id, nome, email FROM usuarios "
            "WHERE papel = 'cliente' AND (nome LIKE ? OR email LIKE ?) "
            "ORDER BY nome LIMIT 30",
            (f"%{termo}%", f"%{termo}%"),
        ))
    return jsonify(all_rows(
        "SELECT id, nome, email FROM usuarios WHERE papel = 'cliente' ORDER BY nome LIMIT 50"
    ))


@bp.route("/clientes/<usuario_id>/prontuario", methods=["GET"])
@requer_admin
def prontuario_paciente(usuario_id):
    cliente = one("SELECT id, nome, email, whatsapp FROM usuarios WHERE id = ?", (usuario_id,))
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
    obrigatorios = ["nome", "email", "whatsapp"]
    faltando = [c for c in obrigatorios if not dados.get(c)]
    if faltando:
        return jsonify({"erro": f"Campos obrigatórios ausentes: {faltando}"}), 400

    if one("SELECT id FROM usuarios WHERE email = ?", (dados["email"],)):
        return jsonify({"erro": "E-mail já cadastrado."}), 409

    usuario_id = new_id()
    token_primeiro_acesso = secrets.token_urlsafe(32)
    # Ver nota em app/auth/routes.py: `cpf` continua NOT NULL UNIQUE no
    # schema para não exigir migração em produção, mas não é mais coletado.
    cpf_interno = f"sem-cpf-{new_id()}"

    execute(
        """
        INSERT INTO usuarios (
            id, nome, cpf, email, senha_hash, whatsapp, papel, ativo,
            token_reset_senha, consentimento_lgpd_aceito
        ) VALUES (?, ?, ?, ?, NULL, ?, 'cliente', 0, ?, 0)
        """,
        (usuario_id, dados["nome"], cpf_interno, dados["email"], dados["whatsapp"],
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
        SELECT a.*, u.nome as cliente_nome, u.whatsapp as cliente_whatsapp,
               p.nome as profissional_nome, s.nome as sala_nome,
               EXISTS(
                   SELECT 1 FROM exames_arquivos e
                   JOIN prontuarios pr ON pr.id = e.prontuario_id
                   WHERE pr.usuario_id = a.usuario_id
               ) as tem_exame
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


@bp.route("/salas/<sala_id>", methods=["DELETE"])
@requer_admin
def excluir_sala(sala_id):
    try:
        execute("DELETE FROM salas WHERE id = ?", (sala_id,))
    except Exception as e:
        if "FOREIGN KEY" in str(e).upper():
            return jsonify({
                "erro": "Não é possível excluir: esta sala já tem agendamentos vinculados. "
                        "Desative em vez de excluir, para preservar o histórico."
            }), 409
        raise
    return jsonify({"mensagem": "Sala excluída."})


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
        """
        INSERT INTO profissionais
            (id, nome, duracao_padrao_min, cep, endereco, numero, complemento, crefito, ativo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        """,
        (prof_id, dados["nome"], dados.get("duracao_padrao_min", 60),
         dados.get("cep"), dados.get("endereco"), dados.get("numero"),
         dados.get("complemento"), dados.get("crefito")),
    )
    return jsonify({"mensagem": "Profissional cadastrado.", "id": prof_id}), 201


@bp.route("/profissionais/<prof_id>", methods=["PUT"])
@requer_admin
def atualizar_profissional(prof_id):
    dados = request.get_json(force=True)
    sets, valores = [], []
    campos_texto = ["nome", "cep", "endereco", "numero", "complemento", "crefito"]
    for campo in campos_texto:
        if campo in dados:
            sets.append(f"{campo} = ?"); valores.append(dados[campo])
    if "duracao_padrao_min" in dados:
        sets.append("duracao_padrao_min = ?"); valores.append(dados["duracao_padrao_min"])
    if "ativo" in dados:
        sets.append("ativo = ?"); valores.append(bool(dados["ativo"]))
    if not sets:
        return jsonify({"erro": "Nada para atualizar."}), 400
    valores.append(prof_id)
    execute(f"UPDATE profissionais SET {', '.join(sets)} WHERE id = ?", valores)
    return jsonify({"mensagem": "Profissional atualizado."})


@bp.route("/profissionais/<prof_id>", methods=["DELETE"])
@requer_admin
def excluir_profissional(prof_id):
    try:
        execute("DELETE FROM profissionais WHERE id = ?", (prof_id,))
    except Exception as e:
        if "FOREIGN KEY" in str(e).upper():
            return jsonify({
                "erro": "Não é possível excluir: este profissional já tem agendamentos "
                        "vinculados. Desative em vez de excluir, para preservar o histórico."
            }), 409
        raise
    return jsonify({"mensagem": "Profissional excluído."})


@bp.route("/bloqueios-dia", methods=["GET"])
@requer_admin
def listar_bloqueios_dia():
    return jsonify(all_rows(
        """
        SELECT b.*, p.nome as profissional_nome
        FROM bloqueios_dia b
        LEFT JOIN profissionais p ON p.id = b.profissional_id
        ORDER BY b.data
        """
    ))


@bp.route("/bloqueios-dia/<bloqueio_id>", methods=["DELETE"])
@requer_admin
def remover_bloqueio_dia(bloqueio_id):
    execute("DELETE FROM bloqueios_dia WHERE id = ?", (bloqueio_id,))
    return jsonify({"mensagem": "Bloqueio removido."})


@bp.route("/janelas-indisponiveis", methods=["GET"])
@requer_admin
def listar_janelas_indisponiveis():
    return jsonify(all_rows(
        """
        SELECT j.*, p.nome as profissional_nome
        FROM janelas_indisponiveis j
        LEFT JOIN profissionais p ON p.id = j.profissional_id
        ORDER BY j.hora_inicio
        """
    ))


@bp.route("/janelas-indisponiveis/<janela_id>", methods=["DELETE"])
@requer_admin
def remover_janela_indisponivel(janela_id):
    execute("DELETE FROM janelas_indisponiveis WHERE id = ?", (janela_id,))
    return jsonify({"mensagem": "Janela indisponível removida."})


@bp.route("/bloqueios-dia", methods=["POST"])
@requer_admin
def criar_bloqueio_dia():
    """Feriado nacional/regional, jogo da Copa, ou força maior (enchente, decreto).
    profissional_id opcional: se informado, bloqueia a agenda só daquele
    profissional nesse dia; se omitido, bloqueia para todos."""
    dados = request.get_json(force=True)
    obrigatorios = ["data", "motivo", "tipo"]
    faltando = [c for c in obrigatorios if not dados.get(c)]
    if faltando:
        return jsonify({"erro": f"Campos obrigatórios ausentes: {faltando}"}), 400

    execute(
        "INSERT INTO bloqueios_dia (id, data, motivo, tipo, profissional_id) VALUES (?, ?, ?, ?, ?)",
        (new_id(), dados["data"], dados["motivo"], dados["tipo"], dados.get("profissional_id")),
    )
    return jsonify({"mensagem": "Bloqueio registrado."}), 201


@bp.route("/janelas-indisponiveis", methods=["POST"])
@requer_admin
def criar_janela_indisponivel():
    """Ex: almoço das 12h às 13h, recorrente (dia_semana) ou pontual (data_especifica).
    profissional_id opcional: se informado, bloqueia só a agenda daquele profissional."""
    dados = request.get_json(force=True)
    if not dados.get("dia_semana") and not dados.get("data_especifica"):
        return jsonify({"erro": "Informe dia_semana (recorrente) ou data_especifica (pontual)."}), 400

    execute(
        """
        INSERT INTO janelas_indisponiveis
            (id, dia_semana, data_especifica, hora_inicio, hora_fim, motivo, profissional_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (new_id(), dados.get("dia_semana"), dados.get("data_especifica"),
         dados["hora_inicio"], dados["hora_fim"], dados.get("motivo"), dados.get("profissional_id")),
    )
    return jsonify({"mensagem": "Janela indisponível registrada."}), 201
