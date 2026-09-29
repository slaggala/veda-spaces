"""Versioned email templates rendered with an escaping engine (02 §10.3, NOTIF-005).

Each template is one versioned file ``templates/<name>.v<N>.jinja`` defining
``subject``, ``text`` and ``html`` blocks. The HTML block is autoescaped; the
layout uses the brand tokens (serif headline, copper accent).
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

TEMPLATE_DIR = Path(__file__).parent / "templates"

# Two environments over the same files: plain text is never HTML-escaped, HTML always is.
_text_env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=False, undefined=StrictUndefined,
                        trim_blocks=True, lstrip_blocks=True)
_html_env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True, undefined=StrictUndefined,
                        trim_blocks=True, lstrip_blocks=True)


def _block(env: Environment, name: str, block: str, context: dict) -> str:
    template = env.get_template(name)
    return "".join(template.blocks[block](template.new_context(context))).strip()


def render(_template: str, _version: int = 1, /, **context) -> tuple[str, str, str]:
    filename = f"{_template}.v{_version}.jinja"
    subject = " ".join(_block(_text_env, filename, "subject", context).split())
    text = _block(_text_env, filename, "text", context) + "\n"
    html = _html_env.get_template(filename).render(context).strip()
    return subject, text, html


def available() -> list[str]:
    return sorted(p.name for p in TEMPLATE_DIR.glob("*.jinja") if not p.name.startswith("_"))
