# Bootstrap Module - Human Testing Guide

**Module:** Application Bootstrap and Assembly  
**Purpose:** Verify application startup, middleware, exception handling, and health checks  
**Prerequisites:** Configured environment (.env file), database, Redis, Qdrant

---

## Quick Start

###  1. Start Application

```bash
cd /home/jithsungh/projects/ai_interviewer

# Activate virtual environment
source .venv/bin/activate

# Run application
uvicorn main:app --reload --port 8000
```

**Expected Output:**
```
🚀 Starting AI Interviewer Backend
✓ Logging configured
Initializing PostgreSQL...
✓ PostgreSQL connected
Initializing Redis...
✓ Redis connected
Initializing Qdrant...
✓ Qdrant connected
✅ Application startup complete
INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

## Test Scenarios

### ✅ Test 1: Health Check Endpoints

**Objective:** Verify basic health endpoints are accessible

#### Test 1.1: Basic Health Check

**Request:**
```bash
curl -X GET http://localhost:8000/health
```

**Expected Response (200 OK):**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "environment": "dev"
}
```

**Validation:**
- ✓ Status code is 200
- ✓ Response contains "status", "version", "environment"
- ✓ Status is "healthy"
- ✓ Response headers include `X-Request-ID`

#### Test 1.2: Database Health Check

**Request:**
```bash
curl -X GET http://localhost:8000/health/database
```

**Expected Response (200 OK):**
```json
{
  "status": "healthy",
  "database": "connected",
  "pool_size": 20,
  "active_connections": 1,
  "timestamp": "2026-02-26T12:00:00Z"
}
```

**Validation:**
- ✓ Status code is 200
- ✓ Database status is "connected" or "degraded"
- ✓ Pool statistics are present

---

### ✅ Test 2: Middleware Stack

**Objective:** Verify middleware is functioning correctly

#### Test 2.1: Request ID Injection

**Request:**
```bash
curl -v http://localhost:8000/health
```

**Expected:**
```
< HTTP/1.1 200 OK
< X-Request-ID: 550e8400-e29b-41d4-a716-446655440000
```

**Validation:**
- ✓ Response headers contain `X-Request-ID`
- ✓ Request ID is valid UUID format (36 characters)

#### Test 2.2: CORS Headers

**Request:**
```bash
curl -X OPTIONS http://localhost:8000/health \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: GET" \
  -v
```

**Expected Headers:**
```
Access-Control-Allow-Origin: http://localhost:3000
Access-Control-Allow-Credentials: true
Access-Control-Allow-Methods: GET, POST, PUT, DELETE, PATCH, OPTIONS
```

**Validation:**
- ✓ CORS headers are present
- ✓ Origin is allowed
- ✓ Credentials are allowed

#### Test 2.3: Request Logging

**Action:** Make any request

**Expected Log Output:**
```json
{
  "timestamp": "2026-02-26T12:00:00Z",
  "level": "INFO",
  "message": "GET /health → 200",
  "event_type": "http.request",
  "latency_ms": 5,
  "metadata": {
    "method": "GET",
    "path": "/health",
    "status_code": 200,
    "request_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

**Validation:**
- ✓ Structured JSON logs in console/file
- ✓ Contains method, path, status, latency
- ✓ Includes request_id

---

### ✅ Test 3: Exception Handling

**Objective:** Verify global exception handlers return structured errors

#### Test 3.1: 404 Not Found

**Request:**
```bash
curl -X GET http://localhost:8000/nonexistent-endpoint
```

**Expected Response (404):**
```json
{
  "error": {
    "code": "http_404",
    "message": "Not Found",
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "metadata": {}
  }
}
```

**Validation:**
- ✓ Status code is 404
- ✓ Structured error format
- ✓ Contains request_id

#### Test 3.2: Validation Error (422)

**Request:**
```bash
curl -X POST http://localhost:8000/api/v1/test \
  -H "Content-Type: application/json" \
  -d '{"invalid": "data"}'
