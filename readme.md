# 🛡️ RateGuard — Rate Limiter as a Service

[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Redis](https://img.shields.io/badge/Redis-DC382D?style=for-the-badge&logo=redis)](https://redis.io/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-336791?style=for-the-badge&logo=postgresql)](https://www.postgresql.org/)

**RateGuard** is a standalone, high-performance rate-limiting API designed to be used as an infrastructure component for other backend services. Unlike simple middleware, RateGuard is a full-blown service providing multi-tenant API key management, flexible policy definitions, and a variety of industry-standard rate-limiting algorithms.

## 🎯 The Problem it Solves
Most applications implement rate limiting as a local middleware. This fails in distributed systems where multiple server instances share the same limit. RateGuard centralizes the rate-limiting state in Redis, ensuring that limits are enforced globally across all service instances with sub-10ms latency.

---

## ✨ Key Features

- **⚡ Ultra-Low Latency:** The "Hot Path" (`/v1/check`) is optimized to eliminate database reads by caching policy configurations in Redis.
- **🔐 Multi-Tenant Architecture:** Isolated API key management and policy definitions for different clients.
- **🛠️ 4-Algorithm Support:** Support for different use cases via Fixed Window, Sliding Log, Token Bucket, and Sliding Window Counter.
- **⚛️ Atomic Operations:** Prevents race conditions under high concurrency using Redis Lua scripts and atomic pipelines.
- **📊 Observability:** Background aggregation of usage stats from Redis to PostgreSQL for historical analytics.
- **📈 Standards Compliant:** Implements GitHub/Stripe style headers (`X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`).

---

## 📐 System Architecture

### The "Hot Path" Flow
To achieve maximum throughput, the request evaluation path follows a strict "Cache-First" strategy:
`Request` $\rightarrow$ `Auth Cache (Redis)` $\rightarrow$ `Policy Cache (Redis)` $\rightarrow$ `Algorithm Execution (Redis)` $\rightarrow$ `Response`.

### Component Stack
- **API Layer:** FastAPI (Asynchronous)
- **Fast State:** Redis (Counters, Sorted Sets, Hashes)
- **Persistent Store:** PostgreSQL (Clients, Policies, Aggregated Logs)
- **Background Worker:** Asyncio-based flusher for usage statistics.

---

## 🧪 Rate Limiting Algorithms

RateGuard allows clients to choose the best algorithm per resource based on their specific needs:

| Algorithm | Mechanism | Best For | Pros | Cons |
| :--- | :--- | :--- | :--- | :--- |
| **Fixed Window** | Counters per time bucket | Basic limits | Simple, extremely fast | Burst at boundaries |
| **Sliding Log** | Sorted set of timestamps | High precision | 100% Accurate | Memory intensive |
| **Token Bucket** | Token refill at fixed rate | Bursty traffic | Handles bursts gracefully | Requires Lua scripts |
| **Sliding Counter**| Weighted average of windows | High scale | Memory efficient, accurate | Approximation |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Redis
- PostgreSQL

### Setup
1. **Clone the repo**
   ```bash
   git clone https://github.com/yourusername/rateguard.git
   cd rateguard
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment**
   Create a `.env` file:
   ```env
   DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/rateguard
   REDIS_URL=redis://localhost:6379/0
   SECRET_KEY=your_random_secret_key
   FAIL_OPEN=true
   ```

4. **Run the application**
   ```bash
   uvicorn app.main:app --reload
   ```

---

## 🛣️ API Specification

### Authentication
All protected endpoints require the `X-API-Key` header:
`X-API-Key: rg_your_secure_token`

### 1. Client Management

#### `POST /v1/auth/signup`
Registers a new client and generates a unique API key.
- **Request Body:**
  ```json
  {
    "name": "My Application",
    "email": "dev@example.com"
  }
  ```
- **Response (201 Created):**
  ```json
  {
    "client_id": "550e8400-e29b-41d4-a716-446655440000",
    "api_key": "rg_abc123xyz..."
  }
  ```

---

### 2. Policy Management

#### `POST /v1/policies`
Creates a rate-limit rule for a specific resource.
- **Request Body:**
  ```json
  {
    "name": "Login Limit",
    "resource_key": "login",
    "algorithm": "token_bucket",
    "limit_count": 10,
    "window_seconds": 60,
    "burst_capacity": 15
  }
  ```
- **Response (201 Created):**
  ```json
  {
    "id": "...",
    "client_id": "...",
    "name": "Login Limit",
    "resource_key": "login",
    "algorithm": "token_bucket",
    "limit_count": 10,
    "window_seconds": 60,
    "burst_capacity": 15,
    "created_at": "2026-08-24T10:00:00Z",
    "updated_at": "2026-08-24T10:00:00Z"
  }
  ```

#### `GET /v1/policies`
Lists all policies belonging to the authenticated client.
- **Response (200 OK):**
  ```json
  [
    {
      "id": "...",
      "name": "Login Limit",
      "resource_key": "login",
      "algorithm": "token_bucket",
      "limit_count": 10,
      "window_seconds": 60,
      "burst_capacity": 15,
      ...
    }
  ]
  ```

#### `PUT /v1/policies/{id}`
Updates an existing policy.
- **Request Body (Partial):**
  ```json
  {
    "limit_count": 20
  }
  ```
- **Response (200 OK):** Updated `PolicyResponse` object.

#### `DELETE /v1/policies/{id}`
Removes a policy.
- **Response:** `204 No Content`

---

### 3. Rate Limit Evaluation (The Hot Path)

#### `POST /v1/check`
Evaluates if a request should be allowed based on the associated policy.
- **Query Parameters:**
  - `identifier` (string): The unique ID of the user/IP (e.g., `user_123`).
  - `resource_key` (string): The resource being accessed (e.g., `login`).
- **Response (200 OK - Allowed):**
  ```json
  {
    "allowed": true,
    "remaining": 9,
    "limit": 10,
    "reset_at": "2026-08-24T10:15:00Z"
  }
  ```
- **Response (429 Too Many Requests - Blocked):**
  ```json
  {
    "allowed": false,
    "remaining": 0,
    "limit": 10,
    "reset_at": "2026-08-24T10:15:00Z"
  }
  ```
- **Response Headers:**
  - `X-RateLimit-Limit`: Max requests allowed in window.
  - `X-RateLimit-Remaining`: Requests remaining before block.
  - `X-RateLimit-Reset`: Timestamp when the window resets.
  - `Retry-After`: (On 429) Seconds to wait before retrying.

---

### 4. Analytics

#### `GET /v1/usage`
Retrieves historical aggregated usage for the authenticated client.
- **Response (200 OK):**
  ```json
  [
    {
      "window_start": "2026-08-24T10:00:00Z",
      "allowed_count": 1500,
      "blocked_count": 45
    },
    {
      "window_start": "2026-08-24T09:00:00Z",
      "allowed_count": 1200,
      "blocked_count": 10
    }
  ]
  ```

---

## 🛠️ Integration Example

### Simple HTTP Request
```bash
curl -X POST "https://api.rateguard.io/v1/check?identifier=user_123&resource_key=login" \
  -H "X-API-Key: rg_abc123..." \
  -H "Content-Type: application/json"
```

### FastAPI Middleware Snippet
```python
async def rate_limit_check(identifier: str, resource_key: str):
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.rateguard.io/v1/check",
            params={"identifier": identifier, "resource_key": resource_key},
            headers={"X-API-Key": "your_api_key"}
        )
        if not resp.json()["allowed"]:
            raise HTTPException(status_code=429, detail="Too Many Requests")
```

---
