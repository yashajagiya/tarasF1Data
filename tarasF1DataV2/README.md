# 🏎️ Taras F1 API v2

### The Simple, Zero-Latency, Edge-Cached Formula 1 Public REST API

> **100% Data Preserved • Zero API Keys • Zero Quotas • Built for Any App**

---

## 📌 Overview

**Taras F1 API v2** transforms complex, fragmented Formula 1 web data into a **clean, standardized, world-class sports API**. Anyone in the world—whether building an Android app, a web dashboard, a Discord bot, or a fantasy league—can integrate this API in under 5 minutes.

- **Isolated & Safe:** Lives in `tarasF1DataV2/` without altering or breaking the legacy V1 pipeline.
- **Zero Data Loss:** Preserves **100%** of all driver dossiers, 16-metric season stats, 8-metric career stats, transparent car cutouts, track outline maps, and session telemetry (FP1 through Sunday Grand Prix).
- **All 23 Drivers Supported:** Full profiles and standings for all 23 drivers (including mid-season additions like Yuki Tsunoda #22 at Racing Bulls).

---

## 🌐 The 5 Unified Endpoints

| Endpoint | File Path | What It Gives in Plain English | Sample Size |
|---|---|---|---|
| **Overview** | [`overview.json`](output/overview.json) | **Home screen in 1 request**: current championship leaders, next race countdown, session schedule, and latest podium. | 2.1 KB |
| **Drivers** | [`drivers.json`](output/drivers.json) | **All 23 drivers**: photos, number vector logos, team colors, bios, 2026 season stats, career stats, and standings. | 208 KB |
| **Teams** | [`teams.json`](output/teams.json) | **All 11 constructors**: 2026 car renders, white logos, leadership, power units, chassis, factory bases, and standings. | 84 KB |
| **Standings** | [`standings.json`](output/standings.json) | Complete leaderboards for both Drivers and Constructors with **round-by-round point breakdowns**. | 190 KB |
| **Calendar** | [`calendar.json`](output/calendar.json) | Complete 22-race season with track outline maps, circuit specifications (lap records, corners, length), and UTC schedules. | 29 KB |
| **Weekend Results** | [`results/latest.json`](output/results/latest.json) | Complete classifications for **every session** (FP1, FP2, FP3, Qualy, Sprint, Race) in one document without overwriting past races! | 51 KB |

---

## 💡 Quickstart Integration Examples

### 1. JavaScript / Web / React (`fetch`)
```javascript
// Render a Home Dashboard in 3 lines
const response = await fetch("https://yashajagiya.github.io/tarasF1Data/v2/overview.json");
const data = await response.json();

console.log(`Championship Leader: ${data.championship_leader.driver.name} (${data.championship_leader.driver.points} pts)`);
console.log(`Next Race: ${data.next_event.race_name} at ${data.next_event.circuit_name}`);
```

### 2. Python (`requests`)
```python
import requests

# Fetch all 23 drivers with photos and team colors
drivers = requests.get("https://yashajagiya.github.io/tarasF1Data/v2/drivers.json").json()

for d in drivers:
    print(f"#{d['number']:>2} {d['code']} | {d['name']:<20} | {d['team']['name']:<18} | {d['standings']['points']} pts")
```

### 3. Android Kotlin (Retrofit)
```kotlin
data class F1Overview(
    val season: Int,
    val round_current: Int,
    val championship_leader: ChampionshipLeader,
    val next_event: NextEvent,
    val latest_race: LatestRace
)

data class ChampionshipLeader(
    val driver: LeaderDriver,
    val team: LeaderTeam
)

data class LeaderDriver(
    val name: String,
    val number: Int,
    val team: String,
    val color_hex: String,
    val points: Int,
    val image: String
)

interface F1ApiService {
    @GET("v2/overview.json")
    suspend fun getOverview(): F1Overview

    @GET("v2/drivers.json")
    suspend fun getDrivers(): List<DriverDto>
}
```

---

## 🛠️ Repository & Architecture Layout

```text
tarasF1DataV2/
├── data/
│   ├── drivers_registry.json    ← Master registry of all 23 drivers (IDs, numbers, colors, images)
│   ├── teams_registry.json      ← Master registry of all 11 teams (specs, engines, leadership)
│   └── calendar_master.json     ← Master 2026 calendar (22 rounds, circuit records, track maps)
├── collectors/
│   ├── espn_standings.py        ← Pure data collector for live ESPN standings (Driver + Constructor)
│   ├── f1_encyclopedia.py       ← Loads deep biographies, career stats, and 16-metric 2026 stats
│   └── f1_sessions.py           ← Consolidates FP1–FP3, Qualy, Sprint, and Race classifications
├── build.py                     ← The Master Build Engine (runs collectors, builds V2 API)
├── output/                      ← The generated, production-ready static API files
│   ├── overview.json
│   ├── drivers.json
│   ├── teams.json
│   ├── standings.json
│   ├── calendar.json
│   └── results/
│       ├── latest.json
│       └── round_16.json
└── README.md                    ← This developer guide
```

---

## 🚀 How to Run & Build

To regenerate all API files with live data:

```bash
cd m:\tarasF1Data\tarasF1DataV2
python build.py
```

All updated endpoints will be written directly into `tarasF1DataV2/output/`.
