"""Client Audit Lite: a small read-only MCP server (stdio).

Three tools that give an agent exact facts instead of guesses:
  fetch_page      facts from one page you name (title, headings, meta, schema, images ...)
  check_robots    robots.txt rules for search and AI crawlers
  contrast_ratio  exact WCAG contrast for two solid colors

It writes nothing, stores nothing, needs no keys. fetch_page and check_robots open the
address you give them over the network, waiting at most 10 seconds per read and 20 seconds
for the whole request (the address lookup included); see audit_core.py for the safety rules.
"""
from __future__ import annotations

from mcp.types import ToolAnnotations

from mcp.server.mcpserver import MCPServer as _Server  # mcp 2.3 or newer (see requirements.txt)
from mcp.server.mcpserver.exceptions import ToolError

import functools

import audit_core as core


def _plain_errors(fn):
    """Show the reason in plain words (for example 'not a public internet address')."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except core.AuditError as exc:
            raise ToolError(str(exc)) from None
    return wrapper

mcp = _Server(
    "client-audit-lite",
    instructions=(
        "Read-only audit helpers. Use fetch_page and check_robots only for pages the user named. "
        "Report the returned facts as they are; do not invent numbers that a tool did not return."
    ),
)

_NETWORK = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True)
_LOCAL = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)


@mcp.tool(annotations=_NETWORK)
@_plain_errors
def fetch_page(url: str) -> dict:
    """Read one public web page that the user named and return facts about it: status and
    redirects, charset, title and meta description with lengths, noindex / nofollow combined from
    every robots-type meta tag and the X-Robots-Tag header (robots_directives lists each source),
    canonical, viewport, language, heading_counts h1-h6, heading outline h1-h3 (max 20 each,
    outline_truncated when cut), word count of the text in the HTML (CSS-hidden text is included), text_preview (first 400 characters of
    visible body text), image alt counts with images_missing_alt_srcs (at most 20 sources; images_missing_alt_attribute is the full count), link counts and
    structured data (JSON-LD) types, with a snippet of each block that does not parse.
    It does not return the full page copy or image sizes, and does not extract author, dates or
    contact details as separate fields; the short text preview and snippets may contain text from the page.
    Long values and lists are capped (output_truncated: true when a long value or list was cut, except the outline and the alt sources above; lengths and
    counts such as title_length and json_ld_block_count stay the real ones), and charset_note
    appears when the page's declared charset was not used.
    A bare host such as example.com is read as https://example.com. Only public http(s)
    addresses are allowed."""
    return core.page_facts(url)


@mcp.tool(annotations=_NETWORK)
@_plain_errors
def check_robots(url: str) -> dict:
    """Read the robots.txt of the site that a page belongs to and say whether each crawler in
    bots_checked (*, Googlebot, Bingbot, GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot,
    Claude-User, PerplexityBot, Google-Extended, CCBot) may fetch the home page and the given
    page (page_path), using Google's matching rules. For each crawler it returns the group used
    and the deciding line (home_rule, this_page_rule; null means no line matched, so allowed),
    plus any sitemap addresses it lists. Other crawlers are not tested.
    Each crawler has a status: "ok", or "unknown_rules_not_fully_read" / "unknown_long_rule_ignored"
    when robots.txt was not fully used (robots_complete: false); then an allowed value of null means
    unknown, never allowed, and only false (blocked by a rule that was read) is certain."""
    return core.robots_report(url)


@mcp.tool(annotations=_LOCAL)
@_plain_errors
def contrast_ratio(foreground: str, background: str) -> dict:
    """Exact WCAG contrast ratio between two solid colors (#rgb, #rrggbb or rgb(r, g, b))
    and whether it passes AA / AAA for normal and large text and for UI components."""
    return core.contrast(foreground, background)


if __name__ == "__main__":
    mcp.run()
