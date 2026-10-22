"""Atlas OS API foundation: structured planning, with no implicit execution."""
from __future__ import annotations

import hmac
import json
import os
from typing import List

from fastapi import FastAPI, HTTPException, Request
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field

app = FastAPI(
    title="Atlas OS API",
    version="0.1.0",
    description="A permission-first personal intelligence API. Planning only; no actions are executed.",
)




@app.middleware("http")
async def require_api_token(request: Request, call_next):
    """Fail closed for planning and API schema routes unless a strong token is configured."""
    protected = request.url.path.startswith("/v1/")
    if not protected:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Cache-Control", "no-store")
        return response
    expected = os.getenv("ATLAS_API_TOKEN", "").strip()
    if len(expected) < 32:
        return JSONResponse(status_code=503, content={"detail": "API unavailable: configure ATLAS_API_TOKEN with at least 32 characters."}, headers={"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer", "Cache-Control": "no-store"})
    supplied = request.headers.get("authorization", "")
    scheme, _, credential = supplied.partition(" ")
    if scheme.lower() != "bearer" or not credential or not hmac.compare_digest(credential, expected):
        return JSONResponse(status_code=401, content={"detail": "Valid bearer token required."}, headers={"WWW-Authenticate": "Bearer", "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer", "Cache-Control": "no-store"})
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Cache-Control", "no-store")
    return response


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(title=app.title, version=app.version, description=app.description, routes=app.routes)
    schema.setdefault("components", {}).setdefault("securitySchemes", {})["BearerAuth"] = {
        "type": "http", "scheme": "bearer", "bearerFormat": "opaque API token"
    }
    for path, operations in schema.get("paths", {}).items():
        if path.startswith("/v1/"):
            for operation in operations.values():
                if isinstance(operation, dict):
                    operation["security"] = [{"BearerAuth": []}]
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi


class PlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

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
    effort = os.getenv("ATLAS_REASONING_EFFORT", "medium").strip().lower()
    if effort not in {"low", "medium", "high"}:
        raise ModelNotConfigured("ATLAS_REASONING_EFFORT must be low, medium, or high")
    client = OpenAI(api_key=api_key, timeout=20.0, max_retries=1)
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


@app.get("/", include_in_schema=False)
def web_preview():
    """Serve the installable browser preview when running the API locally."""
    return FileResponse(Path(__file__).resolve().parent.parent / "index.html")


@app.get("/manifest.webmanifest", include_in_schema=False)
def web_manifest():
    return FileResponse(
        Path(__file__).resolve().parent.parent / "manifest.webmanifest",
        media_type="application/manifest+json",
    )


@app.get("/sw.js", include_in_schema=False)
def service_worker():
    return FileResponse(
        Path(__file__).resolve().parent.parent / "sw.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"},
    )


@app.get("/health")
def health() -> dict:
    """Liveness check; does not imply the model API key or provider is reachable."""
    return {
        "status": "ok",
        "service": "atlas-os-api",
        "model_configured": bool(
            os.getenv("OPENAI_API_KEY", "").strip()
            and os.getenv("OPENAI_MODEL", "").strip()
        ),
        "execution_enabled": False,
    }


@app.post("/v1/plan", response_model=PlanResponse)
def create_plan(request: PlanRequest) -> PlanResponse:
    try:
        return generate_plan(request.goal, request.context)
    except ModelNotConfigured:
        raise HTTPException(
            status_code=503,
            detail="Model not configured. Set both OPENAI_API_KEY and OPENAI_MODEL; ensure ATLAS_REASONING_EFFORT is low, medium, or high.",
        )
    except Exception:
        # Avoid returning provider errors, credentials, or internal stack traces to clients.
        raise HTTPException(
            status_code=502,
            detail="Planning provider failed or returned an invalid response.",
        )
