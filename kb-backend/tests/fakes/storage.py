"""In-memory substitutes for MinIO and Milvus clients."""

from __future__ import annotations

import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable


class FakeMinIO:
    def __init__(self) -> None:
        self.buckets: set[str] = set()
        self.objects: dict[tuple[str, str], bytes] = {}

    def bucket_exists(self, bucket: str) -> bool:
        return bucket in self.buckets

    def make_bucket(self, bucket: str) -> None:
        self.buckets.add(bucket)

    def fput_object(self, bucket: str, object_name: str, local_path: str) -> SimpleNamespace:
        if bucket not in self.buckets:
            raise ValueError(f"bucket does not exist: {bucket}")
        self.objects[(bucket, object_name)] = Path(local_path).read_bytes()
        return SimpleNamespace(object_name=object_name)

    def fget_object(self, bucket: str, object_name: str, local_path: str) -> None:
        Path(local_path).write_bytes(self.objects[(bucket, object_name)])

    def remove_object(self, bucket: str, object_name: str) -> None:
        self.objects.pop((bucket, object_name), None)

    def remove_objects(self, bucket: str, object_names: Iterable[str]) -> list[Any]:
        for object_name in object_names:
            self.remove_object(bucket, object_name)
        return []

    def list_objects(self, bucket: str, prefix: str = "", recursive: bool = True) -> list[SimpleNamespace]:
        del recursive
        return [
            SimpleNamespace(object_name=name)
            for stored_bucket, name in sorted(self.objects)
            if stored_bucket == bucket and name.startswith(prefix)
        ]

    def presigned_get_object(self, bucket: str, object_name: str, **_: Any) -> str:
        return f"https://fake-minio.local/{bucket}/{object_name}"


class FakeMilvus:
    def __init__(self) -> None:
        self.collections: dict[str, list[dict[str, Any]]] = {}

    def has_collection(self, collection_name: str) -> bool:
        return collection_name in self.collections

    def create_collection(self, collection_name: str, **_: Any) -> None:
        self.collections.setdefault(collection_name, [])

    def create_index(self, **_: Any) -> None:
        return None

    def load_collection(self, **_: Any) -> None:
        return None

    def insert(self, collection_name: str, data: list[dict[str, Any]]) -> SimpleNamespace:
        self.collections.setdefault(collection_name, []).extend(data)
        return SimpleNamespace(insert_count=len(data))

    def search(
        self,
        collection_name: str,
        data: list[list[float]],
        limit: int,
        output_fields: list[str] | None = None,
        **_: Any,
    ) -> list[list[dict[str, Any]]]:
        query = data[0]
        hits = []
        for row in self.collections.get(collection_name, []):
            entity = {key: value for key, value in row.items() if key != "vector"}
            if output_fields:
                entity = {key: entity[key] for key in output_fields if key in entity}
            hits.append({"distance": self._cosine(query, list(row["vector"])), "entity": entity})
        hits.sort(key=lambda hit: hit["distance"], reverse=True)
        return [hits[:limit]]

    def delete(self, collection_name: str, filter: str, **_: Any) -> None:
        prefix = 'unit_id == "'
        if filter.startswith(prefix) and filter.endswith('"'):
            unit_id = filter[len(prefix) : -1]
            self.collections[collection_name] = [
                row for row in self.collections.get(collection_name, []) if row.get("unit_id") != unit_id
            ]

    @staticmethod
    def _cosine(left: list[float], right: list[float]) -> float:
        dot = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(value * value for value in left)) or 1.0
        right_norm = math.sqrt(sum(value * value for value in right)) or 1.0
        return dot / (left_norm * right_norm)