```

**Expected Response (422) - if endpoint exists:**
```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed",
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "metadata": {
      "errors": [
        {
          "field": "body.field_name",
          "message": "field required",
          "type": "value_error.missing"
        }
      ]
    }
  }
}
```

**Validation:**
- ✓ Status code is 422
- ✓ Error includes field-level details
- ✓ Structured format

#### Test 3.3: Internal Server Error (500)

**Setup:** Modify code to raise unhandled exception (for testing only)

**Expected Response (500):**
```json
{
  "error": {
    "code": "internal_server_error",
    "message": "An unexpected error occurred. Please contact support.",
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "metadata": {}
  }
}
```

**Validation:**
- ✓ Status code is 500
- ✓ Generic message (no internal details exposed)
- ✓ Error logged with full traceback

---

### ✅ Test 4: OpenAPI Documentation

**Objective:** Verify API documentation (when debug=True)

#### Test 4.1: Swagger UI

**Request:**
```bash
# Open in browser
http://localhost:8000/docs
```

**Expected:**
- ✓ Swagger UI loads
- ✓ Shows endpoint list
- ✓ Shows health check endpoints

#### Test 4.2: ReDoc

**Request:**
```bash
# Open in browser
http://localhost:8000/redoc
```

**Expected:**
- ✓ ReDoc loads  
- ✓ Shows formatted API documentation

#### Test 4.3: OpenAPI Schema

**Request:**
```bash
curl -X GET http://localhost:8000/openapi.json
```

**Expected Response (200):**
```json
{
  "openapi": "3.1.0",
  "info": {
    "title": "AI Interviewer API",
    "version": "1.0.0"
  },
  "paths": {
    "/health": {...},
    "/health/database": {...}
  }
}
```

**Validation:**
- ✓ Valid OpenAPI 3.x schema
- ✓ Contains all endpoints

---

### ✅ Test 5: Application Lifecycle

**Objective:** Verify graceful startup and shutdown

#### Test 5.1: Startup Sequence

**Action:** Start application with `uvicorn main:app`

**Expected Console Output (in order):**
```
🚀 Starting AI Interviewer Backend
✓ Logging configured
Initializing PostgreSQL...
✓ PostgreSQL connected
Initializing Redis...
✓ Redis connected  
Initializing Qdrant...
✓ Qdrant connected
✅ Application startup complete
```

**Validation:**
- ✓ Components initialize in correct order
- ✓ No errors or warnings
- ✓ All connections successful

#### Test 5.2: Shutdown Sequence

**Action:** Press Ctrl+C to stop server

**Expected Console Output (in order):**
```
🛑 Shutting down AI Interviewer Backend
✓ Qdrant disconnected
✓ Redis disconnected
✓ PostgreSQL disconnected
✅ Application shutdown complete
```

**Validation:**
- ✓ Graceful shutdown (no abrupt termination)
- ✓ All connections closed
- ✓ No connection leak warnings

---

## Postman Collection

### Setup Postman Environment

**Variables:**
- `base_url`: `http://localhost:8000`
- `api_prefix`: `/api/v1`

### Collection: Bootstrap Tests

#### Folder: Health Checks

**1. Basic Health**
- Method: `GET`
- URL: `{{base_url}}/health`
- Tests:
  ```javascript
  pm.test("Status is 200", () => {
      pm.response.to.have.status(200);
  });
  pm.test("Has request ID header", () => {
      pm.response.to.have.header("X-Request-ID");
  });
  pm.test("Response has status field", () => {
      pm.expect(pm.response.json()).to.have.property("status");
  });
  ```

**2. Database Health**
- Method: `GET`
- URL: `{{base_url}}/health/database`
- Tests:
  ```javascript
  pm.test("Status is 200", () => {
      pm.response.to.have.status(200);
  });
  pm.test("Database status present", () => {
      pm.expect(pm.response.json()).to.have.property("status");
  });
  ```

#### Folder: Error Handling

**3. Not Found (404)**
- Method: `GET`
- URL: `{{base_url}}/nonexistent`
- Tests:
  ```javascript
  pm.test("Status is 404", () => {
      pm.response.to.have.status(404);
  });
  pm.test("Has structured error", () => {
      const json = pm.response.json();
      pm.expect(json).to.have.property("error");
      pm.expect(json.error).to.have.property("code");
      pm.expect(json.error).to.have.property("message");
      pm.expect(json.error).to.have.property("request_id");
  });
  ```

---

## Automated Testing

