from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

app = FastAPI(title="Roster Optimization Backend")

# Enable CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- IN-MEMORY DATABASE STORE (Replace with a real DB like PostgreSQL/SQLite in production) ---
db_store = {
    "settings": {
        "start_date": "2026-09-01",
        "end_date": "2026-09-30",
        "min_call_interval": 2,
        "max_teams_per_week": 1,
        "max_solve_time": 60,
        "al_call_buffer_before": 1,
        "al_call_buffer_after": 0,
        "blockout_call_buffer_before": 1,
        "blockout_call_buffer_after": 0,
    },
    "team_row_data": [
        {"teamName": "Team A", "2026-09-01": 2, "2026-09-02": 1},
        {"teamName": "Team B", "2026-09-01": 1, "2026-09-02": 2},
        {"teamName": "Team C"},
        {"teamName": "Team D"},
    ],
    "call_row_data": [
        {"callName": "Call 1", "2026-09-01": 1}
    ],
    "roster_row_data": [
        {
            "name": "Person 1",
            "2026-09-01": {"team": "Team A", "call": True},
            "2026-09-02": {"team": "Team B", "call": False}
        },
        {"name": "Person 2"},
        {"name": "Person 3"},
        {"name": "Person 4"},
    ]
}

# --- PYDANTIC MODELS ---
class SettingsUpdate(BaseModel):
    settings: Dict[str, Any]

class CellUpdate(BaseModel):
    table_type: str  # 'team', 'call_req', 'roster_team', 'roster_call', 'roster_name'
    row_index: int
    field: str
    value: Any

class BatchUpdates(BaseModel):
    updates: List[CellUpdate]

class TeamNameUpdate(BaseModel):
    originalTeamName: str
    teamName: str

class AddPersonRequest(BaseModel):
    name: str

class RunModelRequest(BaseModel):
    start_date: str
    end_date: str


# --- ENDPOINTS ---

@app.get("/api/roster/state")
def get_roster_state():
    """Returns the entire application state for frontend initialization."""
    return {
        **db_store["settings"],
        "team_row_data": db_store["team_row_data"],
        "call_row_data": db_store["call_row_data"],
        "roster_row_data": db_store["roster_row_data"]
    }


@app.patch("/api/roster/settings")
def update_settings(payload: SettingsUpdate):
    """Updates global configuration settings."""
    for key, value in payload.settings.items():
        db_store["settings"][key] = value
    return {"status": "success", "settings": db_store["settings"]}


@app.patch("/api/roster/batch-cells")
def batch_update_cells(payload: BatchUpdates):
    """Handles batch cell updates from the frontend queue."""
    for update in payload.updates:
        t_type = update.table_type
        idx = update.row_index
        field = update.field
        val = update.value

        if t_type == 'team':
            if 0 <= idx < len(db_store["team_row_data"]):
                db_store["team_row_data"][idx][field] = val

        elif t_type == 'call_req':
            if 0 <= idx < len(db_store["call_row_data"]):
                db_store["call_row_data"][idx][field] = val

        elif t_type in ['roster_team', 'roster_call', 'roster_name']:
            if 0 <= idx < len(db_store["roster_row_data"]):
                row = db_store["roster_row_data"][idx]
                if t_type == 'roster_name':
                    row['name'] = val
                else:
                    date_key = field  # field is the date string
                    if date_key not in row:
                        row[date_key] = {"team": "", "call": ""}
                    
                    sub_key = "team" if t_type == 'roster_team' else "call"
                    row[date_key][sub_key] = val

    return {"status": "success", "processed": len(payload.updates)}


@app.post("/api/roster/add-row")
def add_roster_row(payload: AddPersonRequest):
    """Persists a newly added person row so indices match cleanly on refresh."""
    new_row = {"name": payload.name}
    db_store["roster_row_data"].append(new_row)
    return {"status": "success", "total_rows": len(db_store["roster_row_data"])}


@app.patch("/api/teams/update")
def update_team_name(payload: TeamNameUpdate):
    """Updates a team's name across the team table and personnel roster references."""
    old_name = payload.originalTeamName
    new_name = payload.teamName

    # Update in team requirements
    for row in db_store["team_row_data"]:
        if row.get("teamName") == old_name:
            row["teamName"] = new_name

    # Update references in personnel roster
    for row in db_store["roster_row_data"]:
        for key, val in row.items():
            if key != 'name' and isinstance(val, dict):
                if val.get("team") == old_name:
                    val["team"] = new_name

    return {"status": "success"}


@app.post("/api/roster/run-model")
def run_optimization_model(payload: RunModelRequest):
    """
    Placeholder for your optimization solver backend (e.g., OR-Tools, PuLP, Gurobi).
    Mutates the roster state with optimized assignments and returns success.
    """
    # Example simulation: Populate dummy results for first row/date
    for row in db_store["roster_row_data"]:
        row[payload.start_date] = {"team": "Team A", "call": True}

    return {
        "status": "success",
        "message": f"Optimization successfully solved for range {payload.start_date} to {payload.end_date}!"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)