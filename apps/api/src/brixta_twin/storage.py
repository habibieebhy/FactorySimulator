from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from pydantic import BaseModel

from .models import Blend, CostBook, Machine, Material, Route, RunResult


class Repository:
    models: dict[str, type[BaseModel]] = {
        "materials": Material,
        "blends": Blend,
        "machines": Machine,
        "routes": Route,
        "cost_books": CostBook,
        "runs": RunResult,
    }
    id_fields = {
        "materials": "material_id",
        "blends": "blend_id",
        "machines": "machine_id",
        "routes": "route_id",
        "cost_books": "cost_book_id",
        "runs": "run_id",
    }

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
        if table not in self.models:
            raise ValueError(f"Unknown repository table: {table}")
        entity_id = str(getattr(model, self.id_fields[table]))
        with self.connect() as db:
            statement = (
                f"INSERT INTO {table} VALUES(?,?,?)"
                if table == "runs"
                else f"INSERT OR REPLACE INTO {table} VALUES(?,?,?)"
            )
            db.execute(statement, (entity_id, model.model_dump_json(), str(getattr(model, "created_at"))))
        return model

    def get(self, table: str, entity_id: str) -> BaseModel | None:
        with self.connect() as db:
            row = db.execute(f"SELECT payload FROM {table} WHERE entity_id=?", (entity_id,)).fetchone()
        return self.models[table].model_validate_json(row["payload"]) if row else None

    def list(self, table: str) -> list[BaseModel]:
        if table not in self.models:
            raise ValueError(f"Unknown repository table: {table}")
        order = "DESC" if table == "runs" else "ASC"
        with self.connect() as db:
            rows = db.execute(f"SELECT payload FROM {table} ORDER BY created_at {order}").fetchall()
        return [self.models[table].model_validate_json(row["payload"]) for row in rows]

    def delete(self, table: str, entity_id: str) -> bool:
        if table not in self.models or table == "runs":
            raise ValueError(f"Deletion is not allowed for repository table: {table}")
        with self.connect() as db:
            cursor = db.execute(
                f"DELETE FROM {table} WHERE entity_id=?",
                (entity_id,),
            )
        return cursor.rowcount > 0

    def references(self, table: str, entity_id: str) -> list[str]:
        """Return immutable records that depend on an entity.

        Hard deletion is only safe when this list is empty. Archived records are
        intentionally included because historical lineage must remain readable.
        """

        references: list[str] = []
        if table == "materials":
            for item in self.list("blends"):
                assert isinstance(item, Blend)
                if any(
                    component.component_type == "material"
                    and component.material_id == entity_id
                    for component in item.components
                ):
                    references.append(f"blend:{item.blend_id}")
            for item in self.list("cost_books"):
                assert isinstance(item, CostBook)
                if any(entry.material_id == entity_id for entry in item.material_costs):
                    references.append(f"cost_book:{item.cost_book_id}")
            for item in self.list("runs"):
                assert isinstance(item, RunResult)
                if any(material.material_id == entity_id for material in item.material_snapshots):
                    references.append(f"run:{item.run_id}")
        elif table == "blends":
            for item in self.list("blends"):
                assert isinstance(item, Blend)
                if item.blend_id != entity_id and any(
                    component.component_type == "blend"
                    and component.blend_id == entity_id
                    for component in item.components
                ):
                    references.append(f"blend:{item.blend_id}")
            for item in self.list("runs"):
                assert isinstance(item, RunResult)
                if item.request.blend_id == entity_id:
                    references.append(f"run:{item.run_id}")
        elif table == "machines":
            for item in self.list("routes"):
                assert isinstance(item, Route)
                if any(node.machine_id == entity_id for node in item.nodes):
                    references.append(f"route:{item.route_id}")
            for item in self.list("runs"):
                assert isinstance(item, RunResult)
                if any(machine.machine_id == entity_id for machine in item.machine_snapshots):
                    references.append(f"run:{item.run_id}")
        elif table == "routes":
            for item in self.list("runs"):
                assert isinstance(item, RunResult)
                if item.request.route_id == entity_id:
                    references.append(f"run:{item.run_id}")
        elif table == "cost_books":
            for item in self.list("runs"):
                assert isinstance(item, RunResult)
                if item.request.cost_book_id == entity_id:
                    references.append(f"run:{item.run_id}")
        return sorted(set(references))
