"""
Envio de e-mail via SMTP puro (smtplib da stdlib, sem dependência extra).

Se SMTP_HOST não estiver configurado, a função não falha — ela loga o
conteúdo que seria enviado e segue em frente. Isso é proposital: em
desenvolvimento/local você não quer que um cadastro quebre só porque
não configurou e-mail ainda. Em produção, configure SMTP_HOST de verdade.

Provedores comuns:
- Gmail: exige "Senha de app" (App Password), não a senha normal da conta,
  já que a verificação em 2 etapas bloqueia login direto de app externo.
  smtp.gmail.com, porta 587.
- Brevo (ex-Sendinblue), SendGrid, Mailtrap (para testes): todos têm
  camada gratuita e SMTP padrão, mais simples de configurar que Gmail.
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from flask import current_app


def enviar_email(destinatario: str, assunto: str, corpo_texto: str) -> bool:
    """Retorna True se enviou (ou simulou o envio via log), False se falhou de verdade."""
    cfg = current_app.config

    if not cfg.get("SMTP_HOST"):
        current_app.logger.warning(
            "SMTP não configurado — e-mail NÃO enviado para %s.\nAssunto: %s\nCorpo:\n%s",
            destinatario, assunto, corpo_texto,
        )
        return True  # não é erro de aplicação, é ausência de configuração

    msg = MIMEMultipart()
    msg["From"] = cfg["SMTP_FROM"]
    msg["To"] = destinatario
    msg["Subject"] = assunto
    msg.attach(MIMEText(corpo_texto, "plain", "utf-8"))

    try:
        if cfg.get("SMTP_USE_SSL"):
            # Porta 465: SSL implícito desde a conexão, sem STARTTLS.
            with smtplib.SMTP_SSL(cfg["SMTP_HOST"], cfg["SMTP_PORT"], timeout=10) as server:
                if cfg.get("SMTP_USER"):
                    server.login(cfg["SMTP_USER"], cfg["SMTP_PASSWORD"])
                server.sendmail(cfg["SMTP_FROM"], [destinatario], msg.as_string())
        else:
            with smtplib.SMTP(cfg["SMTP_HOST"], cfg["SMTP_PORT"], timeout=10) as server:
                # Porta 587 (Gmail, Brevo, SendGrid etc.) usa STARTTLS.
                # Servidores de teste locais (ex: aiosmtpd sem TLS) não
                # suportam — por isso isso é configurável via SMTP_USE_TLS,
                # não fixo no código.
                if cfg.get("SMTP_USE_TLS", True):
                    server.starttls()
                if cfg.get("SMTP_USER"):
                    server.login(cfg["SMTP_USER"], cfg["SMTP_PASSWORD"])
                server.sendmail(cfg["SMTP_FROM"], [destinatario], msg.as_string())
        return True
    except Exception:
        current_app.logger.exception("Falha ao enviar e-mail para %s", destinatario)
        return False


def enviar_codigo_verificacao(email: str, nome: str, codigo: str) -> None:
    assunto = "Confirme seu cadastro — Clínica de Pilates"
    corpo = (
        f"Olá, {nome}!\n\n"
        f"Seu código de verificação é: {codigo}\n\n"
        "Informe esse código para ativar sua conta."
    )
    enviar_email(email, assunto, corpo)


def enviar_link_reset_senha(email: str, token: str) -> None:
    cfg = current_app.config
    base = cfg.get("FRONTEND_BASE_URL")
    if base:
        link = f"{base.rstrip('/')}/redefinir-senha?token={token}"
        corpo = f"Clique no link para redefinir sua senha:\n\n{link}\n\nO link expira em 1 hora."
    else:
        corpo = (
            "Ainda não há frontend configurado (FRONTEND_BASE_URL vazio). "
            "Use o token abaixo diretamente no endpoint da API "
            "(POST /api/auth/esqueci-senha/redefinir):\n\n"
            f"{token}\n\nO token expira em 1 hora."
        )
    enviar_email(email, "Redefinição de senha — Clínica de Pilates", corpo)


def enviar_primeiro_acesso(email: str, nome: str, token: str) -> None:
    cfg = current_app.config
    base = cfg.get("FRONTEND_BASE_URL")
    if base:
        link = f"{base.rstrip('/')}/primeiro-acesso?token={token}"
        corpo = (
            f"Olá, {nome}! Você foi cadastrado na clínica.\n\n"
            f"Defina sua senha e aceite o termo de uso de dados aqui:\n{link}"
        )
    else:
        corpo = (
            f"Olá, {nome}! Você foi cadastrado na clínica.\n\n"
            "Ainda não há frontend configurado (FRONTEND_BASE_URL vazio). "
            "Use o token abaixo em POST /api/auth/primeiro-acesso, junto com "
            "sua nova senha e o aceite do termo de uso de dados:\n\n"
            f"{token}"
        )
    enviar_email(email, "Bem-vindo(a) — defina sua senha", corpo)
