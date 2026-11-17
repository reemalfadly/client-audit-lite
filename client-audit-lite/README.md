# Client Audit Lite

Free edition: audit one web page at a time for classic SEO and AI-search visibility, and get a scored, client-ready report in Arabic or English. Claude reads the page's raw HTML, its response headers and its robots.txt, and labels every finding as Observed, Inferred or Unknown. It does not render JavaScript.

## Install

Requires Claude Code 2.1.275 or later.

```
/plugin install client-audit-lite --marketplace reemalfadly/client-audit-lite
```

The plugin is a skill and a command: Markdown files only, with no program to install and no packages.

## Use it

Run `/client-audit-lite:client-audit https://example.com/page`, or just ask Claude to audit a page. The skill tells Claude to audit at most 10 pages per run and to ask before going beyond that. Ask in Arabic and the report is in Arabic; ask in English and it is in English.

## How the page is read

The skill tries three routes in order and says which one it used:

1. **A shell is available** (Claude Code, Cowork): Claude runs `curl` to get the page with every redirect hop and its headers, and the site's `/robots.txt`.
2. **No shell, but a web-fetch tool:** the tool returns a processed copy of the page, not the raw HTML, so anything that depends on meta tags, headers or structured data is marked Inferred, and Claude asks you to paste the page source for what must be Observed.
3. **Nothing can be fetched:** Claude asks you to paste the page source and robots.txt.

## What the report contains

- A score out of 100 with the points lost in each category, and why.
- Every finding labeled **Observed** (the retrieved HTML, header or robots.txt text shows it), **Inferred** (a reasonable conclusion) or **Unknown** (needs data this edition does not have). The skill tells Claude to take numbers only from what it retrieved or from data you supply.
- Crawler access from robots.txt for `*`, `Googlebot`, `Bingbot`, `GPTBot`, `ChatGPT-User`, `OAI-SearchBot`, `ClaudeBot`, `Claude-User`, `PerplexityBot`, `Google-Extended` and `CCBot`, with the deciding line quoted. Claude applies the matching rules by reading the file, so the result is Inferred from an Observed line.
- If the page has a `noindex` for Googlebot or for all crawlers, or robots.txt blocks it for Googlebot, the score is capped at 40 and that becomes finding 1.
- An AI-search readiness check, a structured-data check, and fixes ordered by impact divided by effort.
- WCAG contrast ratio for two solid colors, if you give them.
- Draft titles, meta descriptions, heading outlines and JSON-LD, shown for review. The plugin contains no code, and Claude is told to change nothing unless you ask.

## Data and network

- The plugin itself has no code, makes no network requests and stores nothing. Anything fetched is fetched by Claude, on your computer, through `curl` or Claude's own web-fetch tool, and only for the pages you name and the robots.txt of their site.
- The skill tells Claude to read public sites only and not to request local or private addresses. This is an instruction to Claude, not a technical block.
- Results become part of your conversation with Claude, including short excerpts of the page.
- The site you audit sees your IP address and the user agent `ClientAuditLite/0.1` when `curl` is used.

## Limits

- Claude reads the HTML the server sends. It does not run JavaScript, so a page built entirely by scripts can look nearly empty; the report says so and marks what depends on rendering as Inferred or Unknown.
- Counts (words, links, images) are done by Claude reading the retrieved text, so they are approximate, and longer pages may be cut.
- Sitemap membership, internal-link reachability, image dimensions, overlays, broken links and page speed are not measured and stay Unknown.
- For "content match to intent" and "trust and expertise", Claude asks you to paste the page copy; if you do not, those items stay Unknown.
- Pages behind a login are out of scope.
- No ranking, traffic or backlink data is measured, and no result is guaranteed.

## License

MIT. See `LICENSE`.
