# Students Database CRUD Application

A small student records API built with Python, FastAPI, and SQLite. It uses dummy data during the examples and does not include the optional Ollama extension.

## Requirements

- Python 3.10 or newer
- pip

## Setup

```powershell
# If ensurepip cannot use the Windows temporary directory (seen with some
# Python 3.15 installations), direct temp files into this writable folder.
New-Item -ItemType Directory -Force .tmp | Out-Null
$env:TEMP = (Resolve-Path .tmp).Path
$env:TMP = $env:TEMP

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Run

```powershell
python -m app
```

The service listens on `http://127.0.0.1:8000`. Open `http://127.0.0.1:8000/docs` for interactive API documentation. SQLite creates `data/students.db` automatically on startup.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/students` | Create a student |
| GET | `/students` | List students; optional `name`, `course`, and `email` substring filters |
| GET | `/students/{student_id}` | Get one student |
| PUT | `/students/{student_id}` | Update one or more student fields |
| DELETE | `/students/{student_id}` | Delete a student |

Each student needs an ID, name, date of birth, and at least one of email or phone. IDs may contain letters, numbers, `_`, or `-`. Invalid input returns FastAPI's validation response (422); duplicates return 409; unknown IDs return 404.

## Example requests and responses

Create a dummy student:

```http
POST /students
Content-Type: application/json

{
  "student_id": "EWB-1001",
  "name": "Asha Rao",
  "date_of_birth": "2003-04-12",
  "email": "asha@example.com",
  "phone": "+1-555-0100",
  "course": "Data Science",
  "address": "12 Sample Street"
}
```

Response (`201 Created`):

```json
{
  "student_id": "EWB-1001",
  "name": "Asha Rao",
  "date_of_birth": "2003-04-12",
  "email": "asha@example.com",
  "phone": "+1-555-0100",
  "course": "Data Science",
  "address": "12 Sample Street"
}
```

Filter with `GET /students?course=Data%20Science`, fetch with `GET /students/EWB-1001`, and update with:

```http
PUT /students/EWB-1001
Content-Type: application/json

{"course": "Applied Data Science"}
```

Successful updates return `200 OK` with the updated student. Deletion returns `204 No Content`.

## Tests

```powershell
pytest -q
```

The tests use isolated temporary SQLite files and cover create, list/filter, read, update, delete, validation, duplicate IDs, missing IDs, and persistence across app instances.
