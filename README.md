# Sistema de Gestão e Agendamento — Clínica de Pilates

Backend Flask + frontend em templates HTML/JS, banco Turso (libSQL), deploy em Vercel Serverless Functions (zero-config, sem `vercel.json`).

## O que já está implementado

**Cliente:**
- Cadastro com código de verificação enviado por e-mail (SMTP), com opção de reenvio se o e-mail não chegar
- Ativação de conta, login com token de sessão real
- Recuperação de senha direta por e-mail (sem CPF)
- **Meu prontuário**: registro de comorbidades (texto livre) e upload de exames (PDF/JPG/PNG), com listagem e download dos já enviados
- Painel com calendário de agendamento (feriados nacionais automáticos + bloqueios manuais já refletidos, profissional exibido com CREFITO quando cadastrado), histórico de sessões, cancelamento

**Administrador:**
- Login com verificação real de papel (`papel = 'admin'`), token exigido em toda rota `/api/admin/*`
- Agendamentos do dia, com cancelamento de qualquer cliente (não só o próprio)
- Prontuário do paciente: busca por nome/e-mail, visualização de comorbidades, exames (com download) e histórico completo
- Cadastro manual de cliente (dispara e-mail de primeiro acesso, nunca expõe senha)
- **CRUD completo de salas e de profissionais** — criar, editar, ativar/desativar e excluir. Exclusão é bloqueada com mensagem clara se já houver agendamentos vinculados (usar "desativar" nesse caso, para preservar o histórico). Profissional tem CEP (com autofill), endereço, número, complemento e CREFITO
- Feriados regionais, eventos (jogos), força maior — cadastrar e remover (feriados nacionais são automáticos, não precisam ser cadastrados)
- Janelas indisponíveis dentro do dia (recorrentes por dia da semana, ou pontuais) — cadastrar e remover
- Configurações: capacidade por dia, horário de abertura/fechamento, duração padrão, dias de funcionamento (qualquer combinação de dias da semana)

**Geral:**
- Frontend responsivo (mobile e desktop) para todas as telas
- Estrutura de pagamento (tabela `pagamentos`) pronta para plugar gateway depois — integração ainda não escrita

## ⚠️ Migração necessária no banco em produção (rodada atual)

Esta versão adiciona: bloqueio de agenda por profissional, e a tabela de solicitações do chatbot. Rode no Turso Studio (Ctrl+A antes de "Run"):
```sql
ALTER TABLE bloqueios_dia ADD COLUMN profissional_id TEXT REFERENCES profissionais(id);
ALTER TABLE janelas_indisponiveis ADD COLUMN profissional_id TEXT REFERENCES profissionais(id);

CREATE TABLE IF NOT EXISTS chatbot_solicitacoes (
    id                  TEXT PRIMARY KEY,
    tipo_atendimento    TEXT NOT NULL CHECK (tipo_atendimento IN ('pilates', 'fisioterapia', 'outro')),
    nome                TEXT NOT NULL,
    email               TEXT NOT NULL,
    telefone            TEXT,
    comorbidade         TEXT,
    sala_desejada       TEXT,
    profissional_desejado TEXT,
    data_desejada       TEXT,
    horario_desejado    TEXT,
    mensagem            TEXT,
    cliente_ja_cadastrado INTEGER NOT NULL DEFAULT 0,
    atendido            INTEGER NOT NULL DEFAULT 0,
    criado_em           TEXT NOT NULL DEFAULT (datetime('now'))
);
```
`profissional_id` fica `NULL` para bloqueios que valem para todos os profissionais — só precisa ser preenchido quando o bloqueio é específico de um.

## Correção de bug: upload em modo `db` falhava mesmo com schema correto

Se você criou o banco Turso bem no início do projeto, a coluna `storage_key` de `exames_arquivos` foi criada como `NOT NULL` (schema antigo). Como só aplicamos migrações via `ALTER TABLE ADD COLUMN` depois, essa restrição nunca foi removida — e o modo `db` nunca preenchia essa coluna (o conteúdo vai em `conteudo`, não em `storage_key`), então todo upload falhava com erro genérico do Turso, não importa o tamanho do arquivo.

**Corrigido no código** (não precisa de migração nova): o upload em modo `db` agora sempre preenche `storage_key` com um valor placeholder (`db:<id-do-exame>`), satisfazendo a constraint em qualquer banco, novo ou antigo. Testado reproduzindo o erro exato contra um banco simulando o schema legado, e confirmando que a correção resolve.

## ⚠️ Migração necessária no banco em produção (rodada mais recente)

```sql
ALTER TABLE usuarios ADD COLUMN deve_trocar_senha INTEGER NOT NULL DEFAULT 0;
```

