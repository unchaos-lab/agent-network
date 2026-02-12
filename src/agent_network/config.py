"""Centralised application settings loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings populated from environment / .env file."""

    # Light-Tasks API connection
    api_base_url: str = "http://app:8000"
    api_prefix: str = "/api/v1"

    # Credentials used to authenticate against Light-Tasks
    admin_email: str = "admin@example.com"
    admin_password: str = "admin123"

    # Agent API key for authenticating as an agent user
    agent_api_key: str = ""

    # Webhook consumer
    webhook_host: str = "0.0.0.0"
    webhook_port: int = 9000
    webhook_callback_url: str = "http://agent-network:9000/webhook"
    webhook_events: str = (
        "task.created,task.updated,task.deleted,task.moved,"
        "task.commented,task.feedback_added,"
        "user.created,user.updated,user.deleted"
    )

    # RabbitMQ
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672/"
    rabbitmq_exchange: str = "agent_network"
    rabbitmq_task_queue: str = "task_events"
    rabbitmq_routing_key: str = "task.created"

    # Startup behaviour
    max_retries: int = 30
    retry_interval: int = 2

    # Logging
    log_level: str = "INFO"

    @property
    def webhook_events_list(self) -> list[str]:
        """Return *webhook_events* as a list of strings."""
        return [s.strip() for s in self.webhook_events.split(",") if s.strip()]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


@lru_cache
def get_settings() -> Settings:
    """Return a cached *Settings* instance."""
    return Settings()
