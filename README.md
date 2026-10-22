# ATLAS-OS

**Autonomous Total Life & Business System — Personal AI Operating System**

This branch establishes the first testable backend foundation. It is deliberately a small, honest vertical slice rather than a pretend finished operating system.

## What works in this slice

- FastAPI service with a health endpoint.
- `POST /v1/plan` calls the OpenAI Responses API using a configurable model.
- Structured output is validated against a Pydantic response model.
- The planner proposes steps only. It does **not** execute external actions.
- Missing API credentials return a clear 503; provider or response failures return a sanitized 502.
- Automated tests cover health, missing credentials, request validation, and the planning response contract.

## Run locally

Python 3.11+ recommended.

```bash
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows PowerShell:
# .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
```

Set `OPENAI_API_KEY` in your local environment (or load it using your preferred secret manager). Never commit the key. Set `OPENAI_MODEL` to a model available to your API project and `ATLAS_REASONING_EFFORT` to `low`, `medium`, or `high`. The `/v1/plan` request's `goal` and `context` are sent to the configured OpenAI API provider to generate the plan; do not include information you are not comfortable sending to that provider.

```bash
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for interactive API documentation.

Run tests:

```bash
pytest -q
```

Tests use a mocked planning result and do not require a paid API call. A real planning request requires a valid API key and model access.

## Safety and current limitations

- No persistent memory, wearable integration, voice, computer control, or background agent is implemented yet.
- No user authentication or authorization layer is included; keep this development service on localhost and do not expose it to the public internet.
- The health endpoint is a liveness check, not a provider availability test.
- The model output is a proposal, not a source of truth. Before adding tools, implement authentication, per-tool permissions, confirmation for consequential actions, idempotency, audit logs, and integration tests.

## Next milestones

1. Add a user-scoped persistent memory store with explicit correction/deletion controls.
2. Add a typed tool registry with allowlisted tools and permission checks.
3. Add audit events and tracing for model/tool calls.
4. Add one real integration behind user consent and test its success/failure paths.
5. Add wearable/health adapters only for devices and APIs that support the required access.


## Required configuration before running

Set `ATLAS_API_TOKEN` to a cryptographically random secret of at least 32 characters, alongside `OPENAI_API_KEY`, `OPENAI_MODEL`, and a supported `ATLAS_REASONING_EFFORT`. Never commit secrets. The API requires `Authorization: Bearer <token>` for planning and schema routes.

Keep the service on localhost or behind HTTPS and a trusted reverse proxy. The shared token is a basic deployment guard, not per-user identity or authorization. Before external users, add per-user access controls, request rate limits, audit/observability, data retention controls, secret rotation, and a security review.
