from datetime import datetime, timedelta
import csv
from roster import Roster

def main():
    # ---------------------------------------------------------
    # CONFIGURABLE PARAMETERS
    # ---------------------------------------------------------
    # leave_buffers = [1, 0]
    # blockout_buffers = [1, 0]
    # min_call_interval = 2
    # max_teams_per_week = 1
    # max_solve_time_seconds = 120

    # ---------------------------------------------------------
    # 1. READ LEAVES & BLOCKOUTS & EXTRACT DATES & STAFF DYNAMICALLY
    # ---------------------------------------------------------
    leaves_blockouts = {}
    staff_members = []
    
    with open('input_leaves_blockouts.csv', 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        dates = [d.strip() for d in header[1:] if d.strip()] # Inferred date list

        for row in reader:
            person = row[0].strip()
            if not person:
                continue
            staff_members.append(person)
            for i, d in enumerate(dates):
                if i + 1 < len(row):
                    status = row[i + 1]
                    if status != '-1':
                        leaves_blockouts.setdefault(person, []).append((dates[i], status))

    # ---------------------------------------------------------
    # 2. READ REMAINING CSV INPUT FILES
    # ---------------------------------------------------------
    
    # Team Parameters
    team_sacrificability = {}
    team_requirements_min = {}
    team_shittiness = {}

    # General Parameters
    leave_buffers = [None, None]
    blockout_buffers = [None, None]
    min_call_interval = None
    max_solve_time_seconds = None

    with open('input_general_parameters.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            team_name = row['#team'].strip()
            if row.get('#sacrificability') is not None and row['#sacrificability'].strip() != '':
                if not team_name:
                    continue
                team_sacrificability[team_name] = int(row['#sacrificability'])
            if row.get('#minimum') is not None and row['#minimum'].strip() != '':
                if not team_name:
                    continue
                min_val = int(row['#minimum'])
                if min_val > 0:
                    team_requirements_min[team_name] = min_val
            if row.get('#shittiness') is not None and row['#shittiness'].strip() != '':
                if not team_name:
                    continue
                team_shittiness[team_name] = int(row['#shittiness'])

            if row.get('#al_buffer_before') is not None and row['#al_buffer_before'].strip() != '':
                leave_buffers[0] = int(row['#al_buffer_before'])
            if row.get('#al_buffer_after') is not None and row['#al_buffer_after'].strip() != '':
                leave_buffers[1] = int(row['#al_buffer_after'])
            if row.get('#bl_buffer_before') is not None and row['#bl_buffer_before'].strip() != '':
                blockout_buffers[0] = int(row['#bl_buffer_before'])
            if row.get('#bl_buffer_after') is not None and row['#bl_buffer_after'].strip() != '':
                blockout_buffers[1] = int(row['#bl_buffer_after'])
            if row.get("#min_call_interval") is not None and row['#min_call_interval'].strip() != '':
                min_call_interval = int(row['#min_call_interval'])
            if row.get("#max_solve_time_seconds") is not None and row['#max_solve_time_seconds'].strip() != '':
                max_solve_time_seconds = int(row['#max_solve_time_seconds'])

    # Team Requirements & Options
    team_requirements = {}
    team_options_set = set()
    with open('input_team_requirements.csv', 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader) # skip header
        for row in reader:
            team_name = row[0].strip()
            if not team_name:
                continue
            team_options_set.add(team_name)
            for i, d in enumerate(dates):
                if i + 1 < len(row):
                    val = int(row[i + 1])
                    if val > 0:
                        team_requirements.setdefault(dates[i], {})[team_name] = val

    team_options_set.add('ps_cover')
    team_options_set.add('leave')
    team_options = list(team_options_set)

    # Team Locks
    teams = {}
    with open('input_teams.csv', 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            person = row[0].strip()
            if not person:
                continue
            for i, d in enumerate(dates):
                if i + 1 < len(row):
                    val = row[i + 1].strip()
                    if val:
                        teams.setdefault(person, {})[dates[i]] = val

    # Call Locks
    calls = {}
    with open('input_calls.csv', 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            person = row[0].strip()
            if not person:
                continue
            for i, d in enumerate(dates):
                if i + 1 < len(row):
                    val_str = row[i + 1].strip()
                    # Skip if empty or marked as -1
                    if val_str and val_str != '-1':
                        val = int(val_str)
                        calls.setdefault(person, {})[dates[i]] = val

    # Call Requirements
    call_requirements = {}
    with open('input_call_requirements.csv', 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)
        row = next(reader)
        for i, d in enumerate(dates):
            if i + 1 < len(row):
                call_requirements[dates[i]] = int(row[i + 1])

    # ---------------------------------------------------------
    # INITIALIZE AND SOLVE MODEL
    # ---------------------------------------------------------
    print(f"\nInitializing Roster optimization model with {len(dates)} days between ({dates[0]} to {dates[-1]})...")
    
    roster_sched = Roster(
        dates=dates,
        persons=staff_members,
        team_requirements=team_requirements,
        team_requirements_min=team_requirements_min,
        team_options=team_options,
        team_sacrificability=team_sacrificability,
        teams=teams,
        calls=calls,
        call_requirements=call_requirements,
        leaves_blockouts=leaves_blockouts,
        leave_buffers=leave_buffers,  
        blockout_buffers=blockout_buffers,
        min_call_interval=min_call_interval,
        team_shittiness=team_shittiness,
        max_solve_time_seconds=max_solve_time_seconds
    )

    print("Solving roster...")
    success = roster_sched.solve()
    
    if success:
        print("\n--- Roster Solved Successfully! Exporting Consolidated CSV file... ---\n")
        csv_filename = "output_roster.csv"
        with open(csv_filename, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            header = ['Staff'] + dates
            writer.writerow(header)
            
            for person in staff_members:
                row = [person]
                for idx, d_str in enumerate(dates):
                    d_obj = datetime.strptime(d_str, '%d/%m/%Y')
                    
                    team_val = ''
                    if person in roster_sched.team_vars and idx in roster_sched.team_vars[person]:
                        var = roster_sched.team_vars[person][idx]
                        val_idx = roster_sched.solver.Value(var)
                        team_val = roster_sched.idx_to_team.get(val_idx, 'Unassigned')
                    else:
                        # Weekends or unassigned days default nicely here
                        team_val = '' if d_obj.weekday() >= 5 else 'Unassigned'
                    
                    if team_val != 'leave' and d_obj.weekday() >= 5:
                        team_val = ''
                    
                    # Query call status safely
                    is_on_call = False
                    if person in roster_sched.call_vars and idx in roster_sched.call_vars[person]:
                        is_on_call = bool(roster_sched.solver.Value(roster_sched.call_vars[person][idx]))
                    
                    if is_on_call:
                        combined_val = f"{team_val} (call)" if team_val else "(call)"
                    else:
                        combined_val = team_val
                        
                    row.append(combined_val)
                    
                writer.writerow(row)
                
        print(f"Consolidated schedule successfully exported to '{csv_filename}'")
    else:
        print("No feasible solution found.")

if __name__ == '__main__':
    main()