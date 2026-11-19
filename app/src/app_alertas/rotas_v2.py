"""Telas da versão 2: lições do celular (Nível 1), aulas do Nível 2 e o catálogo de golpes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

import banco
import verificador
from rotas_mvp import conteudo
from web import celular, golpes, pagina

router = APIRouter()

TEMPLATE_POR_TIPO = {"passos": "celular_passos.html", "audio": "celular_audio.html",
                     "copiar": "celular_copiar.html", "toque": "celular_toque.html"}
# Tema do alerta (robô) -> golpe do catálogo com a explicação completa.
GOLPE_POR_TEMA = {"banco_falso": "banco", "pix_parente": "parente", "codigo_verificacao": "codigo",
                  "falso_suporte": "central", "promocao_falsa": "premio", "inss_beneficios": "inss"}
NOVOS_NA_LISTA = 3


def partes_marcadas(msg: str) -> list[tuple[str, bool]]:
    """'Texto [[marcado]] texto' -> [(texto, False), (marcado, True), ...]."""
    pedacos = msg.replace("]]", "[[").split("[[")
    return [(t, i % 2 == 1) for i, t in enumerate(pedacos) if t]


# ---------- Nível 1: lições do celular ----------

@router.get("/aprender/celular/{licao_id}", response_class=HTMLResponse)
def licao_celular(request: Request, licao_id: str):
    licoes = celular()["nivel1"]["licoes"]
    l = next((x for x in licoes if x["id"] == licao_id), None)
    if not l:
        raise HTTPException(404, "lição não encontrada")
    i = licoes.index(l)
    proxima = licoes[i + 1] if i + 1 < len(licoes) else None
    return pagina(request, TEMPLATE_POR_TIPO[l["tipo"]], l=l, proxima=proxima)


# ---------- Nível 2: aulas ----------

@router.get("/aprender/aula/{aula_id}", response_class=HTMLResponse)
def aula(request: Request, aula_id: str):
    aulas = celular()["aulas"]
    a = next((x for x in aulas if x["id"] == aula_id), None)
    if not a:
        raise HTTPException(404, "aula não encontrada")
    i = aulas.index(a)
    if i + 1 < len(aulas):
        proxima = {"url": f"/aprender/aula/{aulas[i + 1]['id']}", "titulo": aulas[i + 1]["titulo"]}
    else:
        primeira = conteudo()["licoes"][0]
        proxima = {"url": f"/aprender/{primeira['id']}", "titulo": primeira["titulo"]}
    return pagina(request, "aula.html", a=a, proxima=proxima)


# ---------- golpes: novos (robô + revisão) e de sempre (catálogo) ----------

@router.get("/golpes", response_class=HTMLResponse)
def lista_golpes(request: Request, todos: int = 0):
    publicados = banco.listar("publicado")
    novos = publicados if todos else publicados[:NOVOS_NA_LISTA]
    return pagina(request, "golpes.html", novos=novos, total_novos=len(publicados),
                  tem_mais=not todos and len(publicados) > NOVOS_NA_LISTA, catalogo=golpes())


@router.get("/golpes/alerta/{alerta_id}", response_class=HTMLResponse)
def golpe_alerta(request: Request, alerta_id: str):
    a = next((x for x in banco.listar("publicado") if x["id"] == alerta_id), None)
    if not a:
        raise HTTPException(404, "alerta não encontrado")
    rel_id = GOLPE_POR_TEMA.get(a["tema"])
    relacionado = next((g for g in golpes() if g["id"] == rel_id), None)
    licoes = {l["id"] for l in conteudo()["licoes"]}
    return pagina(request, "golpe_alerta.html", a=a, relacionado=relacionado, licoes=licoes)


@router.get("/golpes/{golpe_id}", response_class=HTMLResponse)
def golpe(request: Request, golpe_id: str):
    g = next((x for x in golpes() if x["id"] == golpe_id), None)
    if not g:
        raise HTTPException(404, "golpe não encontrado")
    return pagina(request, "golpe.html", g=g, partes=partes_marcadas(g["msg"]))


# O verificador continua sendo a fonte da verdade: os exemplos do catálogo precisam acender sinais nele.
def exemplos_do_catalogo_sao_detectados() -> list[str]:
    sem_sinal = []
    for g in golpes():
        texto = "".join(t for t, _ in partes_marcadas(g["msg"]))
        if verificador.analisar(texto).nivel in ("inconclusivo",):
            sem_sinal.append(g["id"])
    return sem_sinal
