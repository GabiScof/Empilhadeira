"""Testes de regressão das rotas HTTP de simulação (/sim/*).

Garante que os endpoints de corpo JSON (`/sim/reset-pose`, `/sim/inject-fault`)
expõem um `requestBody` no OpenAPI, em vez de tratarem o modelo Pydantic como
parâmetro de query.

Regressão: com `from __future__ import annotations` + modelos Pydantic definidos
como classes locais dentro da função de registro, o FastAPI não conseguia resolver
a anotação contra os globals do módulo e caía no fallback de query param — todo
POST retornava HTTP 422. Mover os modelos para o nível de módulo corrige isso.
"""

import importlib

import app.config as config
import app.main as main


def _build_sim_app():
    """Recarrega o módulo com SIM=1 e devolve a app FastAPI."""
    config.SIM = True
    importlib.reload(main)
    config.SIM = True
    return main.create_app()


def test_sim_routes_registered_in_sim_mode():
    app = _build_sim_app()
    paths = {route.path for route in app.routes}
    assert "/sim/reset-pose" in paths
    assert "/sim/inject-fault" in paths
    assert "/sim/world-state" in paths


def test_body_endpoints_declare_request_body():
    """As rotas POST devem aceitar corpo JSON (não query params)."""
    app = _build_sim_app()
    schema = app.openapi()

    for path in ("/sim/reset-pose", "/sim/inject-fault"):
        post = schema["paths"][path]["post"]
        assert "requestBody" in post, f"{path} não declara requestBody (vira query 422)"
        # Não deve haver parâmetro de query chamado 'req' (sintoma do bug)
        params = post.get("parameters", [])
        assert not any(p.get("name") == "req" for p in params), f"{path} expõe 'req' como query"
