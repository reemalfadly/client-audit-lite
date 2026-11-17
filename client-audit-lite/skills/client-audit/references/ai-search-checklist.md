# AI-search readiness checklist (GEO: generative engine optimization)

AI answer engines (ChatGPT search, Perplexity, Google AI Overviews and similar) tend to cite pages they can access, understand and trust. Nobody outside those companies knows the exact selection rules, so everything below is **good practice that removes blockers**, not a guaranteed recipe. Say that in the report.

## 1. Access (blockers first)
- [ ] `robots.txt` does not block the page for the crawlers the owner wants to be visible to. Check exactly these user agents: `*`, `Googlebot`, `Bingbot`, `GPTBot`, `ChatGPT-User`, `OAI-SearchBot`, `ClaudeBot`, `Claude-User`, `PerplexityBot`, `Google-Extended`, `CCBot`, by reading the retrieved robots.txt with Google's matching rules. Any other crawler (for example `Claude-SearchBot`, `Applebot-Extended`) was not checked: report it as Unknown and, if it matters, read its group in robots.txt by hand. If robots.txt could not be read, access is Unknown, never "allowed". **These names and their purposes change; tell the user to confirm the current list in each vendor's documentation.** Blocking *training* crawlers while allowing *search/answer* crawlers is a legitimate choice; report what the file does and whether it matches what the owner intends.
- [ ] Important content is in the HTML response, not only produced by scripts.
- [ ] No login wall, cookie wall or interstitial hides the main content from a plain fetch.
- [ ] Page is fast enough to fetch (no multi-second server delay seen); this edition does not measure response time, so mark it Unknown.
- [ ] Optional: an `llms.txt` file. It is a proposal, not a standard that all engines read; do not promise benefits.

## 2. Answer-first structure
- [ ] The page states the answer to the target question in the first 1-3 sentences under the relevant heading (40-80 words is a useful length).
- [ ] Headings are phrased like the questions people ask.
- [ ] Facts are in short, self-contained paragraphs, lists or tables that can be quoted without the surrounding page.
- [ ] Definitions, steps, comparisons, prices and dates are explicit and unambiguous.

## 3. Entities and clarity
- [ ] The brand/person/product is named consistently, with a plain description ("X is a … that …") early on.
- [ ] Same facts (name, address, founding year, product specs) agree across the page, schema and the site's About/Contact pages.
- [ ] Ambiguous pronouns and vague claims ("the best", "leading") are replaced with specifics or removed.
- [ ] Organization identity is linkable: `sameAs` links to official profiles that really exist.

## 4. Trust signals
- [ ] Named author or team with relevant credentials; dates for published and updated.
- [ ] Claims have sources (links to primary or reputable pages); statistics name their source and year.
- [ ] First-hand material: original data, screenshots, case details, quotes. Generic rewrites of other pages are unlikely to stand out.
- [ ] No fabricated reviews or ratings; review markup only for reviews visible on the page.

## 5. Freshness and maintenance
- [ ] Visible "last updated" date that matches reality; content that goes stale (prices, versions, laws) has an owner and a review date.

## 6. Measurement (tell the user, do not invent)
- Ask the same 5-10 target questions in the engines the audience uses, on a schedule, and record whether the site is cited. That is the most direct "AI visibility" measure available to most owners.
- Server logs can show visits by the crawlers above; confirm user-agents against each vendor's published information before trusting them.
