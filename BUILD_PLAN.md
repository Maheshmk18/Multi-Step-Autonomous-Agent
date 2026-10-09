# Build Plan

## Goal

Build a local, single-user multi-agent assistant for web research, Gmail tasks, and read-only MongoDB queries. Keep the interface small and familiar, using Rival's workflow workspace as a visual reference. Use Groq for model calls and MongoDB for run history and resumable graph state.

## Product decisions

- Use a LangGraph supervisor to route work to one specialist at a time.
- Give the research specialist Tavily search and page extraction tools.
- Give the Gmail specialist read, draft, and send tools. Pause every draft or send for explicit approval in the UI.
- Give the data specialist read-only access to an explicit MongoDB collection allowlist.
- Store workflow checkpoints, run records, and approval records in MongoDB.
- Keep Gmail OAuth credentials and tokens local and out of version control.
- Use a compact console with new run, run history, connector status, and approvals views. Do not build a visual workflow editor.
- Keep application source free of code comment lines.
- Leave packaging, containers, deployment, user accounts, and multi-user support out of this build.

## Architecture

1. The React console sends a task to the FastAPI backend.
2. The API validates the task and creates a MongoDB run record.
3. The LangGraph supervisor chooses a specialist and gives it only its allowed tools.
4. The specialist calls its local MCP server, which connects to Tavily, Gmail, or MongoDB.
5. Gmail writes pause at a LangGraph approval checkpoint. The user can approve, edit, or reject the action.
6. The API saves progress and results, and the console refreshes the run and approval views.
7. Optional LangSmith tracing records graph activity when configured.

## Delivery phases

### 1. Repository and scope

Status: complete.

- Create a feature branch and keep the change local for review.
- Record the architecture, product limits, and connector setup steps.
- Use the PDF as an architecture reference while applying the requested Groq, MongoDB, minimal UI, and no-packaging choices.

### 2. Backend foundation

Status: implemented; local setup still needs credentials and a reachable MongoDB instance.

- Add typed application settings and request schemas.
- Add FastAPI endpoints for health, connectors, runs, and approval decisions.
- Persist run history and resumable LangGraph state in MongoDB.
- Restrict CORS to the local frontend origin and bind the documented API command to localhost.

### 3. Agent workflow and tools

Status: implemented; external service access needs credentials.

- Add Groq supervisor routing and three specialist nodes.
- Run each integration as a separate MCP server and expose only the tools assigned to that specialist.
- Add Tavily web search and page extraction.
- Add Gmail message lookup, draft creation, and send actions.
- Add MongoDB collection discovery, descriptions, and bounded read queries with a collection allowlist.
- Require human approval before Gmail draft creation or sending.

### 4. Minimal console

Status: implemented.

- Add a compact workspace inspired by Rival's navigation and run activity layout.
- Show connector readiness, run progress, results, and source links.
- Add run history and an approval inbox with edit, approve, and reject actions.
- Keep the layout responsive without adding a workflow builder.

### 5. Local connection setup

Status: documented; requires the user's own service accounts and MongoDB URI.

- Set `GROQ_API_KEY` and choose an active Groq model in `backend/.env`.
- Set `MONGODB_URI` for agent state. Set `MONGODB_DATA_URI` and `MONGODB_ALLOWED_COLLECTIONS` to enable read-only access to user data.
- Set `TAVILY_API_KEY` to enable web research.
- Enable the Gmail API, create a Desktop OAuth client, save its credentials under `backend/.secrets/`, and run the local authorization command from `backend`.
- Start the backend from `backend` and the frontend from `frontend`.

### 6. Verification and hardening

Status: planned; not run as part of this implementation.

- Verify that a local run can complete with each specialist and that missing credentials produce useful errors.
- Verify Gmail drafts and sends remain paused until approval, and that rejection makes no Gmail change.
- Verify MongoDB read tools cannot access collections outside the allowlist or perform writes.
- Build a 30-case evaluation set covering routing, tool selection, source quality, data access limits, approval behavior, and failure handling.
- Review dependency lockfiles and repeatable local setup before sharing the project.

## Connection details

### Gmail

1. Create or select a Google Cloud project and enable the Gmail API.
2. Configure the OAuth consent screen and add the account as a test user for a local test app.
3. Create an OAuth client with the Desktop app type and download its JSON file.
4. Save it as `backend/.secrets/credentials.json`.
5. From the `backend` directory, run `uv run python -m app.auth.gmail` and approve access in the browser.
6. Restart the backend. The local token is saved as `backend/.secrets/gmail-token.json` and is ignored by Git.

The app uses Gmail read-only access for message lookup and compose access for drafts and sending. Google may require additional verification if the app is published for other users.

### Tavily

1. Create a Tavily account and generate an API key.
2. Set `TAVILY_API_KEY` in `backend/.env`.
3. Restart the backend and confirm Tavily reports Ready in the console.

## Completion criteria

- A local user can submit a task from the console and see its status and final result.
- Research tasks can search the web and return source links.
- Gmail lookup works after OAuth, and every draft or send waits for a user decision.
- Data queries only read collections explicitly listed in `MONGODB_ALLOWED_COLLECTIONS`.
- Runs and pending approvals survive backend restarts through MongoDB checkpoints.
- No packaging or deployment workflow is included.
