"""Atlas OS API foundation: structured planning, with no implicit execution."""
from __future__ import annotations

import json
import os
from typing import List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(
    title="Atlas OS API",
    version="0.1.0",
    description="A permission-first personal intelligence API. Planning only; no actions are executed.",
)


class PlanRequest(BaseModel):
    goal: str = Field(min_length=3, max_length=2000)
    context: str = Field(default="", max_length=6000)


class PlanStep(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    action: str = Field(min_length=1, max_length=500)
    expected_outcome: str = Field(min_length=1, max_length=300)
    approval_required: bool


class PlanResponse(BaseModel):
    summary: str
    steps: List[PlanStep]
    safety_notes: List[str]


class ModelNotConfigured(Exception):
    """Raised when the model cannot be called because configuration is missing."""


PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "action": {"type": "string"},
                    "expected_outcome": {"type": "string"},
                    "approval_required": {"type": "boolean"},
                },
                "required": ["title", "action", "expected_outcome", "approval_required"],
                "additionalProperties": False,
            },
        },
        "safety_notes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "steps", "safety_notes"],
    "additionalProperties": False,
}


def generate_plan(goal: str, context: str) -> PlanResponse:
    """Call the configured GPT-6 model and validate its structured plan."""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ModelNotConfigured("OPENAI_API_KEY is not configured")
    model = os.getenv("OPENAI_MODEL", "").strip()
    if not model:
        raise ModelNotConfigured("OPENAI_MODEL is not configured")

    from openai import OpenAI
    effort = os.getenv("ATLAS_REASONING_EFFORT", "medium")
    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=model,
        reasoning={"effort": effort},
        instructions=(
            "You are Atlas OS, a careful personal planning engine. Turn the user's goal "
            "into a concise, feasible plan. Never claim to have performed actions. Do not "
            "request passwords or secrets. Flag external, financial, health, location, or "
            "irreversible actions for explicit approval. State uncertainty in safety_notes. "
            "Return only the requested schema."
        ),
        input=json.dumps({"goal": goal, "context": context}, ensure_ascii=False),
        text={
            "format": {
                "type": "json_schema",
                "name": "atlas_plan",
                "strict": True,
                "schema": PLAN_SCHEMA,
            }
        },
    )
    if not response.output_text:
        raise ValueError("Model returned no structured output")
    return PlanResponse.model_validate_json(response.output_text)


@app.get("/health")
def health() -> dict:
    """Liveness check; does not imply the model API key or provider is reachable."""
    return {
        "status": "ok",
        "service": "atlas-os-api",
        "model_configured": bool(os.getenv("OPENAI_API_KEY", "").strip()),
        "execution_enabled": False,
    }


@app.post("/v1/plan", response_model=PlanResponse)
def create_plan(request: PlanRequest) -> PlanResponse:
    try:
        return generate_plan(request.goal, request.context)
    except ModelNotConfigured:
        raise HTTPException(
            status_code=503,
            detail="Model not configured. Set OPENAI_API_KEY in the local environment.",
        )
    except Exception:
        # Avoid returning provider errors, credentials, or internal stack traces to clients.
        raise HTTPException(
            status_code=502,
            detail="Planning provider failed or returned an invalid response.",
        )
