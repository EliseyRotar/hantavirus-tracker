# 🦠 Hantavirus Tracker — Live Global Surveillance Map

> **Live interactive map tracking the 2026 Andes hantavirus (ANDV) outbreak linked to the MV Hondius cruise ship.**

[![Deploy to GitHub Pages](https://github.com/EliseyRotar/hantavirus-tracker/actions/workflows/pages.yml/badge.svg)](https://github.com/EliseyRotar/hantavirus-tracker/actions/workflows/pages.yml)
[![Scrape Data](https://github.com/EliseyRotar/hantavirus-tracker/actions/workflows/scrape.yml/badge.svg)](https://github.com/EliseyRotar/hantavirus-tracker/actions/workflows/scrape.yml)

## 🌐 Live Site

**[https://eliseyrotar.github.io/hantavirus-tracker/](https://eliseyrotar.github.io/hantavirus-tracker/)**

---

## What is this?

A real-time surveillance dashboard tracking every known case of the 2025–2026 Andes hantavirus (ANDV) outbreak that originated on the MV Hondius cruise ship. The ship departed Ushuaia, Argentina on April 1, 2026 and arrived in Tenerife, Canary Islands on May 10, 2026 after a deadly outbreak on board.

**As of May 10, 2026:** 35 cases tracked across 19 locations — 4 confirmed, 6 suspected, 3 deceased, 22 monitoring.

---

## Features

- **Live map** — CartoDB dark tiles with Leaflet.js, updated every 4 hours
- **Real-time data** — fetched directly from the [ANDV Hantavirus 2026 ArcGIS dashboard](https://www.arcgis.com/apps/dashboards/5c68442d2afc42d7ba2696e4cd393729) (K. Panozzo, University of Toledo)
- **Case detail panel** — click any marker for full case info: age, sex, onset date, exposure group, source link
- **Status breakdown** — Confirmed (red), Suspected (orange), Deceased (purple), Monitoring (sky blue)
- **MV Hondius route** — dashed cyan polyline showing the ship's voyage from Ushuaia to Tenerife
- **Filters** — filter by status and date range
- **Mobile-first** — responsive layout with bottom sheet on mobile, sidebar on desktop
- **Fully static** — hosted on GitHub Pages, no server required

---

## Data Sources

| Source                                                                                                             | Coverage                         |
| ------------------------------------------------------------------------------------------------------------------ | -------------------------------- |
| [ANDV Hantavirus 2026 Dashboard (ArcGIS)](https://www.arcgis.com/apps/dashboards/5c68442d2afc42d7ba2696e4cd393729) | **Primary** — all 35 cases, live |
| [WHO Disease Outbreak News](https://www.who.int/emergencies/disease-outbreak-news)                                 | Global confirmed outbreaks       |
| [ECDC Rapid Risk Assessment](https://www.ecdc.europa.eu/en/hantavirus-infection)                                   | European regional data           |
| [CDC HAN-00528](https://www.cdc.gov/han/php/notices/han00528.html)                                                 | US response and monitoring       |
| [HealthMap.org](https://www.healthmap.org/)                                                                        | Real-time news signals           |
| [GDELT Project](https://www.gdeltproject.org/)                                                                     | Global media signals             |

Data credit: **K. Panozzo, University of Toledo** — [ANDV Hantavirus 2026 ArcGIS Dashboard](https://www.arcgis.com/apps/dashboards/5c68442d2afc42d7ba2696e4cd393729)

---

## How it works

```
GitHub Actions (every 4 hours)
  └── scraper/main.py
        ├── Fetches ArcGIS Feature Service (primary)
        ├── Fetches WHO, ECDC, CDC, HealthMap, GDELT (supplementary)
        ├── Deduplicates and validates
        └── Writes data/cases.geojson → commits to repo

GitHub Pages (static hosting)
  └── index.html
        ├── Fetches ArcGIS API directly (live, no scraper needed)
        ├── Falls back to data/cases.geojson if API unavailable
        └── Renders with Leaflet.js
```

---

## Running the scraper locally

```bash
pip install -r scraper/requirements.txt
python scraper/main.py
```

Output: `data/cases.geojson` and `scraper/scrape.log`

---

## Tech stack

- **Frontend:** HTML5, CSS3, [Leaflet.js](https://leafletjs.com/) 1.9.4, [Leaflet.markercluster](https://github.com/Leaflet/Leaflet.markercluster)
- **Map tiles:** [CartoDB Dark Matter](https://carto.com/basemaps/)
- **Data:** [ArcGIS Feature Service REST API](https://services1.arcgis.com/wb4Og4gH5mvzQAIV/arcgis/rest/services/Tracking_Hantavirus_2026/FeatureServer/1)
- **Backend:** Python 3.11, requests, BeautifulSoup4
- **CI/CD:** GitHub Actions (scrape every 4h + deploy to Pages on push)
- **Hosting:** GitHub Pages (free, static)

---

## ⚠️ Medical Disclaimer

This tracker is for **informational and research purposes only**. Data may be incomplete, delayed, or inaccurate. Do not use this information to make medical decisions. Always consult a qualified healthcare professional for medical advice.

For authoritative guidance, refer to:

- [WHO](https://www.who.int/emergencies/disease-outbreak-news)
- [CDC](https://www.cdc.gov/hantavirus/)
- [ECDC](https://www.ecdc.europa.eu/en/hantavirus-infection)

---

## Background: The MV Hondius Outbreak

The MV Hondius is a Dutch-flagged expedition cruise ship owned by Oceanwide Expeditions. On April 1, 2026, it departed Ushuaia, Argentina with ~147 passengers and crew from 23 nationalities. A 70-year-old Dutch passenger began showing symptoms on April 6 and died on April 11 — the first known death. By May 2, WHO was notified of a cluster of severe respiratory illness. The Andes virus (ANDV) — the only known hantavirus capable of human-to-human transmission — was confirmed on May 4. The ship arrived in Tenerife on May 10 for a 22-country evacuation.

**Key facts:**

- 3 deaths (Dutch man 70, Dutch woman 69, German woman)
- 6 confirmed cases, 2 suspected (as of May 10, WHO)
- 147 people on board from 23 countries
- CDC classified as Level 3 emergency response
- 17 Americans repatriated to Nebraska quarantine facility
- British Army paratroopers parachuted onto Tristan da Cunha to assist a suspected case

---

_Made with ❤️ for public health awareness. Not affiliated with WHO, CDC, ECDC, or the University of Toledo._
