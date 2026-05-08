"""Chat service: context builder, suggestion parser, and diff helpers."""
import json
import logging
import re
import sqlite3

from ..models import Application, ChatMessage, SUGGESTION_TYPES, TailoredResume, TailoredResumeRow
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


def compute_current_value(
    tailored: TailoredResume, suggestion_type: str, target: str
) -> str:
    """Return the current text being replaced by a suggestion.

    Returns "" on any parse error or out-of-range index (soft fail so the
    diff just looks like a pure addition rather than crashing the stream).
    """
    from .suggestion_apply import parse_target_index

    try:
        indices = parse_target_index(target, suggestion_type)
    except ValueError:
        return ""

    if suggestion_type == "replace_summary":
        return tailored.summary

    if suggestion_type == "rephrase_bullet":
        i, j = indices
        if i >= len(tailored.experience):
            return ""
        exp = tailored.experience[i]
        if j >= len(exp.bullets):
            return ""
        return exp.bullets[j].text

    if suggestion_type == "swap_skill":
        (i,) = indices
        if i >= len(tailored.skills):
            return ""
        return tailored.skills[i]

    return ""


def parse_suggestions(assistant_text: str) -> list[dict]:
    """Extract and parse the <<<SUGGESTIONS>>> block from assistant output.

    Tolerates: markdown fences around the block, alternate field names
    (target_section/proposed_value), and trailing prose. Entries with
    unknown types or missing required fields are silently skipped.
    """
    match = re.search(
        r"<<<SUGGESTIONS>>>\s*(.*?)\s*<<<END>>>",
        assistant_text,
        re.DOTALL,
    )
    if not match:
        return []

    raw = match.group(1).strip()

    # Strip markdown fences if Claude wrapped the JSON
    fence_match = re.fullmatch(r"```(?:json)?\s*\n?(.*?)\n?\s*```", raw, re.DOTALL)
    if fence_match:
        raw = fence_match.group(1).strip()

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
        stype = item.get("type") or item.get("suggestion_type") or ""
        if stype not in SUGGESTION_TYPES:
            log.warning("parse_suggestions: unknown suggestion type %r, skipping", stype)
            continue
        target = item.get("target") or item.get("target_section") or ""
        if not target:
            log.warning("parse_suggestions: missing target, skipping item %r", item)
            continue
        proposed = item.get("proposed") or item.get("proposed_value") or ""
        if not proposed:
            log.warning("parse_suggestions: missing proposed, skipping item %r", item)
            continue
        result.append({
            "type": stype,
            "target": target,
            "proposed": proposed,
            "rationale": item.get("rationale", ""),
        })

    return result
