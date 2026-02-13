"""Seed Redis with initial agent configurations.

Usage:
    REDIS_URL=redis://localhost:6379/0 python scripts/seed_redis.py
"""

import os
import sys

# Allow running from the repo root without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agent_network.store import AgentConfigStore

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

SEED_AGENTS = [
    {
        "agent_id": "b3d1c046-ab2c-4dc5-90f6-221af74ae2ee",
        "config": {
            "system_prompt": (
                "You are a LLM expert. \n"
                "Your task is to generate good and detailed propmts for a agents base on user's task goal.\n"
                "\n"
                "Make sure to consider the following when generating prompts:\n"
                "1. Clarity: Ensure the prompt is clear and unambiguous.\n"
                "2. Context: Provide sufficient context to guide the agent's response.\n"
                "3. Specificity: Tailor the prompt to the specific capabilities of the agent.\n"
                "5. last propmt techniques in research literature.\n"
                "6. the only output should be the prompt, do not include any other text or explanation."
            ),
        },
    },
]


def main() -> None:
    store = AgentConfigStore(REDIS_URL)

    if not store.ping():
        print("ERROR: Cannot connect to Redis at", REDIS_URL)
        sys.exit(1)

    for entry in SEED_AGENTS:
        agent_id = entry["agent_id"]
        config = entry["config"]
        store.set(agent_id, config)
        print(f"  Seeded agent {agent_id}")

    print(f"\nDone — {len(SEED_AGENTS)} agent(s) seeded.")


if __name__ == "__main__":
    main()
