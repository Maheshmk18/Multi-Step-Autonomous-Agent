import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.mongodb import MongoDBSaver
from langgraph.types import Command
from pymongo import MongoClient, ReturnDocument

from app.config import settings
from app.graph.workflow import build_workflow
from app.schemas import ApprovalDecision, RunRequest


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    database = client[settings.mongodb_database]
    database.runs.create_index("created_at")
    database.runs.create_index("status")
    database.approvals.create_index([("status", 1), ("created_at", -1)])
    checkpointer = MongoDBSaver(client, db_name=settings.mongodb_database)
    app.state.mongo_client = client
    app.state.database = database
    app.state.workflow = build_workflow(checkpointer)
    app.state.background_tasks = set()
    try:
        yield
    finally:
        tasks = list(app.state.background_tasks)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        client.close()


app = FastAPI(
    title="Multi-Agent Assistant",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def _now() -> datetime:
    return datetime.now(UTC)


def _public_run(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": document["_id"],
        "thread_id": document["thread_id"],
        "message": document["message"],
        "status": document["status"],
        "created_at": document["created_at"].isoformat(),
        "updated_at": document["updated_at"].isoformat(),
        "final_answer": document.get("final_answer"),
        "results": document.get("results", []),
        "sources": document.get("sources", []),
        "events": document.get("events", []),
        "pending_approval": document.get("pending_approval"),
        "error": document.get("error"),
    }


def _public_approval(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": document["_id"],
        "run_id": document["run_id"],
        "tool_name": document["payload"].get("tool_name"),
        "arguments": document["payload"].get("arguments", {}),
        "message": document["payload"].get("message", ""),
        "status": document["status"],
        "created_at": document["created_at"].isoformat(),
    }


def _interrupt_items(update: dict[str, Any]) -> list[Any]:
    interruptions: list[Any] = []
    for value in update.values():
        if isinstance(value, dict) and value.get("__interrupt__"):
            items = value["__interrupt__"]
            interruptions.extend(items if isinstance(items, (list, tuple)) else [items])
    direct = update.get("__interrupt__")
    if direct:
        interruptions.extend(direct if isinstance(direct, (list, tuple)) else [direct])
    return interruptions


async def _stream_graph(
    request: Request,
    run_id: str,
    thread_id: str,
    graph_input: dict[str, Any] | Command,
) -> None:
    database = request.app.state.database
    workflow = request.app.state.workflow
    config = {"configurable": {"thread_id": thread_id}}
    interruptions: list[Any] = []
    try:
        async for update in workflow.astream(graph_input, config, stream_mode="updates"):
            interruptions.extend(_interrupt_items(update))
            for node_name, node_update in update.items():
                if node_name == "__interrupt__" or not isinstance(node_update, dict):
                    continue
                events = node_update.get("events") or [
                    {"node": node_name, "status": "completed"}
                ]
                for event in events:
                    database.runs.update_one(
                        {"_id": run_id},
                        {
                            "$push": {"events": event},
                            "$set": {"updated_at": _now()},
                        },
                    )

        snapshot = await workflow.aget_state(config)
        state_values = snapshot.values or {}
        if interruptions:
            interruption = interruptions[0]
            payload = getattr(interruption, "value", {})
            interrupt_id = getattr(interruption, "id", str(uuid4()))
            approval_id = f"{run_id}:{interrupt_id}"
            database.approvals.update_one(
                {"_id": approval_id},
                {
                    "$setOnInsert": {
                        "run_id": run_id,
                        "thread_id": thread_id,
                        "payload": payload,
                        "status": "pending",
                        "created_at": _now(),
                    }
                },
                upsert=True,
            )
            database.runs.update_one(
                {"_id": run_id},
                {
                    "$set": {
                        "status": "pending_approval",
                        "pending_approval": {
                            "id": approval_id,
                            "tool_name": payload.get("tool_name"),
                            "arguments": payload.get("arguments", {}),
                            "message": payload.get("message", ""),
                        },
                        "updated_at": _now(),
                    }
                },
            )
            return

        final_answer = state_values.get("final_answer", "")
        database.runs.update_one(
            {"_id": run_id},
            {
                "$set": {
                    "status": "succeeded" if final_answer else "failed",
                    "final_answer": final_answer,
                    "results": state_values.get("results", []),
                    "sources": state_values.get("sources", []),
                    "pending_approval": None,
                    "error": None if final_answer else "The run finished without a final response.",
                    "updated_at": _now(),
                }
            },
        )
    except Exception:
        logger.exception("Run %s failed.", run_id)
        database.runs.update_one(
            {"_id": run_id},
            {
                "$set": {
                    "status": "failed",
                    "error": "The run failed. Review the backend logs for details.",
                    "updated_at": _now(),
                }
            },
        )


def _start_task(request: Request, run_id: str, thread_id: str, graph_input: Any) -> None:
    task = asyncio.create_task(_stream_graph(request, run_id, thread_id, graph_input))
    request.app.state.background_tasks.add(task)
    task.add_done_callback(request.app.state.background_tasks.discard)


@app.get("/api/health")
async def health(request: Request) -> dict[str, str]:
    request.app.state.mongo_client.admin.command("ping")
    return {"status": "ok", "mongodb": "connected"}


@app.get("/api/connectors")
async def connectors() -> dict[str, bool]:
    return {
        "groq": bool(settings.groq_api_key),
        "mongodb_data": bool(settings.mongodb_data_uri),
        "tavily": bool(settings.tavily_api_key),
        "gmail": settings.gmail_credentials_path.is_file()
        and settings.gmail_token_path.is_file(),
        "langsmith": bool(settings.langsmith_api_key and settings.langsmith_tracing),
    }


@app.post("/api/runs", status_code=status.HTTP_202_ACCEPTED)
async def create_run(body: RunRequest, request: Request) -> dict[str, Any]:
    run_id = uuid4().hex
    timestamp = _now()
    request.app.state.database.runs.insert_one(
        {
            "_id": run_id,
            "thread_id": run_id,
            "message": body.message.strip(),
            "status": "running",
            "created_at": timestamp,
            "updated_at": timestamp,
            "events": [],
            "results": [],
            "sources": [],
        }
    )
    _start_task(
        request,
        run_id,
        run_id,
        {
            "request": body.message.strip(),
            "steps": 0,
            "results": [],
            "events": [],
            "sources": [],
        },
    )
    document = request.app.state.database.runs.find_one({"_id": run_id})
    return _public_run(document)


@app.get("/api/runs")
async def list_runs(request: Request, limit: int = 25) -> list[dict[str, Any]]:
    documents = request.app.state.database.runs.find().sort("created_at", -1).limit(
        max(1, min(limit, 100))
    )
    return [_public_run(document) for document in documents]


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str, request: Request) -> dict[str, Any]:
    document = request.app.state.database.runs.find_one({"_id": run_id})
    if document is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    return _public_run(document)