## Senha padrão para novo administrador

Ao cadastrar um administrador pelo painel, a conta é criada já ativa com a senha **`123456`** — não depende mais de e-mail funcionando para o primeiro acesso. Em troca disso, a conta fica marcada com `deve_trocar_senha = 1`: o login funciona normalmente, mas **toda rota `/api/admin/*` fica bloqueada (403)** até a pessoa trocar a senha em `/trocar-senha-obrigatoria` — isso é forçado tanto no frontend (redirecionamento automático após login) quanto no backend (o bloqueio não depende só do frontend se comportar direito).

Um e-mail ainda é enviado avisando sobre a senha temporária, mas não é mais necessário para o acesso funcionar — só é um aviso complementar.

## Correção de responsividade mobile (rodada mais recente)

Dois problemas reais de layout mobile corrigidos:

1. **Cabeçalho da sidebar gigante com espaço vazio**: no CSS Grid, quando a tela empilha em coluna única (mobile), as linhas do grid esticam pra preencher a altura disponível por padrão — mesmo com pouco conteúdo. Corrigido com `grid-auto-rows: min-content` e `align-content: start` no `.app-shell`.
2. **Menu de navegação cortando texto**: a versão anterior deixava os itens do menu em rolagem horizontal, sem indicação visual de que dava pra arrastar — a maioria das pessoas não descobre isso sozinha. Trocado por um menu hambúrguer (☰) padrão: clica, abre um dropdown com a lista completa, sem cortar nada. Funciona no painel do cliente e no admin.

## Paleta de cores atualizada (rodada mais recente)

A identidade visual trocou de oliva/bronze para azul-acinzentado, com gradiente de marca (`--gradiente-marca`, de navy escuro a periwinkle claro) usado no fundo das telas de login/cadastro e na barra lateral do painel/admin — mesma estrutura de variáveis CSS de antes, só os valores mudaram, então nenhum template precisou ser tocado por causa disso.

## Redesign visual "Mouve Pilates Studio" (rodada mais recente)

**Sem migração de banco necessária desta vez** — foi só frontend (CSS, templates, um asset de imagem novo).

- Paleta trocada de teal para oliva/bronze (`#758755`/`#5A6140`), seguindo referência visual fornecida
- Nome do sistema: "Mouve Pilates Studio", com logo real em `app/static/img/logo.png`
- Painel do cliente reestruturado: o calendário de agendamento agora fica dentro da barra lateral (verde-oliva), não mais numa coluna ao lado do formulário — a área principal (branca) mostra só o título e o formulário de horário
- Indicador de etapas decorativo ("01 Data — 02 Detalhes") e campos de sala/profissional/horário com ícone — visual apenas, o comportamento funcional (validação, submissão) não mudou
- Se quiser trocar a logo depois, é só substituir o arquivo `app/static/img/logo.png` por outro do mesmo nome — não precisa mexer em nenhum template

## Novidades desta rodada

- **Bloqueio de agenda por profissional**: ao criar um bloqueio de dia ou janela indisponível, o admin pode escolher "todos os profissionais" (comportamento anterior) ou um profissional específico.
- **Agendamento em vários dias**: o cliente pode marcar o checkbox "Agendar em vários dias" e selecionar múltiplas datas no calendário — mesmo profissional, sala e horário para todas. Cada dia é validado independentemente; se um conflitar, os outros ainda são confirmados (resultado por dia, não tudo-ou-nada).
- **Prontuário do paciente (admin)**: agora é uma lista filtrável por nome/e-mail (só pacientes que já enviaram algo), com ícones por linha — visualizar, baixar, excluir, incluir nova evidência. Quando há só 1 exame, baixar/excluir agem direto; com vários, abre o detalhe para escolher qual.
- **Exclusão de exame**: endpoint novo (`DELETE /api/exames/<id>`), não existia antes.
- **Indicador de arquivo nos agendamentos do dia**: ícone 📎 aparece ao lado do nome do cliente quando ele tem exame salvo no prontuário.
- **Botão de WhatsApp**: nos agendamentos do dia e nas solicitações do chatbot, se o cliente tem WhatsApp cadastrado, aparece um botão que abre `wa.me` com mensagem pré-preenchida — **não é a API oficial do WhatsApp Business** (essa continua exigindo aprovação da Meta, fora de escopo), é um link direto que abre o WhatsApp do próprio admin para conversar manualmente.
- **Chatbot público**: widget de conversa guiada por botões (sem IA) nas telas de login e cadastro. Coleta e-mail, nome (se novo), telefone, comorbidade e preferências de agendamento, e registra como uma "solicitação" — não cria agendamento nem edita prontuário diretamente, por segurança (ver decisão abaixo). O admin vê e gerencia essas solicitações numa aba nova.

