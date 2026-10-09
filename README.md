# Multi-Agent Assistant

A local multi-agent assistant for web research, Gmail actions, and read-only MongoDB lookups. The backend uses LangGraph and Groq, exposes integrations through MCP servers, stores resumable run state in MongoDB, and records traces with LangSmith when configured.

The interface is a small run console inspired by Rival's agent workflow layout. It shows run progress, results, sources, and Gmail approvals.



## Architecture

    React console → FastAPI → Input checks → LangGraph supervisor → Groq
                                      ├── Research agent → Search MCP → Tavily
                                      ├── Action agent → Gmail MCP → Gmail API
                                      └── Data agent → MongoDB MCP → read-only collections

The API stores graph checkpoints, run records, and approvals in MongoDB. LangSmith tracing is enabled when configured.

## Requirements

- Python 3.11 or newer
- Node.js 20 or newer
- MongoDB Atlas or a local MongoDB instance
- A Groq API key
- A Tavily API key
- A Google Cloud project with the Gmail API enabled

## Configure the backend

In PowerShell:

    cd backend
    Copy-Item .env.example .env
    uv sync

Set these values in backend/.env:

    GROQ_API_KEY=your_groq_api_key
    GROQ_MODEL=openai/gpt-oss-20b
    MONGODB_URI=your_agent_state_mongodb_uri
    MONGODB_DATABASE=agent_assistant
    MONGODB_DATA_URI=your_read_only_data_mongodb_uri
    MONGODB_DATA_DATABASE=your_data_database
    MONGODB_ALLOWED_COLLECTIONS=customers,orders
    TAVILY_API_KEY=your_tavily_api_key

Use a MongoDB database user with read and write access for MONGODB_URI, which stores graph checkpoints and run records. Use a separate read-only user for MONGODB_DATA_URI. The data agent only sees collection names listed in MONGODB_ALLOWED_COLLECTIONS.

Start the API after MongoDB is reachable:

    uv run uvicorn app.api.main:app --reload --host 127.0.0.1 --port 8000

## Configure the frontend

Open a second terminal:

    cd frontend
    npm install
    npm run dev

Open http://localhost:5173.

## Connect Tavily

1. Create a Tavily account and an API key in the Tavily dashboard.
2. Copy the key into TAVILY_API_KEY in backend/.env.
3. Restart the backend.
4. Confirm that Tavily shows as Ready in the left connector list.

The search MCP server uses Tavily Search for web_search and Tavily Extract for fetch_page. [Tavily Python SDK documentation](https://github.com/tavily-ai/tavily-python)

## Connect Gmail

1. Open the [Google Cloud Console](https://console.cloud.google.com/) and create or select a project.
2. Enable the Gmail API for that project.
3. Configure the OAuth consent screen. For a personal local setup, add your Google account as a test user.
4. Create an OAuth client with application type **Desktop app**.
5. Download the OAuth client JSON file.
6. In the backend directory, create .secrets and save the downloaded file as .secrets/credentials.json.
7. Check that GMAIL_CREDENTIALS_PATH and GMAIL_TOKEN_PATH in backend/.env point to those files. The defaults already use .secrets/credentials.json and .secrets/gmail-token.json.
8. In the backend directory, run:

       uv run python -m app.auth.gmail

9. Sign in to Google in the browser window and approve access. The app stores the authorization token in .secrets/gmail-token.json.
10. Restart the backend and confirm that Gmail shows as Ready.

The app requests Gmail read-only access for message metadata and compose access for creating drafts and sending messages. Gmail drafts and sends both pause for review in the Approvals screen. Google classifies these scopes as restricted; publishing this app for other users may require OAuth verification and additional review. [Gmail OAuth setup](https://developers.google.com/workspace/gmail/api/quickstart/python), [Gmail scopes](https://developers.google.com/workspace/gmail/api/auth/scopes)

## Optional LangSmith tracing

Set LANGSMITH_TRACING=true, LANGSMITH_API_KEY, and LANGSMITH_PROJECT in backend/.env, then restart the backend.

## Run lifecycle

1. The API validates the request and creates a run record.
2. The supervisor routes work to one specialist at a time.
3. Each specialist receives only its own MCP tools.
4. Gmail draft and send calls pause in LangGraph until approved, edited, or rejected.
5. MongoDB stores checkpoints and approval state so a pending run can resume.
6. The final answer and source links appear in the console.

## Scope

This version is intended for one local user. It does not include Docker, deployment, accounts, multi-user access, or a workflow editor.
