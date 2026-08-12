import base64
import os

from flask import Blueprint, request, jsonify, current_app, send_file, Response

from app.db import execute, one, new_id
from app import storage
from app.authz import requer_login, exige_dono_ou_admin

bp = Blueprint("records", __name__, url_prefix="/api/exames")


def _dono_do_prontuario(prontuario_id: str):
    row = one("SELECT usuario_id FROM prontuarios WHERE id = ?", (prontuario_id,))
    return row["usuario_id"] if row else None


def _limite_atual_bytes() -> int:
    """O limite depende do backend ativo — 'db' é bem mais restrito por causa
    do limite de 4.5MB de corpo de requisição do Vercel (infraestrutura,
    não contornável por configuração)."""
    modo = current_app.config["STORAGE_MODE"]
    if modo == "db":
        return current_app.config["MAX_UPLOAD_BYTES_DB"]
    return current_app.config["MAX_UPLOAD_BYTES"]


def _erro_tamanho(tamanho_bytes: int, limite_bytes: int) -> str:
    tamanho_mb = round(tamanho_bytes / (1024 * 1024), 1)
    limite_mb = round(limite_bytes / (1024 * 1024), 1)
    return f"Este arquivo tem {tamanho_mb}MB. O limite é {limite_mb}MB. Ajuste o tamanho do arquivo e reenvie."


@bp.route("/modo", methods=["GET"])
def modo():
    """Não é dado sensível — o frontend usa isso para saber se faz upload
    multipart direto (local/db) ou pede URL pré-assinada (s3), e qual
    limite de tamanho mostrar antes de tentar enviar."""
    return jsonify({
        "storage_mode": current_app.config["STORAGE_MODE"],
        "max_upload_bytes": _limite_atual_bytes(),
    })


