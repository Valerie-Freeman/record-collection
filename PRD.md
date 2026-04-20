# PRD: Record Collection Browser

**Status:** Draft v3
**Author:** Val
**Last updated:** April 20, 2026

---

## 1. Overview

A static, mobile-first web page that displays our home record collection as a browsable list of album cards — inspired by the Discogs mobile UI. A printed QR code on the record cabinet links anyone's phone directly to the page. The collection is stored as a JSON file in the repo; adding a record is a single commit, and a GitHub Actions pipeline validates the data and deploys to GitHub Pages automatically.

A signature "Surprise me" button picks a random record to listen to, respecting any active filters.

## 2. Goals

- Let anyone in our home scan a QR code and browse our records on their phone in under 3 seconds.
- Let the collection be sorted, filtered, and searched with mobile-friendly controls.
- Let a visitor tap any record to see full details.
- Let a visitor (or me) get a random pick to take decision fatigue out of "what should we play?"
- Let me (the owner) add or update records by editing one JSON file.
- Catch data-entry mistakes before they reach production via CI.
- Keep the whole thing free to host and run.

## 3. Non-Goals

- Visitor-submitted ratings, comments, or edits.
- User accounts, auth, or per-person views.
- An in-browser editor for the collection.
- Streaming links, external enrichment from Discogs/Spotify APIs.
- Analytics or tracking.

## 4. Users

**Primary — Owner (me).** Edits the JSON file, commits to main, reviews CI output. Comfortable with Git.

**Secondary — Household visitors.** Scan a QR, browse cards on their phone. No accounts, no onboarding. Never touch the repo.

## 5. User Stories

1. As a visitor, I scan the QR on the cabinet and see album cards within 3 seconds.
2. As a visitor, I tap "Sort: Rating" and the cards reorder highest-rated first.
3. As a visitor, I tap "Filter: Genre" and pick "Jazz" to narrow the view.
4. As a visitor, I type "Zeppelin" in the search box and see matching albums.
5. As a visitor, I tap a card and see the full detail view with notes and year.
6. As a visitor, I tap "Surprise me" and immediately see one record chosen at random to play.
7. As a visitor, I filter to "Jazz, 4★ and up," then tap "Surprise me" to get a great jazz pick.
8. As the owner, I add a new album by appending an object to `records.json` and pushing.
9. As the owner, if I typo a rating as `6`, malform a JSON block, or leave the artist blank, CI fails before deploy.

## 6. Functional Requirements

### 6.1 Data model

Each record is a JSON object:

```json
{
  "artwork": "images/the-band.jpg",
  "artist": "The Band",
  "title": "The Band",
  "year": 1969,
  "rating": 5,
  "genres": ["Rock", "Americana"],
  "notes": "Brown album. Winchester pressing."
}
```

| Field   | Type     | Required | Notes                                         |
|---------|----------|----------|-----------------------------------------------|
| artwork | string   | yes      | Repo-relative path, e.g. `images/foo.jpg`     |
| artist  | string   | yes      | Free text                                     |
| title   | string   | yes      | Album title                                   |
| year    | integer  | yes      | 4-digit release or pressing year              |
| rating  | integer  | yes      | 1–5 inclusive; rendered as ★                  |
| genres  | string[] | yes      | At least one entry                            |
| notes   | string   | no       | Free text; may contain any characters         |

`records.json` is a top-level array of these objects.

### 6.2 List view (default)

Each record renders as a card showing:

- Album artwork (left, square thumbnail).
- Title (primary text).
- Artist (secondary text).
- Star rating (small, under artist).

Cards stack vertically. Tapping a card opens the detail view.

### 6.3 Sort

Single active sort at a time, toggleable ascending/descending:

- Artist (A→Z default)
- Title
- Year
- Rating

Exposed as a single "Sort" control that opens a small menu or bottom sheet.

### 6.4 Filter

Multi-select filters by:

