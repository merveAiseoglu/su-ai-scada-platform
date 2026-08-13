# Su-AI Project

## Architecture

Su-AI is an IoT + LLM-powered water quality monitoring platform built for Sanliurfa Water Authority. It combines a rule-based anomaly engine with a hybrid LLM layer (cloud-first with local fallback) and RAG-based institutional memory to turn sensor readings into actionable technical recommendations for field personnel.

```mermaid
flowchart TD
    classDef frontend fill:#3b82f6,stroke:#1e40af,stroke-width:2px,color:white;
    classDef backend fill:#10b981,stroke:#047857,stroke-width:2px,color:white;
    classDef database fill:#f59e0b,stroke:#b45309,stroke-width:2px,color:white;
    classDef ai fill:#8b5cf6,stroke:#5b21b6,stroke-width:2px,color:white;
    classDef broker fill:#ef4444,stroke:#b91c1c,stroke-width:2px,color:white;
    classDef metrics fill:#f43f5e,stroke:#be123c,stroke-width:2px,color:white;
    classDef external fill:#6b7280,stroke:#374151,stroke-width:2px,color:white;

    Mobile["React Native App<br/>(Field Personnel/Admin)"]:::frontend
    Sensors["IoT Sensors<br/>(Stations/Nodes)"]:::external

    subgraph Su_AI_System [Su-AI System Architecture - Docker Compose]
        MQTT["Eclipse Mosquitto<br/>(MQTT Broker)"]:::broker
        FastAPI["FastAPI Backend<br/>(Core API, Rule Engine)"]:::backend

        subgraph Data_Storage [Data Layer]
            Postgres[("PostgreSQL<br/>(Organization, Istasyon, SuOlcumu)")]:::database
            Chroma[("ChromaDB<br/>(Vector DB, RAG Memory)")]:::database
        end

        subgraph AI_Layer [Hybrid LLM Layer]
            Ollama["Ollama - Local<br/>(llama3.2:1b Edge Fallback)"]:::ai
            OpenAI["OpenAI API<br/>(gpt-4o-mini Primary)"]:::ai
        end

        subgraph Observability [Monitoring and Observability]
            Prometheus["Prometheus<br/>(Metrics Scraper)"]:::metrics
            Grafana["Grafana<br/>(Dashboards)"]:::metrics
        end
    end

    Mobile <==>|HTTP/REST API| FastAPI
    Sensors ==>|"Publishes to su-ai/stations/+/measurements"| MQTT
    MQTT ==>|Subscribes and processes| FastAPI

    FastAPI <==>|SQLAlchemy AsyncPG| Postgres
    FastAPI <==>|Semantic Search / Embeddings| Chroma

    FastAPI ==>|Prompt and RAG Context| OpenAI
    FastAPI -.->|Fallback if cloud fails| Ollama

    Prometheus ==>|Scrapes /metrics| FastAPI
    Grafana <==>|Queries metrics| Prometheus
```

## Getting Started with Docker

We provide a production-grade Docker Compose setup that orchestrates all necessary backend services (FastAPI, PostgreSQL, ChromaDB, and Ollama) with a single command.

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) installed.
- [Docker Compose](https://docs.docker.com/compose/install/) installed.

### Setup Instructions

1. **Configure Environment Variables**
   Copy the provided example template to create your local `.env` file:
   ```bash
   cp .env.example .env
   ```
   Open the `.env` file and fill in any required keys (like your `OPENAI_API_KEY`). Note that the database and internal service coordinates are already configured to work seamlessly inside the Docker network.

2. **Local Overrides (Optional)**
   If you need to expose different ports or add debug environment variables locally without affecting the shared `docker-compose.yml`:
   ```bash
   cp docker-compose.override.yml.example docker-compose.override.yml
   ```

3. **Start the Stack**
   Bring up the entire stack using the `Makefile` shortcut:
   ```bash
   make up
   ```
   *Alternatively, if you don't have `make` installed:*
   ```bash
   docker-compose up -d
   ```

4. **Useful Makefile Commands**
   - `make up`: Start all services in the background.
   - `make down`: Stop all services.
   - `make logs`: View combined logs of all services.
   - `make rebuild`: Force rebuild the Docker images and start.
   - `make db-shell`: Open an interactive psql shell in the database container.
   - `make backend-shell`: Open a bash shell in the backend container.

### Testleri Çalıştırma

Projede `pytest` ve `pytest-asyncio` tabanlı kapsamlı bir test altyapısı bulunmaktadır. Testler, izole edilmiş bir `su_ai_test` Postgres veritabanı üzerinde her testte işlem geri alımı (transaction rollback) yöntemiyle hızlıca çalışır.

Testleri Docker container içerisinde çalıştırmak için:
```bash
docker exec -t su-ai-backend pytest -v tests/
```

### Architecture Notes
- The backend API runs on port `8080` on the host (mapped to `8000` inside the container).
- ChromaDB runs on port `8000` on the host.
- Ollama runs on port `11434` on the host.
- PostgreSQL runs on port `5432` on the host.

### Multi-Tenancy / SaaS Architecture
Su-AI uses a robust multi-tenancy model to isolate data securely between different organizations (tenants).
- **Data Isolation:** All data querying (Stations, Measurements, Users, etc.) explicitly enforces the `organization_id` at the database level.
- **Backwards Compatibility:** Legacy configurations and users are safely ported to a "Default Organization" automatically via Alembic migrations.
- **Tenant Management:** Organization administrators and system users can manage tenants and assign users safely via the `/admin/organizations` endpoints.