### Run Unit Tests

```bash
# All unit tests
pytest tests/unit/bootstrap/ -v

# Specific test module
pytest tests/unit/bootstrap/test_bootstrap.py -v

# With coverage
pytest tests/unit/bootstrap/ --cov=app.bootstrap --cov-report=html
```

**Expected Output:**
```
tests/unit/bootstrap/test_bootstrap.py::TestExceptionHandlers::test_base_error_handler PASSED
tests/unit/bootstrap/test_bootstrap.py::TestExceptionHandlers::test_http_exception_handler PASSED
tests/unit/bootstrap/test_bootstrap.py::TestMiddlewareRegistration::test_middleware_order_is_documented PASSED
...

======================== XX passed in X.XXs ========================
```

### Run Integration Tests

```bash
# All integration tests
pytest tests/integration/bootstrap/ -v

# With database connection
pytest tests/integration/bootstrap/ --run-integration -v
```

**Expected Output:**
```
tests/integration/bootstrap/test_bootstrap_integration.py::TestApplicationStartup::test_health_endpoint_accessible PASSED
tests/integration/bootstrap/test_bootstrap_integration.py::TestMiddlewareStack::test_request_id_injected PASSED
...

======================== XX passed in X.XXs ========================
```

---

## Common Issues & Troubleshooting

### Issue 1: Application Won't Start

**Symptoms:**
```
RuntimeError: Database not initialized
```

**Solution:**
```bash
# Check DATABASE_URL in .env
cat .env | grep DATABASE_URL

# Verify database is running
psql $DATABASE_URL -c "SELECT 1;"
```

### Issue 2: Redis Connection Failed

**Symptoms:**
```
⚠️  Redis connection failed: Connection refused
```

**Solution:**
```bash
# Check Redis is running
redis-cli ping
# Should return: PONG

# Or start Redis
redis-server
```

### Issue 3: Middleware Not Working

**Symptoms:** Headers missing (e.g., no X-Request-ID)

**Solution:**
- Check middleware registration order in logs
- Verify middleware is not being disabled
- Check `app.middleware` list length

### Issue 4: Logs Not Structured

**Symptoms:** Plain text logs instead of JSON

**Solution:**
```bash
# Check logging configuration in .env
LOG_FORMAT=json
LOG_LEVEL=INFO
```

---

## Environment Configuration

### Required `.env` Variables

```bash
# Application
APP_NAME="AI Interviewer API"
API_VERSION="1.0.0"
APP_ENV=dev
DEBUG=true

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/ai_interviewer

# Redis
REDIS_URL=redis://localhost:6379/0

# Qdrant
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=your-api-key

# Security
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:3001

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

---

## Success Criteria

### ✅ Bootstrap Module is Working If:

1. **Startup**
   - [ ] Application starts without errors
   - [ ] All connections initialize successfully
   - [ ] Startup logs appear in correct order

2. **Health Endpoints**
   - [ ] /health returns 200
   - [ ] /health/database returns 200
   - [ ] Both include proper status fields

3. **Middleware**
   - [ ] X-Request-ID header present in all responses
   - [ ] CORS headers configured correctly
   - [ ] Request logging shows in console/file
   - [ ] Latency is calculated

4. **Exception Handling**
   - [ ] 404 errors return structured format
   - [ ] 500 errors don't expose internals
   - [ ] All errors include request_id

5. **Documentation**
   - [ ] /docs accessible in debug mode
   - [ ] OpenAPI schema is valid

6. **Shutdown**
   - [ ] Ctrl+C triggers graceful shutdown
   - [ ] All connections close properly
   - [ ] No connection leaks

---

## Next Steps

After verifying bootstrap module:

1. **Implement Auth Module** → Uncomment auth router in `router_registry.py`
2. **Implement Admin Module** → Uncomment admin router
3. **Implement Interview Module** → Uncomment interview router
4. **Add Domain Routers** → Continue adding routers incrementally

Each new router will automatically integrate with:
- Middleware stack (request context, logging, auth)
- Exception handling (structured errors)
- OpenAPI documentation (auto-generated)
- Health monitoring (included in /health/database)

---

**Document Version:** 1.0  
**Last Updated:** 2026-02-26  
**Maintained By:** Backend Team
