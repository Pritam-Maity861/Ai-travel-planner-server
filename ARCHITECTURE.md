# Server Architecture Documentation

This document provides a complete architectural reference for the **AI-Travel_planner** backend (`server/`), built with **FastAPI**, **LangGraph**, **Groq LLM (`ChatGroq`)**, **Model Context Protocol (MCP)**, **PostgreSQL** (dual async drivers: `asyncpg` + `psycopg`), and **ReportLab**.

---

## 1. High-Level System Architecture

```mermaid
flowchart TB
    Client["Frontend Client (React + Vite)"]

    subgraph FastAPI["FastAPI Application (server/app/main.py)"]
        Lifespan["Lifespan Manager<br/>• Base.metadata.create_all<br/>• load_mcp_tools()<br/>• AsyncPostgresSaver.setup()"]
        Router["API v1 Router (/api/v1)"]
        AuthEP["/auth<br/>register • login • me"]
        TripsEP["/trips<br/>POST • GET • review • preview-pdf • pdf • DELETE"]
        HealthEP["/health"]
        Deps["Dependencies (deps.py)<br/>get_session • get_current_user<br/>get_auth_service • get_trip_service"]
    end

    subgraph Services["Service & Repository Layer"]
        AuthSvc["AuthService<br/>bcrypt + HS256 JWT"]
        TripSvc["TripService<br/>Graph orchestration • Retry/Reuse<br/>Status sync • Error recovery"]
        PDFSvc["PDF Service (ReportLab)<br/>Ephemeral Preview & Final Master PDF"]
        UserRepo["UserRepository"]
        ConvRepo["ConversationRepository"]
    end

    subgraph LangGraph["LangGraph StateGraph (TravelState)"]
        Graph["Compiled Multi-Agent Workflow<br/>(with AsyncPostgresSaver checkpointer)"]
    end

    subgraph MCP["MCP Client Registry (app/mcp_client/client.py)"]
        MCPLoader["MultiServerMCPClient<br/>(Per-server isolated loader)"]
        WeatherMCP["weather_server.py (stdio)<br/>get_forecast"]
        FlightsMCP["flights_server.py (stdio)<br/>search_flights"]
        WorldTrainMCP["World Train Map (HTTP)<br/>https://worldtrainmap.com/mcp"]
        FindMyTrainMCP["Find My Train (stdio/npx)<br/>@samarth-23-eng/india-mcp"]
        TavilyMCP["Tavily Search (stdio/npx)<br/>tavily-mcp@latest"]
    end

    subgraph External["External APIs & LLM"]
        Groq["Groq Cloud API<br/>(openai/gpt-oss-120b)"]
        OpenMeteo["Open-Meteo Geocoding & Forecast"]
        AviationStack["AviationStack API"]
        TavilyAPI["Tavily Web Search API"]
    end

    subgraph DB["PostgreSQL 16 (docker-compose.yml :5433)"]
        AppTables["SQLAlchemy Tables (asyncpg)<br/>users • conversations (incl. pdf_data)"]
        CheckpointTables["LangGraph Checkpoint Tables (psycopg)<br/>checkpoints • checkpoint_writes • blobs"]
    end

    Client -->|"HTTP + Bearer JWT"| Router
    Router --> AuthEP & TripsEP & HealthEP
    AuthEP & TripsEP --> Deps
    Deps --> AuthSvc & TripSvc
    AuthSvc --> UserRepo --> AppTables
    TripSvc --> ConvRepo --> AppTables
    TripSvc --> PDFSvc
    TripSvc --> Graph
    Graph <-->|"Thread State Persistence"| CheckpointTables
    Graph <-->|"Structured Output & Summaries"| Groq
    Graph --> MCPLoader
    MCPLoader --> WeatherMCP --> OpenMeteo
    MCPLoader --> FlightsMCP --> AviationStack
    MCPLoader --> WorldTrainMCP
    MCPLoader --> FindMyTrainMCP
    MCPLoader --> TavilyMCP --> TavilyAPI
```

---

## 2. Technology Stack

