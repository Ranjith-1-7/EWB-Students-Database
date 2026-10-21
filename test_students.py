
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.main import StudentCreate, StudentUpdate, create_app


def sample_student(student_id="STU-001", **overrides):
    return {"student_id": student_id, "name": "Asha Rao", "date_of_birth": "2003-04-12", "email": "asha@example.com", "phone": "+1-555-0100", "course": "Data Science", "address": "12 Sample Street", **overrides}


def handler(app, path, method):
    return next(route.endpoint for route in app.routes if getattr(route, "path", None) == path and method in getattr(route, "methods", set()))


def invoke(function, *args, **kwargs):
    return function(*args, **kwargs)


@pytest.fixture
def app(tmp_path):
    return create_app(tmp_path / "students-test.db")


def test_create_list_filter_and_get(app):
    create = handler(app, "/students", "POST")
    student = invoke(create, StudentCreate.model_validate(sample_student()))
    assert student.student_id == "STU-001"
    list_students = handler(app, "/students", "GET")
    assert invoke(list_students, None, None, None)[0].name == "Asha Rao"
    assert len(invoke(list_students, "Asha", None, None)) == 1
    assert len(invoke(list_students, None, "Science", None)) == 1
    assert len(invoke(list_students, None, None, "asha@example")) == 1
    assert invoke(list_students, None, "History", None) == []
    get_student = handler(app, "/students/{student_id}", "GET")
    assert invoke(get_student, "STU-001").email == "asha@example.com"


def test_duplicate_and_missing_student_errors(app):
    create = handler(app, "/students", "POST")
    invoke(create, StudentCreate.model_validate(sample_student()))
    with pytest.raises(HTTPException) as duplicate:
        invoke(create, StudentCreate.model_validate(sample_student()))
    assert duplicate.value.status_code == 409
    get_student = handler(app, "/students/{student_id}", "GET")
    with pytest.raises(HTTPException) as missing:
        invoke(get_student, "nope")
    assert missing.value.status_code == 404
    update = handler(app, "/students/{student_id}", "PUT")
    with pytest.raises(HTTPException) as missing_update:
        invoke(update, "nope", StudentUpdate.model_validate({"name": "New Name"}))
    assert missing_update.value.status_code == 404
    delete = handler(app, "/students/{student_id}", "DELETE")
    with pytest.raises(HTTPException) as missing_delete:
        invoke(delete, "nope")
    assert missing_delete.value.status_code == 404


def test_update_and_delete(app):
    invoke(handler(app, "/students", "POST"), StudentCreate.model_validate(sample_student()))
    update = handler(app, "/students/{student_id}", "PUT")
    updated = invoke(update, "STU-001", StudentUpdate.model_validate({"course": "Engineering"}))
    assert updated.course == "Engineering"
    with pytest.raises(HTTPException) as empty_update:
        invoke(update, "STU-001", StudentUpdate.model_validate({}))
    assert empty_update.value.status_code == 400
    delete = handler(app, "/students/{student_id}", "DELETE")
    assert invoke(delete, "STU-001") is None
    with pytest.raises(HTTPException) as missing:
        invoke(handler(app, "/students/{student_id}", "GET"), "STU-001")
    assert missing.value.status_code == 404


@pytest.mark.parametrize("payload", [
    sample_student(name="  "), sample_student(email="not-an-email"),
    sample_student(email=None, phone=None), sample_student(date_of_birth="not-a-date"),
    sample_student(student_id="bad id"),
])
def test_invalid_inputs_are_rejected(payload):
    with pytest.raises(ValidationError):
        StudentCreate.model_validate(payload)


def test_update_cannot_remove_last_contact(app):
    invoke(handler(app, "/students", "POST"), StudentCreate.model_validate(sample_student(phone=None)))
    with pytest.raises(HTTPException) as invalid:
        invoke(handler(app, "/students/{student_id}", "PUT"), "STU-001", StudentUpdate.model_validate({"email": None}))
    assert invalid.value.status_code == 422
    assert "contact method" in invalid.value.detail


def test_persistence_across_app_instances(tmp_path):
    db_path = tmp_path / "persistent.db"
    first = create_app(db_path)
    invoke(handler(first, "/students", "POST"), StudentCreate.model_validate(sample_student()))
    second = create_app(db_path)
    student = invoke(handler(second, "/students/{student_id}", "GET"), "STU-001")
    assert student.name == "Asha Rao"
