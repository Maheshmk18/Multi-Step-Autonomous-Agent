import json
import re
from functools import lru_cache
from typing import Literal

from bson import json_util
from mcp.server.fastmcp import FastMCP
from pymongo import MongoClient

from app.config import settings


mcp = FastMCP("mongodb")


@lru_cache(maxsize=1)
def _database():
    if not settings.mongodb_data_uri:
        raise RuntimeError("Set a read-only MONGODB_DATA_URI before using the data agent.")
    return MongoClient(settings.mongodb_data_uri, serverSelectionTimeoutMS=5000)[
        settings.mongodb_data_database
    ]


def _collection_name(name: str) -> str:
    if name not in settings.allowed_collections:
        raise ValueError("Collection is not in MONGODB_ALLOWED_COLLECTIONS.")
    return name


def _json_ready(value: object) -> object:
    return json.loads(json_util.dumps(value))


def _query_value(value: str) -> object:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return value
    return value if isinstance(parsed, (dict, list)) else parsed


@mcp.tool(
    name="list_collections",
    description="List collections explicitly allowed for read-only data lookup.",
)
def list_collections() -> dict[str, list[str]]:
    database = _database()
    existing = set(database.list_collection_names())
    return {"collections": sorted(existing.intersection(settings.allowed_collections))}


@mcp.tool(
    name="describe_collection",
    description="Return sample field names and an approximate document count for an allowed collection.",
)
def describe_collection(collection: str) -> dict[str, object]:
    name = _collection_name(collection)
    target = _database()[name]
    sample = target.find_one({}, projection={"_id": 0})
    return {
        "collection": name,
        "fields": sorted(sample.keys()) if sample else [],
        "approximate_count": target.estimated_document_count(),
    }


@mcp.tool(
    name="find_documents",
    description="Find up to 50 documents in an allowed collection using one safe field comparison.",
)
def find_documents(
    collection: str,
    field: str,
    operator: Literal["eq", "contains", "gte", "lte"],
    value: str,
    limit: int = 20,
) -> dict[str, object]:
    name = _collection_name(collection)
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", field):
        raise ValueError("Field must be a simple field name.")
    query_value = _query_value(value)
    if operator == "eq":
        query = {field: query_value}
    elif operator == "contains":
        query = {field: {"$regex": re.escape(value), "$options": "i"}}
    elif operator == "gte":
        query = {field: {"$gte": query_value}}
    else:
        query = {field: {"$lte": query_value}}

    documents = list(
        _database()[name]
        .find(query, projection={"_id": 0})
        .limit(max(1, min(limit, 50)))
    )
    return {"documents": _json_ready(documents)}


if __name__ == "__main__":
    mcp.run()
