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

        for row in reader:
            person = row[0].strip()
            if not person:
                continue
            staff_members.append(person)
            for datestr, status in zip(header[1:], row[1:]):
                d = datestr.strip()
                status_val = status.strip()
                if d and status_val and status_val != '-1':
                    leaves_blockouts.setdefault(person, []).append((d, status_val))

    daily_leave_counts = {}
    for person, entries in leaves_blockouts.items():
        for datestr, status in entries:
            if status.strip().upper() == 'L':
                daily_leave_counts[datestr] = daily_leave_counts.get(datestr, 0) + 1

    for datestr, count in daily_leave_counts.items():
        if count > 2:
            raise ValueError(f"Leave Policy Violation: On date {datestr}, there are {count} staff members on leave (maximum allowed is 2).")

    # ---------------------------------------------------------
    # 2. READ REMAINING CSV INPUT FILES
    # ---------------------------------------------------------
    
    # Team Parameters
    team_sacrificability = {}
    team_quota_min = {}
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
                    team_quota_min[team_name] = min_val
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
    team_quota = {}
    team_options_set = {'leave'}
    with open('input_team_requirements.csv', 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            team_name = row[0].strip()
            if not team_name:
                continue
            team_options_set.add(team_name)

            for datestr, val in zip(header[1:], row[1:]):
                d = datestr.strip()
                v = val.strip()
                if d and v:
                    try:
                        int_val = int(v)
                        if int_val > 0:
                            team_quota.setdefault(d, {})[team_name] = int_val
                    except ValueError:
                        pass
    team_options = list(team_options_set)

    # Team Locks
    teams = {}
    with open('input_teams.csv', 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            person = row[0].strip()
            if not person:
                continue
            for datestr, val in zip(header[1:], row[1:]):
                d = datestr.strip()
                v = val.strip()
                if d and v:
                    teams.setdefault(person, {})[d] = v

    # Call Locks
    calls = {}
    with open('input_calls.csv', 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            person = row[0].strip()
            if not person:
                continue
            for datestr, val_str in zip(header[1:], row[1:]):
                d = datestr.strip()
                v = val_str.strip()
                if d and v and v != '-1':
                    try:
                        val = int(v)
                        calls.setdefault(person, {})[d] = val
                    except ValueError:
                        pass

    # Call Requirements
    call_requirements = {}
    with open('input_call_requirements.csv', 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            for datestr, val_str in zip(header[1:], row[1:]):
                d = datestr.strip()
                v = val_str.strip()
                if d and v:
                    try:
                        call_requirements[d] = int(v)
                    except ValueError:
                        pass

    # ---------------------------------------------------------
    # INITIALIZE AND SOLVE MODEL
    # ---------------------------------------------------------
    # print(f"\nInitializing Roster optimization model with {len(dates)} days between ({dates[0]} to {dates[-1]})...")
    print(f"\nInitializing Roster optimization model")
    print(f"Calls: {calls}")
    print(f"Teams: {teams}")
    
    roster_sched = Roster(
        persons=staff_members,
        team_quota=team_quota,
        team_quota_min=team_quota_min,
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
            header_out = ['Staff'] + roster_sched.dates
            writer.writerow(header_out)
            
            for person in staff_members:
                row_out = [person]
                for idx, d_str in enumerate(roster_sched.dates):
                    d_obj = datetime.strptime(d_str, '%d/%m/%Y')
                    
                    team_val = ''
                    if person in roster_sched.team_vars and idx in roster_sched.team_vars[person]:
                        var = roster_sched.team_vars[person][idx]
                        val_idx = roster_sched.solver.Value(var)
                        team_val = roster_sched.idx_to_team.get(val_idx, 'Unassigned')
                    else:
                        team_val = '' if d_obj.weekday() >= 5 else 'Unassigned'
                    
                    if team_val != 'leave' and d_obj.weekday() >= 5:
                        team_val = ''
                    
                    is_on_call = False
                    if person in roster_sched.call_vars and idx in roster_sched.call_vars[person]:
                        is_on_call = bool(roster_sched.solver.Value(roster_sched.call_vars[person][idx]))
                    
                    if is_on_call:
                        combined_val = f"{team_val} (call)" if team_val else "(call)"
                    else:
                        combined_val = team_val
                        
                    row_out.append(combined_val)
                    
                writer.writerow(row_out)
                
        print(f"Consolidated schedule successfully exported to '{csv_filename}'")
    else:
        print("No feasible solution file found.")

if __name__ == '__main__':
    main()