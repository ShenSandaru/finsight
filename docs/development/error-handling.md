# Error Handling & Standardized API Error Responses — FinSight

This document details the exception architecture, domain error hierarchy, and API response envelope standards in FinSight.

---

## 1. Exception Hierarchy

All custom domain and service exceptions inherit from `FinSightError` defined in `app/core/exceptions.py`:

```
FinSightError (Base application exception)
├── ValidationError (400 Bad Request)
│   └── FileValidationError (File size, missing name, forbidden extension)
├── NotFoundError (404 Not Found)
│   └── DocumentNotFoundError (Document UUID not in DB)
├── ServiceError (500 Internal Server Error)
│   └── ProcessingError (Background job / parsing error)
└── ExternalServiceError (503 Service Unavailable - Redis, OpenAI, etc.)
```

---

## 2. Separation of Concerns

- **Services (`app/services/`):** Must NOT import or raise `fastapi.HTTPException`. Services raise custom domain exceptions (`FileValidationError`, `DocumentNotFoundError`, `ExternalServiceError`).
- **API Routes (`app/api/routes/`):** Execute service calls and let exceptions bubble up to global FastAPI exception handlers.
- **FastAPI Exception Handlers (`app/main.py`):** Intercept all domain exceptions and return standardized JSON error envelopes.

---

## 3. Standardized Error Response Envelope

All API errors return a consistent JSON schema defined in `app/schemas/error.py`:

```json
{
  "error": {
    "code": "ERROR_CODE_STRING",
    "message": "Human readable description of the error",
    "details": {
      "field": "optional diagnostic context"
    }
  }
}
```

### HTTP Status Code Mappings

| Exception Class | HTTP Status | Response `code` |
| :--- | :--- | :--- |
| `ValidationError` / `FileValidationError` | `400 Bad Request` | `VALIDATION_ERROR` |
| `RequestValidationError` (Pydantic / FastAPI) | `422 Unprocessable Entity` | `UNPROCESSABLE_ENTITY` |
| `NotFoundError` / `DocumentNotFoundError` | `404 Not Found` | `NOT_FOUND` |
| `ExternalServiceError` | `503 Service Unavailable` | `EXTERNAL_SERVICE_ERROR` |
| `ServiceError` | `500 Internal Server Error` | `INTERNAL_SERVICE_ERROR` |
| Unhandled Exceptions (`Exception`) | `500 Internal Server Error` | `INTERNAL_SERVER_ERROR` |