| Layer | Technology / Library | Purpose |
| :--- | :--- | :--- |
| **Web Framework** | `fastapi`, `uvicorn[standard]` | Async REST API & ASGI server |
| **Agent Orchestration** | `langgraph`, `langchain-core` | Stateful DAG, parallel fan-out, `interrupt()` HITL |
| **LLM Provider** | `langchain-groq` (`openai/gpt-oss-120b`) | Structured outputs (`function_calling` & `json_mode`) and synthesis |
| **Tool Protocol** | `mcp`, `langchain-mcp-adapters` | Local `stdio` & remote `http` MCP tool servers |
| **ORM & Migrations** | `sqlalchemy[asyncio]`, `asyncpg`, `alembic` | Async ORM models (`users`, `conversations`) & schema migrations |
| **Checkpointer** | `langgraph-checkpoint-postgres`, `psycopg[binary,pool]` | Persistent LangGraph state per `thread_id` |
| **Authentication** | `pyjwt` (HS256), `bcrypt` | Password hashing & stateless JWT bearer auth |
| **PDF Generation** | `reportlab` | Branded multi-page travel master PDFs |
| **Config & Validation** | `pydantic`, `pydantic-settings` | `.env` configuration & request/response schemas |
| **Tooling & Tests** | `uv`, `ruff`, `pytest`, `pytest-asyncio` | Dependency management, linting, unit tests |

---

## 3. Directory Structure

```text
server/
├── alembic.ini                     # Alembic migration configuration
├── docker-compose.yml              # PostgreSQL 16 service (port 5433 -> 5432)
├── pyproject.toml                  # Dependencies, Ruff rules, Pytest config
├── mcp_servers/
│   ├── weather_server.py           # FastMCP stdio server (Open-Meteo 16-day forecast)
│   └── flights_server.py           # FastMCP stdio server (AviationStack schedule lookup)
├── migrations/
│   └── versions/                   # Alembic schema revisions (conversations, users, pdf)
├── tests/
│   └── test_pdf.py                 # Unit tests for PDF generation
└── app/
    ├── main.py                     # FastAPI factory & lifespan startup/shutdown
    ├── core/
    │   ├── config.py               # Pydantic Settings (.env)
    │   ├── exceptions.py           # Domain exceptions (TripNotFound, etc.)
    │   ├── logging.py              # Logging configuration
    │   └── security.py             # bcrypt hashing & JWT encode/decode
    ├── db/
    │   ├── base.py                 # SQLAlchemy DeclarativeBase
    │   └── session.py              # AsyncEngine & SessionLocal (asyncpg)
    ├── models/
    │   ├── user.py                 # User ORM model
    │   └── conversation.py         # Conversation + PDF binary ORM model
    ├── repositories/
    │   ├── user_repository.py      # User CRUD queries
    │   └── conversation_repository.py # Conversation CRUD, status updates, PDF storage
    ├── schemas/
    │   ├── user.py                 # UserCreate, UserLogin, TokenResponse, UserResponse
    │   └── trip.py                 # TripCreateRequest, ReviewRequest, TripResponse, TripHistoryItem
    ├── services/
    │   ├── auth_service.py         # Registration & login logic
    │   ├── trip_service.py         # Graph execution, session reuse, failure recovery, PDF save
    │   └── pdf_service.py          # ReportLab PDF builder (preview & final)
    ├── api/
    │   ├── deps.py                 # FastAPI DI providers & JWT guard
    │   └── v1/
    │       ├── router.py           # Combines health, auth, trips routers
    │       └── endpoints/
    │           ├── health.py       # GET /api/v1/health
    │           ├── auth.py         # POST /register, POST /login, GET /me
    │           └── trips.py        # Trip CRUD, HITL review, PDF preview & download
    ├── mcp_client/
    │   └── client.py               # MCP server loader, tool registry, railway fallback
    └── agents/
        ├── llm.py                  # Cached ChatGroq factory (max_tokens=8192, timeout=60)
        ├── prompts.py              # System prompts for all agents
        ├── routing.py              # Staged execution & dependency expansion
        ├── state.py                # TravelState TypedDict & TripConstraints schema
        ├── graph.py                # LangGraph StateGraph wiring
        └── nodes/
            ├── guardrail.py        # Travel-domain validator & blocked handler
            ├── supervisor.py       # Extracts constraints & selects specialist agents
            ├── flight.py           # IATA lookup + AviationStack MCP + summary
            ├── train.py            # Live railway MCP / corridor intelligence + summary
            ├── hotel.py            # Tavily search + structured HotelResults extraction
            ├── weather.py          # Open-Meteo MCP + packing/climate summary
            ├── budget.py           # Structured BudgetAnalysis (nullable transit estimates)
            ├── itinerary.py        # Structured ItineraryPlan (with json_mode fallback)
            ├── human_review.py     # LangGraph interrupt() + revision router
            └── final_response.py   # Synthesizes final Markdown travel master plan
```

---

## 4. LangGraph Multi-Agent Workflow

