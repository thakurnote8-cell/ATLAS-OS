from fastapi.testclient import TestClient

import app.main as atlas

client = TestClient(atlas.app)


def test_health_does_not_claim_model_is_configured(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "atlas-os-api",
        "model_configured": False,
        "execution_enabled": False,
    }


def test_plan_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    response = client.post("/v1/plan", json={"goal": "Plan my week"})
    assert response.status_code == 503
    assert "OPENAI_API_KEY" in response.json()["detail"]


def test_plan_uses_validated_structured_result(monkeypatch):
    expected = atlas.PlanResponse(
        summary="Prepare a realistic weekly plan.",
        steps=[
            atlas.PlanStep(
                title="Collect commitments",
                action="Review the user's provided calendar and task list.",
                expected_outcome="Known time constraints.",
                approval_required=False,
            )
        ],
        safety_notes=["No calendar was accessed by this API."],
    )
    monkeypatch.setattr(atlas, "generate_plan", lambda goal, context: expected)
    response = client.post(
        "/v1/plan",
        json={"goal": "Plan my week", "context": "Keep mornings free."},
    )
    assert response.status_code == 200
    assert response.json()["summary"] == expected.summary
    assert response.json()["steps"][0]["approval_required"] is False


def test_invalid_goal_is_rejected():
    response = client.post("/v1/plan", json={"goal": "x"})
    assert response.status_code == 422


def test_health_requires_both_key_and_model(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["model_configured"] is False


def test_plan_requires_model_configuration(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    response = client.post("/v1/plan", json={"goal": "Plan my week"})
    assert response.status_code == 503
    assert "OPENAI_MODEL" in response.json()["detail"]


def test_invalid_reasoning_effort_is_rejected_before_provider_call(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.setenv("ATLAS_REASONING_EFFORT", "turbo")
    response = client.post("/v1/plan", json={"goal": "Plan my week"})
    assert response.status_code == 503
    assert "ATLAS_REASONING_EFFORT" in response.json()["detail"]
