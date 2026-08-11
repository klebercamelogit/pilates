-- =========================================================
-- SCHEMA - Sistema de Gestão de Clínica de Pilates (Turso/libSQL)
-- =========================================================

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------
-- SESSÕES (token de autenticação emitido no login)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS sessoes (
    id          TEXT PRIMARY KEY,
    usuario_id  TEXT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    token       TEXT NOT NULL UNIQUE,
    criado_em   TEXT NOT NULL DEFAULT (datetime('now')),
    expira_em   TEXT NOT NULL
);

-- ---------------------------------------------------------
-- USUÁRIOS (clientes e administradores)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS usuarios (
    id              TEXT PRIMARY KEY,          -- uuid
    nome            TEXT NOT NULL,
    cpf             TEXT NOT NULL UNIQUE,       -- chave única de identidade
    email           TEXT NOT NULL UNIQUE,
    senha_hash      TEXT,                       -- bcrypt; NULL até ativação
    whatsapp        TEXT NOT NULL,
    cep             TEXT,
    endereco        TEXT,
    numero          TEXT,
    complemento     TEXT,
    idade           INTEGER,
    dia_nascimento  INTEGER,
    mes_nascimento  INTEGER,
    papel           TEXT NOT NULL DEFAULT 'cliente' CHECK (papel IN ('cliente', 'admin')),
    ativo           INTEGER NOT NULL DEFAULT 0,  -- 0 = aguardando confirmação de e-mail
    codigo_verificacao TEXT,
    token_reset_senha  TEXT,
    token_reset_expira TEXT,

    -- --- LGPD: dado de saúde é dado sensível (art. 5º, II) ---
    consentimento_lgpd_aceito     INTEGER NOT NULL DEFAULT 0,
    consentimento_lgpd_data       TEXT,           -- timestamp do aceite
    consentimento_lgpd_versao     TEXT,           -- versão do termo aceito, para auditoria

    criado_em       TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------
-- PRONTUÁRIO / PARECER MÉDICO
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS prontuarios (
    id              TEXT PRIMARY KEY,
    usuario_id      TEXT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    possui_comorbidade INTEGER NOT NULL DEFAULT 0,
    descricao_comorbidade TEXT,
    criado_em       TEXT NOT NULL DEFAULT (datetime('now')),
    atualizado_em   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Arquivos NÃO ficam no banco nem passam pelo Flask/Vercel serverless.
-- Upload é feito direto do navegador para storage de objetos (S3/R2/Vercel Blob)
-- via URL pré-assinada. Aqui guardamos só a referência.
CREATE TABLE IF NOT EXISTS exames_arquivos (
    id              TEXT PRIMARY KEY,
    prontuario_id   TEXT NOT NULL REFERENCES prontuarios(id) ON DELETE CASCADE,
    nome_original   TEXT NOT NULL,
    storage_backend TEXT NOT NULL DEFAULT 'local', -- 'local' | 's3' | 'db'
    storage_key     TEXT,               -- usado quando backend = 'local' ou 's3'
    conteudo        TEXT,               -- usado quando backend = 'db' (conteúdo em base64)
    content_type    TEXT NOT NULL,
    tamanho_bytes   INTEGER NOT NULL CHECK (tamanho_bytes <= 314572800), -- 300MB, teto absoluto
    enviado_em      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------
-- INFRAESTRUTURA DA CLÍNICA
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS salas (
    id          TEXT PRIMARY KEY,
    nome        TEXT NOT NULL,
    ativa       INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS profissionais (
    id                  TEXT PRIMARY KEY,
    usuario_id          TEXT REFERENCES usuarios(id), -- pode ou não ter login no sistema
    nome                TEXT NOT NULL,
    duracao_padrao_min  INTEGER NOT NULL DEFAULT 60,
    cep                 TEXT,
    endereco            TEXT,
    numero              TEXT,
    complemento         TEXT,
    crefito             TEXT,       -- registro no conselho profissional (CREFITO)
    ativo               INTEGER NOT NULL DEFAULT 1
);

-- Configurações gerais (linha única, id fixo = 'default')
CREATE TABLE IF NOT EXISTS configuracoes (
    id                      TEXT PRIMARY KEY DEFAULT 'default',
    capacidade_max_dia      INTEGER NOT NULL DEFAULT 20,
    hora_abertura           TEXT NOT NULL DEFAULT '08:00',
    hora_fechamento         TEXT NOT NULL DEFAULT '18:00',
    dias_funcionamento      TEXT NOT NULL DEFAULT '1,2,3,4,5', -- 0=domingo ... 6=sábado
    duracao_padrao_min      INTEGER NOT NULL DEFAULT 60
);

-- Bloqueios de dia inteiro: feriados nacionais/regionais, jogos da copa, força maior
CREATE TABLE IF NOT EXISTS bloqueios_dia (
    id          TEXT PRIMARY KEY,
    data        TEXT NOT NULL,         -- YYYY-MM-DD
    motivo      TEXT NOT NULL,
    tipo        TEXT NOT NULL CHECK (tipo IN ('feriado_nacional','feriado_regional','evento','forca_maior')),
    UNIQUE(data, tipo, motivo)
);

-- Janelas indisponíveis dentro do dia (ex: almoço 12h-13h), recorrentes ou pontuais
CREATE TABLE IF NOT EXISTS janelas_indisponiveis (
    id              TEXT PRIMARY KEY,
    dia_semana      INTEGER,           -- 0-6, NULL se for data específica
    data_especifica TEXT,              -- YYYY-MM-DD, NULL se for recorrente
    hora_inicio     TEXT NOT NULL,
    hora_fim        TEXT NOT NULL,
    motivo          TEXT
);

-- ---------------------------------------------------------
-- AGENDAMENTOS
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS agendamentos (
    id              TEXT PRIMARY KEY,
    usuario_id      TEXT NOT NULL REFERENCES usuarios(id),
    profissional_id TEXT NOT NULL REFERENCES profissionais(id),
    sala_id         TEXT NOT NULL REFERENCES salas(id),
    data            TEXT NOT NULL,     -- YYYY-MM-DD
    hora_inicio     TEXT NOT NULL,     -- HH:MM
    hora_fim        TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'confirmado'
                        CHECK (status IN ('confirmado','cancelado','concluido','faltou')),
    anotacoes_profissional TEXT,
    criado_em       TEXT NOT NULL DEFAULT (datetime('now')),

    -- >>> Trava de concorrência: impede double-booking na mesma sala/horário <<<
    -- (Constraint parcial não existe em SQLite puro, então tratamos status
    --  cancelado via índice único condicional abaixo)
    UNIQUE(sala_id, data, hora_inicio)
);

-- Índice único adicional por profissional (evita profissional em 2 lugares ao mesmo tempo)
CREATE UNIQUE INDEX IF NOT EXISTS idx_agendamento_profissional_horario
    ON agendamentos(profissional_id, data, hora_inicio)
    WHERE status = 'confirmado';

-- Nota: a UNIQUE(sala_id, data, hora_inicio) acima bloqueia inclusive registros
-- cancelados reocupando o mesmo slot no mesmo insert; na prática, ao cancelar,
-- a aplicação deve fazer UPDATE de status e permitir novo INSERT somente
-- validando via SELECT + INSERT dentro de uma transação (ver app/scheduling/rules.py).

-- ---------------------------------------------------------
-- PAGAMENTOS (estrutura pronta para gateway futuro)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS pagamentos (
    id              TEXT PRIMARY KEY,
    agendamento_id  TEXT NOT NULL REFERENCES agendamentos(id) ON DELETE CASCADE,
    gateway         TEXT,              -- 'stripe' | 'pagseguro' | 'mercadopago'
    gateway_ref     TEXT,              -- id da transação no provedor
    valor_centavos  INTEGER NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pendente'
                        CHECK (status IN ('pendente','pago','estornado','falhou')),
    criado_em       TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------
-- LEMBRETES / WHATSAPP (log de envio, integração é módulo à parte)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS notificacoes_whatsapp (
    id              TEXT PRIMARY KEY,
    agendamento_id  TEXT NOT NULL REFERENCES agendamentos(id) ON DELETE CASCADE,
    tipo            TEXT NOT NULL CHECK (tipo IN ('lembrete_24h','confirmacao','cancelamento')),
    status_envio    TEXT NOT NULL DEFAULT 'pendente' CHECK (status_envio IN ('pendente','enviado','falhou')),
    enviado_em      TEXT
);
