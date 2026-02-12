# agent-network

Webhook consumer and event processor for the [Light-Tasks](../light-tasks) API.

## Architecture

```
src/agent_network/
├── config.py              # Settings from env vars / .env
├── startup.py             # Orchestrator: wait → login → register → serve
├── __main__.py            # python -m agent_network
├── api/
│   └── client.py          # HTTP client wrapper (httpx)
├── auth/
│   └── client.py          # JWT login & token management
└── webhook/
    ├── consumer.py        # FastAPI server receiving webhook events
    ├── registry.py        # Register / clean-up webhooks on Light-Tasks
    └── signature.py       # HMAC-SHA256 verification
```

## Quick Start — Docker Compose

```bash
docker compose up --build
```

This brings up:

| Service          | Port  | Description                          |
|------------------|-------|--------------------------------------|
| `db`             | 5432  | PostgreSQL for Light-Tasks           |
| `app`            | 8000  | Light-Tasks API                      |
| `agent-network`  | 9000  | Webhook consumer (this project)      |

The `agent-network` container will automatically:

1. Wait for the Light-Tasks API to become healthy
2. Log in with the admin credentials
3. Register a webhook for all task / user events
4. Start a FastAPI server that receives and verifies webhook deliveries

## Configuration

All settings are read from environment variables (see `docker-compose.yml`):

| Variable               | Default                                  | Description                      |
|------------------------|------------------------------------------|----------------------------------|
| `API_BASE_URL`         | `http://app:8000`                        | Light-Tasks API base URL         |
| `ADMIN_EMAIL`          | `admin@example.com`                      | Login email                      |
| `ADMIN_PASSWORD`       | `admin123`                               | Login password                   |
| `WEBHOOK_PORT`         | `9000`                                   | Port for the consumer server     |
| `WEBHOOK_CALLBACK_URL` | `http://agent-network:9000/webhook`      | URL Light-Tasks will POST to     |
| `WEBHOOK_EVENTS`       | all task.* and user.* events             | Comma-separated event list       |
| `LOG_LEVEL`            | `INFO`                                   | Python log level                 |

## Local Development

```bash
# Install in editable mode
pip install -e .

# Run
agent-network
# or
python -m agent_network
```
