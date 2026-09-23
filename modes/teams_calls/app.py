from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import streamlit as st
from roster import Roster  # Import your Roster class

st.set_page_config(page_title="Interactive Roster Solver", layout="wide")

st.title("🧩Roster Editor with Human-in-the-Loop Locks")
st.markdown(
    "You can manually lock values in every table, and the model with generate the rest"
    "Data is automatically persisted to the `data/` folder."
)

# --- Ensure Data Directory Exists ---
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

CONFIG_CSV = DATA_DIR / "config_vars.csv"
QUOTAS_CSV = DATA_DIR / "team_quotas.csv"
ROSTER_CSV = DATA_DIR / "roster_locks.csv"

# --- Default Staff & Team Options ---
staff_members = [
    "Alpha",
    "Bravo",
    "Charlie",
    "Delta",
    "Echo",
    "Foxtrot",
    "Golf",
    "Hotel",
    "India",
    "Juliet",
    "Kilo",
]
team_options = [
    "team_subobs",
    "team_ds",
    "team_9ab",
    "team_b1",
    "team_bg",
    "team_go",
    "ps_cover",
    "leave",
]

# --- Load Configuration Variables ---
if CONFIG_CSV.exists():
  try:
    df_config = pd.read_csv(CONFIG_CSV)
    cfg_dict = dict(zip(df_config["Parameter"], df_config["Value"]))
  except Exception:
    cfg_dict = {}
else:
  cfg_dict = {}

default_start = cfg_dict.get("start_date", "01/10/2026")
default_end = cfg_dict.get("end_date", "31/10/2026")
default_min_call = int(cfg_dict.get("min_call_interval", 2))
default_max_teams = int(cfg_dict.get("max_teams_per_week", 1))
default_max_runtime = int(cfg_dict.get("max_solve_time", 15))
default_al_b = int(cfg_dict.get("al_call_buffer_before", 1))
default_al_a = int(cfg_dict.get("al_call_buffer_after", 0))
default_bl_b = int(cfg_dict.get("blockout_call_buffer_before", 1))
default_bl_a = int(cfg_dict.get("blockout_call_buffer_after", 0))

# --- 1. GLOBAL PARAMETERS UI LAYOUT ---
st.subheader("Global Parameters")
col1, col2 = st.columns(2)
with col1:
  start_date_str = st.text_input("Start Date", str(default_start))
with col2:
  end_date_str = st.text_input("End Date", str(default_end))

col1, col2 = st.columns(2)
with col1:
  min_call_interval = st.number_input("Min call interval", value=default_min_call, step=1)
with col2:
  max_teams_per_week = st.number_input("Max teams per week", value=default_max_teams, step=1)

col1, col2, col3, col4 = st.columns(4)
with col1:
  al_call_buffer_before = st.number_input("AL call buffer (before)", value=default_al_b, step=1)
with col2:
  al_call_buffer_after = st.number_input("al (after)", value=default_al_a, step=1)
with col3:
  blockout_call_buffer_before = st.number_input("Blockout call buffer (before)", value=default_bl_b, step=1)
with col4:
  blockout_call_buffer_after = st.number_input("bl (after)", value=default_bl_a, step=1)

max_solve_time = st.number_input("Max Runtime (seconds)", value=default_max_runtime, step=1, min_value=1)

# Save configuration back to CSV
config_data = {
    "Parameter": [
        "start_date", "end_date", "min_call_interval", "max_teams_per_week",
        "max_solve_time", "al_call_buffer_before", "al_call_buffer_after",
        "blockout_call_buffer_before", "blockout_call_buffer_after"
    ],
    "Value": [
        start_date_str, end_date_str, min_call_interval, max_teams_per_week,
        max_solve_time, al_call_buffer_before, al_call_buffer_after,
        blockout_call_buffer_before, blockout_call_buffer_after
    ]
}
pd.DataFrame(config_data).to_csv(CONFIG_CSV, index=False)

