from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
import pandas as pd
import streamlit as st
from roster import Roster  # Import your Roster class

st.set_page_config(page_title="Interactive Roster Solver", layout="wide")

st.title("🧩 Roster Editor with Human-in-the-Loop Locks")
st.markdown(
    "Values auto-save instantly as you edit. Unassigned and cleared cells are stored as `None`."
)

# --- Ensure Data Directory Exists ---
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

CONFIG_CSV = DATA_DIR / "config_vars.csv"
QUOTAS_CSV = DATA_DIR / "team_quotas.csv"
ROSTER_CSV = DATA_DIR / "roster_locks.csv"

# --- Default Staff & Team Options ---
staff_members = [
    "Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot",
    "Golf", "Hotel", "India", "Juliet", "Kilo",
]
team_options = [
    "team_subobs", "team_ds", "team_9ab", "team_b1",
    "team_bg", "team_go", "ps_cover", "leave",
]

# --- Load Configuration Variables ---
if "cfg_dict" not in st.session_state:
  if CONFIG_CSV.exists():
    try:
      df_config = pd.read_csv(CONFIG_CSV)
      st.session_state.cfg_dict = dict(zip(df_config["Parameter"], df_config["Value"]))
    except Exception:
      st.session_state.cfg_dict = {}
  else:
    st.session_state.cfg_dict = {}

cfg_dict = st.session_state.cfg_dict

default_start = cfg_dict.get("start_date", "01/10/2026")
default_end = cfg_dict.get("end_date", "31/10/2026")
default_min_call = int(cfg_dict.get("min_call_interval", 2))
default_max_teams = int(cfg_dict.get("max_teams_per_week", 1))
default_max_runtime = int(cfg_dict.get("max_solve_time", 15))
default_al_b = int(cfg_dict.get("al_call_buffer_before", 1))
default_al_a = int(cfg_dict.get("al_call_buffer_after", 0))
default_bl_b = int(cfg_dict.get("blockout_call_buffer_before", 1))
default_bl_a = int(cfg_dict.get("blockout_call_buffer_after", 0))

# --- 1. GLOBAL PARAMETERS UI LAYOUT (Wrapped in a Form to Prevent Jitter) ---
st.subheader("Global Parameters")

with st.form("config_form"):
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
    al_call_buffer_after = st.number_input("AL call buffer (after)", value=default_al_a, step=1)
  with col3:
    blockout_call_buffer_before = st.number_input("Blockout call buffer (before)", value=default_bl_b, step=1)
  with col4:
    blockout_call_buffer_after = st.number_input("Blockout call buffer (after)", value=default_bl_a, step=1)

  max_solve_time = st.number_input("Max Runtime (seconds)", value=default_max_runtime, step=1, min_value=1)
  
  apply_config = st.form_submit_button("Apply Configuration & Dates", type="secondary")

# Auto-save configuration on form submission or change
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
df_new_config = pd.DataFrame(config_data)
df_old_config = pd.DataFrame(
    {"Parameter": list(cfg_dict.keys()), "Value": list(cfg_dict.values())}
) if cfg_dict else pd.DataFrame()

if apply_config or not df_new_config.equals(df_old_config):
  df_new_config.to_csv(CONFIG_CSV, index=False)
  st.session_state.cfg_dict = dict(zip(df_new_config["Parameter"], df_new_config["Value"]))

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

if not edited_teams_df.equals(st.session_state.df_teams):
  st.session_state.df_teams = edited_teams_df.copy()
  edited_teams_df.to_csv(QUOTAS_CSV, index=False)

st.markdown("---")

# --- 3. STAFF ROSTER GRID & LOCK MANAGEMENT ---
st.subheader("Staff Roster Grid")
st.caption("Type a team name or leave status to lock cells. Empty/cleared cells resolve to `None`.")

