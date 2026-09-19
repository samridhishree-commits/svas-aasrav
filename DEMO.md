# svas-aasrav: a simple demo script

## Before presenting

1. Open the deployed app and check that the city AQI loads.
2. Select **Live data**, then **Rider**.
3. Open your Neo4j Aura instance's **Query** tool in another tab and connect to the
   same database used by the backend. Keep `backend/activity-logs.cypher` ready.
4. If hosting has been idle, run one route search before the presentation.

Live AQI and journey estimates change. Do not promise exact numbers or four routes
for every journey. The expected outcomes below describe behaviour, not fixed readings.

## 1. Automatic rider planning

Paste into the rider assistant and click **Find my routes**:

> Take me from Saket to Rohini within 90 minutes. I have a mask.

**Expect:** fields fill automatically and routes appear without clicking Show my ride.
Usually several routes are available. Compare time, average AQI and the pollution
profiles. Select another route and inspect a map sample to see its station and timestamp.
The decision log beside the options shows the checks and saved recommendation.

**Say:** "We choose the lowest estimated exposure among routes that meet the rider's needs."

## 2. A deadline that cannot be met

> Take me from Saket to Rohini within 5 minutes. I have a mask.

**Expect:** no recommended route, a deadline warning, the fastest available time,
and lateness for each option. The log explains the failed deadline checks.

**Say:** "The app reports an impossible deadline instead of quietly relaxing it."

## 3. A strict air-quality requirement

> Take me from Saket to Rohini within 90 minutes, with US AQI below 50. I have a mask.

**Expect:** if current samples reach 50 or more on every route, no route qualifies.
If unusually clean readings allow a route, it may qualify: the result follows live data.
The AQI ceiling applies to every sampled point, not just the average.

## 4. Conversational fleet suggestions

Switch to **Admin** and click **Suggest routes** after entering:

> I have 5 unmasked riders at Saket. Route them to Rohini within 90 minutes, but absolutely avoid any zones with US AQI over 300.

**Expect:** five riders, unmasked status, the locations and deadline are extracted.
Routes and an explanation appear. Unmasked riders also exclude samples above 200,
so an option can fail even when it stays below 300. "Over 300" permits 300; the
form expresses this as the equivalent strict ceiling "below 301".
Scheduling stays disabled. The last saved log confirms that no riders were dispatched.

Follow up in the same conversation:

> They all have masks now. Keep the same locations and allow 120 minutes.

**Expect:** the group and journey remain, mask status and deadline update, and new
suggestions are calculated. Keep in mind that a mask does not guarantee safety.

## 5. Show the database proof

Expand **Comparison reference** under the decision log and copy the trip ID.
In the Aura Query tool, run the parameter statement and the trip-specific query
from [activity-logs.cypher](backend/activity-logs.cypher), replacing the placeholder ID.
The message order and timestamps match the app. Run the graph query to show:

`Trip -> HAS_EVENT -> ActivityLog`

The same trip connects to candidate routes, route samples and air-quality readings.
No CSV upload or manual import is required. Logs are saved in the existing database.
Default retention is one hour; this is a temporary demo record, not a permanent archive.

**Say:** "These are actual application decisions stored in the graph, not an animated fake log."

## Explain the roles in one sentence

"The assistant understands the request and explains the results; the graph database
checks route eligibility and ranks the candidates by exposure."

## If something fails

- Missing location, rider count or mask status: answer the assistant's clarification.
- Expired comparison after a server restart: calculate the journey again.
- Log says unavailable: route results may still work; check database connectivity.
- Browser cannot reach the backend: check the frontend API URL and backend CORS setting.
- External service unavailable: retry; do not present demo values as live measurements.

End with: "Scheduling, dispatch and real traffic are future features. Today this is a
transparent decision-support tool for pollution-aware journeys."