- **Artist** — list of all artists in the collection.
- **Decade** — buckets like `1960s`, `1970s`, `1980s`; only decades with at least one record appear.
- **Genre** — list of all genres seen across records. A record matches if *any* of its genres match the selected filter(s).
- **Rating** — 1–5; multi-select individual values.

Filters combine with AND across categories, OR within a category. Active filters shown as removable chips at the top of the list. A "Clear all" control resets.

### 6.5 Search

Single text input. Case-insensitive. Matches against `artist` OR `title`. Updates results as you type (debounced). Works in combination with active sort and filters.

### 6.6 "Surprise me" (random pick)

A prominent button near the top of the list. When tapped:

- Picks one record uniformly at random from the *currently visible set* (i.e. respects active search, filters).
- Opens that record's detail view directly.
- If the visible set is empty, the button is disabled with a hint: "Adjust filters to get a pick."

Closing the detail view returns the user to the list with filters and scroll position intact.

### 6.7 Detail view

Tapping a card (or the "Surprise me" button) opens a detail view — modal sheet on mobile, feels native. Shows all fields:

- Full-width or large artwork at top.
- Title, artist, year.
- Star rating.
- Genre chips.
- Notes.
- Close button / swipe-down to dismiss.

Back/close returns to the list with previous scroll position and filter state preserved.

### 6.8 Data source

- Single file `records.json` at repo root.
- UTF-8, top-level array of record objects.
- Fetched and parsed client-side on page load.

### 6.9 QR code

- Points to the stable GitHub Pages URL (never changes).
- Generated once; framed physical print.
- High-contrast, minimum 300×300px for print clarity.

## 7. Non-Functional Requirements

- **Mobile-first.** Designed for a 375px viewport first, scaled up to desktop.
- **Performance.** Initial load under 2s on 4G; artwork lazy-loaded as cards scroll into view.
- **Accessibility.** WCAG AA contrast, semantic markup, keyboard-navigable controls, screen-reader labels for star ratings and artwork.
- **Privacy.** No cookies, no analytics, no third-party trackers.
- **Compatibility.** Last two major versions of Safari iOS, Chrome Android, Chrome/Firefox/Safari desktop.

## 8. Technical Architecture

### 8.1 Stack

- **Frontend.** Single `index.html` + vanilla JS + CSS. No framework.
- **Data loading.** Native `fetch('records.json').then(r => r.json())`. No parser library needed.
- **Rendering.** Hand-rolled card components in vanilla JS. Sort/filter/search/random logic implemented directly.
- **Styling.** Hand-written CSS with custom properties; system font stack; CSS Grid / Flexbox for card layout.
- **Image loading.** Native `loading="lazy"` on `<img>` tags; fallback placeholder for missing artwork.
- **Hosting.** GitHub Pages from the `main` branch via the official Pages Actions workflow.

### 8.2 Repo structure

```
record-collection/
├── .github/
│   └── workflows/
│       └── deploy.yml
├── images/
│   ├── the-band.jpg
│   └── led-zeppelin-ii.jpg
├── scripts/
│   └── validate_records.py
├── records.json
├── index.html
├── styles.css
├── app.js
└── README.md
```

### 8.3 Why vanilla + JSON

No build step, no parser dependency, no framework overhead. The file you edit is the file the browser loads. At a few hundred to low thousands of records, there's no performance reason to add complexity.

## 9. CI/CD Pipeline

GitHub Actions workflow triggered on push and PR to `main`.

### 9.1 Jobs

**validate** — runs on every push and PR:

- Check out repo.
- Run `scripts/validate_records.py` against `records.json`:
  - File is valid JSON; top-level value is an array.
  - Every record has all required fields.
  - `rating` is an integer 1–5.
  - `year` is an integer between 1900 and current year + 1.
  - `genres` is a non-empty array of strings.
  - `artwork` is a repo-relative path pointing to an existing file under `images/`.
  - No duplicate (artist, title, year) triples.
  - UTF-8 decodable.
- Fail the workflow with a clear, record-specific message if any check fails.

**deploy** — runs only on push to `main` after `validate` succeeds:

- Upload the repo as a Pages artifact.
- Deploy to GitHub Pages using `actions/deploy-pages`.

