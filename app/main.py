from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATABASE = PROJECT_ROOT / "data" / "students.db"


class StudentFields(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    date_of_birth: date
    email: EmailStr | None = None
    phone: str | None = Field(default=None, min_length=7, max_length=30)
    course: str | None = Field(default=None, max_length=120)
    address: str | None = Field(default=None, max_length=300)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value

    @field_validator("phone")
    @classmethod
    def phone_not_blank(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            if not value:
                raise ValueError("phone must not be blank when provided")
        return value

    @model_validator(mode="after")
    def contact_required(self):
        if not self.email and not self.phone:
            raise ValueError("provide at least one contact method: email or phone")
        return self


class StudentCreate(StudentFields):
    student_id: str = Field(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_-]+$")


class StudentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=120)
    date_of_birth: date | None = None
    email: EmailStr | None = None
    phone: str | None = Field(default=None, min_length=7, max_length=30)
    course: str | None = Field(default=None, max_length=120)
    address: str | None = Field(default=None, max_length=300)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            if not value:
                raise ValueError("name must not be blank")
        return value


class Student(StudentFields):
    student_id: str


def create_app(database_path: str | Path = DEFAULT_DATABASE) -> FastAPI:
    db_path = Path(database_path)

    def connect() -> sqlite3.Connection:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def database_connection():
        connection = connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize_database() -> None:
        with database_connection() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS students (
                    student_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    date_of_birth TEXT NOT NULL,
                    email TEXT,
                    phone TEXT,
                    course TEXT,
                    address TEXT,
                    CHECK (email IS NOT NULL OR phone IS NOT NULL)
                )"""
            )

    app = FastAPI(
        title="Students Database CRUD Application",
        description="A simple student records API backed by SQLite.",
        version="1.0.0",
    )

    def row_to_student(row: sqlite3.Row) -> Student:
        return Student(**dict(row))

    @app.post("/students", response_model=Student, status_code=status.HTTP_201_CREATED)
    def create_student(student: StudentCreate):
        try:
            with database_connection() as connection:
                connection.execute(
                    "INSERT INTO students (student_id, name, date_of_birth, email, phone, course, address) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (student.student_id, student.name, student.date_of_birth.isoformat(),
                     str(student.email) if student.email else None, student.phone, student.course, student.address),
                )
                row = connection.execute("SELECT * FROM students WHERE student_id = ?", (student.student_id,)).fetchone()
        except sqlite3.IntegrityError as exc:
            if "students.student_id" in str(exc):
                raise HTTPException(status_code=409, detail=f"Student '{student.student_id}' already exists") from exc
            raise HTTPException(status_code=400, detail="Student data violates a database constraint") from exc
        return row_to_student(row)

    @app.get("/students", response_model=list[Student])
    def list_students(
        name: Annotated[str | None, Query(max_length=120)] = None,
        course: Annotated[str | None, Query(max_length=120)] = None,
        email: Annotated[str | None, Query(max_length=254)] = None,
    ):
        clauses, values = [], []
        for column, value in (("name", name), ("course", course), ("email", email)):
            if value:
                clauses.append(f"{column} LIKE ?")
                values.append(f"%{value.strip()}%")
        sql = "SELECT * FROM students"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY student_id"
        with database_connection() as connection:
            rows = connection.execute(sql, values).fetchall()
        return [row_to_student(row) for row in rows]

    @app.get("/students/{student_id}", response_model=Student)
    def get_student(student_id: str):
        with database_connection() as connection:
            row = connection.execute("SELECT * FROM students WHERE student_id = ?", (student_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Student '{student_id}' was not found")
        return row_to_student(row)

    @app.put("/students/{student_id}", response_model=Student)
    def update_student(student_id: str, changes: StudentUpdate):
        updates = changes.model_dump(exclude_unset=True)
        if not updates:
            raise HTTPException(status_code=400, detail="Provide at least one field to update")
        with database_connection() as connection:
            existing = connection.execute("SELECT * FROM students WHERE student_id = ?", (student_id,)).fetchone()
            if existing is None:
                raise HTTPException(status_code=404, detail=f"Student '{student_id}' was not found")
            merged = dict(existing)
            merged.update(updates)
            try:
                Student(**merged)
            except Exception as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            if "email" in updates:
                updates["email"] = str(updates["email"]) if updates["email"] else None
            if "date_of_birth" in updates:
                updates["date_of_birth"] = updates["date_of_birth"].isoformat() if updates["date_of_birth"] else None
            assignments = ", ".join(f"{field} = ?" for field in updates)
            connection.execute(
                f"UPDATE students SET {assignments} WHERE student_id = ?",
                [*updates.values(), student_id],
            )
            row = connection.execute("SELECT * FROM students WHERE student_id = ?", (student_id,)).fetchone()
        return row_to_student(row)

    @app.delete("/students/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_student(student_id: str):
        with database_connection() as connection:
            cursor = connection.execute("DELETE FROM students WHERE student_id = ?", (student_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Student '{student_id}' was not found")
        return None

    initialize_database()
    return app


app = create_app()
