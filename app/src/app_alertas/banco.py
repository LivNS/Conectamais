"""Alertas de golpes em SQLite: rascunhos do robô, revisão humana e publicação.

Mesmo arquivo de banco dos eventos anônimos (DATABASE_PATH). Nada aqui guarda dado de pessoas.
"""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

CAMPOS = ("id", "titulo", "tema", "tema_rotulo", "resumo_simples", "como_se_proteger", "fonte_nome",
          "link_fonte", "data_publicacao", "precisa_revisar_tema", "status", "origem", "criado_em",
          "revisado_em", "motivo_rejeicao")


def _caminho() -> str:
    return os.environ.get("DATABASE_PATH") or "dados_app.sqlite3"


@contextmanager
def _conexao():
    caminho = _caminho()
    pasta = os.path.dirname(caminho)
    if pasta:
        os.makedirs(pasta, exist_ok=True)
    con = sqlite3.connect(caminho)
    con.row_factory = sqlite3.Row
    _criar(con)
    try:
        yield con
        con.commit()
    finally:
        con.close()


def _criar(con) -> None:
    con.execute("""CREATE TABLE IF NOT EXISTS alertas (
        id TEXT PRIMARY KEY, titulo TEXT NOT NULL, tema TEXT NOT NULL, tema_rotulo TEXT NOT NULL,
        resumo_simples TEXT NOT NULL, como_se_proteger TEXT NOT NULL, fonte_nome TEXT NOT NULL,
        link_fonte TEXT NOT NULL, data_publicacao TEXT NOT NULL DEFAULT '',
        precisa_revisar_tema INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL, origem TEXT NOT NULL,
        criado_em TEXT NOT NULL, revisado_em TEXT, motivo_rejeicao TEXT)""")


def iniciar() -> None:
    with _conexao():
        pass


def agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _dict(linha) -> dict:
    d = dict(linha)
    d["como_se_proteger"] = json.loads(d["como_se_proteger"])
    d["precisa_revisar_tema"] = bool(d["precisa_revisar_tema"])
    return d


def inserir_rascunho(dados: dict) -> bool:
    """Insere um rascunho. Devolve False se o id já existe (o robô recebe 409)."""
    dados = {**dados, "status": dados.get("status") or "pendente_revisao"}
    valores = [json.dumps(dados[c], ensure_ascii=False) if c == "como_se_proteger"
               else int(dados[c]) if c == "precisa_revisar_tema" else dados.get(c) for c in CAMPOS]
    with _conexao() as con:
        try:
            con.execute(f"INSERT INTO alertas ({', '.join(CAMPOS)}) VALUES ({', '.join('?' * len(CAMPOS))})",
                        valores)
        except sqlite3.IntegrityError:
            return False
    return True


def listar(status: str) -> list[dict]:
    ordem = "COALESCE(revisado_em, criado_em) DESC" if status == "publicado" else "criado_em"
    with _conexao() as con:
        return [_dict(l) for l in con.execute(f"SELECT * FROM alertas WHERE status = ? ORDER BY {ordem}", (status,))]


def contar() -> dict:
    with _conexao() as con:
        return {s: n for s, n in con.execute("SELECT status, COUNT(*) FROM alertas GROUP BY status")}


def revisar(id_: str, aprovar: bool, motivo: str = "", tema: str | None = None,
            tema_rotulo: str | None = None) -> str:
    with _conexao() as con:
        linha = con.execute("SELECT status FROM alertas WHERE id = ?", (id_,)).fetchone()
        if not linha:
            return "nao_encontrado"
        if linha["status"] != "pendente_revisao":
            return "ja_revisado"
        if aprovar:
            if tema:
                con.execute("UPDATE alertas SET tema = ?, tema_rotulo = ?, precisa_revisar_tema = 0 WHERE id = ?",
                            (tema, tema_rotulo, id_))
            con.execute("UPDATE alertas SET status = 'publicado', revisado_em = ? WHERE id = ?", (agora(), id_))
        else:
            con.execute("UPDATE alertas SET status = 'rejeitado', revisado_em = ?, motivo_rejeicao = ? WHERE id = ?",
                        (agora(), motivo.strip()[:300], id_))
    return "ok"


def vazio() -> bool:
    with _conexao() as con:
        return con.execute("SELECT COUNT(*) FROM alertas").fetchone()[0] == 0
