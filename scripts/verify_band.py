"""Verify live Band credentials before running the pipeline.

For each agent configured in the environment this script:
  * validates the API key via ``agent_api_identity.get_agent_me()``
  * lists the chats the agent participates in (``agent_api_chats.list_agent_chats()``)
  * checks that the configured ``BAND_ROOM_ID`` is among them

Run:  ``uv run python scripts/verify_band.py``

Uses the installed thenvoi-sdk REST client, so it confirms credentials and room
membership against the same API the live pipeline uses.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

from core.live_band import load_creds_from_env  # noqa: E402

load_dotenv(ROOT / ".env")


def _chat_ids(resp) -> list:
    data = getattr(resp, "data", None) or []
    ids = []
    for ch in data:
        cid = getattr(ch, "id", None) or (ch.get("id") if isinstance(ch, dict) else None)
        if cid:
            ids.append(str(cid))
    return ids


def main() -> int:
    try:
        from thenvoi_rest import RestClient
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: thenvoi-sdk not importable ({exc}). Run `pip install thenvoi-sdk`.")
        return 1

    room_id = os.getenv("BAND_ROOM_ID", "")
    creds = load_creds_from_env()

    if not creds:
        print("No Band agent credentials configured in .env — the app runs in MOCK mode.")
        print("Set BAND_AGENT1_API_KEY/_ID … and BAND_ROOM_ID to enable live mode.")
        return 0

    print(f"Band room: {room_id or '(unset!)'}")
    print(f"Configured agents: {', '.join(creds.keys())}\n")

    all_ok = True
    for name, c in creds.items():
        print(f"── {name} ({c.agent_id}) " + "─" * 18)
        client = RestClient(api_key=c.api_key)
        try:
            me = client.agent_api_identity.get_agent_me()
            who = getattr(getattr(me, "data", me), "name", None) or getattr(me, "data", me)
            print(f"  ✅ authenticated as: {who}")
        except Exception as exc:  # noqa: BLE001
            print(f"  ❌ get_agent_me failed: {exc}")
            all_ok = False
            print()
            continue
        try:
            chats = client.agent_api_chats.list_agent_chats()
            ids = _chat_ids(chats)
            print(f"  • chats: {ids}")
            if room_id and room_id not in ids:
                print(f"  ⚠️  configured room {room_id} NOT in this agent's chats — add the agent to the room.")
                all_ok = False
        except Exception as exc:  # noqa: BLE001
            print(f"  ⚠️  list_agent_chats failed: {exc}")
        print()

    print("RESULT:", "✅ all agents ready for live coordination" if all_ok
          else "⚠️ issues found — see above")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
