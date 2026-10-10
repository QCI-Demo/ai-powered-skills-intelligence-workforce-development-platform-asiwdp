# ASIWDP Feedback Service

Learner feedback ingestion and persistence service for the AI-Powered Skills
Intelligence & Workforce Development Platform.

## Features

- **Feedback Entity**: Stores accept/reject actions and optional ratings linked
  to recommendation records
- **Tenant-Scoped Storage**: Multi-tenant isolation via tenant_id foreign key
- **RESTful API**: POST /feedback endpoint with validation
- **OAuth2/JWT Ready**: Integrates with ASIWDP auth middleware

## Installation

```bash
pip install -e "libs/feedback-service[dev]"
```

## Usage

```python
from feedback_service import create_feedback_router, FeedbackRepository

# Create repository and routes
repository = FeedbackRepository()
routes = create_feedback_router(repository)

# Add to your Starlette/FastAPI app
app.routes.extend(routes)
```

## API Endpoints

### POST /feedback

Submit learner feedback on a recommendation.

**Request Body:**
```json
{
  "recommendation_id": "uuid",
  "feedback_type": "accept" | "reject",
  "rating": 1-5,  // optional
  "comment": "string"  // optional
}
```

**Response (201):**
```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  "learner_id": "uuid",
  "recommendation_id": "uuid",
  "feedback_type": "accept",
  "rating": 4,
  "comment": "Great recommendation!",
  "created_at": "2024-01-15T10:30:00Z",
  "model_version": "v1.2.0"
}
```

### GET /feedback/{feedback_id}

Retrieve specific feedback by ID.

### GET /feedback

List feedback with optional filters:
- `recommendation_id`: Filter by recommendation
- `learner_id`: Filter by learner
- `feedback_type`: Filter by type (accept/reject)
- `limit`: Max results (default 100)
- `offset`: Pagination offset

## Testing

```bash
pytest libs/feedback-service/tests -v
```

## Entity Model

The `Feedback` entity includes:

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Unique feedback identifier |
| tenant_id | UUID | Foreign key to tenant (multi-tenancy) |
| learner_id | UUID | Foreign key to user |
| recommendation_id | UUID | Foreign key to recommendation record |
| feedback_type | Enum | "accept" or "reject" |
| rating | int (1-5) | Optional rating |
| comment | string | Optional comment (max 2000 chars) |
| created_at | datetime | Submission timestamp |
| model_version | string | Recommendation model version metadata |