@app.get("/api/approvals")
async def list_approvals(request: Request) -> list[dict[str, Any]]:
    documents = request.app.state.database.approvals.find({"status": "pending"}).sort(
        "created_at", 1
    )
    return [_public_approval(document) for document in documents]


@app.post("/api/approvals/{approval_id}/decision", status_code=status.HTTP_202_ACCEPTED)
async def decide_approval(
    approval_id: str,
    body: ApprovalDecision,
    request: Request,
) -> dict[str, str]:
    database = request.app.state.database
    approval = database.approvals.find_one_and_update(
        {"_id": approval_id, "status": "pending"},
        {
            "$set": {
                "status": "processing",
                "decision": body.model_dump(exclude_none=True),
                "updated_at": _now(),
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    if approval is None:
        raise HTTPException(
            status_code=404,
            detail="Approval was not found or has already been handled.",
        )

    database.runs.update_one(
        {"_id": approval["run_id"]},
        {"$set": {"status": "running", "pending_approval": None, "updated_at": _now()}},
    )
    _start_task(
        request,
        approval["run_id"],
        approval["thread_id"],
        Command(resume=body.model_dump(exclude_none=True)),
    )
    database.approvals.update_one(
        {"_id": approval_id},
        {"$set": {"status": body.action, "updated_at": _now()}},
    )
    return {"status": "accepted"}
