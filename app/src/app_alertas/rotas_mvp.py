"""Rotas do MVP para o pitch de BI: verificador, trilha de lições, eventos anônimos e Impacto.

Ligadas ao app em main.py (app.include_router).
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Annotated, Literal

from fastapi import APIRouter, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, field_validator

import eventos
import verificador
from web import AQUI, celular, ids_praticas, pagina, titulos_praticas

router = APIRouter()

RE_APARELHO = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

EXEMPLOS = [
    {"titulo": "Aviso do banco",
     "texto": "BANCO HORIZONTE: identificamos uma compra suspeita de R$ 2.890,00. Se não reconhece, "
              "acesse urgente bit.ly/hz-seguro e evite o bloqueio da sua conta."},
    {"titulo": "Parente com número novo",
     "texto": "Oi mãe, troquei de número, salva esse aqui. Tô precisando muito de um Pix de 850 reais "
              "pra pagar um boleto, te devolvo amanhã."},
    {"titulo": "Pedido de código",
     "texto": "Olá, aqui é da loja onde você anunciou. Para confirmar o cadastro, me passa o código "
              "de 6 dígitos que chegou por SMS."},
]


def aparelho_valido(valor: str | None) -> str | None:
    return valor if valor and RE_APARELHO.match(valor) else None


@lru_cache(maxsize=1)
def conteudo() -> dict:
    return json.loads((AQUI / "conteudo" / "licoes.json").read_text(encoding="utf-8"))


def licao_por_id(licao_id: str) -> dict | None:
    return next((l for l in conteudo()["licoes"] if l["id"] == licao_id), None)


# ---------- verificador ----------

@router.get("/verificar", response_class=HTMLResponse)
def pagina_verificar(request: Request, exemplo: int | None = None):
    texto = EXEMPLOS[exemplo]["texto"] if exemplo is not None and 0 <= exemplo < len(EXEMPLOS) else ""
    return pagina(request, "verificar.html", secao="verificar", exemplos=EXEMPLOS, texto=texto)


@router.post("/verificar", response_class=HTMLResponse)
def verificar_pela_tela(request: Request, texto: Annotated[str, Form(max_length=verificador.TAMANHO_MAXIMO)] = "",
                        aparelho: Annotated[str, Form()] = ""):
    r = verificador.analisar(texto)
    eventos.registrar("analise", {"nivel": r.nivel, "sinais": [s["id"] for s in r.sinais]},
                      aparelho_valido(aparelho))
    licao = licao_por_id(r.licao_sugerida) if r.licao_sugerida else None
    # O texto volta só nesta resposta, para destacar os trechos; não é guardado em lugar nenhum.
    return pagina(request, "resultado.html", secao="verificar", r=r, licao=licao,
                   partes=verificador.partes_destacadas(texto[:verificador.TAMANHO_MAXIMO], r.trechos))


class PedidoAnalise(BaseModel):
    texto: str = Field(max_length=verificador.TAMANHO_MAXIMO)
    aparelho: str | None = None


@router.post("/api/verificar")
def verificar_api(p: PedidoAnalise):
    r = verificador.analisar(p.texto)
    eventos.registrar("analise", {"nivel": r.nivel, "sinais": [s["id"] for s in r.sinais]},
                      aparelho_valido(p.aparelho))
    return r.para_dict()


# ---------- trilha ----------

ICONES_LICOES = {"banco_falso": "banco", "pix_parente": "pessoa", "codigo_verificacao": "codigo",
                 "promocao_falsa": "presente"}


@router.get("/aprender", response_class=HTMLResponse)
def pagina_trilha(request: Request):
    c = celular()
    return pagina(request, "aprender.html", secao="aprender", nivel1=c["nivel1"], aulas=c["aulas"],
                  licoes=conteudo()["licoes"], icones_licoes=ICONES_LICOES)


@router.get("/aprender/teste/{qual}", response_class=HTMLResponse)
def pagina_teste(request: Request, qual: Literal["pre", "pos"]):
    teste = conteudo()["testes"][qual]
    return pagina(request, "teste.html", secao="aprender", qual=qual, teste=teste)


@router.get("/aprender/{licao_id}", response_class=HTMLResponse)
def pagina_licao(request: Request, licao_id: str, origem: str = ""):
    licao = licao_por_id(licao_id)
    if not licao:
        raise HTTPException(404, "lição não encontrada")
    if origem == "analise":
        eventos.registrar("ponte_licao", {"licao": licao_id})
    licoes = conteudo()["licoes"]
    i = licoes.index(licao)
    proxima = licoes[i + 1] if i + 1 < len(licoes) else None
    exemplo = verificador.partes_destacadas(licao["exemplo"], verificador.analisar(licao["exemplo"]).trechos)
    return pagina(request, "licao.html", secao="aprender", licao=licao, numero=i + 1, total=len(licoes), proxima=proxima,
                   exemplo=exemplo)


# ---------- eventos anônimos ----------

class Evento(BaseModel):
    tipo: Literal["licao_inicio", "licao_fim", "quiz_licao", "pre_teste", "pos_teste", "pratica_fim"]
    aparelho: str
    licao: str | None = Field(default=None, max_length=40)
    acertos: int | None = Field(default=None, ge=0, le=20)
    total: int | None = Field(default=None, ge=1, le=20)

    @field_validator("aparelho")
    @classmethod
    def _aparelho(cls, v: str) -> str:
        if not RE_APARELHO.match(v):
            raise ValueError("identificador de aparelho inválido")
        return v


@router.post("/api/eventos", status_code=204)
def receber_evento(e: Evento):
    if e.tipo == "pratica_fim":
        if e.licao not in ids_praticas():
            raise HTTPException(422, "prática desconhecida")
    elif e.licao is not None and not licao_por_id(e.licao):
        raise HTTPException(422, "lição desconhecida")
    if e.tipo in ("quiz_licao", "pre_teste", "pos_teste"):
        if e.acertos is None or e.total is None or e.acertos > e.total:
            raise HTTPException(422, "acertos e total são obrigatórios e acertos <= total")
    dados = {k: v for k, v in {"licao": e.licao, "acertos": e.acertos, "total": e.total}.items() if v is not None}
    eventos.registrar(e.tipo, dados, e.aparelho)
    return Response(status_code=204)


@router.delete("/api/eventos/{aparelho}")
def apagar_meus_dados(aparelho: str):
    if not RE_APARELHO.match(aparelho):
        raise HTTPException(422, "identificador de aparelho inválido")
    return {"apagados": eventos.apagar_aparelho(aparelho)}


# ---------- impacto ----------

@router.get("/api/impacto")
def impacto_api():
    return eventos.impacto()


@router.get("/impacto", response_class=HTMLResponse)
def pagina_impacto(request: Request):
    return pagina(request, "impacto.html", i=eventos.impacto(),
                   titulos={**titulos_praticas(), **{l["id"]: l["titulo"] for l in conteudo()["licoes"]}})


@router.get("/privacidade", response_class=HTMLResponse)
def pagina_privacidade(request: Request):
    return pagina(request, "privacidade.html")
