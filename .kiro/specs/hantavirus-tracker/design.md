# Design Document: Live Hantavirus Global Tracker

## Overview

A static web application hosted on GitHub Pages that displays hantavirus case data on an interactive map. A Python scraper runs every 4 hours via GitHub Actions, collects data from multiple public health sources, and writes a GeoJSON file to the repository. The frontend reads that file and renders it with Leaflet.js.

## Architecture

```
GitHub Actions (cron: every 4h)
    └── scraper/main.py
            ├── Fetches: WHO, ECDC, CDC, HealthMap, GDELT
            ├── Parses & deduplicates
            └── Writes: data/cases.geojson

GitHub Pages (static hosting)
    └── index.html
            ├── Leaflet.js (map)
            ├── Tailwind CSS (styling)
            └── Fetches: data/cases.geojson
```

## Components

### 1. Data Scraper (`scraper/`)

**Language:** Python 3.11+

**Files:**

- `scraper/main.py` — entry point, orchestrates all sources
- `scraper/sources/who.py` — WHO Disease Outbreak News collector
- `scraper/sources/ecdc.py` — ECDC Surveillance Atlas collector
- `scraper/sources/cdc.py` — CDC State Health Department collector
- `scraper/sources/healthmap.py` — HealthMap.org collector
- `scraper/sources/gdelt.py` — GDELT Project collector
- `scraper/parser.py` — parses raw source data into Case objects
- `scraper/serializer.py` — serializes Case objects to GeoJSON
- `scraper/deduplicator.py` — deduplicates cases by (location, date, source)
- `scraper/validator.py` — validates geographic and temporal fields
- `requirements.txt` — pinned Python dependencies

**Case object (dataclass):**

```python
@dataclass
class Case:
    case_id: str          # deterministic hash of (source, location, date)
    status: str           # "Confirmed" | "Probable" | "Suspected"
    date_reported: str    # ISO 8601 date string
    source: str           # source identifier
    latitude: float
    longitude: float
    location_name: str
    virus_strain: str     # e.g. "Andes", "Sin Nombre", "Unknown"
    source_verified_at: str  # ISO 8601 timestamp of last successful fetch
    notes: str            # optional free-text
```

**GeoJSON output schema:**

```json
{
  "type": "FeatureCollection",
  "metadata": {
    "generated_at": "<ISO timestamp>",
    "source_timestamps": { "<source_id>": "<ISO timestamp>" }
  },
  "features": [
    {
      "type": "Feature",
      "geometry": { "type": "Point", "coordinates": [longitude, latitude] },
      "properties": {
        "case_id": "...",
        "status": "Confirmed",
        "date_reported": "2026-05-01",
        "source": "WHO",
        "latitude": -54.8,
        "longitude": -68.3,
        "location_name": "Ushuaia, Argentina",
        "virus_strain": "Andes",
        "source_verified_at": "2026-05-10T12:00:00Z",
        "notes": ""
      }
    }
  ]
}
```

**Retry / error handling:**

- Each source collector wraps requests in a retry loop: up to 3 attempts with exponential backoff (1s, 2s, 4s)
- On source failure, log the error and continue with remaining sources
- Respect `robots.txt` via `urllib.robotparser`

### 2. Frontend (`index.html`, `js/`, `css/`)

**Files:**

- `index.html` — single-page app shell
- `js/map.js` — Leaflet map initialization, marker rendering, clustering
- `js/filters.js` — filter controls (status, virus strain, date range)
- `js/ui.js` — disclaimer modal, legend, staleness warning, timestamps

**Libraries (CDN):**

- Leaflet.js 1.9.x
- Leaflet.markercluster plugin
- Tailwind CSS 3.x (CDN play build for static hosting)

**Map behavior:**

- Initial view: world bounds, zoom level 2
- Marker colors by status: Confirmed = red, Probable = orange, Suspected = yellow
- Andes virus May 2026 cases: pulsing ring overlay for visual distinction
- MV Hondius route: polyline overlay (coordinates hardcoded from voyage itinerary)
- Cluster radius: 80px; shows count badge
- Popup on click: location_name, status, date_reported, source, virus_strain, notes

**Staleness warning:** if `metadata.generated_at` is older than 24 hours, show a banner.

**Accessibility:**

- All interactive elements have ARIA labels
- Keyboard-navigable controls
- Map has a `role="application"` region with descriptive `aria-label`
- Color choices meet WCAG 2.1 AA contrast ratios

### 3. GitHub Actions (`.github/workflows/scrape.yml`)

```yaml
on:
  schedule:
    - cron: "0 */4 * * *"
  workflow_dispatch:

jobs:
  scrape:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r scraper/requirements.txt
      - run: python scraper/main.py
      - uses: actions/upload-artifact@v4
        with: { name: scrape-log, path: scraper/scrape.log }
      - run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/cases.geojson
          git diff --cached --quiet || git commit -m "chore: update cases [skip ci]"
          git push
```

### 4. Data Storage (`data/`)

- `data/cases.geojson` — the single source of truth, committed to the repo
- Historical data is preserved; new cases are appended; duplicates removed

---

## Correctness Properties

### Property 1: Round-trip consistency

For all valid Case objects `c`, `parse(serialize(c))` produces an equivalent Case object.

- Validates: Requirements 8.4

### Property 2: Coordinate validity

For all cases in the GeoJSON output, longitude ∈ [-180, 180] and latitude ∈ [-90, 90].

- Validates: Requirements 3.2, 8.7

### Property 3: Deduplication idempotency

Applying the deduplicator twice to any case list produces the same result as applying it once.

- Validates: Requirements 3.3

### Property 4: Required field completeness

For all cases that pass validation, the fields case_id, status, date_reported, source, latitude, longitude, and location_name are non-empty.

- Validates: Requirements 3.4, 8.6

### Property 5: Retry exhaustion

For any source that always fails, the scraper attempts exactly 3 requests before logging failure and moving on.

- Validates: Requirements 6.5

### Property 6: Staleness detection

For any GeoJSON metadata where `generated_at` is more than 24 hours before the current time, the frontend staleness flag evaluates to true.

- Validates: Requirements 5.7
