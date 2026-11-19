"""App do Conecta+: verificador, trilha de lições, alertas de golpes (RPA + revisão humana) e Impacto.

Variáveis de ambiente:
  DATABASE_PATH            arquivo SQLite (alertas + eventos anônimos)
  RPA_API_TOKEN            token que o robô usa em POST /api/alertas/rascunhos
  ADMIN_USUARIO, ADMIN_SENHA   login da tela /revisao
  APP_NOME                 nome exibido (padrão: Conecta+)
  ALERTAS_DEMONSTRACAO     "0" desliga os 4 alertas de demonstração no banco vazio
"""
from __future__ import annotations

import os
import secrets
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))  # módulos irmãos (banco, eventos, verificador...) importados pelo nome

from fastapi import Depends, FastAPI, Form, HTTPException, Request  # noqa: E402
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse  # noqa: E402
from fastapi.security import (HTTPAuthorizationCredentials, HTTPBasic, HTTPBasicCredentials,  # noqa: E402
                              HTTPBearer)
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel, Field, HttpUrl  # noqa: E402

import banco  # noqa: E402
import dados_iniciais  # noqa: E402
import eventos  # noqa: E402
from rotas_mvp import router as rotas_mvp  # noqa: E402
from rotas_v2 import router as rotas_v2  # noqa: E402
from web import TEMAS, celular, pagina  # noqa: E402


@asynccontextmanager
async def ciclo(_app: FastAPI):
    banco.iniciar()
    eventos.iniciar()
    if os.environ.get("ALERTAS_DEMONSTRACAO", "1") != "0":
        dados_iniciais.carregar_se_vazio()
    yield


app = FastAPI(title="Conecta+ — API do MVP", version="1.0.0", lifespan=ciclo)
app.mount("/static", StaticFiles(directory=AQUI / "static"), name="static")
app.include_router(rotas_mvp)
app.include_router(rotas_v2)

bearer = HTTPBearer(auto_error=False)
basic = HTTPBasic(realm="Revisao de alertas")


# ---------- segurança ----------

def exigir_robo(cred: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
    esperado = os.environ.get("RPA_API_TOKEN", "")
    if not esperado:
        raise HTTPException(503, "RPA_API_TOKEN não configurado no servidor")
    if cred is None or not secrets.compare_digest(cred.credentials.encode(), esperado.encode()):
        raise HTTPException(401, "token inválido", headers={"WWW-Authenticate": "Bearer"})


def exigir_revisor(cred: Annotated[HTTPBasicCredentials, Depends(basic)]) -> str:
    usuario, senha = os.environ.get("ADMIN_USUARIO", ""), os.environ.get("ADMIN_SENHA", "")
    if not usuario or not senha:
        raise HTTPException(503, "ADMIN_USUARIO/ADMIN_SENHA não configurados no servidor")
    ok = secrets.compare_digest(cred.username.encode(), usuario.encode()) and \
        secrets.compare_digest(cred.password.encode(), senha.encode())
    if not ok:
        raise HTTPException(401, "acesso negado", headers={"WWW-Authenticate": "Basic"})
    return cred.username


# ---------- contrato com o robô (não mudar sem mudar o RPA) ----------

class RascunhoEntrada(BaseModel):
    id: str = Field(min_length=8, max_length=64, pattern=r"^[a-f0-9]+$")
    titulo: str = Field(min_length=10, max_length=300)
    tema: str = Field(max_length=40)
    tema_rotulo: str = Field(max_length=120)
    resumo_simples: str = Field(min_length=1, max_length=600)
    como_se_proteger: list[str] = Field(min_length=1, max_length=6)
    fonte_nome: str = Field(max_length=200)
    link_fonte: HttpUrl
    data_publicacao: str = ""
    precisa_revisar_tema: bool = False
    status: str = "pendente_revisao"
    origem: str = "rpa"
    criado_em: str


@app.post("/api/alertas/rascunhos", status_code=201, dependencies=[Depends(exigir_robo)])
def receber_rascunho(r: RascunhoEntrada):
    dados = r.model_dump()
    dados["link_fonte"] = str(r.link_fonte)
    dados["status"] = "pendente_revisao"  # o robô nunca publica sozinho
    if not banco.inserir_rascunho(dados):
        raise HTTPException(409, "rascunho já recebido")
    return {"id": r.id, "status": "pendente_revisao"}


@app.get("/api/alertas")
def alertas_publicados():
    return banco.listar("publicado")


@app.get("/api/alertas/pendentes", dependencies=[Depends(exigir_revisor)])
def alertas_pendentes():
    return banco.listar("pendente_revisao")


class Decisao(BaseModel):
    motivo: str = ""
    tema: str | None = None


def _aplicar(id_: str, aprovar: bool, motivo: str = "", tema: str | None = None):
    if tema and tema not in TEMAS:
        raise HTTPException(422, "tema desconhecido")
    if not aprovar and not motivo.strip():
        raise HTTPException(422, "informe o motivo da rejeição")
    res = banco.revisar(id_, aprovar, motivo, tema, TEMAS.get(tema) if tema else None)
    if res == "nao_encontrado":
        raise HTTPException(404, "alerta não encontrado")
    if res == "ja_revisado":
        raise HTTPException(409, "alerta já revisado")


@app.post("/api/alertas/{id_}/aprovar", dependencies=[Depends(exigir_revisor)])
def aprovar(id_: str, d: Decisao | None = None):
    _aplicar(id_, True, tema=(d.tema if d else None))
    return {"id": id_, "status": "publicado"}


@app.post("/api/alertas/{id_}/rejeitar", dependencies=[Depends(exigir_revisor)])
def rejeitar(id_: str, d: Decisao):
    _aplicar(id_, False, motivo=d.motivo)
    return {"id": id_, "status": "rejeitado"}


# ---------- telas ----------

@app.get("/", response_class=HTMLResponse)
def inicio(request: Request):
    publicados = banco.listar("publicado")
    return pagina(request, "inicio.html", ultimo=publicados[0] if publicados else None,
                  ids_nivel1=[l["id"] for l in celular()["nivel1"]["licoes"]])


@app.get("/alertas")
def pagina_alertas():
    # Endereço antigo (citado na documentação do RPA): os alertas agora ficam em "Golpes".
    return RedirectResponse("/golpes", status_code=307)


@app.get("/revisao", response_class=HTMLResponse)
def pagina_revisao(request: Request, usuario: Annotated[str, Depends(exigir_revisor)], feito: str = ""):
    return pagina(request, "revisao.html", pendentes=banco.listar("pendente_revisao"), temas=TEMAS,
                  contagem=banco.contar(), usuario=usuario, feito=feito)


@app.post("/revisao/{id_}")
def revisar_pela_tela(id_: str, _usuario: Annotated[str, Depends(exigir_revisor)],
                      acao: Annotated[str, Form()], motivo: Annotated[str, Form()] = "",
                      tema: Annotated[str, Form()] = ""):
    if acao not in ("aprovar", "rejeitar"):
        raise HTTPException(422, "ação inválida")
    _aplicar(id_, acao == "aprovar", motivo, tema or None)
    return RedirectResponse(f"/revisao?feito={'publicado' if acao == 'aprovar' else 'rejeitado'}",
                            status_code=303)


@app.get("/saude")
def saude():
    return {"status": "ok"}


@app.exception_handler(404)
async def nao_encontrado(request: Request, exc: HTTPException):
    if request.url.path.startswith("/api/") or request.url.path.startswith("/static/"):
        return JSONResponse({"detail": exc.detail}, status_code=404)
    return pagina(request, "nao_encontrado.html", status_code=404)
