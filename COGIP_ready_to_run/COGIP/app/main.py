from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "cogip.db"
STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="COGIP - API de pointage",
    version="1.0.0",
    description="API de gestion du pointage COGIP pour interface web et ESP32.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().replace(microsecond=0).isoformat()


def init_db():
    conn = db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            badge_id TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            action TEXT NOT NULL CHECK(action IN ('IN', 'OUT')),
            scanned_at TEXT NOT NULL,
            device_id TEXT,
            FOREIGN KEY(employee_id) REFERENCES employees(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_attendance_employee
        ON attendance(employee_id);

        CREATE INDEX IF NOT EXISTS idx_attendance_scanned
        ON attendance(scanned_at);
    """)
    conn.commit()
    conn.close()


class EmployeeCreate(BaseModel):
    badge_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=150)


class EmployeeUpdate(BaseModel):
    badge_id: Optional[str] = Field(default=None, min_length=1, max_length=100)
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    active: Optional[bool] = None


class ScanRequest(BaseModel):
    badge_id: str = Field(min_length=1, max_length=100)
    device_id: Optional[str] = Field(default=None, max_length=100)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health():
    return {"success": True, "database": "sqlite", "database_file": str(DB_PATH)}


@app.get("/api/employees")
def list_employees(active_only: bool = False):
    conn = db()
    if active_only:
        rows = conn.execute(
            "SELECT * FROM employees WHERE active=1 ORDER BY name"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM employees ORDER BY name"
        ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.post("/api/employees", status_code=201)
def create_employee(data: EmployeeCreate):
    badge = data.badge_id.strip()
    name = data.name.strip()
    if not badge or not name:
        raise HTTPException(400, "Le badge et le nom sont obligatoires.")

    conn = db()
    try:
        cur = conn.execute(
            "INSERT INTO employees (badge_id, name, active, created_at) VALUES (?, ?, 1, ?)",
            (badge, name, now_iso()),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM employees WHERE id=?", (cur.lastrowid,)
        ).fetchone()
        return dict(row)
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Ce badge existe déjà.")
    finally:
        conn.close()


@app.patch("/api/employees/{employee_id}")
def update_employee(employee_id: int, data: EmployeeUpdate):
    conn = db()
    row = conn.execute(
        "SELECT * FROM employees WHERE id=?", (employee_id,)
    ).fetchone()
    if row is None:
        conn.close()
        raise HTTPException(404, "Employé introuvable.")

    fields = []
    values = []
    if data.badge_id is not None:
        fields.append("badge_id=?")
        values.append(data.badge_id.strip())
    if data.name is not None:
        fields.append("name=?")
        values.append(data.name.strip())
    if data.active is not None:
        fields.append("active=?")
        values.append(1 if data.active else 0)

    if fields:
        values.append(employee_id)
        try:
            conn.execute(
                f"UPDATE employees SET {', '.join(fields)} WHERE id=?",
                values,
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            raise HTTPException(409, "Ce badge existe déjà.")

    row = conn.execute(
        "SELECT * FROM employees WHERE id=?", (employee_id,)
    ).fetchone()
    conn.close()
    return dict(row)


@app.delete("/api/employees/{employee_id}")
def delete_employee(employee_id: int):
    conn = db()
    row = conn.execute(
        "SELECT * FROM employees WHERE id=?", (employee_id,)
    ).fetchone()
    if row is None:
        conn.close()
        raise HTTPException(404, "Employé introuvable.")

    conn.execute("DELETE FROM employees WHERE id=?", (employee_id,))
    conn.commit()
    conn.close()
    return {"success": True, "message": "Employé supprimé."}


def get_last_action(conn, employee_id: int):
    row = conn.execute(
        "SELECT action FROM attendance WHERE employee_id=? ORDER BY id DESC LIMIT 1",
        (employee_id,),
    ).fetchone()
    return row["action"] if row else None


@app.post("/api/scan")
def scan(data: ScanRequest):
    badge = data.badge_id.strip()
    if not badge:
        raise HTTPException(400, "badge_id est obligatoire.")

    conn = db()
    employee = conn.execute(
        "SELECT * FROM employees WHERE badge_id=? AND active=1",
        (badge,),
    ).fetchone()

    if employee is None:
        conn.close()
        raise HTTPException(404, "Badge inconnu ou employé désactivé.")

    last_action = get_last_action(conn, employee["id"])
    action = "OUT" if last_action == "IN" else "IN"
    timestamp = now_iso()

    conn.execute(
        "INSERT INTO attendance (employee_id, action, scanned_at, device_id) VALUES (?, ?, ?, ?)",
        (employee["id"], action, timestamp, data.device_id),
    )
    conn.commit()

    row = conn.execute(
        "SELECT * FROM attendance WHERE id=last_insert_rowid()"
    ).fetchone()
    conn.close()

    return {
        "success": True,
        "message": "Entrée enregistrée" if action == "IN" else "Sortie enregistrée",
        "employee": {
            "id": employee["id"],
            "badge_id": employee["badge_id"],
            "name": employee["name"],
        },
        "action": action,
        "scanned_at": row["scanned_at"],
        "device_id": data.device_id,
    }


@app.get("/api/attendance")
def attendance(
    limit: int = Query(default=100, ge=1, le=1000),
    employee_id: Optional[int] = None,
):
    conn = db()
    if employee_id is None:
        rows = conn.execute(
            """
            SELECT a.id, a.action, a.scanned_at, a.device_id,
                   e.id AS employee_id, e.badge_id, e.name
            FROM attendance a
            JOIN employees e ON e.id=a.employee_id
            ORDER BY a.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT a.id, a.action, a.scanned_at, a.device_id,
                   e.id AS employee_id, e.badge_id, e.name
            FROM attendance a
            JOIN employees e ON e.id=a.employee_id
            WHERE e.id=?
            ORDER BY a.id DESC
            LIMIT ?
            """,
            (employee_id, limit),
        ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


@app.get("/api/status")
def status():
    conn = db()
    employees = conn.execute(
        "SELECT COUNT(*) AS n FROM employees WHERE active=1"
    ).fetchone()["n"]
    present = conn.execute(
        """
        SELECT COUNT(*) AS n
        FROM employees e
        WHERE e.active=1
          AND (
            SELECT a.action FROM attendance a
            WHERE a.employee_id=e.id
            ORDER BY a.id DESC LIMIT 1
          ) = 'IN'
        """
    ).fetchone()["n"]
    scans = conn.execute(
        "SELECT COUNT(*) AS n FROM attendance"
    ).fetchone()["n"]
    conn.close()
    return {
        "active_employees": employees,
        "present": present,
        "absent": employees - present,
        "total_scans": scans,
    }
