from datetime import datetime
import csv
import os
from roster import RosterInputs, RosterConfig, TeamSpec, solve_roster, to_date, PS_COVER, LEAVE

def main():
    # 1. Read General Parameters & Team Specs
    leave_buffers = [1, 0]
    blockout_buffers = [1, 0]
    min_call_interval = 2
    max_solve_time_seconds = 10.0
    one_team_per_week = "soft"
    team_specs_map = {}
    
    if os.path.exists('input_general_parameters.csv'):
        with open('input_general_parameters.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                team_name = (row.get('#team') or '').strip()
                if team_name:
                    team_specs_map[team_name] = TeamSpec(
                        name=team_name,
                        allowed_shortfall=int(row['#allowed_shortfall']) if row.get('#allowed_shortfall') and row['#allowed_shortfall'].strip() else 0,
                        shortfall_cost=int(row['#shortfall_cost']) if row.get('#shortfall_cost') and row['#shortfall_cost'].strip() else 100,
                        allowed_surplus=int(row['#allowed_surplus']) if row.get('#allowed_surplus') and row['#allowed_surplus'].strip() else None,
                        surplus_cost=int(row['#surplus_cost']) if row.get('#surplus_cost') and row['#surplus_cost'].strip() else 0,
                        shittiness=int(row['#shittiness']) if row.get('#shittiness') and row['#shittiness'].strip() else 0,
                    )
                
                if row.get('#al_buffer_before') and row['#al_buffer_before'].strip():
                    leave_buffers[0] = int(row['#al_buffer_before'])
                if row.get('#al_buffer_after') and row['#al_buffer_after'].strip():
                    leave_buffers[1] = int(row['#al_buffer_after'])
                if row.get('#bl_buffer_before') and row['#bl_buffer_before'].strip():
                    blockout_buffers[0] = int(row['#bl_buffer_before'])
                if row.get('#bl_buffer_after') and row['#bl_buffer_after'].strip():
                    blockout_buffers[1] = int(row['#bl_buffer_after'])
                if row.get('#min_call_interval') and row['#min_call_interval'].strip():
                    min_call_interval = int(row['#min_call_interval'])
                if row.get('#max_solve_time_seconds') and row['#max_solve_time_seconds'].strip():
                    max_solve_time_seconds = float(row['#max_solve_time_seconds'])
                if row.get('#one_team_per_week') and row['#one_team_per_week'].strip():
                    one_team_per_week = row['#one_team_per_week'].strip()

    # 2. Collect dates and staff data from CSV files to infer ranges
    all_dates = set()
    schedule_dates = set()
    staff_members = set()

    leaves_blockouts = {}
    if os.path.exists('input_leaves_blockouts.csv'):
        with open('input_leaves_blockouts.csv', 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
            date_headers = [to_date(h) for h in header[1:] if h.strip()]
            all_dates.update(date_headers)
            for row in reader:
                if not row or not row[0].strip():
                    continue
                person = row[0].strip()
                staff_members.add(person)
                for d, status in zip(date_headers, row[1:]):
                    s = status.strip()
                    if s and s != '-1':
                        leaves_blockouts.setdefault(person, []).append((d, s))

    team_demand = {}
    team_names_set = set(team_specs_map.keys())
    if os.path.exists('input_team_requirements.csv'):
        with open('input_team_requirements.csv', 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
            date_headers = [to_date(h) for h in header[1:] if h.strip()]
            all_dates.update(date_headers)
            schedule_dates.update(date_headers)
            for row in reader:
                if not row or not row[0].strip():
                    continue
                team_name = row[0].strip()
                team_names_set.add(team_name)
                for d, val in zip(date_headers, row[1:]):
                    v = val.strip()
                    if v:
                        try:
                            iv = int(v)
                            if iv > 0:
                                team_demand.setdefault(d, {})[team_name] = iv
                        except ValueError:
                            pass

    call_demand = {}
    if os.path.exists('input_call_requirements.csv'):
        with open('input_call_requirements.csv', 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
            date_headers = [to_date(h) for h in header[1:] if h.strip()]
            all_dates.update(date_headers)
            schedule_dates.update(date_headers)
            for row in reader:
                for d, val in zip(date_headers, row[1:]):
                    v = val.strip()
                    if v:
                        try:
                            call_demand[d] = int(v)
                        except ValueError:
                            pass

    teams_locks = {}
    if os.path.exists('input_teams.csv'):
        with open('input_teams.csv', 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
            date_headers = [to_date(h) for h in header[1:] if h.strip()]
            all_dates.update(date_headers)
            for row in reader:
                if not row or not row[0].strip():
                    continue
                person = row[0].strip()
                staff_members.add(person)
                for d, val in zip(date_headers, row[1:]):
                    v = val.strip()
                    if v:
                        teams_locks.setdefault(person, {})[d] = v

    call_locks = {}
    if os.path.exists('input_calls.csv'):
        with open('input_calls.csv', 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)
            date_headers = [to_date(h) for h in header[1:] if h.strip()]
            all_dates.update(date_headers)
            for row in reader:
                if not row or not row[0].strip():
                    continue
                person = row[0].strip()
                staff_members.add(person)
                for d, val in zip(date_headers, row[1:]):
                    v = val.strip()
                    if v and v != '-1':
                        try:
                            call_locks.setdefault(person, {})[d] = int(v)
                        except ValueError:
                            pass

    # Ensure PS_COVER spec exists if not explicitly set in general parameters
    if PS_COVER not in team_names_set:
        team_names_set.add(PS_COVER)
        
    teams_list = []
    for name in sorted(team_names_set):
        if name in team_specs_map:
            teams_list.append(team_specs_map[name])
        else:
            teams_list.append(TeamSpec(name=name))

    if not all_dates:
        print("Error: No dates found in any CSV headers.")
        return

    start_date = min(all_dates)
    end_date = max(all_dates)
    schedule_start = min(schedule_dates) if schedule_dates else start_date
    schedule_end = max(schedule_dates) if schedule_dates else end_date

    print(f"\nInferred date range: {start_date.strftime('%d/%m/%Y')} to {end_date.strftime('%d/%m/%Y')}")
    print(f"Inferred schedule range: {schedule_start.strftime('%d/%m/%Y')} to {schedule_end.strftime('%d/%m/%Y')}")

    # 3. Build RosterInputs for roster_2.py
    inputs = RosterInputs.from_raw(
        start=start_date,
        end=end_date,
        schedule_start=schedule_start,
        schedule_end=schedule_end,
        persons=sorted(list(staff_members)),
        teams=teams_list,
        call_demand=call_demand,
        team_demand=team_demand,
        leaves_blockouts=leaves_blockouts,
        call_locks=call_locks,
        team_locks=teams_locks,
    )

    cfg = RosterConfig(
        min_call_interval=min_call_interval,
        leave_buffers=tuple(leave_buffers),
        blockout_buffers=tuple(blockout_buffers),
        one_team_per_week=one_team_per_week,
        max_solve_time_seconds=max_solve_time_seconds,
    )

    print("Initializing and solving roster model...")
    solution = solve_roster(inputs, cfg=cfg, log=True)

    if not solution.ok:
        print(f"Solver status: {solution.status}. No solution found.")
        return

    print("\n--- Exporting Consolidated Roster ---")
    date_strs = [d.strftime('%d/%m/%Y') for d in inputs.dates]
    with open("output_roster.csv", mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Staff'] + date_strs)
        for person in inputs.persons:
            row_out = [person]
            for d in inputs.dates:
                team_val = solution.teams.get(person, {}).get(d, '')
                if team_val == LEAVE:
                    team_val = 'leave'
                elif team_val is None:
                    team_val = ''
                
                if not cfg.is_team_day(d) and team_val != 'leave':
                    team_val = ''

                is_on_call = bool(solution.calls.get(person, {}).get(d, 0))

                if team_val and is_on_call:
                    combined = f"{team_val} (call)"
                elif is_on_call:
                    combined = "(call)"
                else:
                    combined = team_val
                row_out.append(combined)
            writer.writerow(row_out)

    print("Consolidated schedule successfully exported to 'output_roster.csv'")

if __name__ == '__main__':
    main()