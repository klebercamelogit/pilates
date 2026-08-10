import random
import secrets
from datetime import datetime, timedelta

import bcrypt
from flask import Blueprint, request, jsonify, current_app

from app.db import execute, one, new_id
from app import notifications
from app.authz import usuario_da_requisicao

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.route("/cadastro", methods=["POST"])
def cadastro():
    dados = request.get_json(force=True)

    campos_obrigatorios = ["nome", "email", "whatsapp", "senha",
                            "consentimento_lgpd_aceito"]
    faltando = [c for c in campos_obrigatorios if not dados.get(c)]
    if faltando:
        return jsonify({"erro": f"Campos obrigatórios ausentes: {faltando}"}), 400

    # LGPD: consentimento explícito é obrigatório, não implícito num "aceito os termos" genérico
    if not dados["consentimento_lgpd_aceito"]:
        return jsonify({
            "erro": "É necessário aceitar explicitamente o tratamento de dados "
                    "sensíveis de saúde (LGPD, art. 11) para se cadastrar."
        }), 400

    if one("SELECT id FROM usuarios WHERE email = ?", (dados["email"],)):
        return jsonify({"erro": "E-mail já cadastrado."}), 409

    senha_hash = bcrypt.hashpw(dados["senha"].encode(), bcrypt.gensalt()).decode()
    codigo_verificacao = f"{random.randint(0, 999999):06d}"
    usuario_id = new_id()
    # A coluna `cpf` é NOT NULL UNIQUE no schema (mantida assim de propósito,
    # para não exigir migração no banco em produção). CPF não é mais
    # coletado do cliente — isto é só um identificador interno opaco,
    # nunca exibido nem usado para nada além de satisfazer a constraint.
    cpf_interno = f"sem-cpf-{new_id()}"

    execute(
        """
        INSERT INTO usuarios (
            id, nome, cpf, email, senha_hash, whatsapp, cep, endereco,
            complemento, idade, dia_nascimento, mes_nascimento, papel, ativo,
            codigo_verificacao, consentimento_lgpd_aceito, consentimento_lgpd_data,
            consentimento_lgpd_versao
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'cliente', 0, ?, 1, ?, ?)
        """,
        (
            usuario_id, dados["nome"], cpf_interno, dados["email"], senha_hash,
            dados["whatsapp"], dados.get("cep"), dados.get("endereco"),
            dados.get("complemento"), dados.get("idade"), dados.get("dia_nascimento"),
            dados.get("mes_nascimento"), codigo_verificacao,
            datetime.utcnow().isoformat(),
            current_app.config["TERMO_LGPD_VERSAO_ATUAL"],
        ),
    )

    # Envio de e-mail não bloqueia o cadastro: se o SMTP falhar, a conta já
    # foi criada e o código pode ser reenviado depois (endpoint futuro) ou
    # consultado direto no banco em ambiente de teste.
    notifications.enviar_codigo_verificacao(dados["email"], dados["nome"], codigo_verificacao)

    return jsonify({"mensagem": "Cadastro criado. Verifique seu e-mail para ativar a conta.",
                     "usuario_id": usuario_id}), 201


@bp.route("/reenviar-codigo", methods=["POST"])
def reenviar_codigo():
    dados = request.get_json(force=True)
    email = dados.get("email")
    if not email:
        return jsonify({"erro": "email é obrigatório."}), 400

    usuario = one("SELECT id, nome FROM usuarios WHERE email = ? AND ativo = 0", (email,))
    # Resposta genérica mesmo se não encontrar — evita confirmar/negar
    # existência de e-mail cadastrado ou já ativado para quem não é dono dele.
    if usuario:
        novo_codigo = f"{random.randint(0, 999999):06d}"
        execute(
            "UPDATE usuarios SET codigo_verificacao = ? WHERE id = ?",
            (novo_codigo, usuario["id"]),
        )
        notifications.enviar_codigo_verificacao(email, usuario["nome"], novo_codigo)

    return jsonify({
        "mensagem": "Se o e-mail existir e a conta ainda não estiver ativa, "
                    "um novo código foi enviado."
    })


@bp.route("/ativar", methods=["POST"])
def ativar_conta():
    dados = request.get_json(force=True)
    usuario = one(
        "SELECT id FROM usuarios WHERE email = ? AND codigo_verificacao = ?",
        (dados.get("email"), dados.get("codigo")),
    )
    if not usuario:
        return jsonify({"erro": "Código inválido."}), 400

    execute(
        "UPDATE usuarios SET ativo = 1, codigo_verificacao = NULL WHERE id = ?",
        (usuario["id"],),
    )
    return jsonify({"mensagem": "Conta ativada com sucesso."})


@bp.route("/esqueci-senha/iniciar", methods=["POST"])
def esqueci_senha_iniciar():
    """
    Recuperação direta por e-mail — sem CPF em nenhuma etapa. Cliente
    informa o e-mail; se existir e tiver senha definida, um token de
    redefinição é gerado e enviado por e-mail. Resposta genérica sempre,
    para não confirmar/negar existência de e-mail cadastrado.
    """
    dados = request.get_json(force=True)
    email = dados.get("email")
    if not email:
        return jsonify({"erro": "email é obrigatório."}), 400

    usuario = one("SELECT id FROM usuarios WHERE email = ? AND senha_hash IS NOT NULL", (email,))
    if usuario:
        token = secrets.token_urlsafe(32)
        expira = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        execute(
            "UPDATE usuarios SET token_reset_senha = ?, token_reset_expira = ? WHERE id = ?",
            (token, expira, usuario["id"]),
        )
        notifications.enviar_link_reset_senha(email, token)

    return jsonify({
        "mensagem": "Se o e-mail existir e tiver uma conta ativa, um link de "
                    "redefinição foi enviado."
    })


