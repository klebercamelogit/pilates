"""
Storage de exames (PDF/JPG/PNG, até 300MB).

Decisão de arquitetura: o arquivo NUNCA é enviado para o Flask.
Em serverless (Vercel), o limite de corpo de requisição fica muito abaixo
de 300MB e as funções têm timeout curto — subir um exame de imagem médica
por ali travaria ou seria rejeitado antes de chegar ao seu código.

Fluxo real:
1. Frontend pede uma URL de upload pré-assinada para este backend
   (gerar_url_upload).
2. Frontend faz PUT/POST direto para o bucket S3-compatible usando essa URL.
3. Frontend avisa o backend que o upload terminou; o backend só grava
   a referência (storage_key) no banco — nunca os bytes do arquivo.
"""
import os
from flask import current_app

EXTENSOES_PERMITIDAS = {"pdf", "jpg", "jpeg", "png"}
CONTENT_TYPES_PERMITIDOS = {
    "application/pdf",
    "image/jpeg",
    "image/png",
}


def _client():
    # Import local para não exigir boto3 instalado quando STORAGE_MODE=local
    import boto3
    from botocore.client import Config as BotoConfig

    cfg = current_app.config
    return boto3.client(
        "s3",
        endpoint_url=cfg["S3_ENDPOINT_URL"],
        aws_access_key_id=cfg["S3_ACCESS_KEY"],
        aws_secret_access_key=cfg["S3_SECRET_KEY"],
        region_name=cfg["S3_REGION"],
        config=BotoConfig(signature_version="s3v4"),
    )


# ---------------------------------------------------------------------
# Modo LOCAL: sem bucket, sem URL pré-assinada. Como não há limite de
# payload nem timeout curto rodando no seu próprio Flask local, o upload
# pode ir direto por multipart/form-data — só em desenvolvimento.
# ---------------------------------------------------------------------
def salvar_arquivo_local(storage_key: str, file_storage) -> None:
    caminho_completo = os.path.join(current_app.config["LOCAL_UPLOAD_DIR"], storage_key)
    os.makedirs(os.path.dirname(caminho_completo), exist_ok=True)
    file_storage.save(caminho_completo)


def caminho_arquivo_local(storage_key: str) -> str:
    return os.path.join(current_app.config["LOCAL_UPLOAD_DIR"], storage_key)


def extensao_valida(nome_arquivo: str, content_type: str) -> bool:
    ext = nome_arquivo.rsplit(".", 1)[-1].lower() if "." in nome_arquivo else ""
    return ext in EXTENSOES_PERMITIDAS and content_type in CONTENT_TYPES_PERMITIDOS


def gerar_url_upload(storage_key: str, content_type: str, expira_segundos: int = 900) -> str:
    """
    Gera uma URL PUT pré-assinada. O frontend deve enviar o arquivo via
    PUT diretamente para essa URL, com o header Content-Type igual ao
    informado aqui.
    """
    client = _client()
    return client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": current_app.config["S3_BUCKET"],
            "Key": storage_key,
            "ContentType": content_type,
        },
        ExpiresIn=expira_segundos,
    )


def gerar_url_leitura(storage_key: str, expira_segundos: int = 3600) -> str:
    """URL temporária para o cliente/admin baixar o exame."""
    client = _client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": current_app.config["S3_BUCKET"], "Key": storage_key},
        ExpiresIn=expira_segundos,
    )


def montar_storage_key(usuario_id: str, nome_original: str) -> str:
    import uuid

    ext = nome_original.rsplit(".", 1)[-1].lower() if "." in nome_original else "bin"
    return f"exames/{usuario_id}/{uuid.uuid4()}.{ext}"