The core intelligence is orchestrated as a staged, cyclic **LangGraph `StateGraph`** compiled with `AsyncPostgresSaver`.

### 4.1 Graph Topology

```mermaid
flowchart TD
    Start((START)) --> Guardrail["guardrail_node<br/>Validates travel-domain intent"]
    Guardrail -->|"allowed = false"| Blocked["blocked_node<br/>Sets blocked_reason"] --> EndNode((END))
    Guardrail -->|"allowed = true"| Supervisor["supervisor_node<br/>Extracts TripConstraints & picks agents"]

    Supervisor -->|"Stage 0: Parallel Fan-out"| Flight["flight_node"]
    Supervisor -->|"Stage 0: Parallel Fan-out"| Train["train_node"]
    Supervisor -->|"Stage 0: Parallel Fan-out"| Hotel["hotel_node"]
    Supervisor -->|"Stage 0: Parallel Fan-out"| Weather["weather_node"]

    Flight & Train & Hotel & Weather --> Collect["collect_node<br/>Parallel Join Barrier"]

    Collect -->|"Stage 1 (if selected)"| Budget["budget_node<br/>BudgetAnalysis"]
    Collect -->|"Skip Stage 1"| Itinerary
    Budget -->|"Stage 2 (if selected)"| Itinerary["itinerary_node<br/>ItineraryPlan (with json_mode fallback)"]

    Itinerary --> HumanReview{"human_review_node<br/>LangGraph interrupt()"}
    Budget -->|"If itinerary skipped"| HumanReview

    HumanReview -->|"action = approve OR<br/>revision_count >= max_revisions"| FinalResp["final_response_node<br/>Synthesizes Markdown Master Plan"]
    HumanReview -->|"action = request_changes<br/>Command(goto=expanded_agents)"| ReRun["Re-run Selected Agent(s)<br/>+ Downstream Dependents"]

    ReRun -.->|"Enters at earliest<br/>required stage"| Supervisor
    FinalResp --> EndNode
```

### 4.2 Shared `TravelState` & Reducers (`app/agents/state.py`)
Because Stage 0 agents (`flight`, `train`, `hotel`, `weather`) execute **concurrently**, `TravelState` uses safe reducer annotations:
- `messages: Annotated[list[AnyMessage], add_messages]`
- `llm_calls: Annotated[int, operator.add]`
- Specialist outputs write to disjoint keys: `flight_results`, `train_results`, `hotel_results`, `weather_info`, `budget_analysis`, `itinerary_plan`.

### 4.3 Staged Routing & Dependency Expansion (`app/agents/routing.py`)
Agents are organized into ordered stages:
```python
STAGES = [["flight", "train", "hotel", "weather"], ["budget"], ["itinerary"]]
```
When a user requests changes during `human_review`, an LLM selects the minimal `agents_to_rerun`, and `expand_with_dependents()` automatically pulls in downstream dependents:
- `flight` / `train` / `hotel` $\rightarrow$ `["budget", "itinerary"]`
- `weather` / `budget` $\rightarrow$ `["itinerary"]`

---

## 5. End-to-End Request & HITL Lifecycle

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant API as FastAPI (/api/v1/trips)
    participant Svc as TripService
    participant Repo as ConversationRepository
    participant Graph as LangGraph + Checkpointer
    participant PDF as PDF Service (ReportLab)

    User->>API: POST /trips (Bearer JWT, TripCreateRequest)
    API->>Svc: create_trip(request, user_id)
    alt Existing thread_id provided
        Svc->>Repo: update_status(thread_id, status="running")
    else New session
        Svc->>Repo: create(user_query, user_id)
    end

    Svc->>Graph: ainvoke(state_input, config={thread_id})
    Note over Graph: Runs guardrail -> supervisor -> parallel specialists -> budget -> itinerary
    Graph-->>Svc: Pauses at human_review (interrupt)
    Svc->>Repo: update(status="awaiting_review", title, destination)
    Svc-->>User: TripResponse(status="awaiting_review", review_payload)

    opt Draft Preview
        User->>API: GET /trips/{thread_id}/preview-pdf
        API->>Svc: preview_pdf(thread_id)
        Svc->>Graph: aget_state(thread_id)
        Svc->>PDF: generate_trip_pdf(values, is_preview=True)
        PDF-->>User: Inline Draft PDF stream
    end

    User->>API: POST /trips/{thread_id}/review (action="approve")
    API->>Svc: review(thread_id, ReviewRequest)
    Svc->>Graph: ainvoke(Command(resume={"action": "approve"}))
    Graph->>Graph: final_response_node -> END
    Svc->>Repo: update(status="completed", final_response=...)
    Svc->>PDF: generate_trip_pdf(values, is_preview=False)
    Svc->>Repo: save_pdf(thread_id, pdf_bytes, filename)
    Svc-->>User: TripResponse(status="completed", has_pdf=True)

    User->>API: GET /trips/{thread_id}/pdf
    API->>Svc: get_pdf(thread_id)
    Svc->>Repo: get(thread_id)
    API-->>User: Attachment Official Master PDF