@bp.route("/upload", methods=["POST"])
@requer_login
def upload():
    """
    Upload multipart direto pro Flask — usado nos modos 'local' (disco,
    desenvolvimento) e 'db' (base64 no Turso, produção sem bucket, arquivo
    pequeno). Em modo 's3', use /url-upload em vez desta rota.
    """
    modo_atual = current_app.config["STORAGE_MODE"]
    if modo_atual not in ("local", "db"):
        return jsonify({
            "erro": "Upload multipart direto só é permitido em STORAGE_MODE=local ou db. "
                    "Em modo s3, peça uma URL pré-assinada em /api/exames/url-upload."
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

    exame_id = new_id()

    if modo_atual == "db":
        conteudo_bytes = arquivo.read()
        tamanho = len(conteudo_bytes)
        limite = _limite_atual_bytes()
        if tamanho > limite:
            return jsonify({"erro": _erro_tamanho(tamanho, limite)}), 413

        conteudo_b64 = base64.b64encode(conteudo_bytes).decode("ascii")
        # storage_key não é usado no modo 'db' (o conteúdo vai na coluna
        # `conteudo`), mas alguns bancos criados com uma versão antiga do
        # schema ainda têm essa coluna como NOT NULL — preenchemos um
        # placeholder pra não depender de migrar essa constraint específica.
        storage_key_placeholder = f"db:{exame_id}"
        execute(
            """
            INSERT INTO exames_arquivos
                (id, prontuario_id, nome_original, storage_backend, storage_key, conteudo,
                 content_type, tamanho_bytes)
            VALUES (?, ?, ?, 'db', ?, ?, ?, ?)
            """,
            (exame_id, prontuario_id, arquivo.filename, storage_key_placeholder, conteudo_b64,
             arquivo.content_type, tamanho),
        )
        return jsonify({"mensagem": "Exame enviado.", "exame_id": exame_id}), 201

    # modo_atual == "local"
    storage_key = storage.montar_storage_key(prontuario_id, arquivo.filename)
    storage.salvar_arquivo_local(storage_key, arquivo)

    tamanho = os.path.getsize(storage.caminho_arquivo_local(storage_key))
    limite = _limite_atual_bytes()
    if tamanho > limite:
        os.remove(storage.caminho_arquivo_local(storage_key))
        return jsonify({"erro": _erro_tamanho(tamanho, limite)}), 413

    execute(
        """
        INSERT INTO exames_arquivos
            (id, prontuario_id, nome_original, storage_backend, storage_key,
             content_type, tamanho_bytes)
        VALUES (?, ?, ?, 'local', ?, ?, ?)
        """,
        (exame_id, prontuario_id, arquivo.filename, storage_key, arquivo.content_type, tamanho),
    )
    return jsonify({"mensagem": "Exame enviado.", "exame_id": exame_id}), 201


@bp.route("/url-upload", methods=["POST"])
@requer_login
def url_upload():
    """Modo s3: gera URL pré-assinada para o frontend subir o arquivo direto pro bucket."""
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
    Modo s3: depois que o navegador faz o PUT direto pro bucket usando a
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

    limite = current_app.config["MAX_UPLOAD_BYTES"]
    if dados["tamanho_bytes"] > limite:
        return jsonify({"erro": _erro_tamanho(dados["tamanho_bytes"], limite)}), 413

    exame_id = new_id()
    execute(
        """
        INSERT INTO exames_arquivos
            (id, prontuario_id, nome_original, storage_backend, storage_key,
             content_type, tamanho_bytes)
        VALUES (?, ?, ?, 's3', ?, ?, ?)
        """,
        (exame_id, dados["prontuario_id"], dados["nome_original"], dados["storage_key"],
         dados["content_type"], dados["tamanho_bytes"]),
    )
    return jsonify({"mensagem": "Exame registrado.", "exame_id": exame_id}), 201


@bp.route("/<exame_id>", methods=["DELETE"])
@requer_login
def excluir_exame(exame_id):
    exame = one("SELECT * FROM exames_arquivos WHERE id = ?", (exame_id,))
    if not exame:
        return jsonify({"erro": "Exame não encontrado."}), 404

    dono = _dono_do_prontuario(exame["prontuario_id"])
    if not dono or not exige_dono_ou_admin(request.usuario_atual, dono):
        return jsonify({"erro": "Acesso negado a este exame."}), 403

    if exame["storage_backend"] == "local":
        try:
            os.remove(storage.caminho_arquivo_local(exame["storage_key"]))
        except OSError:
            pass  # arquivo já não existe em disco — segue removendo o registro
    elif exame["storage_backend"] == "s3":
        try:
            storage.remover_arquivo_s3(exame["storage_key"])
        except Exception:
            pass  # best-effort — não bloqueia a exclusão do registro por falha no bucket

    execute("DELETE FROM exames_arquivos WHERE id = ?", (exame_id,))
    return jsonify({"mensagem": "Exame excluído."})


@bp.route("/<exame_id>/download", methods=["GET"])
@requer_login
def download(exame_id):
    exame = one("SELECT * FROM exames_arquivos WHERE id = ?", (exame_id,))
    if not exame:
        return jsonify({"erro": "Exame não encontrado."}), 404

    dono = _dono_do_prontuario(exame["prontuario_id"])
    if not dono or not exige_dono_ou_admin(request.usuario_atual, dono):
        return jsonify({"erro": "Acesso negado a este exame."}), 403

    # Decide pelo backend GRAVADO NA LINHA, não pelo STORAGE_MODE atual da
    # config — se o modo mudar depois (ex: admin passa a usar s3), exames
    # antigos salvos em 'db' ou 'local' continuam recuperáveis do jeito
    # como foram salvos.
    backend = exame["storage_backend"]

    if backend == "db":
        conteudo_bytes = base64.b64decode(exame["conteudo"])
        return Response(
            conteudo_bytes,
            mimetype=exame["content_type"],
            headers={"Content-Disposition": f'attachment; filename="{exame["nome_original"]}"'},
        )

    if backend == "local":
        caminho = storage.caminho_arquivo_local(exame["storage_key"])
        return send_file(caminho, download_name=exame["nome_original"], as_attachment=True)

    # backend == "s3"
    url = storage.gerar_url_leitura(exame["storage_key"])
    return jsonify({"url_download": url})
