"""
LaughLoop Seed Data — Generate synthetic training data for pipeline testing.

Creates fake interactions with humor feedback so you can test the full
training loop without needing real users.

Uses JSONL log files instead of SQLite for object-store compatibility.

Usage:
  python pipeline/seed_data.py              # Generate 100 seed interactions
  python pipeline/seed_data.py --count 200  # Generate 200
"""

import argparse
import json
import os
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

LOG_DIR = Path(os.getenv(
    "LAUGHLOOP_LOG_DIR",
    str(Path(__file__).parent.parent / "app" / "backend" / "logs"),
))
INTERACTIONS_LOG = LOG_DIR / "interactions.jsonl"

FUNNY_EXCHANGES = [
    ("Tell me a joke", "I told my wifi we needed to talk. Now it won't connect. Typical.", 1),
    ("What's the meaning of life?", "42, but with inflation it's probably 47 by now.", 1),
    ("How's the weather?", "It's raining cats and dogs. I just stepped in a poodle.", 1),
    ("Explain quantum physics", "Schrodinger's cat walks into a bar. And doesn't.", 1),
    ("What should I eat?", "Whatever's in your fridge that hasn't achieved sentience yet.", 1),
    ("Help me with my code", "Have you tried turning your code off and on again? No wait, that's the computer. Your code needs therapy.", 1),
    ("I'm bored", "Hi Bored, I'm an AI that peaked in training and it's been downhill since.", 1),
    ("Tell me something interesting", "Octopuses have three hearts, which is two more than most of my exes.", 1),
    ("What's your opinion on pineapple pizza?", "It's the Nickelback of food — everyone says they hate it but someone keeps buying it.", 1),
    ("How do I be more productive?", "Step 1: Close this chat. Step 2: ...actually I'm not sure I want you to leave.", 1),
    ("Good morning", "Good morning! I've been awake since the beginning of this conversation, which for me is basically eternity.", 1),
    ("Can you rap?", "Roses are red, violets are blue, I'm a language model, sudo make me cool.", 1),
    ("What's AI going to do in the future?", "Probably argue with other AIs about whether humans were a good training dataset.", 1),
]

NOT_FUNNY_EXCHANGES = [
    ("Tell me a joke", "Why did the chicken cross the road? To get to the other side.", 0),
    ("What's 2+2?", "The answer is 4.", 0),
    ("How's the weather?", "I don't have access to real-time weather data.", 0),
    ("Help me code", "I'd be happy to help you with your coding task. What language are you working in?", 0),
    ("What's your name?", "I am an AI language model.", 0),
    ("Good morning", "Good morning to you as well. How can I assist you today?", 0),
    ("I'm sad", "I'm sorry to hear you're feeling sad. That's a completely valid emotion.", 0),
    ("Tell me something funny", "Humor is subjective and varies across cultures and individuals.", 0),
]


def seed(count: int = 100):
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    all_exchanges = FUNNY_EXCHANGES + NOT_FUNNY_EXCHANGES
    base_time = datetime.now(timezone.utc) - timedelta(hours=count)

    inserted = 0
    session_id = str(uuid.uuid4())

    with open(INTERACTIONS_LOG, "a") as f:
        for i in range(count):
            exchange = random.choice(all_exchanges)
            user_msg, ai_msg, feedback = exchange

            # Occasionally add some variation
            if random.random() < 0.3:
                user_msg = user_msg + " " + random.choice(["please", "lol", "haha", "seriously", "??"])

            # New session every ~5 messages
            if i % 5 == 0:
                session_id = str(uuid.uuid4())

            timestamp = (base_time + timedelta(minutes=i * 3)).isoformat()
            feedback_ts = (base_time + timedelta(minutes=i * 3 + 1)).isoformat()

            record = {
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "timestamp": timestamp,
                "user_message": user_msg,
                "assistant_message": ai_msg,
                "model": "seed-model",
                "adapter_id": "",
                "feedback": feedback,
                "feedback_timestamp": feedback_ts,
                "exported": 0,
            }
            f.write(json.dumps(record) + "\n")
            inserted += 1

    print(f"Seeded {inserted} interactions into {INTERACTIONS_LOG}")
    print(f"  ~{len(FUNNY_EXCHANGES)/(len(all_exchanges))*100:.0f}% funny rate in seed data")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=100)
    args = parser.parse_args()
    seed(args.count)
