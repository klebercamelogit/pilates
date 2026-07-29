#!/usr/bin/env bash
# Sobe o app 100% local: sem Turso, sem S3, sem SMTP.
set -e

cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
    echo "Criando ambiente virtual..."
    python3 -m venv venv
fi
source venv/bin/activate

echo "Instalando dependências (sem boto3/libsql, que não são usados no modo local)..."
pip install -q flask bcrypt python-dotenv flask-wtf email-validator flask-login

cp -n .env.local .env 2>/dev/null || true

if [ ! -f "local.db" ]; then
    echo "Inicializando banco local..."
    python scripts/init_local_db.py
fi

mkdir -p instance/uploads

echo "Subindo Flask em http://localhost:5000 ..."
export FLASK_APP=wsgi
export $(grep -v '^#' .env | xargs)
flask run --debug
