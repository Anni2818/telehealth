# Semantic emergency screening

## Purpose and safety boundary

CareConnect runs deterministic emergency screening first, then an optional Azure OpenAI semantic screening layer, before the normal Azure AI Foundry receptionist workflow. Semantic screening is intended to catch indirect or conversational descriptions that deterministic patterns may not recognize. It is a safety screen, not a diagnostic system, and it must not replace professional medical assessment or emergency services.

## Request flow

1. `process_chat()` calls `screen_emergency(message)` from `app/services/emergency_service.py`.
2. A deterministic emergency result is returned immediately. Semantic screening and Foundry are not called.
3. Otherwise `screen_semantic_emergency(message)` is called from `app/services/semantic_emergency_service.py`.
4. `NORMAL` continues to the existing Foundry workflow.
5. `POTENTIAL_EMERGENCY` and `UNCERTAIN` return a fixed safety response and stop the normal Foundry flow.
6. If semantic screening is disabled, it returns `None`; deterministic screening continues to run as usual.

The semantic layer fails closed. Missing configuration, malformed or contradictory model output, timeouts, authentication errors, and provider failures result in `UNCERTAIN`, not `NORMAL`.

## Dependencies

From the repository root:

```bash
python -m pip install -r requirements.txt
```

The Foundry integration imports `azure.ai.projects`. The pinned `azure-ai-projects==2.4.0` package declares `openai>=2.8.0`, so the project requirement is `openai>=2.8,<3`. The authentication service uses `pwdlib` with Argon2; the `pwdlib[argon2]` extra installs that backend.

## Local configuration

Copy `genaicapstone/.env.example` to `genaicapstone/.env`. Fill only the values for the services you are using. Keep `.env` private; `.gitignore` excludes it.

Generate a JWT signing secret locally:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Use the output as `JWT_SECRET_KEY`. Do not share it or commit it.

The existing receptionist uses these separate Foundry settings:

- `FOUNDRY_TENANT_ID`
- `FOUNDRY_CLIENT_ID`
- `FOUNDRY_CLIENT_SECRET`
- `FOUNDRY_PROJECT_ENDPOINT`
- `FOUNDRY_AGENT_NAME`

The semantic screening layer uses an Azure OpenAI endpoint and deployment, not the Foundry project endpoint:

- `SEMANTIC_EMERGENCY_SCREENING_ENABLED` — `false` by default; use `true` only in a controlled test environment after configuration.
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_API_VERSION` — defaults to `2024-10-21`.
- `AZURE_OPENAI_EMERGENCY_DEPLOYMENT`
- `SEMANTIC_SCREENING_TIMEOUT_SECONDS` — defaults to `12`.

Do not enable the feature until a suitable Azure OpenAI resource/deployment and approved credentials are available. Never put credentials in source code, logs, issues, pull requests, or chat messages.

`AZURE_SQL_CONNECTIONSTRING` is required for database-backed authentication and workflows. `MCP_API_KEY` and `MCP_PUBLIC_HOST` are required only when running the separate MCP gateway (`app.mcp_server.gateway`); the MCP gateway requires a long random API key and the exact forwarded hostname.

## Run the API

From `genaicapstone/`, after dependencies and required local settings are configured:

```bash
python -m uvicorn app.main:app --reload
```

The health endpoint is `GET /health`. A successful health response does not verify SQL, Entra ID, Foundry, Azure OpenAI, or appointment workflows.

## Tests

From `genaicapstone/`:

```bash
PYTHONPATH=. python -m unittest test_chat_service_integration test_semantic_emergency_service -v
PYTHONPATH=. python -m unittest discover -v
PYTHONPATH=. python -m compileall -q app
```

The `process_chat()` integration tests mock SQL session persistence and external Azure/Foundry calls. They validate control-flow ordering and response shape, not live service connectivity or model accuracy.

## Manual Azure OpenAI validation plan

In a controlled, non-production environment with an approved Azure OpenAI deployment:

1. Keep the deterministic emergency layer active.
2. Configure the Azure OpenAI endpoint, API key, API version, deployment name, and timeout in the local `.env` or the environment's secret store.
3. Enable `SEMANTIC_EMERGENCY_SCREENING_ENABLED=true` only for the test environment.
4. Exercise direct and indirect emergency descriptions, historical/educational examples, ambiguous descriptions, and ordinary appointment requests.
5. Simulate missing deployment, invalid credentials, empty/malformed output, provider unavailability, and timeouts. Every failure must return `UNCERTAIN` and block Foundry.
6. Record expected category/status, actual category/status, latency, and provider failures without recording patient-identifying information.
7. Disable the feature after the controlled test if deployment/configuration is not approved for continued use.

Passing these tests does not establish clinical reliability. Use a reviewed evaluation dataset with emphasis on false negatives, and obtain sign-off from a qualified clinical safety reviewer before any real-patient use.
