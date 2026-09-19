# svas-aasrav

A Delhi NCR rider dashboard: React/Vite + FastAPI, with **Neo4j calculating the route ranking**. Maps now use an open-source stack. No Google billing, Google API key, or map-service signup is needed for this small hackathon demo.

## Run locally

Requires Node.js 20.19+ or 22.12+ and Python 3.12. This workspace also includes an ignored portable Python runtime at `.tools/python`.

```sh
npm install
npm run dev
```

Frontend: http://localhost:5173. On Windows PowerShell, use `npm.cmd` if script execution is disabled. Use `--cache .npm-cache` if the default npm cache is inaccessible.

In a second terminal, from the project root:

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

On this machine, Python is also available with:

```powershell
.\.tools\python\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

API docs: http://localhost:8000/docs. Copy `.env.example` to `.env` **only if `.env` does not already exist**. Keep existing credentials. FastAPI reads root `.env`, with optional overrides in `backend/.env`. Vite reads root `.env`. Restart after environment changes.

For manual routing, the only secret credentials required are the exact Aura values for `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, and `NEO4J_DATABASE`. Existing Google variables are ignored. Never put database credentials in public `VITE_` variables.

## Free map stack

| Job | Service | Configuration |
| --- | --- | --- |
| Interactive browser map | MapLibre + OpenFreeMap | Optional `VITE_MAP_STYLE_URL` |
| Address to coordinates | Photon / OpenStreetMap | `PHOTON_BASE_URL` |
| Road route alternatives | OSRM / OpenStreetMap | `OSRM_BASE_URL` |
| Current regional AQI | Open-Meteo / CAMS | `OPEN_METEO_BASE_URL` |
| Route scoring and graph queries | Neo4j Aura | `NEO4J_*` |

Default public endpoints require no map key. They are community-hosted services, not an availability guarantee or unlimited production infrastructure. Photon permits reasonable use; the FOSSGIS OSRM service has a maximum of one request per second. The backend serializes each provider's requests at least 1.05 seconds apart, caches geocoding for 24 hours and routes for five minutes, and searches only on form submission. Keep **one backend process/worker** for these process-local limits. For scaled deployment, use a shared limiter or your own service instances.

The rendering, geocoding and routing software can be self-hosted for control; operating servers still has infrastructure costs. All map endpoints are configurable. The UI retains attribution, credits OSRM, and links to OpenStreetMap's map-correction page.

