# Hantavirus Tracker — MV Hondius 2026 Outbreak

Live surveillance map tracking the 2025–2026 Andes hantavirus (ANDV) outbreak linked to the MV Hondius cruise ship.

[![Deploy to GitHub Pages](https://github.com/EliseyRotar/hantavirus-tracker/actions/workflows/pages.yml/badge.svg)](https://github.com/EliseyRotar/hantavirus-tracker/actions/workflows/pages.yml)
[![Scrape Hantavirus Data](https://github.com/EliseyRotar/hantavirus-tracker/actions/workflows/scrape.yml/badge.svg)](https://github.com/EliseyRotar/hantavirus-tracker/actions/workflows/scrape.yml)

**Live site:** https://eliseyrotar.github.io/hantavirus-tracker/

---

## What this is

An interactive map showing every tracked case from the MV Hondius Andes hantavirus cluster — confirmed cases, suspected cases, deaths, and people under monitoring across 28+ locations worldwide. The frontend fetches live data directly from the public ArcGIS Feature Service on every page load. A Python scraper also runs every 4 hours via GitHub Actions to keep a local snapshot current.

**As of May 2026:** 107+ cases tracked across 28 locations — 8 confirmed, 7 suspected, 3 deceased, 89 monitoring.

---

## Background

On 1 April 2026, the Dutch-flagged expedition cruise ship MV Hondius departed Ushuaia, Argentina with ~147 passengers and crew from 23 nationalities. A 70-year-old Dutch passenger (the index case) began showing symptoms on 6 April and died on 11 April. By 2 May, WHO was notified of a cluster of severe respiratory illness. The Andes virus — the only known hantavirus capable of human-to-human transmission — was confirmed on 4 May. The ship arrived in Tenerife on 10 May for a 22-country evacuation.

Key facts:

- 3 deaths: Dutch male (70, index case), Dutch female (69, wife of index case), German female
- 8 confirmed cases as of 11 May 2026
- 147 people on board from 23 countries
- CDC classified as Level 3 emergency response
- 17 Americans repatriated to Nebraska quarantine facility
- British Army paratroopers parachuted onto Tristan da Cunha to assist a suspected case

---

## How it works

```
Frontend (GitHub Pages)
  index.html
    → fetches ArcGIS Feature Service directly (live, on every page load)
    → falls back to data/cases.geojson if API unavailable

GitHub Actions (every 4 hours)
  scraper/main.py
    → ANDV Dashboard (ArcGIS) — primary, 107+ cases
    → WHO seed data — 20 cases
    → ECDC seed data — 7 cases
    → CDC seed data — 6 cases
    → HealthMap signals — 5 cases
    → GDELT signals — 5 cases
    → deduplicates, validates, merges
    → writes data/cases.geojson → commits to repo
    → pages workflow redeploys
```

---

## Data sources

| Source                                                                                                                                                        | Type     | Cases |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- | ----- |
| [ANDV Hantavirus 2026 Dashboard (ArcGIS)](https://www.arcgis.com/apps/dashboards/5c68442d2afc42d7ba2696e4cd393729)                                            | Live API | 107+  |
| [WHO Disease Outbreak News DON599](https://www.who.int/emergencies/disease-outbreak-news/item/2026-DON599)                                                    | Seed     | 20    |
| [ECDC Rapid Risk Assessment](https://www.ecdc.europa.eu/en/infectious-disease-topics/hantavirus-infection/surveillance-and-updates/andes-hantavirus-outbreak) | Seed     | 7     |
| [CDC HAN-00528](https://www.cdc.gov/han/php/notices/han00528.html)                                                                                            | Seed     | 6     |
| HealthMap.org                                                                                                                                                 | Signals  | 5     |
| GDELT Project                                                                                                                                                 | Signals  | 5     |

Primary data credit: **K. Panozzo, University of Toledo** — [ANDV Hantavirus 2026 ArcGIS Dashboard](https://www.arcgis.com/apps/dashboards/5c68442d2afc42d7ba2696e4cd393729)

---

## Running locally

```bash
# Install dependencies
pip install -r scraper/requirements.txt

# Run the scraper (writes data/cases.geojson)
python3 scraper/main.py

# Run tests
pytest scraper/tests/ -v

# Serve the site locally
python3 -m http.server 8000
# then open http://localhost:8000
```

---

## Project structure

```
.
├── index.html              # Single-page app (Leaflet.js map)
├── js/
│   ├── map.js              # Map init, ArcGIS fetch, marker rendering
│   ├── filters.js          # Filter controls (status, date range)
│   └── ui.js               # Timestamps, staleness banner
├── data/
│   └── cases.geojson       # Snapshot updated every 4h by scraper
├── scraper/
│   ├── main.py             # Orchestrator
│   ├── models.py           # Case dataclass
│   ├── parser.py           # JSON/XML/CSV → Case
│   ├── serializer.py       # Case → GeoJSON
│   ├── deduplicator.py     # Deduplication logic
│   ├── validator.py        # Field + coordinate validation
│   ├── http_client.py      # Retry-aware HTTP client
│   ├── requirements.txt    # Python dependencies
│   └── sources/
│       ├── arcgis.py       # ArcGIS Feature Service (primary)
│       ├── who.py          # WHO DON seed data
│       ├── ecdc.py         # ECDC seed data
│       ├── cdc.py          # CDC seed data
│       ├── healthmap.py    # HealthMap signals
│       └── gdelt.py        # GDELT signals
├── .github/workflows/
│   ├── scrape.yml          # Runs scraper every 4h
│   └── pages.yml           # Deploys to GitHub Pages on push
├── sitemap.xml
└── robots.txt
```

---

## Tech stack

- **Frontend:** HTML5, CSS3, [Leaflet.js](https://leafletjs.com/) 1.9.4, [Leaflet.markercluster](https://github.com/Leaflet/Leaflet.markercluster)
- **Map tiles:** [CartoDB Dark Matter](https://carto.com/basemaps/)
- **Live data:** [ArcGIS Feature Service REST API](https://services1.arcgis.com/wb4Og4gH5mvzQAIV/arcgis/rest/services/Tracking_Hantavirus_2026/FeatureServer/1)
- **Scraper:** Python 3.11, requests, BeautifulSoup4
- **CI/CD:** GitHub Actions (scrape every 4h + deploy on push)
- **Hosting:** GitHub Pages (free, static)

---

## Medical disclaimer

This tracker is for informational and research purposes only. Data may be incomplete, delayed, or inaccurate. Do not use this information to make medical decisions. Always consult a qualified healthcare professional.

For authoritative guidance: [WHO](https://www.who.int/) · [CDC](https://www.cdc.gov/) · [ECDC](https://www.ecdc.europa.eu/)
