import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "troque-isto-em-producao")

    # Turso / libSQL
    TURSO_DATABASE_URL = os.environ.get("TURSO_DATABASE_URL")  # ex: libsql://seu-db.turso.io
    TURSO_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN")

    # Storage de objetos para exames (S3-compatible: AWS S3, Cloudflare R2, Backblaze B2...)
    # Upload NUNCA passa pelo Flask/serverless: o navegador envia direto pro bucket
    # usando uma URL pré-assinada gerada aqui. Vercel Serverless tem limite de
    # payload muito abaixo de 300MB, então essa é a única arquitetura viável.
    S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL")
    S3_BUCKET = os.environ.get("S3_BUCKET")
    S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY")
    S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY")
    S3_REGION = os.environ.get("S3_REGION", "auto")

    MAX_UPLOAD_BYTES = 300 * 1024 * 1024  # 300MB

    # E-mail (para código de verificação e reset de senha)
    SMTP_HOST = os.environ.get("SMTP_HOST")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
    SMTP_USER = os.environ.get("SMTP_USER")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
    SMTP_FROM = os.environ.get("SMTP_FROM", "no-reply@clinica.com")

    # WhatsApp Business API (Meta) — integração opcional/futura, ver README
    WHATSAPP_ENABLED = os.environ.get("WHATSAPP_ENABLED", "false").lower() == "true"
    WHATSAPP_PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
    WHATSAPP_ACCESS_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN")

    # LGPD
    TERMO_LGPD_VERSAO_ATUAL = os.environ.get("TERMO_LGPD_VERSAO_ATUAL", "v1.0")