# --- Generate Date List ---
try:
  start_dt = datetime.strptime(start_date_str, "%d/%m/%Y")
  end_dt = datetime.strptime(end_date_str, "%d/%m/%Y")
  dates = [
      (start_dt + timedelta(days=i)).strftime("%d/%m/%Y")
      for i in range((end_dt - start_dt).days + 1)
  ]
except ValueError:
  dates = []
  st.error("Please enter valid dates in DD/MM/YYYY format.")

st.markdown("---")

# --- 2. TEAM QUOTAS & REQUIREMENTS TABLE ---
st.subheader("Team Quotas & Requirements")
st.caption("Define team requirements, sacrificability rankings, minimum teams, and per-date quotas/call requirements.")

if "df_teams" not in st.session_state:
  if QUOTAS_CSV.exists():
    try:
      df_teams_loaded = pd.read_csv(QUOTAS_CSV)
      for d in dates:
        if d not in df_teams_loaded.columns:
          df_teams_loaded[d] = 1
      cols_to_keep = ["Team", "Team Req", "Sacrificability", "Min Team"] + [d for d in dates if d in df_teams_loaded.columns]
      st.session_state.df_teams = df_teams_loaded[[c for c in cols_to_keep if c in df_teams_loaded.columns]]
    except Exception:
      st.session_state.df_teams = None

  if "df_teams" not in st.session_state or st.session_state.df_teams is None or len(dates) == 0:
    teams_data = {
        "Team": [
            "team_subobs", "team_ds", "team_9ab", "team_go",
            "team_b1", "team_bg", "ps_cover",
        ],
        "Team Req": [3, 2, 2, 1, 1, 1, 1],
        "Sacrificability": [14, 14, 5, 1, 1, 1, 0],
        "Min Team": [1, 1, 1, 1, 1, 1, 1],
    }
    base_reqs = {
        "team_subobs": 3, "team_ds": 2, "team_9ab": 2,
        "team_go": 1, "team_b1": 1, "team_bg": 1, "ps_cover": 1,
    }
    for d in dates:
      teams_data[d] = [base_reqs[t] for t in teams_data["Team"]]
    
    teams_data["Team"].append("Call Req")
    teams_data["Team Req"].append(0)
    teams_data["Sacrificability"].append(0)
    teams_data["Min Team"].append(0)
    for d in dates:
      d_obj = datetime.strptime(d, "%d/%m/%Y")
      default_calls = 2 if d_obj.weekday() >= 5 else 1
      teams_data[d].append(default_calls)

    st.session_state.df_teams = pd.DataFrame(teams_data)

edited_teams_df = st.data_editor(
    st.session_state.df_teams, num_rows="fixed", use_container_width=True, key="teams_editor"
)
edited_teams_df.to_csv(QUOTAS_CSV, index=False)

st.markdown("---")

# --- 3. STAFF ROSTER GRID & LOCK MANAGEMENT ---
st.subheader("Staff Roster Grid")
st.caption("Type a team name or leave status directly into any cell to lock it. Changes save automatically.")

# Initialize session state from CSV ONLY ONCE when the app starts up
if "df_staff" not in st.session_state:
  if ROSTER_CSV.exists():
    try:
      df_staff_loaded = pd.read_csv(ROSTER_CSV, dtype=str).fillna("")
      for person in staff_members:
        if not ((df_staff_loaded["Staff"] == person)).any():
          new_row = {"Staff": person}
          for d in dates:
            new_row[d] = ""
          df_staff_loaded = pd.concat([df_staff_loaded, pd.DataFrame([new_row])], ignore_index=True)
      for d in dates:
        if d not in df_staff_loaded.columns:
          df_staff_loaded[d] = ""
      st.session_state.df_staff = df_staff_loaded[["Staff"] + dates]
    except Exception:
      st.session_state.df_staff = None

  if "df_staff" not in st.session_state or st.session_state.df_staff is None or len(dates) == 0:
    initial_data = {"Staff": staff_members}
    for d in dates:
      initial_data[d] = ["" for _ in staff_members]
    st.session_state.df_staff = pd.DataFrame(initial_data)

