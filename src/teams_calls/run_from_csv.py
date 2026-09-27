from datetime import datetime, timedelta
import csv
import random
from roster import Roster  # Assuming your Roster class is in roster.py

def main():
    start_date = '1/11/2026'
    end_date = '30/11/2026'

    leave_buffers = [1, 0]
    blockout_buffers = [1, 0]
    min_call_interval = 2
    max_teams_per_week = 1
    max_solve_time_seconds = 120

    # ---------------------------------------------------------
    # READ INPUT CSV FILES & EXTRACT DYNAMIC LISTS
    # ---------------------------------------------------------
    
    # 1. Read Team Parameters (Sacrificability, Min Requirements, Shittiness)
    team_sacrificability = {}
    team_requirements_min = {}
    team_shittiness = {}

    with open('input_team_parameters.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            team_name = row['Team'].strip()
            if not team_name:
                continue
            
            # Sacrificability
            if row.get('#sacrificability') is not None and row['#sacrificability'].strip() != '':
                team_sacrificability[team_name] = int(row['#sacrificability'])
                
            # Minimum Team Requirements
            if row.get('#minimum') is not None and row['#minimum'].strip() != '':
                min_val = int(row['#minimum'])
                if min_val > 0:
                    team_requirements_min[team_name] = min_val
                    
            # Team Shittiness
            if row.get('#shittiness') is not None and row['#shittiness'].strip() != '':
                team_shittiness[team_name] = int(row['#shittiness'])

    # 2. Read Leaves & Blockouts & Dynamically extract staff members
    leaves_blockouts = {}
    staff_members = []
    with open('input_leaves_blockouts.csv', 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        date_cols = header[1:]
        for row in reader:
            person = row[0].strip()
            if not person:
                continue
            staff_members.append(person)
            for i, d in enumerate(date_cols):
                status = row[i+1]
                if status != '-1':
                    leaves_blockouts.setdefault(person, []).append((d, status))

    # 3. Read Team Requirements & Dynamically extract team options
    team_requirements = {}
    team_options_set = set()
    with open('input_team_requirements.csv', 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        date_cols = header[1:]
        for row in reader:
            team_name = row[0].strip()
            if not team_name:
                continue
            team_options_set.add(team_name)
            for i, d in enumerate(date_cols):
                val = int(row[i+1])
                if val > 0:
                    team_requirements.setdefault(date_cols[i], {})[team_name] = val

    # Ensure special system options are always included in team_options
    team_options_set.add('ps_cover')
    team_options_set.add('leave')
    team_options = list(team_options_set)

    # 4. Read Team Locks
    teams = {}
    with open('input_teams.csv', 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        date_cols = header[1:]
        for row in reader:
            person = row[0].strip()
            if not person:
                continue
            for i, d in enumerate(date_cols):
                val = row[i+1].strip()
                if val:
                    teams.setdefault(person, {})[date_cols[i]] = val

    # 5. Read Call Locks
    calls = {}
    with open('input_calls.csv', 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        date_cols = header[1:]
        for row in reader:
            person = row[0].strip()
            if not person:
                continue
            for i, d in enumerate(date_cols):
                val = int(row[i+1])
                if val != -1:
                    calls.setdefault(person, {})[date_cols[i]] = val

    # 6. Read Call Requirements
    call_requirements = {}
    with open('input_call_requirements.csv', 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        date_cols = header[1:]
        row = next(reader)
        for i, d in enumerate(date_cols):
            call_requirements[date_cols[i]] = int(row[i+1])

    start_dt = datetime.strptime(start_date, '%d/%m/%Y')
    end_dt = datetime.strptime(end_date, '%d/%m/%Y')
    dates = [(start_dt + timedelta(days=i)).strftime('%d/%m/%Y') for i in range((end_dt - start_dt).days + 1)]

    # ---------------------------------------------------------
    # INITIALIZE AND SOLVE MODEL
    # ---------------------------------------------------------
    print("\nInitializing Roster optimization model...")
    roster_sched = Roster(
        start_date=start_date,
        end_date=end_date,
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
        max_teams_per_week=max_teams_per_week,
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
                    
                    team_val = roster_sched.teams_table[person].get(d_str, 'Unassigned')
                    if team_val != 'leave' and d_obj.weekday() >= 5:
                        team_val = ''
                    
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