# TeamSync AI

**Explainable Multi-Agent Project Intelligence Platform**

TeamSync AI is a production-style final-year project that predicts team coordination failures early, explains risks clearly, and recommends corrective actions. Built as a modular AI-first distributed monolith.

## 🏗️ Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Frontend   │────▶│  Core API   │────▶│ PostgreSQL  │
│  (Next.js)  │     │  (FastAPI)  │     │  (Primary)  │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
                           ▼                    ┌─────────────┐
                    ┌─────────────┐             │    Redis    │
                    │  AI Service │             │ (Cache/Queue)│
                    │  (FastAPI)  │             └─────────────┘
                    └─────────────┘                      │
                           │                             ▼
                           ▼                    ┌─────────────┐
                    ┌─────────────┐             │   Celery    │
                    │   Groq API  │             │  Workers    │
                    │  (Llama 3.1)│             └─────────────┘
                    └─────────────┘
```

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Groq API Key (for AI service)

### 1. Clone and Configure
```bash
git clone <repo-url>
cd teamsync-ai
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
```

### 2. Start Services
```bash
make up
```

This starts:
- **Frontend**: http://localhost:3000
- **Core API**: http://localhost:8000
- **AI Service**: http://localhost:8001
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

### 3. Run Migrations
```bash
make db-migrate
```

### 4. Seed Demo Data (Optional)
```bash
make db-seed
```

## 📁 Project Structure

```
teamsync-ai/
├── frontend/           # Next.js 14 + React 18 + Tailwind
├── backend/            # FastAPI + SQLAlchemy 2.0 + Pydantic v2
├── ai-service/         # FastAPI + LangGraph + Groq
├── docker-compose.yml  # Full stack local development
├── Makefile           # Common commands
└── .env.example       # Environment template
```

## 🔧 Core Features

### Multi-Tenancy & Auth
- Organization-based multi-tenancy
- JWT authentication with refresh tokens
- Role-based access control (Owner, Admin, PM, Developer, Viewer)
- Project-scoped permissions

### Project & Task Management
- Projects with milestones and deadlines
- Kanban board with drag-and-drop
- Task dependencies, subtasks, comments
- Status workflow: Backlog → Planned → In Progress → Blocked → Review → Done

### AI-Powered Intelligence
- **Planning Agent**: Sprint readiness, milestone feasibility
- **Progress Agent**: Velocity trends, completion forecasts
- **Meeting Intelligence**: Extract decisions, action items, blockers
- **Communication Intelligence**: Response delays, participation gaps
- **Workload Intelligence**: Overloaded/underutilized members, SPOFs
- **Risk Prediction**: 6 risk types with evidence
- **Recommendations**: Prioritized actions with reasoning

### Explainable AI
- Every recommendation includes clear reasoning
- Evidence references from source data
- Confidence scores for all predictions
- Rule-based fallbacks when LLM unavailable

### Professional Review Trio
- Frontend, Backend, and AI/ML agents review proposals
- Consensus building with conflict resolution
- Structured output with verdicts and required changes

### Real-Time Updates
- WebSocket connections for live dashboards
- Task updates, risk changes, notifications
- Multi-user collaboration

## 📚 API Documentation

Once running, visit:
- Core API Docs: http://localhost:8000/docs
- AI Service Docs: http://localhost:8001/docs

## 🧪 Testing

```bash
# Run all tests
make test

# Backend only
make test-backend

# AI Service only
make test-ai

# Frontend only
make test-frontend
```

## 🧹 Code Quality

```bash
# Lint all services
make lint

# Format all services
make format
```

## 📦 Production Deployment

```bash
# Build production images
make prod-build

# Deploy
make prod-up
```

For Kubernetes deployment, see `k8s/` directory.

## 🔑 Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `JWT_SECRET` | Secret key for JWT tokens | Yes |
| `DB_PASSWORD` | PostgreSQL password | Yes |
| `GROQ_API_KEY` | Groq API key for LLM | Yes |
| `AI_MODEL` | LLM model to use | No (default: llama-3.1-70b-versatile) |

## 📖 Learn More

- [Architecture Overview](docs/architecture.md)
- [API Reference](docs/api.md)
- [Agent Design](docs/agent-design.md)
- [Database Schema](docs/database.md)
- [Deployment Guide](docs/deployment.md)
- [Testing Strategy](docs/testing.md)
- [Demo Flow](docs/demo-flow.md)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details.

## 🙏 Acknowledgments

- Groq for fast LLM inference
- LangGraph for agent orchestration
- shadcn/ui for beautiful components
- All open-source dependencies