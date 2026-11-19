"""Versão 2: lições do celular, aulas do Nível 2, catálogo de golpes e telas com letra grande."""
import json
import re
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

SRC = Path(__file__).resolve().parent.parent / "src" / "app_alertas"
sys.path.insert(0, str(SRC))

import verificador  # noqa: E402
from main import app  # noqa: E402
from rotas_v2 import partes_marcadas  # noqa: E402
from web import celular, golpes  # noqa: E402

CELULAR = json.loads((SRC / "conteudo" / "celular.json").read_text(encoding="utf-8"))


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "v2.db"))
    monkeypatch.delenv("EVENTOS_DB_PATH", raising=False)
    with TestClient(app) as c:
        yield c


def test_nome_do_produto(cliente):
    assert "Conecta+" in cliente.get("/").text


def test_inicio_tem_tres_caminhos_e_nada_de_pedir_ajuda(cliente):
    html = cliente.get("/").text
    for href in ('href="/aprender"', 'href="/verificar"', 'href="/golpes"'):
        assert href in html
    assert "Pedir ajuda" not in html


def test_nenhum_link_quebrado_nas_telas_principais(cliente):
    """Regra do projeto: nenhum botão sem funcionamento. Segue cada link interno das telas de entrada."""
    vistos, fila = set(), ["/", "/aprender", "/golpes", "/verificar"]
    while fila:
        url = fila.pop()
        if url in vistos:
            continue
        vistos.add(url)
        r = cliente.get(url)
        assert r.status_code == 200, url
        for href in re.findall(r'href="(/[^"#?]*)', r.text):
            if href.startswith(("/static", "/api", "/revisao")) or href in vistos:
                continue
            fila.append(href)
    assert len(vistos) > 30


@pytest.mark.parametrize("licao", [l["id"] for l in CELULAR["nivel1"]["licoes"]])
def test_cada_licao_do_celular_abre(cliente, licao):
    assert cliente.get(f"/aprender/celular/{licao}").status_code == 200


def test_licoes_em_passos_tem_android_e_iphone():
    for l in celular()["nivel1"]["licoes"]:
        if l["tipo"] == "passos":
            assert 3 <= len(l["android"]) <= 5 and 3 <= len(l["iphone"]) <= 5, l["id"]


def test_aulas_tem_pergunta_valida(cliente):
    for a in celular()["aulas"]:
        p = a["pergunta"]
        assert 0 <= p["correta"] < len(p["opcoes"]) and p["certo"] and p["errado"]
        assert cliente.get(f"/aprender/aula/{a['id']}").status_code == 200


def test_licao_ou_aula_inexistente_404(cliente):
    assert cliente.get("/aprender/celular/nao-existe").status_code == 404
    assert cliente.get("/aprender/aula/nao-existe").status_code == 404
    assert cliente.get("/golpes/nao-existe").status_code == 404


def test_catalogo_tem_12_golpes_e_cada_exemplo_acende_o_verificador(cliente):
    assert len(golpes()) == 12
    for g in golpes():
        texto = "".join(t for t, _ in partes_marcadas(g["msg"]))
        assert verificador.analisar(texto).nivel != "inconclusivo", g["id"]
        html = cliente.get(f"/golpes/{g['id']}").text
        assert "<mark>" in html and g["fonte"] in html


def test_partes_marcadas():
    assert partes_marcadas("a [[b]] c") == [("a ", False), ("b", True), (" c", False)]


def test_pratica_concluida_conta_no_impacto(cliente):
    ap = str(uuid.uuid4())
    assert cliente.post("/api/eventos", json={"tipo": "pratica_fim", "aparelho": ap, "licao": "audio"}).status_code == 204
    assert cliente.post("/api/eventos", json={"tipo": "pratica_fim", "aparelho": ap, "licao": "link"}).status_code == 204
    assert cliente.post("/api/eventos", json={"tipo": "pratica_fim", "aparelho": ap, "licao": "inventada"}).status_code == 422
    i = cliente.get("/api/impacto").json()
    assert i["praticas_concluidas"] == 2 and i["pessoas_praticando"] == 1
    assert i["praticas_por_licao"] == {"audio": 1, "link": 1}
    html = cliente.get("/impacto").text
    assert "Mandar áudio" in html and "lições do celular concluídas" in html


def test_verificar_tem_colar_e_aula_de_copiar(cliente):
    html = cliente.get("/verificar").text
    assert "data-colar-mensagem" in html and "/aprender/celular/copiar" in html


@pytest.mark.parametrize("texto,titulo", [
    ("BANCO HORIZONTE: compra suspeita, acesse urgente bit.ly/x e evite o bloqueio", "Cuidado!"),
    ("Bom dia! A reunião do grupo de caminhada é amanhã às 8h na praça.", "Não deu para saber"),
])
def test_resultado_fala_simples(cliente, texto, titulo):
    html = cliente.post("/verificar", data={"texto": texto}).text
    assert titulo in html


def test_resultado_de_risco_ensina_a_bloquear(cliente):
    html = cliente.post("/verificar", data={"texto": "BANCO HORIZONTE: compra suspeita, acesse urgente bit.ly/x"}).text
    assert "/aprender/celular/bloquear" in html


def test_fonte_servida_pelo_proprio_app(cliente):
    css = cliente.get("/static/estilo.css").text
    assert "fonts.googleapis" not in css and "/static/fontes/" in css
    assert "fonts.googleapis" not in cliente.get("/").text
