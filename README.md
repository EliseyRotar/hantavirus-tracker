# Live Hantavirus Global Tracker

An automated surveillance dashboard that aggregates hantavirus case data from multiple public health sources and displays it on an interactive world map. Data is refreshed every 4 hours via GitHub Actions and served as a static site on GitHub Pages.

## Live Site

**[https://eliseyrotar.github.io/hantavirus-tracker/](https://eliseyrotar.github.io/hantavirus-tracker/)**

## Features

- Interactive Leaflet.js map with case markers color-coded by status (Confirmed / Probable / Suspected)
- Marker clustering for readability at global zoom levels
- Special highlighting for May 2026 Andes virus cases and the MV Hondius voyage route
- Filter controls by status, virus strain, and date range
- Staleness warning when data is older than 24 hours
- Prominent medical disclaimer and links to official health authorities

## Running the Scraper Locally

```bash
pip install -r scraper/requirements.txt && python scraper/main.py
```

The scraper writes output to `data/cases.geojson` and logs to `scraper/scrape.log`.

## Data Sources

| Source                                                                             | Coverage                                     |
| ---------------------------------------------------------------------------------- | -------------------------------------------- |
| [WHO Disease Outbreak News](https://www.who.int/emergencies/disease-outbreak-news) | Global confirmed outbreaks                   |
| [ECDC Surveillance Atlas](https://atlas.ecdc.europa.eu/)                           | European regional data                       |
| [CDC State Health Departments](https://www.cdc.gov/hantavirus/)                    | US Hantavirus Pulmonary Syndrome (HPS) cases |
| [HealthMap.org](https://www.healthmap.org/)                                        | Real-time news signals                       |
| [GDELT Project](https://www.gdeltproject.org/)                                     | Global event and media signals               |

## Automated Updates

A GitHub Actions workflow (`.github/workflows/scrape.yml`) runs the scraper on a schedule (`0 */4 * * *` — every 4 hours) and commits the updated `data/cases.geojson` back to the repository. The workflow can also be triggered manually via `workflow_dispatch`.

Scrape logs are uploaded as a workflow artifact (`scrape-log`) on each run for troubleshooting.

## Medical Disclaimer

> **This tracker is for informational and research purposes only.** Data may be incomplete, delayed, or inaccurate. Do not use this information to make medical decisions. Always consult a qualified healthcare professional for medical advice. For authoritative guidance, refer to the [WHO](https://www.who.int/), [CDC](https://www.cdc.gov/), or your local public health authority.
