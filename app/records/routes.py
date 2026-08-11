import os

from flask import Blueprint, request, jsonify, current_app, send_file

from app.db import execute, one, new_id
from app import storage
from app.authz import requer_login, exige_dono_ou_admin

bp = Blueprint("records", __name__, url_prefix="/api/exames")


def _dono_do_prontuario(prontuario_id: str):
    row = one("SELECT usuario_id FROM prontuarios WHERE id = ?", (prontuario_id,))
    return row["usuario_id"] if row else None


@bp.route("/modo", methods=["GET"])
def modo():
    """Não é dado sensível — o frontend usa isso para saber se faz upload
    multipart direto (local) ou pede URL pré-assinada (cloud)."""
    return jsonify({"storage_mode": current_app.config["STORAGE_MODE"]})


@bp.route("/upload", methods=["POST"])
@requer_login
def upload():
    """
    Modo local (STORAGE_MODE=local): multipart/form-data direto, campo 'arquivo'.
    Modo cloud (STORAGE_MODE=s3): use GET /url-upload abaixo para pedir a URL
    pré-assinada e faça o PUT direto pro bucket a partir do navegador —
    NÃO chame esta rota em produção.
    """
    if current_app.config["STORAGE_MODE"] != "local":
        return jsonify({
            "erro": "Upload multipart direto só é permitido em STORAGE_MODE=local. "
                    "Em produção, peça uma URL pré-assinada em /api/exames/url-upload."
        }), 400

    prontuario_id = request.form.get("prontuario_id")
    arquivo = request.files.get("arquivo")
    if not prontuario_id or not arquivo:
        return jsonify({"erro": "prontuario_id e arquivo são obrigatórios."}), 400

    dono = _dono_do_prontuario(prontuario_id)
    if not dono:
        return jsonify({"erro": "Prontuário não encontrado."}), 404
    if not exige_dono_ou_admin(request.usuario_atual, dono):
        return jsonify({"erro": "Acesso negado a este prontuário."}), 403

    if not storage.extensao_valida(arquivo.filename, arquivo.content_type):
        return jsonify({"erro": "Extensão ou tipo de arquivo não permitido."}), 400

    storage_key = storage.montar_storage_key(prontuario_id, arquivo.filename)
    storage.salvar_arquivo_local(storage_key, arquivo)

    tamanho = os.path.getsize(storage.caminho_arquivo_local(storage_key))
    if tamanho > current_app.config["MAX_UPLOAD_BYTES"]:
        os.remove(storage.caminho_arquivo_local(storage_key))
        tamanho_mb = round(tamanho / (1024 * 1024), 1)
        limite_mb = round(current_app.config["MAX_UPLOAD_BYTES"] / (1024 * 1024), 1)
        return jsonify({"erro": f"Este arquivo tem {tamanho_mb}MB. O limite é {limite_mb}MB. Ajuste o tamanho do arquivo e reenvie."}), 413

    exame_id = new_id()
    execute(
        """
        INSERT INTO exames_arquivos
            (id, prontuario_id, nome_original, storage_key, content_type, tamanho_bytes)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (exame_id, prontuario_id, arquivo.filename, storage_key, arquivo.content_type, tamanho),
    )
    return jsonify({"mensagem": "Exame enviado.", "exame_id": exame_id}), 201


@bp.route("/url-upload", methods=["POST"])
@requer_login
def url_upload():
    """Modo cloud: gera URL pré-assinada para o frontend subir o arquivo direto pro bucket."""
    if current_app.config["STORAGE_MODE"] != "s3":
        return jsonify({"erro": "Esta rota é só para STORAGE_MODE=s3."}), 400

    dados = request.get_json(force=True)
    nome_original = dados.get("nome_original")
    content_type = dados.get("content_type")
    prontuario_id = dados.get("prontuario_id")
    if not (nome_original and content_type and prontuario_id):
        return jsonify({"erro": "nome_original, content_type e prontuario_id obrigatórios."}), 400

    dono = _dono_do_prontuario(prontuario_id)
    if not dono:
        return jsonify({"erro": "Prontuário não encontrado."}), 404
    if not exige_dono_ou_admin(request.usuario_atual, dono):
        return jsonify({"erro": "Acesso negado a este prontuário."}), 403

    if not storage.extensao_valida(nome_original, content_type):
        return jsonify({"erro": "Extensão ou tipo de arquivo não permitido."}), 400

    storage_key = storage.montar_storage_key(prontuario_id, nome_original)
    url = storage.gerar_url_upload(storage_key, content_type)
    return jsonify({"url_upload": url, "storage_key": storage_key})


@bp.route("/confirmar", methods=["POST"])
@requer_login
def confirmar_upload():
    """
    Modo cloud: depois que o navegador faz o PUT direto pro bucket usando a
    URL de /url-upload, ele chama esta rota para registrar os metadados do
    exame no banco — o Flask nunca viu os bytes do arquivo em nenhum momento.
    """
    if current_app.config["STORAGE_MODE"] != "s3":
        return jsonify({"erro": "Esta rota é só para STORAGE_MODE=s3."}), 400

    dados = request.get_json(force=True)
    obrigatorios = ["prontuario_id", "storage_key", "nome_original", "content_type", "tamanho_bytes"]
    faltando = [c for c in obrigatorios if not dados.get(c)]
    if faltando:
        return jsonify({"erro": f"Campos obrigatórios ausentes: {faltando}"}), 400

    dono = _dono_do_prontuario(dados["prontuario_id"])
    if not dono:
        return jsonify({"erro": "Prontuário não encontrado."}), 404
    if not exige_dono_ou_admin(request.usuario_atual, dono):
        return jsonify({"erro": "Acesso negado a este prontuário."}), 403

    if dados["tamanho_bytes"] > current_app.config["MAX_UPLOAD_BYTES"]:
        tamanho_mb = round(dados["tamanho_bytes"] / (1024 * 1024), 1)
        limite_mb = round(current_app.config["MAX_UPLOAD_BYTES"] / (1024 * 1024), 1)
        return jsonify({"erro": f"Este arquivo tem {tamanho_mb}MB. O limite é {limite_mb}MB. Ajuste o tamanho do arquivo e reenvie."}), 413

    exame_id = new_id()
    execute(
        """
        INSERT INTO exames_arquivos
            (id, prontuario_id, nome_original, storage_key, content_type, tamanho_bytes)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (exame_id, dados["prontuario_id"], dados["nome_original"], dados["storage_key"],
         dados["content_type"], dados["tamanho_bytes"]),
    )
    return jsonify({"mensagem": "Exame registrado.", "exame_id": exame_id}), 201


@bp.route("/<exame_id>/download", methods=["GET"])
@requer_login
def download(exame_id):
    exame = one("SELECT * FROM exames_arquivos WHERE id = ?", (exame_id,))
    if not exame:
        return jsonify({"erro": "Exame não encontrado."}), 404

    dono = _dono_do_prontuario(exame["prontuario_id"])
    if not dono or not exige_dono_ou_admin(request.usuario_atual, dono):
        return jsonify({"erro": "Acesso negado a este exame."}), 403

    if current_app.config["STORAGE_MODE"] == "local":
        caminho = storage.caminho_arquivo_local(exame["storage_key"])
        return send_file(caminho, download_name=exame["nome_original"], as_attachment=True)

    url = storage.gerar_url_leitura(exame["storage_key"])
    return jsonify({"url_download": url})
