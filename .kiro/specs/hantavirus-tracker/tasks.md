# Implementation Plan: Live Hantavirus Global Tracker

## Overview

Implement the tracker incrementally: data layer first (Case model, parser, serializer, deduplicator), then source collectors, then GitHub Actions automation, then the frontend map and UI. Each phase is independently testable.

## Tasks

- [x] 1. Set up project structure and core data model
  - Create `scraper/` directory with `__init__.py`
  - Create `data/` directory with an empty `cases.geojson` placeholder
  - Define the `Case` dataclass in `scraper/models.py` with all fields from the design
  - Add `scraper/requirements.txt` with pinned dependencies (`requests`, `hypothesis`, `pytest`, `urllib3`)
  - _Requirements: 3.4, 8.1_

- [ ] 2. Implement data validation, parsing, and serialization
  - [x] 2.1 Implement `scraper/validator.py`
    - Validate required fields (location, date, status) per design
    - Validate coordinate ranges: longitude ∈ [-180, 180], latitude ∈ [-90, 90]
    - Return descriptive error messages for invalid input
    - _Requirements: 3.2, 8.6, 8.7_

  - [ ] 2.2 Write property test for coordinate validity (Property 2)
    - **Property 2: Coordinate validity**
    - **Validates: Requirements 3.2, 8.7**
    - Use `hypothesis` to generate arbitrary float pairs and assert validator rejects out-of-range coords

  - [x] 2.3 Implement `scraper/parser.py`
    - Parse JSON, XML, and CSV source formats into `Case` objects
    - Return descriptive errors for invalid/missing required fields
    - Generate deterministic `case_id` as hash of (source, location, date)
    - _Requirements: 8.1, 8.2, 8.5, 8.6_

  - [x] 2.4 Implement `scraper/serializer.py`
    - Serialize a list of `Case` objects to a GeoJSON FeatureCollection
    - Include `metadata.generated_at` and `metadata.source_timestamps`
    - Ensure coordinates are written as `[longitude, latitude]`
    - _Requirements: 8.3, 8.7, 3.1, 3.4_

  - [ ] 2.5 Write property test for round-trip consistency (Property 1)
    - **Property 1: Round-trip consistency**
    - **Validates: Requirements 8.4**
    - Use `hypothesis` to generate valid `Case` objects and assert `parse(serialize([c]))[0] == c`

  - [ ] 2.6 Write property test for required field completeness (Property 4)
    - **Property 4: Required field completeness**
    - **Validates: Requirements 3.4, 8.6**
    - Assert that every Case passing validation has all required fields non-empty

- [ ] 3. Implement deduplication
  - [x] 3.1 Implement `scraper/deduplicator.py`
    - Deduplicate cases by (location_name, date_reported, source) composite key
    - Preserve historical cases while adding new ones
    - _Requirements: 3.3, 3.7_

  - [ ] 3.2 Write property test for deduplication idempotency (Property 3)
    - **Property 3: Deduplication idempotency**
    - **Validates: Requirements 3.3**
    - Use `hypothesis` to generate case lists and assert `dedup(dedup(cases)) == dedup(cases)`

- [x] 4. Checkpoint — ensure all scraper unit and property tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Implement data source collectors
  - [x] 5.1 Implement shared HTTP client with retry logic in `scraper/http_client.py`
    - Retry up to 3 times with exponential backoff (1s, 2s, 4s)
    - Respect `robots.txt` via `urllib.robotparser`
    - Log each failure with source name and error detail
    - _Requirements: 6.4, 6.5, 6.7_

  - [ ] 5.2 Write property test for retry exhaustion (Property 5)
    - **Property 5: Retry exhaustion**
    - **Validates: Requirements 6.5**
    - Mock a source that always fails and assert exactly 3 attempts are made before giving up

  - [x] 5.3 Implement `scraper/sources/who.py`
    - Fetch from WHO Disease Outbreak News API
    - Parse response through `parser.py`
    - Record `source_verified_at` timestamp on success
    - _Requirements: 1.1, 3.6_

  - [x] 5.4 Implement `scraper/sources/ecdc.py`
    - Fetch from ECDC Surveillance Atlas for European regions
    - Parse response through `parser.py`
    - _Requirements: 1.2, 3.6_

  - [x] 5.5 Implement `scraper/sources/cdc.py`
    - Fetch CDC State Health Department reports for US HPS cases
    - Parse response through `parser.py`
    - _Requirements: 1.3, 3.6_

  - [x] 5.6 Implement `scraper/sources/healthmap.py` and `scraper/sources/gdelt.py`
    - Fetch real-time news signals from HealthMap.org and GDELT Project
    - Parse responses through `parser.py`
    - _Requirements: 1.4, 3.6_

  - [x] 5.7 Implement `scraper/main.py` orchestrator
    - Call all source collectors, collect results and errors
    - On source failure: log and continue with remaining sources
    - Pass all cases through validator, deduplicator, then serializer
    - Write output to `data/cases.geojson`
    - _Requirements: 1.5, 1.6, 3.5, 6.3_

  - [x] 5.8 Add Andes virus / MV Hondius prioritization in `scraper/main.py`
    - Flag cases with `virus_strain == "Andes"` from South American sources
    - Collect cases along MV Hondius itinerary (Ushuaia → Canary Islands)
    - Collect passenger manifest / contact tracing data when available
    - _Requirements: 7.1, 7.2, 7.6_

