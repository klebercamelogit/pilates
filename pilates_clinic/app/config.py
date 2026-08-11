import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "troque-isto-em-producao")

    # --- Modo de execução ---
    # DB_MODE=local      -> SQLite em arquivo, zero dependência externa (localhost)
    # DB_MODE=cloud      -> Turso/libSQL (produção, Vercel)
    DB_MODE = os.environ.get("DB_MODE", "cloud")
    LOCAL_DB_PATH = os.environ.get("LOCAL_DB_PATH", "local.db")

    # STORAGE_MODE=local -> exames salvos em disco, upload multipart direto pro Flask
    #                       (só funciona em desenvolvimento local — o sistema de
    #                       arquivos do Vercel é só leitura fora de /tmp)
    # STORAGE_MODE=db    -> conteúdo do arquivo salvo em base64 numa coluna do
    #                       Turso. Funciona em produção sem precisar de bucket,
    #                       mas o Vercel limita o corpo de requisição de toda
    #                       função serverless a 4.5MB (nível de infraestrutura,
    #                       não contornável) — por isso o limite é bem menor
    #                       que os outros modos, ver MAX_UPLOAD_BYTES_DB.
    # STORAGE_MODE=s3    -> bucket S3-compatible via URL pré-assinada (produção,
    #                       único modo que sustenta arquivos grandes de verdade)
    STORAGE_MODE = os.environ.get("STORAGE_MODE", "s3")
    LOCAL_UPLOAD_DIR = os.environ.get("LOCAL_UPLOAD_DIR", "instance/uploads")
    MAX_UPLOAD_BYTES_DB = int(os.environ.get("MAX_UPLOAD_BYTES_DB", 3 * 1024 * 1024))  # 3MB

    # Turso / libSQL (usado só quando DB_MODE=cloud)
    TURSO_DATABASE_URL = os.environ.get("TURSO_DATABASE_URL")  # ex: libsql://seu-db.turso.io
    TURSO_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN")

    # Storage de objetos para exames (usado só quando STORAGE_MODE=s3)
    # Upload NUNCA passa pelo Flask/serverless em produção: o navegador envia
    # direto pro bucket usando uma URL pré-assinada gerada aqui, porque o
    # Vercel Serverless tem limite de payload bem abaixo de 300MB.
    S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL")
    S3_BUCKET = os.environ.get("S3_BUCKET")
    S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY")
    S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY")
    S3_REGION = os.environ.get("S3_REGION", "auto")

    MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", 300 * 1024 * 1024))  # 300MB padrão

    # E-mail (para código de verificação e reset de senha)
    SMTP_HOST = os.environ.get("SMTP_HOST")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
    SMTP_USER = os.environ.get("SMTP_USER")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
    SMTP_FROM = os.environ.get("SMTP_FROM", "no-reply@clinica.com")
    # STARTTLS (porta 587, padrão Gmail/Brevo/SendGrid) por padrão.
    # Desligue para servidores de teste locais sem TLS (ex: aiosmtpd).
    SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"
    # SSL implícito (porta 465). Se ligado, ignora SMTP_USE_TLS.
    SMTP_USE_SSL = os.environ.get("SMTP_USE_SSL", "false").lower() == "true"

    # WhatsApp Business API (Meta) — integração opcional/futura, ver README
    WHATSAPP_ENABLED = os.environ.get("WHATSAPP_ENABLED", "false").lower() == "true"
    WHATSAPP_PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
    WHATSAPP_ACCESS_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN")

    # LGPD
    TERMO_LGPD_VERSAO_ATUAL = os.environ.get("TERMO_LGPD_VERSAO_ATUAL", "v1.0")

    # URL do frontend (opcional). Se vazio, os e-mails enviam o token cru
    # com instrução de uso via API, em vez de um link clicável.
    FRONTEND_BASE_URL = os.environ.get("FRONTEND_BASE_URL")
