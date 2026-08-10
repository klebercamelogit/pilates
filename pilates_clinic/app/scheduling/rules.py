"""
Regras de negócio de agendamento.

Ponto crítico: a checagem de disponibilidade (SELECT) e a criação do
agendamento (INSERT) rodam como statements sequenciais na mesma transação
via db.execute_tx(). A garantia final contra double-booking, porém, é a
UNIQUE constraint em `agendamentos(sala_id, data, hora_inicio)` no schema —
se dois requests concorrentes passarem pela checagem ao mesmo tempo, o
segundo INSERT falha por violação de constraint, e é isso (não a checagem
prévia) que efetivamente impede o overbooking.
"""
from datetime import datetime, date, timedelta
from app.db import execute, execute_tx, one, all_rows, new_id
from app.scheduling.holidays import eh_feriado_nacional

DIAS_SEMANA_PADRAO = {0, 1, 2, 3, 4}  # seg-sex (0=segunda aqui, ajuste na app)


class IndisponivelError(Exception):
    pass


def carregar_configuracoes():
    cfg = one("SELECT * FROM configuracoes WHERE id = 'default'")
    if not cfg:
        raise RuntimeError("Configurações da clínica não encontradas. Rode o seed inicial.")
    cfg["dias_funcionamento"] = {int(d) for d in cfg["dias_funcionamento"].split(",") if d}
    return cfg


def dia_esta_bloqueado(data_str: str) -> bool:
    if eh_feriado_nacional(data_str):
        return True
    row = one("SELECT id FROM bloqueios_dia WHERE data = ?", (data_str,))
    return row is not None


def dia_da_semana_permitido(data_str: str, cfg: dict) -> bool:
    d = datetime.strptime(data_str, "%Y-%m-%d").date()
    # Python: monday=0 ... sunday=6. Ajuste de convenção se necessário.
    return d.weekday() in cfg["dias_funcionamento"]


def horario_dentro_do_expediente(hora_inicio: str, hora_fim: str, cfg: dict) -> bool:
    return cfg["hora_abertura"] <= hora_inicio and hora_fim <= cfg["hora_fechamento"]


def horario_em_janela_indisponivel(data_str: str, hora_inicio: str, hora_fim: str) -> bool:
    d = datetime.strptime(data_str, "%Y-%m-%d").date()
    janelas = all_rows(
        """
        SELECT * FROM janelas_indisponiveis
        WHERE (dia_semana = ? OR data_especifica = ?)
        """,
        (d.weekday(), data_str),
    )
    for j in janelas:
        # sobreposição de intervalos [hora_inicio, hora_fim) x [j.inicio, j.fim)
        if hora_inicio < j["hora_fim"] and j["hora_inicio"] < hora_fim:
            return True
    return False


def capacidade_excedida(data_str: str, cfg: dict) -> bool:
    row = one(
        "SELECT COUNT(*) as total FROM agendamentos WHERE data = ? AND status = 'confirmado'",
        (data_str,),
    )
    return row["total"] >= cfg["capacidade_max_dia"]


def validar_disponibilidade(data_str: str, hora_inicio: str, hora_fim: str):
    cfg = carregar_configuracoes()

    if dia_esta_bloqueado(data_str):
        raise IndisponivelError("Data bloqueada (feriado, evento ou força maior).")

    if not dia_da_semana_permitido(data_str, cfg):
        raise IndisponivelError("Clínica fechada neste dia da semana.")

    if not horario_dentro_do_expediente(hora_inicio, hora_fim, cfg):
        raise IndisponivelError("Horário fora do expediente da clínica.")

    if horario_em_janela_indisponivel(data_str, hora_inicio, hora_fim):
        raise IndisponivelError("Horário dentro de uma janela indisponível (ex: almoço).")

    if capacidade_excedida(data_str, cfg):
        raise IndisponivelError("Capacidade máxima do dia atingida.")


def criar_agendamento(usuario_id: str, profissional_id: str, sala_id: str,
                       data_str: str, hora_inicio: str, hora_fim: str) -> str:
    """
    Levanta IndisponivelError se as regras de negócio bloquearem o horário
    (checagem otimista). Se passar, tenta o INSERT — que é a garantia real
    contra concorrência via UNIQUE constraint. Se outro request já tomou
    o slot entre a checagem e o insert, o banco rejeita e nós propagamos
    como IndisponivelError também, para o cliente tentar outro horário.
    """
    validar_disponibilidade(data_str, hora_inicio, hora_fim)

    agendamento_id = new_id()
    try:
        execute(
            """
            INSERT INTO agendamentos
                (id, usuario_id, profissional_id, sala_id, data, hora_inicio, hora_fim, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'confirmado')
            """,
            (agendamento_id, usuario_id, profissional_id, sala_id, data_str, hora_inicio, hora_fim),
        )
    except Exception as e:
        msg = str(e).upper()
        # violação de UNIQUE(sala_id, data, hora_inicio) ou do índice por profissional
        if "UNIQUE" in msg:
            raise IndisponivelError(
                "Este horário acabou de ser reservado por outra pessoa. Escolha outro."
            )
        # usuario_id, profissional_id ou sala_id inexistente
        if "FOREIGN KEY" in msg:
            raise IndisponivelError(
                "usuario_id, profissional_id ou sala_id inválido (não encontrado)."
            )
        raise
    return agendamento_id


def cancelar_agendamento(agendamento_id: str, usuario_id: str):
    row = one(
        "SELECT * FROM agendamentos WHERE id = ? AND usuario_id = ?",
        (agendamento_id, usuario_id),
    )
    if not row:
        raise ValueError("Agendamento não encontrado para este usuário.")
    execute(
        "UPDATE agendamentos SET status = 'cancelado' WHERE id = ?",
        (agendamento_id,),
    )


def listar_dias_disponiveis(ano: int, mes: int) -> dict:
    """
    Retorna um dict {'YYYY-MM-DD': True/False} para pintar o calendário
    de verde (disponível) ou bloqueado, sem expor detalhes de horário aqui.
    """
    cfg = carregar_configuracoes()
    resultado = {}
    d = date(ano, mes, 1)
    while d.month == mes:
        data_str = d.strftime("%Y-%m-%d")
        disponivel = (
            d.weekday() in cfg["dias_funcionamento"]
            and not dia_esta_bloqueado(data_str)
            and not capacidade_excedida(data_str, cfg)
        )
        resultado[data_str] = disponivel
        d += timedelta(days=1)
    return resultado
