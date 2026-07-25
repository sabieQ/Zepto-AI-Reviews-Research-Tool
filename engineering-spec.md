# 02_ENGINEERING_SPEC.md


This document defines the technical architecture, engineering standards, technology stack, and development approach for building the MVP of the AI Product Research Assistant.

Unlike the Product Requirements Document (PRD), this document focuses on **how the system should be built**, while intentionally remaining lightweight and implementation-friendly.

The goal is to provide enough engineering guidance for developers and AI coding assistants without over-engineering the MVP.

---

# 2. Engineering Objectives

The engineering solution should be:

- Simple
- Modular
- Easy to maintain
- Low-cost
- Cloud deployable
- Built primarily using free-tier services
- Easy to extend after MVP validation

The application should prioritize rapid development and clean architecture over enterprise-level scalability.

---

# 3. High-Level System Architecture

```
                Browser

                   │

             Next.js Frontend
             (Hosted on Vercel)

                   │

            REST API (HTTPS)

                   │

          FastAPI Backend
         (Hosted on Render)

          ┌────────┴────────┐
          │                 │
          │                 │

 Supabase PostgreSQL    AI Provider

      + pgvector        (OpenRouter /
                         Groq /
                         Gemini /
                         Ollama)

          │

      Research Reports
```

---

# 4. Technology Stack

## Frontend

- Next.js 15
- React 19
- TypeScript
- Tailwind CSS
- shadcn/ui
- TanStack Query
- React Hook Form
- Zod

Deployment:

**Vercel Free Tier**

---

## Backend

- Python 3.12+
- FastAPI
- SQLAlchemy
- Alembic
- Pydantic

Deployment:

**Render Free Web Service**

---

## Database

Supabase PostgreSQL

Stores:

- Datasets
- Customer Conversations
- Reports
- Application Settings
- Metadata

---

## Vector Search

pgvector (Supabase)

Stores:

- Embeddings
- Semantic similarity indexes

No separate vector database is required for the MVP.

---

## AI Providers

The AI layer should be provider-independent.

Supported providers:

- OpenRouter
- Groq
- Gemini
- Ollama (Optional)
- Any OpenAI-compatible API

The application should allow switching providers using environment variables.

No provider-specific logic should exist inside the application.

---

## Deployment

Frontend

Vercel

Backend

Render

Database

Supabase

Storage

Local uploads for MVP

Future:

Supabase Storage

---

# 5. Engineering Principles

The project should follow these principles.

## Simplicity

Always choose the simplest solution that satisfies the requirement.

---

## Modularity

Every module should have one responsibility.

---

## Separation of Concerns

Frontend

Displays information.

Backend

Handles business logic.

Database

Stores data.

AI Layer

Generates analysis.

---

## Reusability

Avoid duplicate code.

Create reusable services and components.

---

## Configuration First

Anything likely to change should be configurable rather than hardcoded.

Examples:

- AI Provider
- Model Name
- Embedding Model
- API URLs

---

# 6. Project Structure

```
project/

├── frontend/
├── backend/
├── database/
├── prompts/
├── scripts/
├── docs/
├── docker/
└── README.md
```

---

## Frontend Structure

```
frontend/

components/

pages/

layouts/

hooks/

services/

types/

utils/
```

---

## Backend Structure

```
backend/

api/

services/

repositories/

models/

schemas/

workers/

core/

utils/
```

---

# 7. Application Workflow

```
Import Dataset

↓

Clean Data

↓

Store Conversations

↓

Generate Embeddings

↓

Store Vectors

↓

User Asks Free-Form Research Question
(optional preset shortcut may pre-fill)

↓

Semantic Retrieval

↓

Relevant Context

↓

LLM Analysis

↓

Research Report
(stores question_text)

↓

Export
```

This workflow should remain the core of the MVP. Free-form questions are the primary input; predefined presets are optional shortcuts only.

---

# 8. Database Design

Primary tables:

## datasets

Stores dataset information.

---

## conversations

Stores imported customer conversations.

---

## reports

Stores completed AI research reports, including the free-form `question_text` the user asked.

---

## research_questions

Optional preset shortcuts that may pre-fill the research question. Not required to run research.

---

## settings

Stores application configuration.

---

## logs

Stores application events.

---

Embeddings are stored using **pgvector** within Supabase.

---

# 9. API Design

REST API only.

Suggested endpoints:

```
GET     /datasets

POST    /datasets

DELETE  /datasets/{id}

POST    /import

POST    /research
        Body: { dataset_id, question (required), research_question_id? (optional preset), top_k? }

GET     /research-questions
        Optional preset catalog for UI shortcuts

GET     /reports

GET     /reports/{id}

DELETE  /reports/{id}

GET     /settings

PUT     /settings
```

