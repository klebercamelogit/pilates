# Sistema de Gestão e Agendamento — Clínica de Pilates

Backend Flask, banco Turso (libSQL), deploy em Vercel Serverless Functions.

## O que já está implementado

- Cadastro de cliente com código de verificação por e-mail (envio de e-mail é TODO — ver `app/auth/routes.py`).
- Recuperação de senha por CPF + confirmação de e-mail ofuscado + link de reset.
- Prontuário e exames: schema pronto, upload via URL pré-assinada (`app/storage.py`), **não** via Flask.
- Agendamento com validação de regras (feriados, dia da semana, expediente, janelas indisponíveis, capacidade) e proteção contra concorrência via UNIQUE constraint no banco.
- Painel admin: cadastro manual de cliente (sem expor senha), configurações, bloqueios de dia, janelas indisponíveis, listagem de agendamentos.
- Estrutura de pagamento (tabela `pagamentos`) pronta para plugar gateway depois.

## O que NÃO está implementado ainda (de propósito)

Estes pontos exigem decisões de produto/infra que não estavam claras no escopo original e não devem ser "inventadas" no código:

1. **Autenticação de sessão real** — as rotas de login retornam os dados do usuário mas não emitem sessão/JWT. Decida entre Flask-Login com sessão (SSR) ou JWT (SPA/mobile) antes de ir pra produção.
2. **Verificação de papel admin** — as rotas em `app/admin/routes.py` não checam `papel = 'admin'`. Isso precisa de um decorator aplicado antes do deploy.
3. **Envio de e-mail** (código de verificação, reset de senha, primeiro acesso) — pontos marcados com `# TODO` em `app/auth/routes.py` e `app/admin/routes.py`. Precisa de um provedor (SES, SendGrid, Postmark).
4. **WhatsApp Business API** — isolado de propósito. Exige conta Business verificada na Meta e aprovação de templates de mensagem antes de qualquer código funcionar. Trate como fase 2, não como parte do MVP.
5. **Gateway de pagamento** — schema pronto, integração não escrita (o escopo original também tratava isso como "inclusão futura").

## Por que estas decisões de arquitetura

- **Turso via `libsql-client` puro, não SQLAlchemy**: o dialeto SQLAlchemy para libSQL é limitado; SQL explícito é mais previsível em serverless.
- **Upload de exames fora do Flask**: Vercel Serverless tem limite de payload muito abaixo de 300MB e timeout curto. O navegador sobe o arquivo direto pro bucket S3-compatible via URL pré-assinada; o Flask só grava a referência.
- **UNIQUE constraint como trava de concorrência real**: a validação de regras de negócio (`rules.py`) é uma checagem otimista. Quem realmente impede overbooking é o `UNIQUE(sala_id, data, hora_inicio)` no schema — se dois requests colidirem, o segundo INSERT falha e vira um erro tratado, não um agendamento duplicado.
- **LGPD**: cadastro exige consentimento explícito (`consentimento_lgpd_aceito`) separado de qualquer "aceito os termos" genérico, com data e versão do termo registradas para auditoria. Cadastro manual pelo admin **não** pode marcar esse campo — só o próprio cliente, no primeiro acesso.

## Setup local

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # preencha TURSO_DATABASE_URL, TURSO_AUTH_TOKEN, S3_*, SMTP_*

# aplicar schema no Turso (via turso CLI ou libsql-client)
turso db shell seu-banco < schema/schema.sql
turso db shell seu-banco < schema/seed.sql

flask --app wsgi run --debug
```

## Deploy (Vercel)

O entrypoint serverless está em `api/index.py`, mapeado por `vercel.json`.
Configure as mesmas variáveis de `.env.example` nas Environment Variables do projeto Vercel.

```bash
vercel deploy
```
