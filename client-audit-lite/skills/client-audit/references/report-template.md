# Report template

Translate every heading and label below (Executive summary, Scorecard, Findings, Why it matters, Fix, Verify, Drafts, Limits ...) into the report language. Keep URLs, code, tag and tool names and numbers as returned.

```
# SEO + AI-search audit — <page or site>
Date: <date> · Pages audited: <n> · Goal: <goal> · Audience: <audience/country/language>
Target queries: <1-3>

## Executive summary
<!-- the summary text (Score line to Top 3 fixes) is under 120 words; the list below it is outside the count -->
Score: <NN>/100 (<band>). Treat it as a provisional ceiling when any item was not measured. <If the BLOCKER rule applies: "Capped at 40: the page cannot be indexed (<noindex source or robots line>)."> <Two sentences: the biggest blocker or opportunity.>
Top 3 fixes: 1) … 2) … 3) …

Not measured: <list>

## Scorecard
| Category | Score | Why points were lost |
|---|---|---|
| Crawl and index access | x/15 | … |
| Titles, meta, headings | x/15 | … |
| Content match to intent | x/20 | … |
| Trust and expertise | x/10 | … |
| Structured data | x/10 | … |
| AI-search readiness | x/15 | … |
| Experience basics | x/10 | … |
| Links | x/5 | … |

## Findings (ordered by impact ÷ effort, blockers first)
### 1. BLOCKER: <title>   (write "BLOCKER:" only when the page is noindex or blocked for Googlebot; otherwise start with the finding of highest impact)
[Observed|Inferred|Unknown] <what> — <where>
Why it matters: …
Fix: …
Verify: …
Impact 1-3 · Effort 1-3

## Drafts for review (not applied)
Written in <language of the page>.
- Title: "…" (<n> characters)
- Meta description: "…" (<n> characters)
- Heading outline: …
- JSON-LD: …
- FAQ block (only if you will show it on the page): …

## How to measure progress
- Search Console: indexing status and queries
- Re-run this audit in 30 days
- Ask the same target questions in AI engines monthly and record whether the site is cited

## Limits of this audit
Based on <fetched HTML / pasted source / screenshots supplied by the user> on <date>. No rankings, traffic, backlink or performance data was available unless listed above. Length figures (title, meta description, answer passages) are common heuristics, not search-engine rules. No result is guaranteed.
```
