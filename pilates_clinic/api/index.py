# Entry point para Vercel Serverless Functions (Python runtime).
# Vercel detecta este arquivo e expõe `app` como handler WSGI.
from app import create_app

app = create_app()
