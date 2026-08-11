"""
Feriados nacionais brasileiros, calculados automaticamente por ano —
o administrador não precisa cadastrar esses manualmente (diferente de
feriados regionais, jogos e força maior, que continuam em `bloqueios_dia`
e são cadastrados pelo admin).

IMPORTANTE — escopo desta lista: inclui os 8 feriados civis de data fixa
reconhecidos nacionalmente e a Sexta-feira Santa (móvel, calculada a partir
da Páscoa). Não inclui Carnaval nem Corpus Christi: são amplamente
observados no Brasil, mas seu status como feriado nacional decretado
(em vs. ponto facultativo, e variação municipal) é menos uniforme —
se a sua clínica os observa, cadastre-os manualmente como
`feriado_regional` ou `evento` pelo painel admin, junto com qualquer
feriado municipal específico da sua cidade. Esta função não substitui
conferência do calendário oficial do seu município.
"""
from datetime import date, timedelta


def _pascoa(ano: int) -> date:
    """Domingo de Páscoa via algoritmo de Meeus/Jones/Butcher (gregoriano)."""
    a = ano % 19
    b = ano // 100
    c = ano % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = ((h + l - 7 * m + 114) % 31) + 1
    return date(ano, mes, dia)


def feriados_nacionais(ano: int) -> set:
    """Retorna um set de strings 'YYYY-MM-DD' com os feriados nacionais do ano."""
    pascoa = _pascoa(ano)
    sexta_santa = pascoa - timedelta(days=2)

    datas = [
        date(ano, 1, 1),    # Confraternização Universal
        date(ano, 4, 21),   # Tiradentes
        date(ano, 5, 1),    # Dia do Trabalho
        sexta_santa,        # Sexta-feira Santa (móvel)
        date(ano, 9, 7),    # Independência
        date(ano, 10, 12),  # Nossa Senhora Aparecida
        date(ano, 11, 2),   # Finados
        date(ano, 11, 15),  # Proclamação da República
        date(ano, 12, 25),  # Natal
    ]
    return {d.strftime("%Y-%m-%d") for d in datas}


def eh_feriado_nacional(data_str: str) -> bool:
    ano = int(data_str.split("-")[0])
    return data_str in feriados_nacionais(ano)