if "df_staff" not in st.session_state:
  if ROSTER_CSV.exists():
    try:
      df_staff_loaded = pd.read_csv(ROSTER_CSV, dtype=str)
      for person in staff_members:
        if not (df_staff_loaded["Staff"] == person).any():
          new_row = {"Staff": person}
          for d in dates:
            new_row[d] = None
          df_staff_loaded = pd.concat([df_staff_loaded, pd.DataFrame([new_row])], ignore_index=True)
      for d in dates:
        if d not in df_staff_loaded.columns:
          df_staff_loaded[d] = None
      
      # Convert artifact strings back to proper None values on load
      df_staff_loaded = df_staff_loaded.replace(["nan", "None", "NaN", "NoneType", ""], np.nan)
      st.session_state.df_staff = df_staff_loaded[["Staff"] + dates]
    except Exception:
      st.session_state.df_staff = None

  if "df_staff" not in st.session_state or st.session_state.df_staff is None or len(dates) == 0:
    initial_data = {"Staff": staff_members}
    for d in dates:
      initial_data[d] = [None for _ in staff_members]
    st.session_state.df_staff = pd.DataFrame(initial_data)

# Normalize empty or artifact values to None for grid view
for d in dates:
  if d in st.session_state.df_staff.columns:
    st.session_state.df_staff[d] = st.session_state.df_staff[d].replace(["nan", "None", "NaN", "NoneType", ""], np.nan)

edited_staff_df = st.data_editor(
    st.session_state.df_staff, num_rows="fixed", use_container_width=True, key="staff_editor"
)

# Constant smart auto-save for staff roster grid with state diffing
if not edited_staff_df.equals(st.session_state.df_staff):
  st.session_state.df_staff = edited_staff_df.copy()
  df_to_save = edited_staff_df.copy()
  for d in dates:
    if d in df_to_save.columns:
      df_to_save[d] = df_to_save[d].replace(["nan", "None", "NaN", "NoneType", ""], np.nan)
  df_to_save.to_csv(ROSTER_CSV, index=False)

# --- 4. EXECUTION & CONTROLS ---
st.markdown("---")
col_btn1, col_btn2 = st.columns([1, 5])
with col_btn1:
  run_solver = st.button("🚀 Run Solver", type="primary", use_container_width=True)
with col_btn2:
  clear_auto = st.button("Clear Auto-Filled Values")

if clear_auto:
  reset_data = {"Staff": staff_members}
  for d in dates:
    col_vals = []
    for person in staff_members:
      val = st.session_state.df_staff.loc[st.session_state.df_staff["Staff"] == person, d].values[0]
      if pd.notna(val) and "(auto)" in str(val):
        col_vals.append(None)
      else:
        col_vals.append(val)
    reset_data[d] = col_vals
  
  df_reset = pd.DataFrame(reset_data)
  st.session_state.df_staff = df_reset
  df_reset.to_csv(ROSTER_CSV, index=False)
  st.rerun()

if run_solver:
  # Capture true user locks safely ignoring None/NaN/empty values
  current_locks = {}
  for _, row in st.session_state.df_staff.iterrows():
    person = row["Staff"]
    current_locks[person] = {}
    for d in dates:
      if d in row:
        val = row[d]
        
        if pd.isna(val) or val is None:
          continue
          
        val_str = str(val).strip()
        
        if val_str.lower() in ["nan", "none", ""]:
          continue
        if "(auto)" in val_str:
          continue
          
        if val_str in team_options:
          current_locks[person][d] = val_str

  # Build team requirements and call requirements dictionaries
  team_requirements = {}
  call_requirements = {}

  for d in dates:
    day_reqs = {}
    for _, row in st.session_state.df_teams.iterrows():
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
            solved_val = roster_sched.teams_table[person].get(d, None)
            if solved_val:
              column_values.append(f"{solved_val} (auto)")
            else:
              column_values.append(None)
        new_grid_data[d] = column_values

      st.session_state.df_staff = pd.DataFrame(new_grid_data)
      
      # Save solved results back to disk automatically
      df_to_save = st.session_state.df_staff.copy()
      for d in dates:
        if d in df_to_save.columns:
          df_to_save[d] = df_to_save[d].replace(["nan", "None", "NaN", "NoneType", ""], np.nan)
      df_to_save.to_csv(ROSTER_CSV, index=False)

      st.success("Roster optimized successfully, auto-filled values mapped to None where empty, and changes saved!")
      st.rerun()
    else:
      st.error(
          "No feasible solution found with current manual locks. Check your "
          "constraints or conflicting selections."
      )

  except Exception as e:
    st.error(f"Error running model: {e}")