```

---

## 6. MCP Server Integration (`app/mcp_client/client.py`)

`load_mcp_tools()` connects to each MCP server **independently** inside isolated `try/except` blocks so one slow or unreachable external server never prevents local tools from loading:

| Server Name | Transport | Source / Command | Exposed / Used Capabilities |
| :--- | :--- | :--- | :--- |
| `weather` | `stdio` | `mcp_servers/weather_server.py` | `get_forecast(city, days)` via Open-Meteo (up to 16 days) |
| `flights` | `stdio` | `mcp_servers/flights_server.py` | `search_flights(dep_iata, arr_iata)` via AviationStack |
| `world_train_map` | `http` | `https://worldtrainmap.com/mcp` | `city_pair`, `search_routes`, `night_trains`, `routes_in_country` |
| `find_my_train` | `stdio` | `npx -y @samarth-23-eng/india-mcp railways` | Live Indian Railways status & trains between stations (with `CITY_TO_STATION_CODE` resolver) |
| `tavily` | `stdio` | `npx -y tavily-mcp@latest` | Live web search for hotel discovery (`hotel_node`) |

If remote train MCP servers are unreachable or lack a specific regional corridor, `search_train_routes` gracefully falls back to `_get_sector_routes()` (covering Indian Railways, Japanese Shinkansen, and general intercity corridors).

---

## 7. API Endpoints Summary (`/api/v1`)

| Method | Endpoint | Auth | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | No | Health check (`{"status": "ok"}`) |
| `POST` | `/auth/register` | No | Register user & return HS256 JWT |
| `POST` | `/auth/login` | No | Authenticate user & return HS256 JWT |
| `GET` | `/auth/me` | Yes | Return authenticated `UserResponse` |
| `POST` | `/trips` | Yes | Start new trip or retry existing `thread_id`; catches graph failures into `status="failed"` |
| `GET` | `/trips` | Yes | List user's past journeys (`TripHistoryItem[]`) |
| `GET` | `/trips/{thread_id}` | No* | Fetch synced trip state from PostgreSQL + LangGraph checkpoint |
| `POST` | `/trips/{thread_id}/review` | No* | Resume HITL `interrupt()` (`approve` or `request_changes`) |
| `GET` | `/trips/{thread_id}/preview-pdf` | No* | Stream ephemeral draft PDF during review |
| `GET` | `/trips/{thread_id}/pdf` | No* | Download finalized PDF stored in PostgreSQL `pdf_data` |
| `DELETE` | `/trips/{thread_id}` | Yes | Delete journey owned by `current_user` |

*\*Note: `GET /trips/{thread_id}`, `POST /trips/{thread_id}/review`, and PDF endpoints validate existence via `ConversationRepository` and can be scoped further with `get_current_user` if strict per-route ownership enforcement is desired.*

---

## 8. Database Architecture

Two PostgreSQL connection layers share the same Postgres instance (`localhost:5433/travel_db` in `docker-compose.yml`):

1. **SQLAlchemy Async (`asyncpg`)** — `app/db/session.py`:
   - `users`: `id (UUID PK)`, `email (unique)`, `hashed_password`, `name`, `created_at`, `updated_at`
   - `conversations`: `id (UUID PK / thread_id)`, `user_id (FK -> users.id CASCADE)`, `title`, `destination`, `user_query`, `status`, `final_response`, `blocked_reason`, `pdf_data (LargeBinary)`, `pdf_filename`, `pdf_created_at`, `created_at`, `updated_at`
   - Ensured at startup via `Base.metadata.create_all` in `main.py` and versioned via Alembic in `server/migrations/`.

2. **LangGraph Checkpointer (`psycopg` AsyncConnectionPool)** — `app/main.py`:
   - `checkpointer.setup()` initializes LangGraph's checkpoint tables (`checkpoints`, `checkpoint_writes`, `checkpoint_blobs`, `checkpoint_migrations`) to persist graph state across `interrupt()` pauses and human-in-the-loop revisions.

