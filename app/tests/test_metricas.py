"""Observabilidade: /metrics expõe as 4 métricas de ouro e respeita o token."""
from fastapi.testclient import TestClient


def _cliente(tmp_path, monkeypatch, token=""):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "t.sqlite3"))
    if token:
        monkeypatch.setenv("METRICS_TOKEN", token)
    else:
        monkeypatch.delenv("METRICS_TOKEN", raising=False)
    import main
    return TestClient(main.app)


def test_metricas_golden_signals(tmp_path, monkeypatch):
    with _cliente(tmp_path, monkeypatch) as c:
        c.get("/")
        c.get("/golpes/banco")
        c.get("/pagina-que-nao-existe")
        texto = c.get("/metrics").text
    assert "http_requests_total" in texto
    assert "http_request_duration_seconds_bucket" in texto
    assert "http_requests_in_progress" in texto
    assert 'route="/golpes/{golpe_id}"' in texto or 'route="/golpes/{' in texto
    assert "/golpes/banco" not in texto  # nunca o caminho real
    assert 'route="nao_encontrada"' in texto


def test_metricas_exige_token(tmp_path, monkeypatch):
    with _cliente(tmp_path, monkeypatch, token="segredo-teste") as c:
        assert c.get("/metrics").status_code == 401
        assert c.get("/metrics", headers={"Authorization": "Bearer errado"}).status_code == 401
        ok = c.get("/metrics", headers={"Authorization": "Bearer segredo-teste"})
        assert ok.status_code == 200


def test_texto_conferido_nao_vai_para_metricas(tmp_path, monkeypatch):
    with _cliente(tmp_path, monkeypatch) as c:
        c.post("/verificar", data={"texto": "Seu banco bloqueou MARCADOR123 clique"})
        assert "MARCADOR123" not in c.get("/metrics").text
