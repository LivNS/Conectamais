"""Métricas Prometheus com as 4 métricas de ouro (golden signals).

- Latência: histograma `http_request_duration_seconds`
- Tráfego: contador `http_requests_total`
- Erros: `http_requests_total{status=~"5.."}` (e 4xx separados)
- Saturação: `http_requests_in_progress` + métricas do processo (CPU, memória)

Os rótulos usam o MODELO da rota (ex.: /golpes/{id}), nunca o caminho real,
para não guardar nada digitado pela pessoa e não explodir a cardinalidade.
O /metrics é protegido por token quando METRICS_TOKEN está definido.
"""
from __future__ import annotations

import os
import secrets
import time

from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

REQUISICOES = Counter(
    "http_requests_total", "Requisições HTTP recebidas", ["method", "route", "status"])
LATENCIA = Histogram(
    "http_request_duration_seconds", "Tempo de resposta das requisições", ["method", "route"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5))
EM_ANDAMENTO = Gauge(
    "http_requests_in_progress", "Requisições sendo atendidas agora")

IGNORADAS = {"/metrics", "/saude"}


def _rota(request: Request) -> str:
    rota = request.scope.get("route")
    caminho = getattr(rota, "path", None)
    if caminho:
        return caminho
    if request.url.path.startswith("/static/"):
        return "/static"
    return "nao_encontrada"


async def medir(request: Request, call_next):
    if request.url.path in IGNORADAS:
        return await call_next(request)
    EM_ANDAMENTO.inc()
    inicio = time.perf_counter()
    status = 500
    try:
        resposta = await call_next(request)
        status = resposta.status_code
        return resposta
    finally:
        EM_ANDAMENTO.dec()
        rota = _rota(request)
        LATENCIA.labels(request.method, rota).observe(time.perf_counter() - inicio)
        REQUISICOES.labels(request.method, rota, str(status)).inc()


def expor_metricas(request: Request):
    esperado = os.environ.get("METRICS_TOKEN", "")
    if esperado:
        recebido = request.headers.get("authorization", "")
        if not secrets.compare_digest(recebido, f"Bearer {esperado}"):
            return PlainTextResponse("não autorizado", status_code=401)
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def instalar(app: FastAPI) -> None:
    app.middleware("http")(medir)
    app.add_api_route("/metrics", expor_metricas, methods=["GET"], include_in_schema=False)
