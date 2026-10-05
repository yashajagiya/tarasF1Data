# 🏎️ Taras F1 API v1 (Legacy)

This directory contains the complete legacy **Formula 1 API v1** pipeline, endpoints, datasets, and scraping scripts.

> **Note:** For new integrations and high-performance apps, please use [**Taras F1 API v2**](../tarasF1DataV2/README.md) located in [`/v2`](../v2/).

---

## 📌 Datasets & Endpoints in v1

| Endpoint / File | Description | Contents |
|---|---|---|
| [`driversperrace.json`](driversperrace.json) | Driver Championship Standings | Rank, car number, driver name, team, total points, and round-by-round points. |
| [`carperrace.json`](carperrace.json) | Constructor Championship Standings | Rank, team name, total points, and round-by-round team points. |
| [`f1_standings.json`](f1_standings.json) | Driver Standings (Root Alias) | Same data as `driversperrace.json`. |
| [`f1_constructor_standings.json`](f1_constructor_standings.json) | Constructor Standings (Root Alias) | Same data as `carperrace.json`. |
| [`f1Info/drivers_data.json`](f1Info/drivers_data.json) | Driver Dossiers & Encyclopedia | Biographies, images, 2026 stats, and career statistics. |
| [`f1Info/teams_data.json`](f1Info/teams_data.json) | Constructor Profiles | Team specifications, chassis, engine, leadership, car renders. |
| [`f1Info/races_data.json`](f1Info/races_data.json) | Circuit & Race Calendar | 2026 circuits, lap records, and session schedules. |
| [`practice1/fp1_extracted.json`](practice1/fp1_extracted.json) | Practice 1 Results | Classification, lap time or gap, laps completed. |
| [`practice2/fp2_extracted.json`](practice2/fp2_extracted.json) | Practice 2 Results | Classification, lap time or gap, laps completed. |
| [`practice3/fp3_extracted.json`](practice3/fp3_extracted.json) | Practice 3 Results | Classification, lap time or gap, laps completed. |
| [`qualifying/qualifying_results.json`](qualifying/qualifying_results.json) | Qualifying Classification | Starting grid, Q1, Q2, Q3 lap times, and laps. |
| [`sprint-quly/sprint_quly_result.json`](sprint-quly/sprint_quly_result.json) | Sprint Qualifying Results | Sprint shootout SQ1, SQ2, SQ3 times. |
| [`sprint-race/sprint_race_result.json`](sprint-race/sprint_race_result.json) | Sprint Race Results | Finishing order, time or gap, sprint points. |
| [`race-result/race_results.json`](race-result/race_results.json) | Grand Prix Classification | Official race finishing order, total time/retired status, points. |
| [`notification/notification.json`](notification/notification.json) | In-App Notifications | Push notifications for the Taras Android client. |

---

## 🛠️ Running the V1 Scrapers

Each session folder has its own isolated scraper under `code/`:

```bash
# Free Practice 1
python v1/practice1/code/fp1.py

# Free Practice 2
python v1/practice2/code/fp2.py

# Free Practice 3
python v1/practice3/code/fp3.py

# Qualifying
python v1/qualifying/code/qualifying_scraper.py

# Sprint Qualifying
python v1/sprint-quly/code/sprintquly.py

# Sprint Race
python v1/sprint-race/code/sprintrace.py

# Grand Prix Race
python v1/race-result/code/raceResult.py

# Calculate Standings
python v1/peerracepointdriver.py
python v1/peerracepointcar.py
```
