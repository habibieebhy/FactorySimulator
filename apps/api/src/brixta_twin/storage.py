from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from pydantic import BaseModel

from .models import Blend, Machine, Material, Route, RunResult


class Repository:
    models: dict[str, type[BaseModel]] = {
        "materials": Material,
        "blends": Blend,
        "machines": Machine,
        "routes": Route,
        "runs": RunResult,
    }
    id_fields = {"materials": "material_id", "blends": "blend_id", "machines": "machine_id", "routes": "route_id", "runs": "run_id"}

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path or os.getenv("BRIXTA_TWIN_DATABASE_PATH", "./data/brixta_twin.sqlite3")).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            for table in self.models:
                db.execute(f"CREATE TABLE IF NOT EXISTS {table}(entity_id TEXT PRIMARY KEY,payload TEXT NOT NULL,created_at TEXT NOT NULL)")

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        return db

    def count(self, table: str) -> int:
        with self.connect() as db:
            row = db.execute(f"SELECT count(*) c FROM {table}").fetchone()
            return int(row["c"]) if row else 0

    def save(self, table: str, model: BaseModel) -> BaseModel:
        entity_id = str(getattr(model, self.id_fields[table]))
        with self.connect() as db:
            db.execute(f"INSERT OR REPLACE INTO {table} VALUES(?,?,?)", (entity_id, model.model_dump_json(), str(getattr(model, "created_at"))))
        return model

    def get(self, table: str, entity_id: str) -> BaseModel | None:
        with self.connect() as db:
            row = db.execute(f"SELECT payload FROM {table} WHERE entity_id=?", (entity_id,)).fetchone()
        return self.models[table].model_validate_json(row["payload"]) if row else None

    def list(self, table: str) -> list[BaseModel]:
        with self.connect() as db:
            rows = db.execute(f"SELECT payload FROM {table} ORDER BY created_at").fetchall()
        return [self.models[table].model_validate_json(row["payload"]) for row in rows]

