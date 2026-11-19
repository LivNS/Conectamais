"""Peças compartilhadas pelas telas: templates, nome do app e temas de golpe."""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

AQUI = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=AQUI / "templates")

# Mesmos ids do robô (rpa/src/rpa_alertas/regras.py). Quatro deles têm lição com o mesmo id.
TEMAS = {
    "banco_falso": "Falso contato do banco",
    "pix_parente": "Pedido de dinheiro de falso parente",
    "codigo_verificacao": "Pedido de código de verificação",
    "falso_suporte": "Falso suporte técnico",
    "promocao_falsa": "Falsa promoção ou prêmio",
    "inss_beneficios": "Golpe com aposentadoria ou benefício",
    "outros": "Outros golpes",
}
MESES = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")


def nome_app() -> str:
    return os.environ.get("APP_NOME", "Conecta+")


def data_curta(iso: str | None) -> str:
    """'2026-11-16...' -> '16 nov 2026'."""
    if not iso or len(iso) < 10:
        return ""
    try:
        return f"{int(iso[8:10])} {MESES[int(iso[5:7]) - 1]} {iso[0:4]}"
    except (ValueError, IndexError):
        return ""


templates.env.filters["data_curta"] = data_curta


def pagina(request: Request, nome: str, status_code: int = 200, **ctx):
    return templates.TemplateResponse(request, nome, {"app_nome": nome_app(), "secao": "", **ctx},
                                      status_code=status_code)


@lru_cache(maxsize=None)
def _json(nome: str) -> dict:
    return json.loads((AQUI / "conteudo" / nome).read_text(encoding="utf-8"))


def celular() -> dict:
    """Nível 1 (lições do celular) e aulas do Nível 2."""
    return _json("celular.json")


def golpes() -> list[dict]:
    """Catálogo fixo dos golpes de sempre."""
    return _json("golpes.json")["golpes"]


def ids_praticas() -> set[str]:
    c = celular()
    return {l["id"] for l in c["nivel1"]["licoes"]} | {a["id"] for a in c["aulas"]}


def titulos_praticas() -> dict[str, str]:
    c = celular()
    return {x["id"]: x["titulo"] for x in c["nivel1"]["licoes"] + c["aulas"]}
