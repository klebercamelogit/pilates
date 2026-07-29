-- Rodar uma única vez após aplicar schema.sql
INSERT OR IGNORE INTO configuracoes (id, capacidade_max_dia, hora_abertura, hora_fechamento, dias_funcionamento, duracao_padrao_min)
VALUES ('default', 20, '08:00', '18:00', '0,1,2,3,4', 60);
-- dias_funcionamento usa weekday() do Python: 0=segunda ... 6=domingo

INSERT OR IGNORE INTO salas (id, nome, ativa) VALUES ('sala-1', 'Sala 1', 1);

INSERT OR IGNORE INTO profissionais (id, usuario_id, nome, duracao_padrao_min, ativo)
VALUES ('prof-1', NULL, 'Instrutor(a) Principal', 60, 1);
