"""Word-level diff for suggestion cards."""
import difflib

from markupsafe import Markup, escape


def word_diff(old: str, new: str) -> Markup:
    """Return HTML-safe word-level diff between old and new.

    Deleted words → <del class="diff-del">word</del>
    Inserted words → <ins class="diff-ins">word</ins>
    Unchanged words → plain escaped text

    Each token is HTML-escaped before wrapping so user text cannot inject markup.
    """
    old_tokens = old.split()
    new_tokens = new.split()

    parts: list[str] = []
    for token in difflib.ndiff(old_tokens, new_tokens):
        code = token[:2]
        word = str(escape(token[2:]))
        if code == "  ":
            parts.append(word)
        elif code == "- ":
            parts.append(f'<del class="diff-del">{word}</del>')
        elif code == "+ ":
            parts.append(f'<ins class="diff-ins">{word}</ins>')
        # "? " hint lines are skipped

    return Markup(" ".join(parts))
