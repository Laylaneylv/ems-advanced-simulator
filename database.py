"""Database utilities for the EMS web application."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from typing import Any, Dict, Iterable, Optional

import pandas as pd
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    func,
    text,
)
from sqlalchemy.engine import Engine, Result
from sqlalchemy.exc import IntegrityError

# Determine database URL (external DB via env var, fallback to local SQLite)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///ems_users.db")

# SQLite needs a special flag to allow usage across multiple threads (Streamlit)
connect_args: Dict[str, Any] = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

# Create SQLAlchemy engine with pooling and pre-ping to keep connections healthy
engine: Engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    future=True,
    pool_pre_ping=True,
)

metadata = MetaData()

users_table = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("username", String, unique=True, nullable=False),
    Column("email", String, unique=True, nullable=False),
    Column("password_hash", String, nullable=False),
    Column("company", String),
    Column("created_at", DateTime, server_default=func.now()),
    Column("last_login", DateTime),
)

user_sessions_table = Table(
    "user_sessions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, ForeignKey("users.id")),
    Column("session_data", Text),
    Column("created_at", DateTime, server_default=func.now()),
)

simulation_results_table = Table(
    "simulation_results",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, ForeignKey("users.id")),
    Column("project_name", String),
    Column("simulation_data", Text),
    Column("config_data", Text),
    Column("results_data", Text),
    Column("created_at", DateTime, server_default=func.now()),
)


@contextmanager
def get_connection():
    """Provide a transactional scope around a series of operations."""
    with engine.begin() as connection:
        yield connection


def init_db() -> None:
    """Initialize required tables if they do not exist."""
    metadata.create_all(engine)


def create_user(username: str, email: str, password_hash: str, company: str) -> bool:
    """Create a new user record."""
    try:
        with get_connection() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO users (username, email, password_hash, company)
                    VALUES (:username, :email, :password_hash, :company)
                    """
                ),
                {
                    "username": username,
                    "email": email,
                    "password_hash": password_hash,
                    "company": company,
                },
            )
        return True
    except IntegrityError:
        return False


def fetch_user(username: str, password_hash: str) -> Optional[Dict[str, Any]]:
    """Retrieve a user by username/password hash."""
    with engine.connect() as conn:
        result: Result = conn.execute(
            text(
                """
                SELECT id, username, email, company
                FROM users
                WHERE username = :username AND password_hash = :password_hash
                """
            ),
            {"username": username, "password_hash": password_hash},
        )
        row = result.mappings().first()
        return dict(row) if row else None


def save_simulation_result(
    user_id: int,
    project_name: str,
    config: Dict[str, Any],
    results: Dict[str, Any],
) -> bool:
    """Persist simulation config and results for a user."""
    try:
        serializable_results = results.copy()
        if "data" in serializable_results and isinstance(serializable_results["data"], pd.DataFrame):
            serializable_results["data"] = serializable_results["data"].to_dict("records")

        with get_connection() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO simulation_results (user_id, project_name, config_data, results_data)
                    VALUES (:user_id, :project_name, :config_data, :results_data)
                    """
                ),
                {
                    "user_id": user_id,
                    "project_name": project_name,
                    "config_data": json.dumps(config),
                    "results_data": json.dumps(serializable_results, default=str),
                },
            )
        return True
    except Exception:
        return False


def get_user_simulations(user_id: int) -> Iterable[tuple]:
    """Return recent simulations for a user ordered by creation date."""
    with engine.connect() as conn:
        result: Result = conn.execute(
            text(
                """
                SELECT id, project_name, created_at
                FROM simulation_results
                WHERE user_id = :user_id
                ORDER BY created_at DESC
                """
            ),
            {"user_id": user_id},
        )
        return result.fetchall()


def get_simulation_details(simulation_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve the stored config and results for a simulation."""
    with engine.connect() as conn:
        result: Result = conn.execute(
            text(
                """
                SELECT project_name, config_data, results_data
                FROM simulation_results
                WHERE id = :simulation_id
                """
            ),
            {"simulation_id": simulation_id},
        )
        row = result.first()

    if not row:
        return None

    project_name, config_data, results_data = row
    config = json.loads(config_data)
    results = json.loads(results_data)

    if "data" in results and isinstance(results["data"], list):
        results["data"] = pd.DataFrame(results["data"])
        if "timestamp" in results["data"].columns:
            results["data"]["timestamp"] = pd.to_datetime(results["data"]["timestamp"])

    return {
        "project_name": project_name,
        "config": config,
        "results": results,
    }
