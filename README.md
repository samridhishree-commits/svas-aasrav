# svas-aasrav

A route planner for Delhi NCR that considers delivery time and air pollution.
Riders describe a journey; managers describe a group of riders. The app compares
real road routes and suggests the lowest-exposure option that meets their requirements.

## What it does

- Turns natural-language requests into route searches.
- Compares up to four distinct routes with time, US AQI and exposure estimates.
- Flags missed deadlines and routes that exceed AQI limits.
- Gives fleet suggestions without scheduling or dispatching riders.
- Saves decision logs in Neo4j and shows them beside the route options.

## Built with

React + Vite, FastAPI, Neo4j and Gemini. Maps use MapLibre/OpenFreeMap;
Photon finds places, OSRM finds roads, and WAQI supplies nearby station readings.
Without a WAQI token, the app uses Open-Meteo regional estimates.

## Run locally

Use Node.js 22.12+ and Python 3.12. Copy `.env.example` to `.env` only if you do not
already have one. Fill in the Neo4j credentials, `GEMINI_API_KEY` and `WAQI_API_TOKEN`.
Never commit `.env` or put secret keys in `VITE_` variables.

```sh
npm install
npm run dev
```

In a second terminal, from the project root:

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --reload --port 8000
```

Frontend: http://localhost:5173. API docs: http://localhost:8000/docs.
Restart the backend after changing `.env`.

## How recommendations work

First check the deadline, mask status and requested AQI ceiling. Then choose the
qualifying route with the lowest exposure index: `sum(sample AQI * estimated minutes)`.
Shortest time breaks ties. If nothing qualifies, no route is recommended.
Unmasked riders exclude sampled US AQI above 200, even when their requested limit is higher.

## Deploy

- **Render:** build `pip install -r backend/requirements.txt`; start
  `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`. Add backend secrets from `.env`.
- **Vercel:** import this repo as Vite; build `npm run build`; output `dist`.
  Set `VITE_API_BASE_URL` to the Render URL.
- Set Render's `CORS_ORIGINS` to your exact Vercel URL, without a trailing slash.

## Demo and logs

See [DEMO.md](DEMO.md) for prompts and expected results. Run queries from
[backend/activity-logs.cypher](backend/activity-logs.cypher) in your Aura Query console.
Logs save automatically after a completed comparison; no manual import is needed.
They share the comparison's retention period (60 minutes by default), with expired
records removed during a subsequent route comparison. Logs contain generated decision
summaries, not raw prompts, credentials or full addresses.

## Tests and limits

```sh
pip install -r backend/requirements-dev.txt
python -m pytest backend/tests -q
npm test
npm run build
```

This is a hackathon prototype: no live traffic, street-level pollution guarantee,
user authentication or real dispatch. Station readings are nearby estimates, and US AQI
is different from Indian AQI. Follow [WAQI's data-use terms](https://aqicn.org/api/)
before public/commercial use; source credits remain visible in the app.
