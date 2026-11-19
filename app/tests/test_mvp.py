"""Testes do MVP de BI: verificador (gabarito), rotas, eventos anônimos, impacto e privacidade."""
import json
import sqlite3
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

AQUI = Path(__file__).resolve().parent
SRC = AQUI.parent / "src" / "app_alertas"
sys.path.insert(0, str(SRC))

import eventos  # noqa: E402
import verificador  # noqa: E402
from main import app  # noqa: E402

GABARITO = json.loads((AQUI / "gabarito_mensagens.json").read_text(encoding="utf-8"))
SEGREDO = "BANCO HORIZONTE: sua conta sera bloqueada hoje, acesse bit.ly/xyz-segredo-123"


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    monkeypatch.delenv("EVENTOS_DB_PATH", raising=False)
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "eventos.sqlite3"))
    with TestClient(app) as c:
        yield c


def novo_aparelho():
    return str(uuid.uuid4())


# ---------- verificador ----------

@pytest.mark.parametrize("caso", GABARITO, ids=lambda c: f"msg{c['id']}-{c['tema']}")
def test_gabarito(caso):
    assert verificador.analisar(caso["texto"]).nivel == caso["esperado"]


def test_gabarito_cobre_todos_os_niveis():
    assert len(GABARITO) == 20
    assert {c["esperado"] for c in GABARITO} == {"alto", "medio", "baixo", "inconclusivo"}


def test_nunca_diz_que_e_seguro():
    for caso in GABARITO:
        r = verificador.analisar(caso["texto"])
        assert "seguro" not in r.rotulo.lower()
        assert any("confirm" in a.lower() or "confiança" in a.lower() for a in r.acoes)


def test_trechos_apontam_para_o_texto_original_com_acentos():
    texto = "Atenção: seu cartão será BLOQUEADO hoje. Confirme os dados do cartão."
    r = verificador.analisar(texto)
    marcados = [texto[a:b].lower() for a, b in r.trechos]
    assert "bloqueado" in marcados and "hoje" in marcados


def test_link_oficial_gov_nao_e_suspeito_mas_marca_falsa_e():
    oficial = verificador.analisar("Consulte valores no site oficial valoresareceber.bcb.gov.br quando quiser.")
    falso = verificador.analisar("Consulte valores em valores-receber-gov.site quando quiser, é rápido.")
    assert "link_suspeito" not in [s["id"] for s in oficial.sinais]
    assert "link_suspeito" in [s["id"] for s in falso.sinais]


def test_curto_demais_e_inconclusivo():
    r = verificador.analisar("pix?")
    assert r.nivel == "inconclusivo" and "curta" in r.motivo_inconclusivo


def test_detecta_dado_sensivel():
    assert verificador.analisar("Meu CPF é 123.456.789-09, pode cadastrar por favor").tem_dado_sensivel
    assert not verificador.analisar("Bom dia, a reunião ficou para amanhã às 10h.").tem_dado_sensivel


def test_ponte_sugere_licao_do_sinal_mais_forte():
    r = verificador.analisar(GABARITO[4]["texto"])  # pedido de código
    assert r.licao_sugerida == "codigo_verificacao"


def test_texto_gigante_e_cortado():
    r = verificador.analisar("pix " * 5000)
    assert r.nivel in {"medio", "alto", "baixo"}


# ---------- telas ----------

@pytest.mark.parametrize("url", ["/verificar", "/verificar?exemplo=0", "/aprender", "/aprender/banco_falso",
                                 "/aprender/teste/pre", "/aprender/teste/pos", "/impacto", "/privacidade",
                                 "/static/app.js", "/static/estilo.css", "/static/selo.svg"])
def test_paginas_abrem(cliente, url):
    assert cliente.get(url).status_code == 200


def test_licao_inexistente_404(cliente):
    assert cliente.get("/aprender/nao_existe").status_code == 404
    assert cliente.get("/aprender/teste/meio").status_code == 422


def test_resultado_destaca_sinais_e_oferece_licao(cliente):
    html = cliente.post("/verificar", data={"texto": GABARITO[0]["texto"], "aparelho": ""}).text
    assert "Risco alto" in html
    assert "<mark>" in html
    assert "/aprender/banco_falso?origem=analise" in html


def test_resultado_escapa_html(cliente):
    html = cliente.post("/verificar", data={"texto": "<script>alert(1)</script> faça um pix urgente"}).text
    assert "<script>alert(1)</script>" not in html


def test_api_verificar_nao_devolve_o_texto(cliente):
    r = cliente.post("/api/verificar", json={"texto": SEGREDO})
    assert r.status_code == 200
    assert r.json()["nivel"] == "alto"
    assert "segredo" not in r.text


# ---------- privacidade ----------

