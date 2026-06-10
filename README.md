# trending.ai
<img width="1273" height="827" alt="Screenshot 2026-06-10 at 2 28 52 PM" src="https://github.com/user-attachments/assets/f841b257-1a49-4a16-9ae0-496b0b27cf2a" />
<img width="1309" height="815" alt="Screenshot 2026-06-10 at 2 29 18 PM" src="https://github.com/user-attachments/assets/49c6f64c-c0d2-48e7-99b2-5ab411bd77b8" />


Prototype dashboard and pipeline for turning prediction-market activity into
business content signals.

The current proof of concept:

- keeps one mock business per account in a local JSON database
- provides an Account page for business facts plus image/video source uploads
- saves preferred Polymarket trend tags on the business profile
- provides a Latest Trends page that runs Polymarket when `Find trends` is clicked
- normalizes Polymarket markets into trend rows with scan tags like sports,
  politics, crypto, tech, economy, culture, and general
- appends each trend run to a local CSV database

## Run locally

Dashboard:

```bash
node server.js
```

Then open `http://localhost:3000`.

Dashboard data is stored locally in:

- `data/dashboard-db.json` for the fake account/business/media/latest trends
- `data/business-trend-runs.csv` for appended Polymarket trend runs with a
  business profile snapshot

Offline/mock run:

```bash
python3 -m trending_ai.cli --source mock --output data/trends.csv
```

Live Polymarket run:

```bash
python3 -m trending_ai.cli --source polymarket --limit 50 --output data/trends.csv
```

Live Kalshi run:

```bash
python3 -m trending_ai.cli --source kalshi --limit 50 --output data/trends.csv
```

Both sources:

```bash
python3 -m trending_ai.cli --source all --limit 50 --output data/trends.csv
```

## CSV output

Rows are appended to `data/trends.csv` with:

- source market metadata: `source`, `trend_id`, `title`, `category`, `url`,
  `volume_24h`, `volume_total`, `liquidity`, `probability`, `close_time`
- business enrichment: `business_industry`, `business_started_date`,
  `business_audience`, `business_what_they_do`, `preferred_trend_tags`,
  `preferred_tag_match`, `preferred_tag_matches`, `matching_terms`,
  `content_angles`
- ingestion metadata: `run_id`, `fetched_at`, `business_name`

## Current data sources

The dashboard uses the Polymarket Gamma events endpoint:

```text
https://gamma-api.polymarket.com/events?active=true&closed=false&order=volume_24hr&ascending=false&limit=...
```

The older CLI prototype can still call Kalshi with:

```text
https://external-api.kalshi.com/trade-api/v2/markets?status=open&limit=...
```

## Next steps

- replace the mock `BusinessProfile` with real account/business records from your app
- add a scheduled job that appends fresh rows every N minutes or hours
- swap CSV for SQLite/Postgres once you want querying, deduping, or dashboards
