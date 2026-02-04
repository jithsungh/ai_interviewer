
```

backend/
├── app/
│   ├── bootstrap/                # FastAPI app, middleware, lifespan
│   ├── config/                   # env, feature flags, constants
│   ├── shared/                   # truly shared primitives only
│   │   ├── errors/
│   │   ├── auth_context/
│   │   └── observability/
│
│   ├── auth/                     # AUTH MONOLITH
│   │   ├── api/
│   │   ├── domain/
│   │   ├── persistence/
│   │   └── contracts/
│
│   ├── admin/                    # CONTROL PLANE MONOLITH
│   │   ├── api/
│   │   ├── domain/               # immutability, versioning
│   │   ├── persistence/
│   │   └── validation/
│
│   ├── interview/                # RUNTIME MONOLITH (CORE)
│   │   ├── api/                  # REST + WS entrypoints
│   │   ├── session/              # state machine
│   │   ├── orchestration/        # event flow control
│   │   ├── exchanges/            # immutable exchange creation
│   │   ├── realtime/             # websocket protocol
│   │   └── persistence/
│
│   ├── evaluation/               # EVALUATION MONOLITH
│   │   ├── api/
│   │   ├── scoring/
│   │   ├── aggregation/
│   │   ├── snapshots/
│   │   └── persistence/
│
│   ├── question/                 # QUESTION ENGINE
│   │   ├── selection/
│   │   ├── retrieval/            # Qdrant
│   │   ├── prompting/
│   │   ├── generation/
│   │   └── persistence/          # read-only
│
│   ├── ai/                       # AI INFRA (NO DOMAIN)
│   │   ├── llm/
│   │   ├── prompts/
│   │   └── telemetry/
│
│   ├── proctoring/               # PROCTORING MONOLITH
│   │   ├── ingestion/
│   │   ├── rules/
│   │   ├── risk_model/
│   │   └── persistence/
│
│   ├── coding/                   # CODE EXECUTION MONOLITH
│   │   ├── api/
│   │   ├── execution/
│   │   ├── sandbox/
│   │   ├── evaluation/
│   │   └── persistence/
│
│   ├── audio/                    # AUDIO ANALYSIS MONOLITH
│   │   ├── ingestion/
│   │   ├── transcription/
│   │   ├── analysis/
│   │   └── persistence/
│
│   └── persistence/              # INFRA ONLY
│       ├── postgres/
│       ├── redis/
│       └── qdrant/
│
├── alembic/
├── tests/
└── docker/

```