All APIs return JSON.

---

# 10. Frontend Pages

The MVP should contain only the following pages.

Dashboard

Displays:

- Recent reports
- Dataset summary

---

Datasets

Displays:

- Dataset list
- Import button
- Delete button

---

Research

Displays:

- Dataset selector
- Free-form question input (required)
- Optional preset question shortcuts (pre-fill the input)
- Generate Report button

---

History

Displays:

Previously generated reports, including the question text asked.

---

Settings

Displays:

- AI Provider
- Model
- Embedding Model

No advanced configuration panels.

---

# 11. AI Layer

The AI system should always follow Retrieval-Augmented Generation (RAG).

Workflow:

```
Dataset

↓

User Free-Form Question
(+ optional preset)

↓

Semantic Search
(embed the question text)

↓

Relevant Chunks

↓

Context Builder

↓

Prompt
(free_form_research.md or preset prompt)

↓

LLM

↓

Research Report
(with question_text)
```

The LLM should never answer without retrieved evidence. Off-topic or unsupported free-form questions must fail with insufficient evidence rather than answering from world knowledge.

---

# 12. Prompt Management

Prompts should be stored separately from application code.

Suggested structure:

```
prompts/

free_form_research.md      # Primary generic prompt for any user question (required)

pain_points.md              # Optional preset

feature_requests.md

sentiment.md

opportunities.md

executive_summary.md
```

Prompts should be editable without modifying application code. Free-form research uses `free_form_research.md` by default; presets may select a specialized file.

---

# 13. Environment Variables

Example:

```
DATABASE_URL=

SUPABASE_URL=

SUPABASE_KEY=

AI_PROVIDER=

AI_MODEL=

EMBEDDING_MODEL=

API_BASE_URL=
```

Sensitive information should never be hardcoded.

---

# 14. Error Handling

All APIs should return a standard format.

```
{
  "success": true,
  "message": "",
  "data": {}
}
```

Error responses:

```
{
  "success": false,
  "message": "",
  "errors": []
}
```

Never expose internal stack traces.

---

# 15. Logging

Log the following events:

- Dataset import
- AI requests
- Report generation
- API errors
- Background jobs
- System startup
- System shutdown

Use structured logging.

---

# 16. Security

The MVP does not require authentication.

Anyone with the application URL may access it.

Basic security requirements:

- Validate API input
- Sanitize uploaded data
- Secure environment variables
- Use HTTPS in production
- Protect backend endpoints from malformed requests

---

# 17. Performance Guidelines

The application should be optimized for simplicity rather than scale.

Recommended targets:

- Dashboard loads within 2 seconds
- Dataset listing within 2 seconds
- Report generation depends on AI provider
- API responses under 500ms (excluding AI requests)

Premature optimization should be avoided.

---

# 18. Coding Standards

General guidelines:

- Use TypeScript strict mode.
- Use Python type hints.
- Keep functions small.
- Prefer composition over inheritance.
- One responsibility per module.
- Avoid duplicated code.
- Use descriptive naming.
- Write readable code before clever code.

---

# 19. Development Order

Build the application in the following sequence.

### Phase 1

Project setup

- Frontend
- Backend
- Database
- Deployment

---

### Phase 2

Dataset management

- Import
- Storage
- Cleaning

---

### Phase 3

Embedding generation

- pgvector
- Semantic indexing

---

### Phase 4

Research engine

- Free-form question acceptance
- Generic + optional preset prompts
- Retrieval
- Prompt construction
- AI provider integration
- Report generation (store question_text)

---

### Phase 5

Frontend integration

- Research workspace with free-form input
- Optional preset shortcuts
- Report display (including question asked)
- Export functionality

---

### Phase 6

Testing and deployment

- Bug fixes
- Performance improvements
- Production deployment

---

# 20. Future Scalability

The architecture should allow future support for:

- Authentication
- Multi-user workspaces
- Team collaboration
- Multiple AI providers
- Additional data sources
- Report templates
- Background queues
- Cloud storage
- Advanced analytics

These features are intentionally excluded from the MVP.

---

# 21. Definition of Done

A feature is complete when:

- It satisfies the PRD.
- It is tested.
- It handles errors gracefully.
- It follows coding standards.
- It is documented where necessary.
- It integrates successfully with the application.

---

# 22. Engineering Vision

The engineering objective is to build a lightweight, browser-based AI Product Research Assistant that transforms customer conversations into evidence-backed product research reports.

The architecture should remain simple, modular, and affordable to operate while supporting future growth without requiring significant redesign.

Every engineering decision should reinforce the project's core philosophy:

**Build only what is necessary to validate the product, keep the codebase clean, and make future enhancements straightforward.**