### 9.2 Branch protection (recommended)

- Require `validate` to pass before merging PRs to `main`.

## 10. UI/UX Requirements

### 10.1 Layout (mobile, 375px)

```
┌─────────────────────────┐
│  Collection        143  │  ← H1 + count
├─────────────────────────┤
│ 🔍 Search artist/title  │
├─────────────────────────┤
│  🎲  Surprise me        │  ← prominent button
├─────────────────────────┤
│ [Sort ▾] [Filter ▾]     │
│ [Genre: Jazz ×] [4★ ×]  │  ← active filter chips
├─────────────────────────┤
│ ┌───┐ Revolver          │
│ │🖼️│ The Beatles        │
│ │   │ ★★★★★             │
│ └───┘                   │
│ ┌───┐ Rubber Soul       │
│ │🖼️│ The Beatles        │
│ │   │ ★★★★☆             │
│ └───┘                   │
└─────────────────────────┘
```

- "Surprise me" is visually distinct (filled accent color) — it's the fun button.
- Sort opens a menu with the four options plus asc/desc toggle.
- Filter opens a sheet listing categories (Artist / Decade / Genre / Rating) with multi-select inside each.
- Tap targets ≥44×44px.
- Active filters and search state preserved when opening/closing detail view.

### 10.2 Detail view (mobile sheet)

```
┌─────────────────────────┐
│  ✕                      │
│                         │
│   ┌─────────────────┐   │
│   │                 │   │
│   │    Artwork      │   │
│   │                 │   │
│   └─────────────────┘   │
│                         │
│  Revolver               │
│  The Beatles • 1966     │
│  ★★★★★                  │
│                         │
│  [Rock] [Psychedelic]   │
│                         │
│  Notes:                 │
│  Original UK pressing…  │
└─────────────────────────┘
```

### 10.3 Visual design

- Single warm, slightly analog palette to match the record-cabinet context.
- Star rating uses `★` / `☆` glyphs, not images.
- Genre rendered as small rounded chips.
- One accent color for active states, focus rings, and the "Surprise me" button.

### 10.4 Empty and error states

- Empty search/filter result: "No records match." with a "Clear filters" button.
- "Surprise me" with empty set: button disabled, small hint text.
- Missing artwork: neutral placeholder tile with the album title.
- JSON fetch failure: "Couldn't load the collection. Try refreshing."

## 11. Out of Scope for v1

- Format (LP / 45 / 10"), label, pressing details beyond year.
- Album cover art auto-fetch from Discogs.
- Favorites, wishlist, "currently spinning."
- Service worker / full offline support.
- Export / print view.

## 12. Future Enhancements (v2+)

- Format, label, pressing year fields.
- Cover art auto-fetch via Discogs API.
- Stats page: total count, average rating, breakdown by decade, top genres.
- Separate wishlist view.
- Smarter random: weight toward unplayed/rarely-picked records.

## 13. Success Criteria

- A visitor can scan the QR, sort or filter, and tap into a detail view in under 15 seconds with no instructions.
- "Surprise me" gets used regularly — it's the feature that makes this more than a catalog.
- Adding a record is one commit, under a minute of my time (including artwork).
- CI catches at least one class of data error I would have otherwise shipped.
- Zero hosting cost, zero maintenance beyond data entry.

## 14. Milestones

**M1 — Walking skeleton.** `index.html` loads `records.json`, renders cards with artwork/title/artist/rating. Five sample records. Deployed to Pages manually.

**M2 — Sort, filter, search.** All three controls functional with active-state UI, including decade buckets and rating filter.

**M3 — Detail view + Surprise me.** Tap-to-open modal sheet with all fields. Surprise me button wired to random pick respecting active filters.

**M4 — CI/CD.** `validate_records.py` + Actions workflow running on PRs. Auto-deploy on merge to `main`.

**M5 — Polish.** Empty states, lazy-loaded images, accessibility pass.

**M6 — Launch.** Final data migration, QR generated and framed, mounted on cabinet.