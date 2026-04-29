"""Chat service: context builder and suggestion parser."""
import json
import logging
import re
import sqlite3

from ..models import Application, ChatMessage, SUGGESTION_TYPES, TailoredResumeRow
from ..prompts.chat import CHAT_SYSTEM

log = logging.getLogger(__name__)

_HISTORY_LIMIT = 20


def build_chat_context(
    application: Application,
    tailored_row: TailoredResumeRow,
    history: list[ChatMessage],
    new_user_message: str,
) -> tuple[str, list[dict]]:
    """Build (system_prompt, messages) ready for stream_llm.

    The system prompt embeds the JD + tailored resume snapshot so they are
    prompt-cached. The messages list contains up to the last 20 history
    entries plus the new user message.
    """
    tailored_json = tailored_row.content.model_dump_json(indent=2)

    system_prompt = (
        f"JOB DESCRIPTION:\n{application.jd}\n\n"
        f"CURRENT TAILORED RESUME (JSON):\n{tailored_json}\n\n"
        f"---\n\n{CHAT_SYSTEM}"
    )

    recent = history[-_HISTORY_LIMIT:]
    messages: list[dict] = [
        {"role": msg.role, "content": msg.content}
        for msg in recent
    ]
    messages.append({"role": "user", "content": new_user_message})

    return system_prompt, messages


def parse_suggestions(assistant_text: str) -> list[dict]:
    """Extract and parse the <<<SUGGESTIONS>>> block from assistant output.

    Returns a list of validated suggestion dicts. Entries missing required
    fields or with unknown types are silently skipped.
    """
    match = re.search(
        r"<<<SUGGESTIONS>>>\s*(.*?)\s*<<<END>>>",
        assistant_text,
        re.DOTALL,
    )
    if not match:
        return []

    raw = match.group(1).strip()
    try:
        items = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        log.warning("parse_suggestions: invalid JSON in suggestions block: %s", exc)
        return []

    if not isinstance(items, list):
        log.warning("parse_suggestions: suggestions block is not a JSON array")
        return []

    result: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            log.warning("parse_suggestions: skipping non-dict item: %r", item)
            continue
        stype = item.get("type", "")
        if stype not in SUGGESTION_TYPES:
            log.warning("parse_suggestions: unknown suggestion type %r, skipping", stype)
            continue
        if not item.get("target"):
            log.warning("parse_suggestions: missing target, skipping item %r", item)
            continue
        if not item.get("proposed"):
            log.warning("parse_suggestions: missing proposed, skipping item %r", item)
            continue
        result.append(item)

    return result
