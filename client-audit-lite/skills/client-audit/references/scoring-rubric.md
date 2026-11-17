# Scoring rubric (100 points)

Score each category, show points lost with the reason. Use whole points. Whenever any item was not measured, the total is a provisional ceiling, never a final score; do not present 100 as final unless every item was measured.

| # | Category | Points | What full marks look like |
|---|---|---|---|
| 1 | Crawl and index access | 15 | 200 status, no redirect chains (max 1 hop), not blocked by robots.txt or `noindex`, canonical points to itself or the right page, in the sitemap (if a sitemap was seen), reachable by internal links |
| 2 | Titles, meta, headings | 15 | Unique `<title>` of about 30-60 characters with the main topic early; meta description that matches the page (about 70-160 characters); exactly one `<h1>`; logical `h2/h3` outline that mirrors the questions users ask |
| 3 | Content match to intent | 20 | The page answers the target query in its first screen; covers the sub-questions a reader would have; original information (examples, data, experience) rather than generic text; clear next step |
| 4 | Trust and expertise | 10 | Named author or organization, contact details, dates (published/updated), sources cited for claims, no unsupported superlatives |
| 5 | Structured data | 10 | Valid JSON-LD of fitting types that matches visible content (Organization, WebSite, Article, Product, FAQPage only if real FAQs are visible, BreadcrumbList) |
| 6 | AI-search readiness | 15 | See `ai-search-checklist.md`: AI crawlers not blocked by accident, answer-first passages, clear entities, extractable lists/tables, freshness signal |
| 7 | Experience basics | 10 | Mobile viewport meta, readable text, images with `alt` and dimensions, no intrusive overlays; performance only if measured (otherwise mark Unknown and give the test to run) |
| 8 | Internal and external links | 5 | Descriptive anchor text, no orphan page, no broken links among those checked, outbound links to credible sources |

**Reporting bands** (for communication only, not a promise): 85-100 strong · 70-84 good with gaps · 50-69 needs work · below 50 needs major work. Use the word "blockers" only when category 1 scores below 8 or the BLOCKER rule below applies.

**Sub-weights (use them so partial credit is consistent):**
- Crawl and index access 15: status/redirects 4 · robots and noindex 4 · canonical (and reciprocal hreflang on multilingual sites) 3 · sitemap/internal reachability 4
- Titles, meta, headings 15: title 5 · meta description 4 · single h1 3 · outline 3
- Content match to intent 20: answers the query 7 · covers sub-questions 5 · original information 5 · clear next step 3
- Trust and expertise 10: author/organization 3 · contact 2 · dates 2 · sources and no unsupported claims 3
- Structured data 10: present and parses 4 · fitting types 3 · matches visible content 3 (a block that does not parse scores 0 for that block)
- AI-search readiness 15: access 4 · answer-first 4 · entities 3 · trust/sources 2 · freshness 2
- Experience basics 10: viewport 2 · readable/mobile 3 · images alt and size 3 · overlays/performance 2 (Unknown if not measured)
- Links 5: anchor text 2 · no orphan/broken 2 · credible outbound 1

**Always Unknown in this edition** (do not deduct, say so in the report): sitemap membership, internal-link reachability and orphan pages, image dimensions, intrusive overlays, broken links and page speed.

Length figures (title, meta description, answer passages) are common heuristics, not search-engine rules; say so in the report.

**Cap rule:** if category 1 scores below 8, cap the total at 60 and say why (crawl and index problems limit every other fix).

**BLOCKER rule (overrides the arithmetic):** if the page has a `noindex` (or `none`) that applies to all crawlers or to Googlebot (a noindex limited to another crawler such as Bingbot does not block Google), or robots.txt blocks the audited page for `Googlebot`, the page cannot be indexed. Cap the total at **40** whatever the categories add up to, put that problem as finding 1, label it **BLOCKER**, and name the source (the meta tag, the `X-Robots-Tag` header or the robots.txt line). The weights above still add to 100; only the total is capped.

**Unknown items:** do not score them as zero and do not deduct for them. Score = full points minus *observed* losses only, so when any category is partly measured, call the total a **provisional ceiling** (it can only fall if the unknowns turn out badly). List what is missing and say how many of the 100 points could actually be measured. Never fill in performance, rankings or backlink data.
