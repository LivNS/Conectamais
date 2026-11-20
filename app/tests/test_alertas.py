"""Alertas: contrato com o robô, revisão humana, página pública e telas gerais."""
import re
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

SRC = Path(__file__).resolve().parent.parent / "src" / "app_alertas"
sys.path.insert(0, str(SRC))

from main import app  # noqa: E402

RASCUNHO = {
    "id": "0ad748e293557124", "titulo": "Mensagens falsas avisam que a conta será bloqueada",
    "tema": "banco_falso", "tema_rotulo": "Falso contato do banco",
    "resumo_simples": "Criminosos enviam SMS com link falso.",
    "como_se_proteger": ["Não clique no link."], "fonte_nome": "Observatório Fictício",
    "link_fonte": "https://alertas.exemplo.org/x", "data_publicacao": "2026-11-15",
    "precisa_revisar_tema": False, "status": "pendente_revisao", "origem": "rpa",
    "criado_em": "2026-11-17T00:00:00+00:00",
}
ROBO = {"Authorization": "Bearer token-teste"}
ADMIN = ("revisor", "senha-teste")


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("RPA_API_TOKEN", "token-teste")
    monkeypatch.setenv("ADMIN_USUARIO", ADMIN[0])
    monkeypatch.setenv("ADMIN_SENHA", ADMIN[1])
    monkeypatch.setenv("ALERTAS_DEMONSTRACAO", "0")
    with TestClient(app) as c:
        yield c


def test_robo_envia_rascunho_que_fica_pendente_e_nao_publico(cliente):
    assert cliente.post("/api/alertas/rascunhos", json=RASCUNHO, headers=ROBO).status_code == 201
    assert cliente.get("/api/alertas").json() == []
    pend = cliente.get("/api/alertas/pendentes", auth=ADMIN).json()
    assert [p["id"] for p in pend] == [RASCUNHO["id"]]


def test_robo_nao_consegue_publicar_direto(cliente):
    cliente.post("/api/alertas/rascunhos", json={**RASCUNHO, "status": "publicado"}, headers=ROBO)
    assert cliente.get("/api/alertas").json() == []


def test_rascunho_repetido_responde_409(cliente):
    cliente.post("/api/alertas/rascunhos", json=RASCUNHO, headers=ROBO)
    assert cliente.post("/api/alertas/rascunhos", json=RASCUNHO, headers=ROBO).status_code == 409


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer errado"}])
def test_robo_sem_token_valido_401(cliente, headers):
    assert cliente.post("/api/alertas/rascunhos", json=RASCUNHO, headers=headers).status_code == 401


def test_rascunho_invalido_422(cliente):
    r = cliente.post("/api/alertas/rascunhos", json={**RASCUNHO, "link_fonte": "nao-e-link"}, headers=ROBO)
    assert r.status_code == 422


def test_revisao_exige_login(cliente):
    assert cliente.get("/revisao").status_code == 401
    assert cliente.get("/revisao", auth=("revisor", "errada")).status_code == 401


def test_fluxo_completo_robo_revisao_publicacao_pela_tela(cliente):
    cliente.post("/api/alertas/rascunhos", json=RASCUNHO, headers=ROBO)
    html = cliente.get("/revisao", auth=ADMIN).text
    assert RASCUNHO["titulo"] in html and "1 esperando revisão" in html
    token = re.search(r'name="csrf_token" value="([0-9a-f]+)"', html).group(1)
    r = cliente.post(f"/revisao/{RASCUNHO['id']}",
                     data={"acao": "aprovar", "tema": "banco_falso", "csrf_token": token},
                     auth=ADMIN, follow_redirects=False)
    assert r.status_code == 303
    publica = cliente.get("/golpes").text
    assert RASCUNHO["titulo"] in publica
    detalhe = cliente.get(f"/golpes/alerta/{RASCUNHO['id']}").text
    assert "/aprender/banco_falso" in detalhe            # alerta leva à aula do mesmo golpe
    assert "/golpes/banco" in detalhe                    # e à explicação completa do golpe
    assert "Observatório Fictício" in detalhe            # fonte sempre visível
    assert RASCUNHO["titulo"][:40] in cliente.get("/").text  # aparece como mais recente no início
    assert cliente.get("/alertas").url.path == "/golpes"     # endereço antigo continua funcionando


def test_rejeicao_exige_motivo_e_nao_publica(cliente):
    cliente.post("/api/alertas/rascunhos", json=RASCUNHO, headers=ROBO)
    url = f"/api/alertas/{RASCUNHO['id']}/rejeitar"
    assert cliente.post(url, json={"motivo": " "}, auth=ADMIN).status_code == 422
    assert cliente.post(url, json={"motivo": "não confirmado"}, auth=ADMIN).status_code == 200
    assert cliente.get("/api/alertas").json() == []
    assert cliente.post(url, json={"motivo": "de novo"}, auth=ADMIN).status_code == 409


def test_aprovar_com_tema_desconhecido_422(cliente):
    cliente.post("/api/alertas/rascunhos", json=RASCUNHO, headers=ROBO)
    r = cliente.post(f"/api/alertas/{RASCUNHO['id']}/aprovar", json={"tema": "inventado"}, auth=ADMIN)
    assert r.status_code == 422


def test_golpes_novos_mostra_tres_e_ver_mais_mostra_todos(cliente):
    for i in range(5):
        cliente.post("/api/alertas/rascunhos", json={**RASCUNHO, "id": f"aa{i}aa{i}aa{i}", "titulo": f"Alerta número {i} de teste"},
                     headers=ROBO)
        cliente.post(f"/api/alertas/aa{i}aa{i}aa{i}/aprovar", auth=ADMIN)
    curta = cliente.get("/golpes").text
    assert curta.count("/golpes/alerta/") == 3 and "Ver mais golpes novos (5)" in curta
    assert cliente.get("/golpes?todos=1").text.count("/golpes/alerta/") == 5


def test_alerta_nao_publicado_nao_abre(cliente):
    cliente.post("/api/alertas/rascunhos", json=RASCUNHO, headers=ROBO)
    assert cliente.get(f"/golpes/alerta/{RASCUNHO['id']}").status_code == 404


def test_demonstracao_so_no_banco_vazio(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "d.db"))
    monkeypatch.delenv("ALERTAS_DEMONSTRACAO", raising=False)
    with TestClient(app) as c:
        alertas = c.get("/api/alertas").json()
        assert len(alertas) == 4 and all(a["origem"] == "demonstracao" for a in alertas)
        assert "Alerta de demonstração" in c.get("/golpes").text
    with TestClient(app) as c:                       # reiniciar não duplica
        assert len(c.get("/api/alertas").json()) == 4


@pytest.mark.parametrize("url", ["/", "/golpes", "/saude", "/privacidade"])
def test_telas_gerais_abrem(cliente, url):
    assert cliente.get(url).status_code == 200


def test_404_amigavel(cliente):
    r = cliente.get("/nao-existe")
    assert r.status_code == 404 and "Voltar ao início" in r.text
    assert cliente.get("/api/nao-existe").status_code == 404


def test_revisao_barra_formulario_forjado_csrf(cliente):
    cliente.post("/api/alertas/rascunhos", json=RASCUNHO, headers=ROBO)
    for dados in ({"acao": "aprovar"}, {"acao": "aprovar", "csrf_token": "0" * 64}):
        r = cliente.post(f"/revisao/{RASCUNHO['id']}", data=dados, auth=ADMIN, follow_redirects=False)
        assert r.status_code == 403
    assert RASCUNHO["titulo"] not in cliente.get("/golpes").text
