from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Any, Dict, List
import json
from pathlib import Path
from datetime import datetime, timedelta

from roster import Roster

app = FastAPI(title="Roster Backend API", version="1.0.0")

@app.on_event("startup")
def debug_print_routes():
    print("\n--- CHECKING REGISTERED ROUTES ---")
    for route in app.routes:
        print(f"Route found: {route.methods} -> {route.path}")
    print("----------------------------------\n")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_FILE = Path("roster_state.json")

DEFAULT_STATE = {
    "start_date": "2026-09-01",
    "end_date": "2026-09-30",
    "min_call_interval": 2,
    "max_teams_per_week": 1,
    "max_solve_time": 60,
    "al_call_buffer_before": 1,
    "al_call_buffer_after": 0,
    "blockout_call_buffer_before": 1,
    "blockout_call_buffer_after": 0,
    "team_row_data": [
        {"teamName": "Team A", "2026-09-01": 3, "2026-09-02": 3},
        {"teamName": "Team B", "2026-09-01": 2, "2026-09-02": 2},
        {"teamName": "Team C", "2026-09-01": 1, "2026-09-02": 1},
        {"teamName": "Team D", "2026-09-01": 1, "2026-09-02": 1},
        {"teamName": "ps_cover", "2026-09-01": 1, "2026-09-02": 1},
    ],
    "call_row_data": [
        {"callName": "Call 1", "2026-09-01": 1, "2026-09-02": 1}
    ],
    "roster_team_row_data": [
        {"name": "Person 1"},
        {"name": "Person 2"},
        {"name": "Person 3"},
        {"name": "Person 4"},
    ],
    "roster_call_row_data": [
        {"name": "Person 1"},
        {"name": "Person 2"},
        {"name": "Person 3"},
        {"name": "Person 4"},
    ]
}

def load_data() -> dict:
    if not DATA_FILE.exists():
        save_data(DEFAULT_STATE)
        return DEFAULT_STATE
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            updated = False
            for k, v in DEFAULT_STATE.items():
                if k not in data:
                    data[k] = v
                    updated = True
            if updated:
                save_data(data)
            return data
    except Exception as e:
        print(f"Error reading JSON file, falling back to default: {e}")
        return DEFAULT_STATE

