"""Eventos anônimos de uso e indicadores da página Impacto.

Nada aqui identifica uma pessoa: o "aparelho" é um número aleatório criado no próprio
navegador, sem nome, telefone ou e-mail. O texto das mensagens analisadas nunca chega aqui.
"""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

TIPOS = {
    "analise",        # dados: nivel, sinais (ids)
    "ponte_licao",    # dados: licao  (lição aberta a partir de um resultado)
    "licao_inicio",   # dados: licao
    "licao_fim",      # dados: licao
    "quiz_licao",     # dados: licao, acertos, total
    "pre_teste",      # dados: acertos, total
    "pos_teste",      # dados: acertos, total
    "pratica_fim",    # dados: licao (lição do celular ou aula do Nível 2 concluída)
}
CAMPOS_PERMITIDOS = {"nivel", "sinais", "licao", "acertos", "total"}
NIVEIS = ("alto", "medio", "baixo", "inconclusivo")
AMOSTRA_MINIMA = 10


def _caminho() -> str:
    return os.environ.get("EVENTOS_DB_PATH") or os.environ.get("DATABASE_PATH") or "dados_app.sqlite3"


@contextmanager
def _conexao():
    caminho = _caminho()
    pasta = os.path.dirname(caminho)
    if pasta:
        os.makedirs(pasta, exist_ok=True)
    con = sqlite3.connect(caminho)
    _criar_tabela(con)   # idempotente e barato; sobrevive a disco efêmero apagado
    try:
        yield con
        con.commit()
    finally:
        con.close()


def _criar_tabela(con) -> None:
    con.execute("""CREATE TABLE IF NOT EXISTS eventos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            criado_em TEXT NOT NULL,
            aparelho TEXT,
            tipo TEXT NOT NULL,
            dados TEXT NOT NULL DEFAULT '{}')""")
    con.execute("CREATE INDEX IF NOT EXISTS ix_eventos_tipo ON eventos(tipo)")
    con.commit()


def iniciar() -> None:
    with _conexao():
        pass


def registrar(tipo: str, dados: dict | None = None, aparelho: str | None = None) -> None:
    if tipo not in TIPOS:
        raise ValueError(f"tipo de evento desconhecido: {tipo}")
    limpos = {k: v for k, v in (dados or {}).items() if k in CAMPOS_PERMITIDOS}
    with _conexao() as con:
        con.execute("INSERT INTO eventos (criado_em, aparelho, tipo, dados) VALUES (?, ?, ?, ?)",
                    (datetime.now(timezone.utc).isoformat(timespec="seconds"), aparelho, tipo,
                     json.dumps(limpos, ensure_ascii=False)))


def apagar_aparelho(aparelho: str) -> int:
    with _conexao() as con:
        cur = con.execute("DELETE FROM eventos WHERE aparelho = ?", (aparelho,))
        return cur.rowcount


def _linhas(con, tipo):
    return [(a, json.loads(d)) for a, d in
            con.execute("SELECT aparelho, dados FROM eventos WHERE tipo = ? ORDER BY id", (tipo,))]


def _pct(parte: float, todo: float) -> float | None:
    return round(100 * parte / todo, 1) if todo else None


def impacto() -> dict:
    """Indicadores agregados. Só números, nunca eventos individuais."""
    with _conexao() as con:
        analises = _linhas(con, "analise")
        pontes = _linhas(con, "ponte_licao")
        inicios = _linhas(con, "licao_inicio")
        fins = _linhas(con, "licao_fim")
        quizzes = _linhas(con, "quiz_licao")
        pres = _linhas(con, "pre_teste")
        poss = _linhas(con, "pos_teste")
        praticas = _linhas(con, "pratica_fim")

    por_nivel = {n: 0 for n in NIVEIS}
    for _, d in analises:
        if d.get("nivel") in por_nivel:
            por_nivel[d["nivel"]] += 1
    com_risco = por_nivel["alto"] + por_nivel["medio"] + por_nivel["baixo"]

    # Ganho de conhecimento: só aparelhos que fizeram pré e pós (pareado), último resultado de cada.
    pre_ap = {a: d for a, d in pres if a}
    pos_ap = {a: d for a, d in poss if a}
    pareados = [a for a in pos_ap if a in pre_ap]

    def media(dic, chaves):
        tot = sum(dic[a].get("total", 0) for a in chaves)
        ac = sum(dic[a].get("acertos", 0) for a in chaves)
        return _pct(ac, tot)

    pre_media = media(pre_ap, pareados)
    pos_media = media(pos_ap, pareados)
    ganho = round(pos_media - pre_media, 1) if pre_media is not None and pos_media is not None else None

    licoes_concluidas = {}
    for _, d in fins:
        licoes_concluidas[d.get("licao")] = licoes_concluidas.get(d.get("licao"), 0) + 1
    tot_q = sum(d.get("total", 0) for _, d in quizzes)
    ac_q = sum(d.get("acertos", 0) for _, d in quizzes)

    aparelhos_trilha = {a for a, _ in pres + inicios if a}
    capacitados = len(set(pos_ap))

    praticas_por_licao: dict[str, int] = {}
    for _, d in praticas:
        praticas_por_licao[d.get("licao")] = praticas_por_licao.get(d.get("licao"), 0) + 1

    return {
        "praticas_concluidas": len(praticas),
        "praticas_por_licao": praticas_por_licao,
        "pessoas_praticando": len({a for a, _ in praticas if a}),
        "analises_total": len(analises),
        "analises_por_nivel": por_nivel,
        "ponte_analise_licao_pct": _pct(len(pontes), com_risco),
        "pessoas_na_trilha": len(aparelhos_trilha),
        "pessoas_capacitadas": capacitados,
        "conclusao_trilha_pct": _pct(capacitados, len(aparelhos_trilha)),
        "licoes_concluidas": sum(licoes_concluidas.values()),
        "licoes_concluidas_por_tema": licoes_concluidas,
        "acerto_quizzes_licoes_pct": _pct(ac_q, tot_q),
        "amostra_pareada": len(pareados),
        "acerto_pre_pct": pre_media,
        "acerto_pos_pct": pos_media,
        "ganho_conhecimento_pp": ganho,
        "amostra_pequena": len(pareados) < AMOSTRA_MINIMA,
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
