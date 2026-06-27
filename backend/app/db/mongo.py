from __future__ import annotations

import copy
import re
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def serialize_doc(value: Any) -> Any:
    if isinstance(value, list):
        return [serialize_doc(item) for item in value]
    if isinstance(value, dict):
        return {key: serialize_doc(item) for key, item in value.items()}
    if value.__class__.__name__ == "ObjectId":
        return str(value)
    return value


def get_nested(doc: dict[str, Any], dotted_key: str) -> Any:
    current: Any = doc
    for part in dotted_key.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def set_nested(doc: dict[str, Any], dotted_key: str, value: Any) -> None:
    current = doc
    parts = dotted_key.split(".")
    for part in parts[:-1]:
        current = current.setdefault(part, {})
    current[parts[-1]] = value


def _matches_operator(actual: Any, operator: str, expected: Any, options: str = "") -> bool:
    if operator == "$in":
        if isinstance(actual, list):
            return any(item in expected for item in actual)
        return actual in expected
    if operator == "$gte":
        return actual is not None and actual >= expected
    if operator == "$lte":
        return actual is not None and actual <= expected
    if operator == "$gt":
        return actual is not None and actual > expected
    if operator == "$lt":
        return actual is not None and actual < expected
    if operator == "$regex":
        flags = re.IGNORECASE if "i" in options else 0
        return actual is not None and re.search(str(expected), str(actual), flags) is not None
    if operator == "$ne":
        return actual != expected
    return False


def matches_filter(doc: dict[str, Any], query: dict[str, Any] | None) -> bool:
    if not query:
        return True

    for key, expected in query.items():
        if key == "$or":
            return any(matches_filter(doc, clause) for clause in expected)
        if key == "$and":
            return all(matches_filter(doc, clause) for clause in expected)

        actual = get_nested(doc, key)
        if isinstance(expected, dict):
            regex_options = expected.get("$options", "")
            for operator, operator_expected in expected.items():
                if operator == "$options":
                    continue
                if not _matches_operator(actual, operator, operator_expected, regex_options):
                    return False
            continue

        if isinstance(actual, list):
            if expected not in actual:
                return False
        elif actual != expected:
            return False

    return True


class AppDatabase:
    """Tiny repository wrapper that uses MongoDB Atlas when configured.

    Without MONGODB_URI it falls back to an in-memory store so judges can run
    the hackathon demo immediately.
    """

    def __init__(self, settings: Any):
        self.settings = settings
        self.client = None
        self.db = None
        self.memory: dict[str, list[dict[str, Any]]] = defaultdict(list)

    @property
    def is_mongo(self) -> bool:
        return self.db is not None

    async def connect(self) -> None:
        if not self.settings.mongodb_uri:
            return

        from motor.motor_asyncio import AsyncIOMotorClient

        self.client = AsyncIOMotorClient(self.settings.mongodb_uri)
        self.db = self.client[self.settings.mongodb_db_name]
        await self.db.command("ping")

    async def close(self) -> None:
        if self.client:
            self.client.close()

    def collection(self, name: str) -> Any:
        if not self.is_mongo:
            raise RuntimeError("MongoDB is not configured")
        return self.db[name]

    async def insert_one(self, collection: str, doc: dict[str, Any]) -> str:
        payload = copy.deepcopy(doc)
        payload.setdefault("_id", str(uuid.uuid4()))
        payload.setdefault("created_at", utc_now())
        payload.setdefault("updated_at", utc_now())

        if self.is_mongo:
            await self.db[collection].insert_one(payload)
        else:
            self.memory[collection].append(payload)
        return str(payload["_id"])

    async def insert_many(self, collection: str, docs: list[dict[str, Any]]) -> list[str]:
        ids = []
        for doc in docs:
            ids.append(await self.insert_one(collection, doc))
        return ids

    async def find_one(self, collection: str, query: dict[str, Any] | None = None) -> dict[str, Any] | None:
        if self.is_mongo:
            doc = await self.db[collection].find_one(query or {})
            return serialize_doc(doc) if doc else None

        for doc in self.memory[collection]:
            if matches_filter(doc, query):
                return serialize_doc(copy.deepcopy(doc))
        return None

    async def find_many(
        self,
        collection: str,
        query: dict[str, Any] | None = None,
        *,
        sort: list[tuple[str, int]] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if self.is_mongo:
            cursor = self.db[collection].find(query or {})
            if sort:
                cursor = cursor.sort(sort)
            cursor = cursor.limit(limit)
            return serialize_doc(await cursor.to_list(length=limit))

        docs = [copy.deepcopy(doc) for doc in self.memory[collection] if matches_filter(doc, query)]
        if sort:
            for key, direction in reversed(sort):
                docs.sort(key=lambda item: get_nested(item, key) or 0, reverse=direction < 0)
        return serialize_doc(docs[:limit])

    async def update_one(
        self,
        collection: str,
        query: dict[str, Any],
        update: dict[str, Any],
        *,
        upsert: bool = False,
    ) -> None:
        if self.is_mongo:
            await self.db[collection].update_one(query, update, upsert=upsert)
            return

        target = None
        inserted = False
        for doc in self.memory[collection]:
            if matches_filter(doc, query):
                target = doc
                break

        if target is None and upsert:
            target = {key: value for key, value in query.items() if not key.startswith("$") and not isinstance(value, dict)}
            target.setdefault("_id", target.get("student_id", str(uuid.uuid4())))
            target.setdefault("created_at", utc_now())
            target.setdefault("updated_at", utc_now())
            self.memory[collection].append(target)
            inserted = True

        if target is None:
            return

        if "$setOnInsert" in update and inserted:
            for key, value in update["$setOnInsert"].items():
                target.setdefault(key, copy.deepcopy(value))
        for key, value in update.get("$set", {}).items():
            set_nested(target, key, copy.deepcopy(value))
        for key, value in update.get("$inc", {}).items():
            set_nested(target, key, (get_nested(target, key) or 0) + value)
        for key, value in update.get("$push", {}).items():
            current = get_nested(target, key) or []
            if isinstance(value, dict) and "$each" in value:
                current.extend(copy.deepcopy(value["$each"]))
            else:
                current.append(copy.deepcopy(value))
            set_nested(target, key, current)
        for key, value in update.get("$addToSet", {}).items():
            current = get_nested(target, key) or []
            values = value.get("$each", []) if isinstance(value, dict) and "$each" in value else [value]
            for item in values:
                if item not in current:
                    current.append(copy.deepcopy(item))
            set_nested(target, key, current)
        target["updated_at"] = utc_now()

    async def delete_many(self, collection: str, query: dict[str, Any] | None = None) -> int:
        if self.is_mongo:
            result = await self.db[collection].delete_many(query or {})
            return result.deleted_count

        original_count = len(self.memory[collection])
        self.memory[collection] = [doc for doc in self.memory[collection] if not matches_filter(doc, query)]
        return original_count - len(self.memory[collection])

    async def count_documents(self, collection: str, query: dict[str, Any] | None = None) -> int:
        if self.is_mongo:
            return await self.db[collection].count_documents(query or {})
        return sum(1 for doc in self.memory[collection] if matches_filter(doc, query))
