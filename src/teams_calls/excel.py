from datetime import datetime, timedelta
import csv
import random
from roster import Roster  # Assuming your Roster class is in roster.py

def main():
    start_date = '1/11/2026'
    end_date = '30/11/2026'
    
    start_dt = datetime.strptime(start_date, '%d/%m/%Y')
    end_dt = datetime.strptime(end_date, '%d/%m/%Y')
    dates = [(start_dt + timedelta(days=i)).strftime('%d/%m/%Y') for i in range((end_dt - start_dt).days + 1)]

    team_options = [
        'team_subobs',  'team_ds',  
        'team_9ab', 'team_b1', 'team_bg', 'team_go',  
        'ps_cover', 'leave',
    ]
    
    team_sacrificability = {
        'team_subobs': 12, 
        'team_ds': 14, 
        'team_9ab': 5,
        'team_b1': 1,
        'team_bg': 1,
        'team_go': 1, 
        'ps_cover': 0,
        'leave': 0,
    }

    daily_team_requirement = {
        'team_subobs': 3,
        'team_ds': 2,
        'team_9ab': 2,
        'team_b1': 1,
        'team_bg': 1,
        'team_go': 1,
        'ps_cover': 1
    }

    min_team_requirements = {
        'team_subobs': 1,
        'team_ds': 1,
        'team_9ab': 1,
        'team_b1': 1,
        'team_bg': 1,
        'team_go': 1,
    }

    staff_members = [
        'Alpha', 'Bravo', 'Charlie', 'Delta', 
        'Echo', 'Foxtrot', 'Golf', 'Hotel', 
        'India', 'Juliet', 'Kilo'
    ]

    blockouts_per_month = 8
    leave_buffers = [1, 0]
    blockout_buffers = [1, 0]
    call_interval = 2
    max_teams_per_week = 1

    max_solve_time_seconds = 120

    # Read Leaves & Blockouts -> Expected: {person: [(date, status), ...]}
    leaves_blockouts = {}
    with open('input_leaves_blockouts.csv', 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        date_cols = header[1:]
        for row in reader:
            person = row[0]
            if person == '':
                continue
            for i, d in enumerate(date_cols):
                status = row[i+1]
                if status != '-1':
                    # convert matrix to only non-null instances
                    leaves_blockouts.setdefault(person, []).append((d, status))

    # Read Team Locks -> Expected: {person: {date: team_name}}
    teams = {}
    with open('input_teams.csv', 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        date_cols = header[1:]
        for row in reader:
            person = row[0]
            if person == '':
                continue
            for i, d in enumerate(date_cols):
                val = row[i+1]
                if val != '':
                    teams.setdefault(person, {})[date_cols[i]] = val

    # Read Call Locks -> Expected: {person: {date: val}}
    calls = {}
    with open('input_calls.csv', 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        date_cols = header[1:]
        for row in reader:
            person = row[0]
            if person == '':
                continue
            for i, d in enumerate(date_cols):
                val = int(row[i+1])
                if val != -1:
                    calls.setdefault(person, {})[date_cols[i]] = val

    # Read Team Requirements -> Expected: {date_str: {team_name: count}}
    team_requirements = {}
    with open('input_team_requirements.csv', 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        date_cols = header[1:]
        for row in reader:
            team_name = row[0]
            if team_name == '':
                continue
            for i, d in enumerate(date_cols):
                val = int(row[i+1])
                if val > 0:
                    team_requirements.setdefault(date_cols[i], {})[team_name] = val

    # Read Call Requirements -> Expected: {date_str: count}
    call_requirements = {}
    with open('input_call_requirements.csv', 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        date_cols = header[1:]
        row = next(reader)
        for i, d in enumerate(date_cols):
            call_requirements[date_cols[i]] = int(row[i+1])

    # ---------------------------------------------------------
    # STEP 3: INITIALIZE AND SOLVE MODEL
    # ---------------------------------------------------------
    print("\nInitializing Roster optimization model...")
    roster_sched = Roster(
        start_date=start_date,
        end_date=end_date,
        persons=staff_members,
        team_requirements=team_requirements,
        team_options=team_options,
        team_sacrificability=team_sacrificability,
        teams=teams,
        calls=calls,
        call_requirements=call_requirements,
        leaves_blockouts=leaves_blockouts,
        leave_buffers=leave_buffers,  
        blockout_buffers=blockout_buffers,
        call_interval=call_interval,
        max_teams_per_week=max_teams_per_week,
        min_team_requirements=min_team_requirements,
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
                    else:
                        team_val = team_val.replace("team_", "")
                    
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