def test_texto_analisado_nunca_e_gravado(cliente, tmp_path, capsys, caplog):
    cliente.post("/verificar", data={"texto": SEGREDO, "aparelho": novo_aparelho()})
    cliente.post("/api/verificar", json={"texto": SEGREDO})
    bruto = (tmp_path / "eventos.sqlite3").read_bytes()
    assert b"segredo" not in bruto and b"bit.ly" not in bruto
    saida = capsys.readouterr()
    assert "segredo" not in saida.out + saida.err + caplog.text


def test_evento_rejeita_campos_e_aparelho_invalidos(cliente):
    assert cliente.post("/api/eventos", json={"tipo": "pre_teste", "aparelho": "joao@email.com",
                                              "acertos": 1, "total": 3}).status_code == 422
    assert cliente.post("/api/eventos", json={"tipo": "analise", "aparelho": novo_aparelho()}).status_code == 422
    assert cliente.post("/api/eventos", json={"tipo": "pre_teste", "aparelho": novo_aparelho(),
                                              "acertos": 5, "total": 3}).status_code == 422
    assert cliente.post("/api/eventos", json={"tipo": "licao_fim", "aparelho": novo_aparelho(),
                                              "licao": "inventada"}).status_code == 422


def test_apagar_meus_dados(cliente, tmp_path):
    ap = novo_aparelho()
    cliente.post("/api/eventos", json={"tipo": "pre_teste", "aparelho": ap, "acertos": 1, "total": 3})
    cliente.post("/api/eventos", json={"tipo": "licao_inicio", "aparelho": ap, "licao": "banco_falso"})
    assert cliente.delete(f"/api/eventos/{ap}").json() == {"apagados": 2}
    con = sqlite3.connect(tmp_path / "eventos.sqlite3")
    assert con.execute("SELECT COUNT(*) FROM eventos WHERE aparelho = ?", (ap,)).fetchone()[0] == 0


# ---------- impacto ----------

def test_impacto_vazio_nao_quebra(cliente):
    i = cliente.get("/api/impacto").json()
    assert i["analises_total"] == 0 and i["ganho_conhecimento_pp"] is None
    assert "ainda sem dados" in cliente.get("/impacto").text


def test_impacto_calcula_ganho_pareado_e_ponte(cliente):
    a, b, so_pre = novo_aparelho(), novo_aparelho(), novo_aparelho()
    for ap, pre, pos in ((a, 1, 3), (b, 2, 3)):
        cliente.post("/api/eventos", json={"tipo": "pre_teste", "aparelho": ap, "acertos": pre, "total": 3})
        cliente.post("/api/eventos", json={"tipo": "pos_teste", "aparelho": ap, "acertos": pos, "total": 3})
    cliente.post("/api/eventos", json={"tipo": "pre_teste", "aparelho": so_pre, "acertos": 0, "total": 3})
    cliente.post("/api/eventos", json={"tipo": "quiz_licao", "aparelho": a, "licao": "pix_parente",
                                       "acertos": 2, "total": 3})
    cliente.post("/api/eventos", json={"tipo": "licao_fim", "aparelho": a, "licao": "pix_parente"})
    cliente.post("/verificar", data={"texto": GABARITO[0]["texto"]})
    cliente.post("/verificar", data={"texto": GABARITO[2]["texto"]})
    cliente.get("/aprender/banco_falso?origem=analise")

    i = cliente.get("/api/impacto").json()
    assert i["amostra_pareada"] == 2                     # quem só fez o pré não entra no ganho
    assert i["acerto_pre_pct"] == 50.0 and i["acerto_pos_pct"] == 100.0
    assert i["ganho_conhecimento_pp"] == 50.0
    assert i["analises_por_nivel"]["alto"] == 2
    assert i["ponte_analise_licao_pct"] == 50.0
    assert i["pessoas_na_trilha"] == 3 and i["pessoas_capacitadas"] == 2
    assert i["licoes_concluidas_por_tema"] == {"pix_parente": 1}
    assert i["amostra_pequena"] is True
    html = cliente.get("/impacto").text
    assert "+50 pontos" in html and "Amostra pequena" in html


# ---------- conteúdo ----------

def test_conteudo_bem_formado():
    dados = json.loads((SRC / "conteudo" / "licoes.json").read_text(encoding="utf-8"))
    assert len(dados["licoes"]) == 4
    blocos = [l["quiz"] for l in dados["licoes"]] + [dados["testes"]["pre"]["perguntas"], dados["testes"]["pos"]["perguntas"]]
    for perguntas in blocos:
        assert len(perguntas) == 3
        for q in perguntas:
            assert 0 <= q["correta"] < len(q["opcoes"]) and q["explicacao"]
    ids_licoes = {l["id"] for l in dados["licoes"]}
    assert {s.licao for s in verificador.SINAIS} <= ids_licoes