### Por que o chatbot não agenda nem anexa exame diretamente

Sem exigir senha no meio da conversa, não tem como confirmar que quem está digitando um e-mail é realmente o dono daquela conta. Se o chatbot gravasse direto no prontuário de quem quer que informasse aquele e-mail, qualquer pessoa poderia anexar arquivo ou ver dado de outro cliente só sabendo o e-mail dele. Por isso o chatbot **coleta a intenção** (o que a pessoa quer, dados de contato) como uma solicitação pendente, e quem finaliza o agendamento de verdade — ou orienta a fazer login para enviar exame — é o admin, revisando manualmente.

## ⚠️ Migrações de rodadas anteriores (se ainda não aplicadas)

Upload de exame guardado direto no Turso (`STORAGE_MODE=db`):
```sql
ALTER TABLE exames_arquivos ADD COLUMN storage_backend TEXT NOT NULL DEFAULT 'local';
ALTER TABLE exames_arquivos ADD COLUMN conteudo TEXT;
```
`storage_key` continua existindo e sendo usado nos modos `local`/`s3`; `conteudo` é novo e só é preenchido no modo `db`. **Sobre o limite de 3MB nesse modo:** o Vercel limita o corpo de requisição de qualquer função serverless a 4.5MB (infraestrutura, não contornável), então `STORAGE_MODE=db` aceita só até ~3MB por arquivo. Arquivos maiores só funcionam com `STORAGE_MODE=s3` (bucket, até 300MB).

Campos de endereço/CREFITO em `usuarios` e `profissionais`:
```sql
ALTER TABLE usuarios ADD COLUMN numero TEXT;

ALTER TABLE profissionais ADD COLUMN cep TEXT;
ALTER TABLE profissionais ADD COLUMN endereco TEXT;
ALTER TABLE profissionais ADD COLUMN numero TEXT;
ALTER TABLE profissionais ADD COLUMN complemento TEXT;
ALTER TABLE profissionais ADD COLUMN crefito TEXT;
```
Sem isso, cadastrar profissional ou cliente vai falhar com erro de "table has no column named ...".

## CPF removido do fluxo de usuário

CPF não é mais coletado em nenhuma tela (cadastro público nem cadastro manual pelo admin). A recuperação de senha, que antes usava CPF como identificador (CPF → e-mail ofuscado → confirmação), agora é direta por e-mail: o cliente informa o e-mail e recebe um link/token de redefinição, sem etapa intermediária.

**Detalhe técnico:** a coluna `cpf` continua existindo no schema como `NOT NULL UNIQUE` — de propósito, para não exigir mais uma migração no banco em produção. O backend preenche automaticamente com um valor interno opaco (`sem-cpf-<uuid>`) que nunca é exibido nem usado para nada, só satisfaz a constraint do banco. Verificação de duplicata no cadastro passou a ser por e-mail, não mais por CPF.

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
| `STORAGE_MODE` | `local` para testar sem bucket (⚠️ upload de exame **não vai funcionar de verdade** — o sistema de arquivos do Vercel é só leitura fora de `/tmp`, e mesmo `/tmp` não persiste entre execuções; o resto do sistema funciona normalmente), ou `s3` com as variáveis `S3_*` preenchidas (necessário para upload de exame funcionar em produção) |
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
- **Upload de exames fora do Flask em produção**: Vercel Serverless tem limite de payload bem abaixo de 300MB e timeout curto. O navegador sobe o arquivo direto pro bucket S3-compatible via URL pré-assinada; o Flask só grava a referência. **Em modo local, os caminhos de arquivo são sempre absolutos** (`os.path.abspath`) — Flask's `send_file()` resolve caminhos relativos em relação ao `root_path` da aplicação, não ao diretório de trabalho do processo, o que causava um bug real (upload e download apontavam para pastas diferentes até essa correção).
- **UNIQUE constraint como trava real de concorrência**: a validação de regras de negócio em `rules.py` é uma checagem otimista. Quem impede overbooking de verdade é `UNIQUE(sala_id, data, hora_inicio)` no schema — se dois requests colidirem, o segundo INSERT falha e vira erro tratado, não duplicata.
- **Token de sessão simples, não JWT/Flask-Login**: resolve o problema real (rotas admin sem checagem nenhuma) sem introduzir dependência nova. O modelo de dados (tabela `sessoes`) comporta migrar para JWT depois, se o projeto crescer.
- **LGPD**: cadastro exige consentimento explícito, separado de qualquer "aceito os termos" genérico, com data e versão do termo registradas para auditoria. Cadastro manual pelo admin nunca marca esse campo — só o próprio cliente, no primeiro acesso.
