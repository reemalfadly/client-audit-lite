# Client Audit Lite

Free edition: audit one web page at a time for classic SEO and AI-search visibility, and get a scored, client-ready report in Arabic or English. The plugin measures what tools can measure (page facts, robots.txt rules, color contrast) and labels everything else as Inferred or Unknown. It does not render JavaScript.

## Install

Requires Claude Code 2.1.275 or later.

```
/plugin install client-audit-lite --marketplace reemalfadly/client-audit-lite
```

The tool server needs Python 3.10 or later (tested on 3.11) and the packages `mcp` (2.3 or newer, with its own dependencies) and `certifi`. If the tools do not appear, install them with the same Python that runs `python` on your computer, then restart the app:

```
python -m pip install -r mcp/requirements.txt
```

Run that command from the plugin folder (the one that holds `.mcp.json`). The plugin starts the server with the command `python`. If your computer only has `python3` (macOS and Linux) or `py` (Windows), make `python` available first; on Windows, `python3` is often a Microsoft Store stub that does not work.

## Use it

Run `/client-audit-lite:client-audit https://example.com/page`, or just ask Claude to audit a page. Claude is instructed to audit at most 10 pages per run and to ask before going beyond that. Ask in Arabic and the report is in Arabic; ask in English and it is in English.

The plugin measures the page with three read-only tools, then Claude writes the report with the bundled rubric:

| Tool | What it returns |
|---|---|
| `fetch_page` | Status and redirects, title and meta description with lengths, noindex and nofollow with the source of each, canonical, viewport, language, heading counts and outline, word count of the text in the HTML (CSS-hidden text is included), image alt counts, link counts, structured data (JSON-LD) blocks and whether each one parses |
| `check_robots` | Whether `*`, `Googlebot`, `Bingbot`, `GPTBot`, `ChatGPT-User`, `OAI-SearchBot`, `ClaudeBot`, `Claude-User`, `PerplexityBot`, `Google-Extended` and `CCBot` may fetch the home page and the given page, the robots.txt line that decided it, and the sitemaps listed |
| `contrast_ratio` | The WCAG contrast ratio, to two decimals, for two solid colors you provide, and whether it passes AA and AAA |

## What the report contains

- A score out of 100 with the points lost in each category, and why.
- Every finding labeled **Observed** (a tool returned it), **Inferred** (a reasonable conclusion) or **Unknown** (needs data the tools do not have). The skill tells Claude to take numbers only from the tools or from data you supply.
- If the page is `noindex` for Googlebot or for all crawlers, or robots.txt blocks it for Googlebot, the score is capped at 40 and that becomes finding 1.
- An AI-search readiness check, a structured-data check, and fixes ordered by impact divided by effort.
- Draft titles, meta descriptions, heading outlines and JSON-LD, shown for review. The plugin has no tool that edits files, and Claude is told to change nothing unless you ask.

## Data and network

- `fetch_page` reads the page you name and follows up to 5 redirects, checking every hop. `check_robots` reads only that site's `/robots.txt`.
- Only public sites are read: local and private addresses are refused, and only ports 80 and 443 are used.
- A request waits at most 10 seconds per read and 20 seconds in total, including the address lookup.
- The tools keep no data, write no report or data files, and need no keys or accounts. The server is started with Python's `-B` flag so it does not write compiled code into the plugin folder.
- The results, including a short text preview of the page, are passed to Claude as part of your conversation. The site you audit sees your IP address and the user agent `ClientAuditLite/0.1`.

## Limits

- The tools read the HTML the server sends. They do not run JavaScript, so a page built entirely by scripts can look nearly empty; the report says so and marks what depends on rendering as Inferred or Unknown.
- The tools do not return the full page copy. For "content match to intent" and "trust and expertise", Claude asks you to paste the page copy; if you do not, those items stay Unknown.
- Sitemap membership, internal-link reachability, image dimensions, overlays, broken links and page speed are not measured, and stay Unknown.
- Pages behind a login are out of scope.
- No ranking, traffic or backlink data is measured, and no result is guaranteed.

## Where it works

The tools run on your own computer, so the plugin works where local tool servers run: Claude Code and Cowork sessions on your computer. In apps that cannot run local tool servers, such as the web chat, the skill asks you to paste the page source and robots.txt instead.

## License

MIT. See `LICENSE`.
