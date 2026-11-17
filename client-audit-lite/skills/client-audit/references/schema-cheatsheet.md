# Structured data cheat sheet (JSON-LD)

Use JSON-LD in a `<script type="application/ld+json">` block. Markup must describe **content that is visible on the page**; never mark up what users cannot see.

## Which type for which page
| Page | Type(s) |
|---|---|
| Home / brand | `Organization` (or `LocalBusiness`), `WebSite` |
| Blog post / guide | `Article` (or `BlogPosting`), `BreadcrumbList`, author as `Person` |
| Product | `Product` with `Offer` (price, currency, availability must match the page) |
| Real FAQ section on the page | `FAQPage` (only if the questions and answers are visible) |
| How-to with steps visible | `HowTo` (check current support before promising anything) |
| Local shop | `LocalBusiness` with address, opening hours, phone |
| Software | `SoftwareApplication` |
| Dated event (class, webinar) | `Event` (name, startDate, location, offers; details must be visible) |
| Video | `VideoObject` |

Vocabulary and field lists live at schema.org. Search engines publish which types they currently use for rich results and change this over time, so tell the user to check each engine's current documentation before promising a visual result.

## Minimal examples
Organization:
```json
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "Example Co",
  "url": "https://www.example.com/",
  "logo": "https://www.example.com/logo.png",
  "sameAs": ["https://www.linkedin.com/company/example"]
}
```
Article:
```json
{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "How to choose a standing desk",
  "datePublished": "2026-01-15",
  "dateModified": "2026-06-02",
  "author": { "@type": "Person", "name": "Jane Doe" },
  "publisher": { "@type": "Organization", "name": "Example Co" }
}
```

## Validation checklist
- [ ] JSON parses (no trailing commas, straight quotes).
- [ ] Required fields for the chosen type are present; dates are ISO 8601.
- [ ] Every value matches what the visitor sees (price, name, rating, dates).
- [ ] No duplicate or conflicting blocks for the same entity (common with plugins).
- [ ] `sameAs` URLs exist and belong to the entity.
- [ ] Do not add `AggregateRating` or `Review` unless real, visible reviews exist on that page.

Tell the user to confirm with a schema validator and with the search engine's own testing tools; you cannot run those from here.
