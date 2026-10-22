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
