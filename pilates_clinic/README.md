# Sistema de Gestão e Agendamento — Clínica de Pilates

Backend Flask + frontend em templates HTML/JS, banco Turso (libSQL), deploy em Vercel Serverless Functions (zero-config, sem `vercel.json`).

## O que já está implementado

**Cliente:**
- Cadastro com código de verificação enviado por e-mail (SMTP), com opção de reenvio se o e-mail não chegar
- Ativação de conta, login com token de sessão real
- Recuperação de senha: CPF → e-mail ofuscado → confirmação → token de reset, tudo por e-mail
- Prontuário: registro de comorbidades e upload de exames (PDF/JPG/PNG)
- Painel com calendário de agendamento (feriados nacionais automáticos + bloqueios manuais já refletidos), histórico de sessões, cancelamento

**Administrador:**
- Login com verificação real de papel (`papel = 'admin'`), token exigido em toda rota `/api/admin/*`
- Agendamentos do dia, com cancelamento de qualquer cliente (não só o próprio)
- Prontuário do paciente: busca por nome/CPF/e-mail, visualização de comorbidades, exames (com download) e histórico completo
- Cadastro manual de cliente (dispara e-mail de primeiro acesso, nunca expõe senha)
- CRUD de salas e de profissionais — quantidade gerenciável, duração de atendimento individual por profissional (negociável)
- Feriados regionais, eventos (jogos), força maior — cadastrar e remover (feriados nacionais são automáticos, não precisam ser cadastrados)
- Janelas indisponíveis dentro do dia (recorrentes por dia da semana, ou pontuais) — cadastrar e remover
- Configurações: capacidade por dia, horário de abertura/fechamento, duração padrão, dias de funcionamento (qualquer combinação de dias da semana)

**Geral:**
- Frontend responsivo (mobile e desktop) para todas as telas
- Estrutura de pagamento (tabela `pagamentos`) pronta para plugar gateway depois — integração ainda não escrita

## Feriados nacionais — o que está incluído

Calculados automaticamente por ano em `app/scheduling/holidays.py`, sem o admin precisar cadastrar nada: os 8 feriados civis de data fixa (Confraternização Universal, Tiradentes, Dia do Trabalho, Independência, Nossa Senhora Aparecida, Finados, Proclamação da República, Natal) mais a Sexta-feira Santa (móvel, calculada a partir da Páscoa).

**Carnaval e Corpus Christi não estão incluídos** — são amplamente observados no Brasil, mas seu status como feriado nacional decretado varia por município. Cadastre-os manualmente como "feriado regional" pelo painel admin se sua clínica os observa, junto com qualquer feriado municipal específico da sua cidade. Esta lista não substitui a conferência do calendário oficial do seu município.

## O que NÃO está implementado ainda (de propósito)

1. **WhatsApp Business API** — isolado de propósito. Exige conta Business verificada na Meta e aprovação de templates de mensagem antes de qualquer código funcionar. Trate como fase 2, não como parte do MVP.
2. **Gateway de pagamento** — schema pronto, integração não escrita.

Tudo relacionado a autenticação e isolamento de dados entre clientes está implementado agora — não só rotas admin, mas também `/api/agendamentos/minhas/<id>`, `/api/agendamentos` (criar/cancelar), `/api/prontuarios/<id>` e `/api/exames/*` exigem token e verificam que o usuário só acessa os próprios dados (ou é admin). Testado com dois clientes diferentes tentando acessar dados um do outro — bloqueado com 403 em todos os casos.

## Setup — 100% local (sem Turso, sem S3, sem SMTP)

```bash
chmod +x run_local.sh
./run_local.sh
```
Cria venv, instala as dependências do modo local, aplica `schema.sql` + `seed.sql` em `local.db` (SQLite puro), sobe em `http://localhost:5000`. Exames vão para `instance/uploads` (disco local, sem URL pré-assinada — sem sentido em ambiente local).

Teste rápido:
```bash
curl http://localhost:5000/api/health
```

Para testar sem SMTP configurado: os e-mails são simulados via log (não quebram o fluxo). Para pegar o código de verificação ou token de reset sem configurar e-mail:
```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('local.db')
print(conn.execute('SELECT email, codigo_verificacao FROM usuarios').fetchall())
"
```

Resetar o banco local do zero:
```bash
rm local.db && python scripts/init_local_db.py
```

## Setup — produção (Turso + Vercel)

### 1. Criar e popular o banco Turso
```bash
turso db create clinica-pilates
turso db show clinica-pilates --url
turso db tokens create clinica-pilates
```
No **Turso Studio** (SQL console), cole e rode `schema/schema.sql` completo, depois `schema/seed.sql` — selecione todo o texto (Ctrl+A) antes de clicar em "Run", ou o console pode executar só o último statement.

### 2. Configurar variáveis de ambiente no Vercel
| Variável | Valor |
|---|---|
| `DB_MODE` | `cloud` |
| `TURSO_DATABASE_URL` | a URL do banco, com prefixo **`https://`** (não `libsql://` — WebSocket não funciona em serverless) |
| `TURSO_AUTH_TOKEN` | o token gerado acima |
| `STORAGE_MODE` | `local` para testar sem bucket (upload de exame não funciona assim em produção — sistema de arquivos é efêmero), ou `s3` com as variáveis `S3_*` preenchidas |
| `SECRET_KEY` | string aleatória longa |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_USE_TLS` | seu provedor SMTP — Gmail exige Senha de App (não a senha normal da conta), gerada em Conta Google → Segurança → Senhas de app |
| `TERMO_LGPD_VERSAO_ATUAL` | `v1.0` |

### 3. Deploy
Sem `vercel.json` — o Vercel detecta `api/index.py` (que expõe a app Flask) e empacota o projeto inteiro automaticamente (zero-config). Basta enviar o repositório (via `git push` ou upload) e o deploy acontece sozinho.

### 4. Promover um usuário a admin
Não existe cadastro de admin pela interface (proposital). Depois que o usuário já tiver se cadastrado e ativado a conta, promova via SQL no Turso Studio:
```sql
UPDATE usuarios SET papel = 'admin' WHERE email = 'seu-email@exemplo.com';
```

## Por que estas decisões de arquitetura

- **Turso via `libsql-client` puro (modo cloud) ou `sqlite3` da stdlib (modo local)**, nunca SQLAlchemy: o dialeto SQLAlchemy para libSQL é limitado; SQL explícito é mais previsível em serverless. Os dois modos compartilham a mesma interface em `app/db.py`, então o resto do código não sabe qual está rodando.
- **Upload de exames fora do Flask em produção**: Vercel Serverless tem limite de payload bem abaixo de 300MB e timeout curto. O navegador sobe o arquivo direto pro bucket S3-compatible via URL pré-assinada; o Flask só grava a referência.
- **UNIQUE constraint como trava real de concorrência**: a validação de regras de negócio em `rules.py` é uma checagem otimista. Quem impede overbooking de verdade é `UNIQUE(sala_id, data, hora_inicio)` no schema — se dois requests colidirem, o segundo INSERT falha e vira erro tratado, não duplicata.
- **Token de sessão simples, não JWT/Flask-Login**: resolve o problema real (rotas admin sem checagem nenhuma) sem introduzir dependência nova. O modelo de dados (tabela `sessoes`) comporta migrar para JWT depois, se o projeto crescer.
- **LGPD**: cadastro exige consentimento explícito, separado de qualquer "aceito os termos" genérico, com data e versão do termo registradas para auditoria. Cadastro manual pelo admin nunca marca esse campo — só o próprio cliente, no primeiro acesso.
