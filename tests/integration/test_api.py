"""API integration tests with LLM mocked."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from modernization_pipeline.api.routes import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ok", "degraded"}
    assert "postgres" in body
    assert "langfuse" in body


def test_modernize_endpoint_mocked(client):
    fake_result = {
        "status": "success",
        "generated_code": "async def fn_saldo_cliente(p_cliente_id: int) -> float:\n    return 0.0\n",
        "report": {"parsing": {}, "validation": {"ast": {"ok": True}}},
        "history_id": "00000000-0000-0000-0000-000000000001",
        "run_id": "run-1",
    }
    with patch(
        "modernization_pipeline.graph.run_pipeline",
        new=AsyncMock(return_value=fake_result),
    ):
        response = client.post(
            "/modernize",
            json={
                "source_code": (
                    "CREATE OR REPLACE FUNCTION fn_x() RETURNS INT LANGUAGE plpgsql "
                    "AS $$ BEGIN RETURN 1; END; $$;"
                )
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert "async def" in body["generated_code"]
    assert body["history_id"]