# Ensure strict string formatting for the grid view
for d in dates:
  if d in st.session_state.df_staff.columns:
    st.session_state.df_staff[d] = st.session_state.df_staff[d].fillna("").astype(str).replace(["nan", "None", "NaN"], "")

# Render the interactive data editor
edited_staff_df = st.data_editor(
    st.session_state.df_staff, num_rows="fixed", use_container_width=True, key="staff_editor"
)

# Real-time sync: Update session state and persist to CSV immediately upon cell edit completion
if not edited_staff_df.equals(st.session_state.df_staff):
  st.session_state.df_staff = edited_staff_df.copy()
  # Clean potential string artifacts before writing to file
  for d in dates:
    if d in edited_staff_df.columns:
      edited_staff_df[d] = edited_staff_df[d].fillna("").astype(str).replace(["nan", "None", "NaN"], "")
  edited_staff_df.to_csv(ROSTER_CSV, index=False)

# --- 4. EXECUTION & CONTROLS ---
col_btn1, col_btn2 = st.columns([1, 5])
with col_btn1:
  run_solver = st.button("🚀 Run Solver", type="primary")
with col_btn2:
  clear_auto = st.button("Clear Auto-Filled Values")

if clear_auto:
  reset_data = {"Staff": staff_members}
  for d in dates:
    col_vals = []
    for person in staff_members:
      val = str(edited_staff_df.loc[edited_staff_df["Staff"] == person, d].values[0])
      if "(auto)" in val:
        col_vals.append("")
      else:
        col_vals.append(val)
    reset_data[d] = col_vals
  st.session_state.df_staff = pd.DataFrame(reset_data)
  st.session_state.df_staff.to_csv(ROSTER_CSV, index=False)
  st.rerun()

if run_solver:
  # Capture only true user locks from staff grid (ignoring cells with '(auto)')
  current_locks = {}
  for _, row in edited_staff_df.iterrows():
    person = row["Staff"]
    current_locks[person] = {}
    for d in dates:
      if d in row:
        val = str(row[d]).strip()
        if "(auto)" in val:
          continue
        
        val_clean = val.strip()
        if val_clean in team_options:
          current_locks[person][d] = val_clean

  # Build team requirements dictionary and call requirements dynamically
  team_requirements = {}
  call_requirements = {}

  for d in dates:
    day_reqs = {}
    for _, row in edited_teams_df.iterrows():
      team_name = row["Team"]
      val = int(row[d]) if d in row and pd.notnull(row[d]) else 0
      if team_name == "Call Req":
        call_requirements[d] = val
      else:
        day_reqs[team_name] = val
    team_requirements[d] = day_reqs

  try:
    roster_sched = Roster(
        start_date=start_date_str,
        end_date=end_date_str,
        persons=staff_members,
        team_requirements=team_requirements,
        team_options=team_options,
        call_requirements=call_requirements,
        team=current_locks,
        leaves_blockouts={p: [] for p in staff_members},
        leave_buffers=[al_call_buffer_before, al_call_buffer_after],
        blockout_buffers=[
            blockout_call_buffer_before,
            blockout_call_buffer_after,
        ],
        call_interval=min_call_interval,
        max_teams_per_week=int(max_teams_per_week),
        max_solve_time_seconds=int(max_solve_time)
    )

    success = roster_sched.solve()

    if success:
      new_grid_data = {"Staff": staff_members}
      for d in dates:
        column_values = []
        for person in staff_members:
          if person in current_locks and d in current_locks[person]:
            column_values.append(current_locks[person][d])
          else:
            solved_val = roster_sched.teams_table[person].get(d, "")
            column_values.append(
                f"{solved_val} (auto)" if solved_val else ""
            )
        new_grid_data[d] = column_values

      st.session_state.df_staff = pd.DataFrame(new_grid_data)
      st.session_state.df_staff.to_csv(ROSTER_CSV, index=False)
      st.success("Roster optimized successfully around your locked values and saved!")
      st.rerun()
    else:
      st.error(
          "No feasible solution found with current manual locks. Check your"
          " constraints or conflicting selections."
      )

  except Exception as e:
    st.error(f"Error running model: {e}")