- [x] 6. Checkpoint — run scraper end-to-end with mocked sources, verify GeoJSON output
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Set up GitHub Actions workflow
  - Create `.github/workflows/scrape.yml` per the design
  - Schedule cron every 4 hours; add `workflow_dispatch` trigger
  - Commit updated `data/cases.geojson` after successful run using `[skip ci]` commit message
  - Upload scrape log as artifact on each run
  - _Requirements: 1.7, 6.1, 6.2, 6.3, 6.6_

- [-] 8. Implement frontend map
  - [x] 8.1 Create `index.html` page shell
    - Include Leaflet.js 1.9.x, Leaflet.markercluster, and Tailwind CSS via CDN
    - Add `role="application"` map container with descriptive `aria-label`
    - Add prominent Safety_Disclaimer section with links to official health authorities
    - Add legend explaining Confirmed/Probable/Suspected marker colors
    - _Requirements: 4.1, 4.2, 4.4, 4.6, 5.1, 5.2, 5.3, 5.4_

  - [x] 8.2 Implement `js/map.js`
    - Initialize Leaflet map centered on world view (zoom level 2)
    - Fetch `data/cases.geojson` and render markers with color by status
    - Enable marker clustering with 80px radius and count badges
    - Show popup on click with location_name, status, date_reported, source, virus_strain, notes
    - Support zoom levels from global to city-level
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

  - [x] 8.3 Add Andes virus and MV Hondius overlays in `js/map.js`
    - Render Andes virus May 2026 cases with a pulsing ring CSS overlay
    - Draw MV Hondius route as a polyline using hardcoded voyage coordinates
    - _Requirements: 7.3, 7.7_

  - [x] 8.4 Implement `js/filters.js`
    - Add filter controls for status (Confirmed/Probable/Suspected)
    - Add filter for virus strain (Andes / all)
    - Add date range filter
    - Wire filters to re-render map markers without page reload
    - _Requirements: 7.4, 7.5_

  - [x] 8.5 Implement `js/ui.js`
    - Display `metadata.generated_at` as "last updated" timestamp
    - Display per-source `source_timestamps` in a data sources panel
    - Show staleness warning banner when `generated_at` is older than 24 hours
    - _Requirements: 4.5, 5.5, 5.6, 5.7_

  - [ ] 8.6 Write property test for staleness detection (Property 6)
    - **Property 6: Staleness detection**
    - **Validates: Requirements 5.7**
    - Use `hypothesis` to generate timestamps and assert staleness flag is true iff age > 24h
    - Implement as a pure JS function tested with a Node.js test runner or extracted Python utility

  - [x] 8.7 Implement accessibility attributes across all interactive elements
    - Add ARIA labels to all buttons, filter controls, and map popups
    - Ensure keyboard navigation works for all controls
    - Verify marker colors meet WCAG 2.1 AA contrast ratios
    - _Requirements: 4.7_

- [x] 9. Final checkpoint — ensure all tests pass and GeoJSON loads correctly in the browser
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Property tests use the `hypothesis` library; run with `pytest scraper/tests/`
- All source collectors share the retry-aware HTTP client from `scraper/http_client.py`
- The frontend is fully static — no build step required for GitHub Pages deployment