@bp.route("/esqueci-senha/redefinir", methods=["POST"])
def esqueci_senha_redefinir():
    dados = request.get_json(force=True)
    usuario = one(
        "SELECT id, token_reset_expira FROM usuarios WHERE token_reset_senha = ?",
        (dados.get("token"),),
    )
    if not usuario:
        return jsonify({"erro": "Token inválido."}), 400
    if datetime.fromisoformat(usuario["token_reset_expira"]) < datetime.utcnow():
        return jsonify({"erro": "Token expirado."}), 400
    if dados.get("nova_senha") != dados.get("repetir_senha"):
        return jsonify({"erro": "Senhas não conferem."}), 400

    novo_hash = bcrypt.hashpw(dados["nova_senha"].encode(), bcrypt.gensalt()).decode()
    execute(
        "UPDATE usuarios SET senha_hash = ?, token_reset_senha = NULL, token_reset_expira = NULL "
        "WHERE id = ?",
        (novo_hash, usuario["id"]),
    )
    return jsonify({"mensagem": "Senha redefinida com sucesso."})


@bp.route("/primeiro-acesso", methods=["POST"])
def primeiro_acesso():
    """
    Usado quando o ADMIN cadastra o cliente manualmente (ver app/admin/routes.py).
    O cliente recebe um token por e-mail e usa esta rota para definir a
    própria senha e dar o consentimento LGPD — o admin nunca pode marcar
    esse consentimento em nome do cliente.
    """
    dados = request.get_json(force=True)

    usuario = one(
        "SELECT id FROM usuarios WHERE token_reset_senha = ? AND ativo = 0",
        (dados.get("token"),),
    )
    if not usuario:
        return jsonify({"erro": "Token inválido ou conta já ativada."}), 400

    if not dados.get("consentimento_lgpd_aceito"):
        return jsonify({
            "erro": "É necessário aceitar explicitamente o tratamento de dados "
                    "sensíveis de saúde (LGPD, art. 11) para ativar a conta."
        }), 400

    if dados.get("nova_senha") != dados.get("repetir_senha"):
        return jsonify({"erro": "Senhas não conferem."}), 400
    if not dados.get("nova_senha"):
        return jsonify({"erro": "nova_senha é obrigatória."}), 400

    senha_hash = bcrypt.hashpw(dados["nova_senha"].encode(), bcrypt.gensalt()).decode()
    execute(
        """
        UPDATE usuarios
        SET senha_hash = ?, ativo = 1, token_reset_senha = NULL,
            consentimento_lgpd_aceito = 1, consentimento_lgpd_data = ?,
            consentimento_lgpd_versao = ?
        WHERE id = ?
        """,
        (
            senha_hash, datetime.utcnow().isoformat(),
            current_app.config["TERMO_LGPD_VERSAO_ATUAL"], usuario["id"],
        ),
    )
    return jsonify({"mensagem": "Conta ativada e senha definida com sucesso."})


@bp.route("/login", methods=["POST"])
def login():
    dados = request.get_json(force=True)
    usuario = one(
        "SELECT id, senha_hash, ativo, papel FROM usuarios WHERE email = ?",
        (dados.get("email"),),
    )
    if not usuario or not usuario["senha_hash"]:
        return jsonify({"erro": "Credenciais inválidas."}), 401
    if not bcrypt.checkpw(dados.get("senha", "").encode(), usuario["senha_hash"].encode()):
        return jsonify({"erro": "Credenciais inválidas."}), 401
    if not usuario["ativo"]:
        return jsonify({"erro": "Conta ainda não ativada."}), 403

    token = secrets.token_urlsafe(32)
    expira = (datetime.utcnow() + timedelta(hours=12)).isoformat()
    execute(
        "INSERT INTO sessoes (id, usuario_id, token, expira_em) VALUES (?, ?, ?, ?)",
        (new_id(), usuario["id"], token, expira),
    )

    return jsonify({
        "mensagem": "Login ok",
        "usuario_id": usuario["id"],
        "papel": usuario["papel"],
        "token": token,
    })


@bp.route("/logout", methods=["POST"])
def logout():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[len("Bearer "):].strip()
        execute("DELETE FROM sessoes WHERE token = ?", (token,))
    return jsonify({"mensagem": "Sessão encerrada."})


@bp.route("/eu", methods=["GET"])
def eu():
    """Confere se o token ainda é válido e devolve quem está logado —
    usado pelo frontend para checar a sessão ao carregar uma página protegida."""
    usuario = usuario_da_requisicao()
    if not usuario:
        return jsonify({"erro": "Não autenticado."}), 401
    return jsonify({"usuario_id": usuario["usuario_id"], "papel": usuario["papel"], "email": usuario["email"]})