def save_data(data: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

class CellUpdate(BaseModel):
    table_type: str
    row_index: int
    field: str
    value: Any

class BatchCellUpdatePayload(BaseModel):
    updates: List[CellUpdate]

class TeamUpdatePayload(BaseModel):
    originalTeamName: str
    teamName: str

class SettingsUpdatePayload(BaseModel):
    settings: Dict[str, Any]

class OptimizationPayload(BaseModel):
    start_date: str
    end_date: str

@app.get("/api/roster/state")
def get_roster_state():
    return load_data()

@app.patch("/api/roster/batch-cells")
def update_roster_batch_cells(payload: BatchCellUpdatePayload):
    db = load_data()
    
    for update in payload.updates:
        table_type = update.table_type
        idx = update.row_index
        field = update.field
        val = update.value

        target_list = None
        if table_type == 'team':
            target_list = db["team_row_data"]
        elif table_type == 'call_req':
            target_list = db["call_row_data"]
        elif table_type == 'roster_team':
            target_list = db["roster_team_row_data"]
        elif table_type == 'roster_call':
            target_list = db["roster_call_row_data"]
        else:
            continue

        if 0 <= idx < len(target_list):
            target_list[idx][field] = val

    save_data(db)
    return {"status": "success", "message": f"Successfully processed {len(payload.updates)} cell updates."}

@app.patch("/api/teams/update")
def update_team_name(payload: TeamUpdatePayload):
    db = load_data()
    team_list = db["team_row_data"]

    # Find the team by its original name
    target_team = None
    for team in team_list:
        if team.get("teamName") == payload.originalTeamName:
            target_team = team
            break

    if not target_team:
        # If it doesn't exist yet (e.g. a newly added row), append it!
        new_row = {"teamName": payload.teamName}
        team_list.append(new_row)
    else:
        target_team["teamName"] = payload.teamName

    save_data(db)
    return {"status": "success", "message": "Team name updated successfully."}

@app.patch("/api/roster/settings")
def update_roster_settings(payload: SettingsUpdatePayload):
    db = load_data()
    allowed_keys = {
        "start_date", "end_date", "min_call_interval", "max_teams_per_week",
        "max_solve_time", "al_call_buffer_before", "al_call_buffer_after",
        "blockout_call_buffer_before", "blockout_call_buffer_after"
    }
    
    for key, value in payload.settings.items():
        if key in allowed_keys:
            db[key] = value
            
    save_data(db)
    return {"status": "success", "message": "Settings updated and saved successfully."}

@app.post("/api/roster/run-model")
def run_optimization_model(payload: OptimizationPayload):
    db = load_data()
    
    try:
        start_dt = datetime.strptime(payload.start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(payload.end_date, '%Y-%m-%d')
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format received. Expected YYYY-MM-DD.")

    start_date_fmt = start_dt.strftime('%d/%m/%Y')
    end_date_fmt = end_dt.strftime('%d/%m/%Y')

    dates_list = [(start_dt + timedelta(days=i)).strftime('%d/%m/%Y') for i in range((end_dt - start_dt).days + 1)]
    ui_dates_list = [(start_dt + timedelta(days=i)).strftime('%Y-%m-%d') for i in range((end_dt - start_dt).days + 1)]

    min_call_interval = int(db.get("min_call_interval", 2))
    max_teams_per_week = int(db.get("max_teams_per_week", 1))
    max_solve_time = int(db.get("max_solve_time", 60))
    leave_buffers = [int(db.get("al_call_buffer_before", 1)), int(db.get("al_call_buffer_after", 0))]
    blockout_buffers = [int(db.get("blockout_buffer_before", 1)), int(db.get("blockout_buffer_after", 0))]

    staff_members = [row.get("name") for row in db.get("roster_team_row_data", []) if row.get("name")]
    if not staff_members:
        raise HTTPException(status_code=400, detail="No personnel found in roster to optimize.")

    team_options = []
    daily_team_requirement = {}
    for row in db.get("team_row_data", []):
        t_name = row.get("teamName")
        if t_name:
            team_options.append(t_name)
            sample_val = row.get(ui_dates_list[0], 1)
            daily_team_requirement[t_name] = int(sample_val) if sample_val not in ("", None) else 1

    for default_opt in ['ps_cover', 'leave']:
        if default_opt not in team_options:
            team_options.append(default_opt)

    team_sacrificability = {opt: 5 for opt in team_options}
    team_sacrificability['leave'] = 0
    team_sacrificability['ps_cover'] = 0

    team_requirements = {d: daily_team_requirement for d in dates_list}

    call_requirements = {}
    call_row = db.get("call_row_data", [{}])[0]
    for idx, d_str in enumerate(dates_list):
        ui_d = ui_dates_list[idx]
        val = call_row.get(ui_d, 1)
        call_requirements[d_str] = int(val) if val not in ("", None) else 1

    team_locks = {person: {} for person in staff_members}
    call_locks = {person: {} for person in staff_members}

    for row in db.get("roster_team_row_data", []):
        person = row.get("name")
        if not person:
            continue
        for ui_d, solver_d in zip(ui_dates_list, dates_list):
            cell_val = row.get(ui_d)
            if cell_val:
                team_locks[person][solver_d] = cell_val

    for row in db.get("roster_call_row_data", []):
        person = row.get("name")
        if not person:
            continue
        for ui_d, solver_d in zip(ui_dates_list, dates_list):
            cell_val = row.get(ui_d)
            if cell_val is True or cell_val == 'True':
                call_locks[person][solver_d] = 1
            elif cell_val is False or cell_val == 'False':
                call_locks[person][solver_d] = 0

    try:
        roster_sched = Roster(
            start_date=start_date_fmt,
            end_date=end_date_fmt,
            persons=staff_members,
            team_requirements=team_requirements,
            team_options=team_options,
            team_sacrificability=team_sacrificability,
            team=team_locks,
            call_requirements=call_requirements,
            calls=call_locks,
            leave_buffers=leave_buffers,
            blockout_buffers=blockout_buffers,
            call_interval=min_call_interval,
            max_teams_per_week=max_teams_per_week,
            max_solve_time_seconds=max_solve_time
        )

        success = roster_sched.solve()
        if not success:
            return {"status": "error", "message": "Optimization completed, but no feasible solution was found."}

        solved_team_rows = []
        solved_call_rows = []

        for person in staff_members:
            new_team_row = {"name": person}
            new_call_row = {"name": person}

            for ui_d, solver_d in zip(ui_dates_list, dates_list):
                assigned_team = roster_sched.teams_table.get(person, {}).get(solver_d, '')
                new_team_row[ui_d] = assigned_team if assigned_team else ''

                try:
                    is_call = bool(roster_sched.solver.Value(roster_sched.call_vars[person][dates_list.index(solver_d)]))
                    new_call_row[ui_d] = is_call
                except Exception:
                    new_call_row[ui_d] = False

            solved_team_rows.append(new_team_row)
            solved_call_rows.append(new_call_row)

        db["roster_team_row_data"] = solved_team_rows
        db["roster_call_row_data"] = solved_call_rows
        save_data(db)

        return {
            "status": "success", 
            "message": f"Optimization model executed successfully for {payload.start_date} through {payload.end_date}!"
        }

    except Exception as e:
        print(f"Solver execution error: {e}")
        raise HTTPException(status_code=500, detail=f"Solver execution failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
    