- [OpenFreeMap setup](https://openfreemap.org/quick_start/)
- [MapLibre installation, including Vite worker setup](https://maplibre.org/maplibre-gl-js/docs/)
- [Photon public service](https://github.com/komoot/photon)
- [OSRM public service usage policy](https://routing.openstreetmap.de/about.html)

## Live architecture and Neo4j

```text
React form -> FastAPI -> Photon geocoding -> OSRM road alternatives
                                                  |
                                    Coordinates sampled along each route
                                                  |
                                      Open-Meteo current US AQI
                                                  |
                                 Neo4j graph + Cypher scoring/ranking
                                                  |
                                MapLibre polylines + comparison cards
```

Neo4j stores a connected graph, with additional `Svas*` labels isolating app-owned data:

```text
(Trip)-[:HAS_CANDIDATE]->(Route)-[:HAS_SAMPLE]->(RouteSample)
(RouteSample)-[:IN_ZONE]->(AirZone)-[:HAS_READING]->(AQIReading)
(RouteSample)-[:USES_READING]->(AQIReading)
```

Cypher traverses the samples/readings, calculates duration-weighted AQI and exposure, applies the delivery window and mask preference, and ranks eligible candidates by:

```text
exposure_index = sum(sample AQI * estimated sample minutes)
routing_cost = route minutes + POLLUTION_WEIGHT * exposure_index / 100
```

Neo4j is required for recommendations; it is not just a logging database. The app ranks valid OSRM road alternatives. It does not import an entire road graph or need APOC/Dijkstra. Both route arrays can be identical when the fastest route wins; no alternative or reduction is fabricated.

The graph stores scoring inputs, model cells and readings for `GRAPH_RETENTION_MINUTES` (default 60). Entered addresses and full route geometry are not persisted in Neo4j. Expired app-owned nodes are cleaned on the next route write. Unique constraints initialize automatically, or run `python -m backend.init_db`.

For the sponsor demo, paste the queries from **`backend/graph-demo.cypher`** into Aura Query. The Admin preview also shows actual shared model cells from `/api/graph-summary`.

## Included UI

- Rider and Admin views, with explicitly labelled Live and Demo data.
- Free-text Delhi NCR address entry, swapping, validation and resolved address labels.
- Actual OSRM alternatives, estimated time/distance, AQI comparison and Neo4j scoring.
- Solid green AQI-weighted route, dashed grey alternatives, selectable route cards, A/B markers and clickable AQI samples.
- Map zoom/fullscreen controls, route fit, AQI layer toggle and source attribution.
- Delivery window and mask preference, with explicit warnings if no route qualifies.
- Loading, service-error, retry, zero-reduction and changed-preference states. Live data never silently falls back to mocks.
- Responsive layouts; the original demo retains winter simulation, ride start/complete, session history, CSV export, settings and fleet previews.

**OSRM's default profile is driving/car. It has no live traffic and is not a motorcycle-specific routing service.** Its times are estimates. The matched locality or landmark is displayed so riders can verify the resolved destination. Follow road signs and restrictions.

Admin fleet counts, profile, notifications and historic rides remain simulations. The standalone Air quality and My impact / Impact report sections have been removed. Live route calculation does not start background tracking or turn-by-turn navigation. Admin/Rider switching is not authentication.

## API

- `GET /api/health`: API availability, map provider names and configuration flags. This is not a deep provider-health check.
- `GET /api/city-aqi`: actual Delhi baseline AQI, standard, timestamp and model resolution.
- `POST /api/calculate-route`: geocode, request alternatives, sample AQI, score in Neo4j.
- `GET /api/graph-summary`: recent model cells and route counts from Neo4j.

```json
{
  "pickup": "Saket, New Delhi",
  "drop": "Rohini, New Delhi",
  "delivery_window_minutes": 90,
  "has_mask": true,
  "travel_mode": "DRIVE"
}
```

Only pickup/drop are required. Optional `max_aqi` is an exclusive ceiling for every sampled AQI (1 to 501, or null for no extra ceiling); `aqi_standard` supports only `US`. Neo4j enforces the ceiling alongside the deadline and mask preference. The response includes `standard_route` and `green_route` arrays of `{lat,lng}`, all candidate `routes`, selected IDs, `recommended_route_id`, `lower_aqi_percent`, `exposure_reduction_percent`, `graph`, provider names and `warnings`. A null recommendation means constraints were unmet. Negative reductions mean increases. A null percentage means the baseline was zero and a percentage is undefined.

Service failures produce actionable errors, never a fake clean route. Open-Meteo requests use the air-quality host, not the weather host, and cache coordinate results for ten minutes.

## Deployment

**Vercel:** import the repository, select Vite, build with `npm run build`, output `dist`. Set `VITE_API_BASE_URL=https://YOUR-API.onrender.com` and redeploy. No browser API key is needed. `VITE_MAP_STYLE_URL` is optional.

**Render:** use the included `render.yaml`, or create a Python web service with repository root:

```text
Build: pip install -r backend/requirements.txt
Start: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
Health: /api/health
```

Set `GEMINI_API_KEY` to enable AI features (optional for manual routing), the four `NEO4J_*` variables and `CORS_ORIGINS=https://YOUR-FRONTEND.vercel.app`. Use the exact database name from Aura. Multiple exact origins can be comma separated. Public map endpoints have defaults; no Google variables are needed. Keep one worker with the shared public map services. CORS is not authentication; this remains a hackathon prototype.

## Data limits

**Live data uses US AQI; demo data uses Indian AQI.** Open-Meteo's endpoint is `https://air-quality-api.open-meteo.com/v1/air-quality`. Delhi's CAMS data has roughly 45 km resolution, so it cannot establish street-level pollution spikes. Different route samples may share a model cell. Readings older than six hours are rejected.

Equal-distance intervals receive estimated time in proportion to distance. AQI times minutes is a comparison proxy, not medical dose. The unmasked preference excludes candidate routes with sampled US AQI above 200. A mask does not make pollution safe. The fastest route can also win the composite ranking and yield 0% improvement.

## Verification

```sh
npm test
pip install -r backend/requirements-dev.txt
python -m pytest backend/tests -q
npm run build
# Start Vite and FastAPI before browser checks:
node tests/live-ui.mjs
node tests/smoke.mjs
node tests/gemini-ui.mjs
node tests/layout.mjs
# Real providers and database, no mock coordinates:
python -m backend.smoke_live
node tests/open-source-live.mjs
```

`tests/live-ui.mjs` injects fixtures to check form behavior. `tests/open-source-live.mjs` checks actual geocoding, routing, AQI, Neo4j, rendered map markers, popup controls, mobile layout and absence of Google Maps requests. Browser tests use Chrome; set `CHROME_PATH` if needed. `python -m backend.check_connections` provides secret-safe connection diagnostics.

Main files: `src/LivePlanner.jsx`, `src/LiveRouteMap.jsx`, `src/api.js`, `backend/main.py`, `backend/openstreetmap.py`, `backend/providers.py`, `backend/database.py`, `backend/service.py`.


## Gemini trip planner and exposure analyst

Add these server-only variables in root `.env` (or Render environment). The slots already exist in this workspace; preserve all other credentials:

```env
GEMINI_API_KEY=your_google_ai_studio_key
GEMINI_MODEL=gemini-3.5-flash-lite
```

Get a Gemini key from https://aistudio.google.com/apikey. This is separate from a Maps key. Availability and quotas depend on your Gemini project; quota failures are shown honestly and manual routing remains available. Restart FastAPI after setting the key. Never create a `VITE_GEMINI_API_KEY` variable.

**Trip planning:** type ?Saket to Rohini within an hour, AQI below 300, I have a mask? and select **Fill trip details**. `POST /api/ai/parse-trip` asks Gemini for schema-constrained JSON, validates it with Pydantic, then returns a payload accepted by `/api/calculate-route`:

```json
{
  "pickup": "Saket",
  "drop": "Rohini",
  "delivery_window_minutes": 60,
  "has_mask": true,
  "travel_mode": "DRIVE",
  "max_aqi": 300,
  "aqi_standard": "US"
}
```

The rider can edit the filled form before selecting **Show my ride**. Unspecified preferences retain current form values. Missing locations, contradictory requests, Indian AQI and unsupported constraints produce a clarification instead of a silently weakened request. The submitted text is sent to Gemini. The backend never executes Gemini-generated Cypher or arbitrary tools.

**Exposure analyst:** after calculating routes, select a route and click **Explain this route**. `POST /api/ai/exposure-analysis` accepts only `{ "trip_id": "...", "route_id": "..." }`. The backend retrieves its own stored comparison facts; the browser cannot submit invented AQI or savings as analyst input. Gemini writes a short summary, tradeoff and caveat. The numerical cards remain calculated facts; Neo4j remains the recommendation engine. AI prose is labelled and is not medical guidance.

Analysis facts are held in a bounded process-local cache for 30 minutes, without full route geometry or entered addresses. A server restart or expiry requires a fresh route calculation. Keep one backend worker for this prototype; use shared storage before scaling. Changing the selected route resets the explanation; changing form preferences prevents analysis until the route is recalculated.

The implementation uses the existing HTTPX client and Gemini's REST `generateContent` endpoint with JSON Schema; no extra Python SDK is required. See [Gemini structured output](https://ai.google.dev/gemini-api/docs/structured-output) and [GenerateContent reference](https://ai.google.dev/api/generate-content).

`backend/tests/test_gemini.py` and `tests/gemini-ui.mjs` use controlled responses to verify validation, safe missing-key behavior, exact payloads, strict AQI ceiling behavior, server-owned analysis facts and UI states. Passing these tests does not prove a live Gemini key is configured.


### Station AQI and deadline-aware comparisons

Set `WAQI_API_TOKEN` in the server `.env`, then restart FastAPI. This selects WAQI monitoring-station data for city AQI and route samples. Without a token, the app uses Open-Meteo/CAMS regional estimates and labels their roughly 45 km resolution. A configured station provider never silently falls back to model data on failure.

Each sample uses the station returned by WAQI's coordinate feed. Readings older than six hours or stations farther than `STATION_MAX_DISTANCE_KM` (default 10) are rejected. The map popup shows the station, timestamp and sample-to-station distance; route profiles share a common AQI scale. Station values remain proxies for road conditions, not street-level measurements. Identical readings remain identical.

`ROUTE_TARGET_COUNT=4` requests up to four distinct driving options. If native OSRM alternatives are sparse, the backend checks perpendicular waypoint corridors and labels the resulting road routes as detours. Near-duplicate paths and detours taking over 1.65 times the direct-route estimate are excluded. Fewer options are returned honestly if additional corridors fail. OSRM still has no live traffic.

`deadline_summary` reports the requested window, fastest time and minimum lateness. Each route includes `deadline_met`, `late_by_minutes`, and `constraint_failures`. No qualifying route means `recommended_route_id=null`; amber map paths are comparisons, not recommendations. AQI limits and unmasked-rider constraints remain strict. Gemini receives these server-calculated facts.

WAQI feeds are fetched fresh with request-local deduplication; the app does not provide a station-history download or cache endpoint. Neo4j retains the temporary scoring graph according to its configured retention. Credits include WAQI and the originating monitoring agencies. Review [WAQI's data and app usage terms](https://aqicn.org/api/) before public/commercial deployment: paid use and cached/archived redistribution are restricted, and organizational public use has notification/agreement requirements. This integration does not obtain those permissions for you.

For Render, add `WAQI_API_TOKEN` as a backend secret. Never put it in a `VITE_` variable. The frontend receives readings and attribution only.


### Conversational fleet suggestions and automatic rider planning

The rider assistant now fills the form and immediately requests routes. Manual edits can still be submitted with Show my ride. Admin has a conversational fleet advisor at `/api/ai/fleet-suggestions`: structured extraction captures group size, shared locations, mask status, deadline and US AQI ceiling; the normal route service evaluates candidates; the assistant explains the computed result. Missing group size or mask status triggers clarification. No deadline defaults to a disclosed 90-minute planning window. Unmasked riders retain the stricter sampled-AQI-above-200 restriction. Scheduling is disabled and no assignments or notifications are created.

Ranking now excludes ineligible routes from recommendation and orders qualifying routes by lowest AQI-times-minutes exposure, then shortest duration. The former weighted time-plus-exposure formula is no longer used. `routing_cost` remains a compatibility field equal to exposure index. Interface implementation names were removed; required data-provider attributions remain.
