# Sistema de Gestão e Agendamento — Clínica de Pilates

Backend Flask, banco Turso (libSQL), deploy em Vercel Serverless Functions.

## O que já está implementado

- Cadastro de cliente com código de verificação **enviado por e-mail via SMTP** (ver `app/notifications.py`). Se `SMTP_HOST` estiver vazio, o envio é simulado via log — não quebra o cadastro.
- Recuperação de senha por CPF + confirmação de e-mail ofuscado + link de reset **enviado por e-mail**.
- Primeiro acesso (`POST /api/auth/primeiro-acesso`): cliente cadastrado manualmente pelo admin recebe e-mail com token, define a própria senha e dá o consentimento LGPD — o admin nunca marca isso em nome dele.
- Prontuário e exames: schema pronto, upload via URL pré-assinada (`app/storage.py`) em produção, ou multipart direto em modo local.
- Agendamento com validação de regras (feriados, dia da semana, expediente, janelas indisponíveis, capacidade) e proteção contra concorrência via UNIQUE constraint no banco.
- Painel admin: cadastro manual de cliente (sem expor senha), configurações, bloqueios de dia, janelas indisponíveis, listagem de agendamentos.
- Estrutura de pagamento (tabela `pagamentos`) pronta para plugar gateway depois.

### Configurando o envio de e-mail (SMTP)

Preencha no `.env` (ou nas variáveis de ambiente do Vercel):

```
SMTP_HOST=smtp.gmail.com      # ou smtp-relay.brevo.com, smtp.sendgrid.net, etc.
SMTP_PORT=587
SMTP_USER=seu-usuario
SMTP_PASSWORD=sua-senha-de-app
SMTP_FROM=no-reply@suaclinica.com
SMTP_USE_TLS=true             # STARTTLS na porta 587 (padrão)
SMTP_USE_SSL=false            # true só se usar porta 465 (SSL implícito)
```

**Gmail exige "Senha de app"**, não a senha normal da conta — a verificação em 2 etapas bloqueia login direto de aplicação externa. Gere em: Conta Google → Segurança → Senhas de app.

Alternativas mais simples para testar rápido: **Brevo** (ex-Sendinblue) ou **Mailtrap**, ambos com camada gratuita e SMTP padrão sem a complicação de senha de app.

`FRONTEND_BASE_URL` é opcional — se vazio, os e-mails de reset de senha e primeiro acesso enviam o token cru com instrução de uso direto na API, em vez de um link clicável (já que ainda não existe frontend).

## O que NÃO está implementado ainda (de propósito)

Estes pontos exigem decisões de produto/infra que não estavam claras no escopo original e não devem ser "inventadas" no código:

1. **Autenticação de sessão real** — as rotas de login retornam os dados do usuário mas não emitem sessão/JWT. Decida entre Flask-Login com sessão (SSR) ou JWT (SPA/mobile) antes de ir pra produção.
2. **Verificação de papel admin** — as rotas em `app/admin/routes.py` não checam `papel = 'admin'`. Isso precisa de um decorator aplicado antes do deploy.
3. **WhatsApp Business API** — isolado de propósito. Exige conta Business verificada na Meta e aprovação de templates de mensagem antes de qualquer código funcionar. Trate como fase 2, não como parte do MVP.
4. **Gateway de pagamento** — schema pronto, integração não escrita (o escopo original também tratava isso como "inclusão futura").

## Por que estas decisões de arquitetura

- **Turso via `libsql-client` puro, não SQLAlchemy**: o dialeto SQLAlchemy para libSQL é limitado; SQL explícito é mais previsível em serverless.
- **Upload de exames fora do Flask**: Vercel Serverless tem limite de payload muito abaixo de 300MB e timeout curto. O navegador sobe o arquivo direto pro bucket S3-compatible via URL pré-assinada; o Flask só grava a referência.
- **UNIQUE constraint como trava de concorrência real**: a validação de regras de negócio (`rules.py`) é uma checagem otimista. Quem realmente impede overbooking é o `UNIQUE(sala_id, data, hora_inicio)` no schema — se dois requests colidirem, o segundo INSERT falha e vira um erro tratado, não um agendamento duplicado.
- **LGPD**: cadastro exige consentimento explícito (`consentimento_lgpd_aceito`) separado de qualquer "aceito os termos" genérico, com data e versão do termo registradas para auditoria. Cadastro manual pelo admin **não** pode marcar esse campo — só o próprio cliente, no primeiro acesso.

## Rodando 100% local (sem Turso, sem S3, sem SMTP)

Modo pensado para desenvolvimento: banco em SQLite (arquivo `local.db`) e
exames salvos em disco (`instance/uploads`), sem precisar de conta Turso
nem bucket S3. É o mesmo código de regras de negócio — só troca a camada
de persistência via `DB_MODE=local` / `STORAGE_MODE=local`.

```bash
chmod +x run_local.sh   # se ainda não tiver permissão de execução
./run_local.sh
```

O script `run_local.sh` faz tudo: cria venv, instala só as dependências
necessárias no modo local, aplica `schema.sql` + `seed.sql` em `local.db`
(via `scripts/init_local_db.py`) e sobe o Flask em `http://localhost:5000`.

Teste rápido depois de subir:
```bash
curl http://localhost:5000/api/health
```

**O que funciona neste modo:** cadastro, login, agendamento (com a trava
de concorrência real via UNIQUE constraint), cancelamento, painel admin,
upload/download de exames (via multipart direto — sem URL pré-assinada,
já que não há limite de payload/timeout rodando localmente).

**O que continua pendente neste modo** (mesmos TODOs do modo cloud): envio
de e-mail (verificação, reset de senha) e verificação de papel admin nas
rotas. Para testar o código de verificação de e-mail sem SMTP configurado,
consulte direto o banco:
```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('local.db')
print(conn.execute('SELECT email, codigo_verificacao FROM usuarios').fetchall())
"
```

Para resetar o banco local do zero:
```bash
rm local.db && python scripts/init_local_db.py
```

---

## Setup para produção (Turso + S3 + Vercel)

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # preencha TURSO_DATABASE_URL, TURSO_AUTH_TOKEN, S3_*, SMTP_*
# no .env, defina DB_MODE=cloud e STORAGE_MODE=s3

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
