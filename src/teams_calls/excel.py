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

    # # Temporary per-person tracking for generation logic
    # temp_leaves_blockouts = {person: [] for person in staff_members}
    # daily_leave_counts = {d: 0 for d in dates}
    # max_daily_leave = 2  # Strict cap of 2

    # for person in staff_members:
    #     assigned_person = False
    #     attempts = 0
    #     while not assigned_person and attempts < 500:
    #         attempts += 1
    #         temp_leaves = []
    #         temp_daily_counts = daily_leave_counts.copy()
            
    #         def add_block(block_dates):
    #             if any(temp_daily_counts[d] >= max_daily_leave for d in block_dates):
    #                 return False
    #             if any(d in [e[0] for e in temp_leaves] for d in block_dates):
    #                 return False
    #             for d in block_dates:
    #                 temp_leaves.append((d, 'L'))
    #                 temp_daily_counts[d] += 1
    #             return True

    #         start_idx1 = random.randint(0, len(dates) - 4)
    #         b1 = [dates[start_idx1 + i] for i in range(4)]
    #         if not add_block(b1):
    #             continue
                
    #         single_success = True
    #         existing_assigned = [e[0] for e in temp_leaves]
    #         remaining_pool = [d for d in dates if d not in existing_assigned and temp_daily_counts[d] < max_daily_leave]
            
    #         if len(remaining_pool) < 2:
    #             continue
                
    #         chosen_singles = random.sample(remaining_pool, 2)
    #         for d in chosen_singles:
    #             if not add_block([d]):
    #                 single_success = False
    #                 break
            
    #         if single_success:
    #             for d, s in temp_leaves:
    #                 temp_leaves_blockouts[person].append((d, s))
    #                 daily_leave_counts[d] += 1
    #             assigned_person = True

    #     temp_leaves_blockouts[person].sort(key=lambda x: datetime.strptime(x[0], '%d/%m/%Y'))

    # # Fallback single leave generation strictly respects max_daily_leave
    # for d in dates:
    #     if daily_leave_counts[d] < 1:
    #         eligible_staff = [
    #             p for p in staff_members 
    #             if len([e for e in temp_leaves_blockouts[p] if e[1] == 'L']) < 9 
    #             and d not in [e[0] for e in temp_leaves_blockouts[p]]
    #             and daily_leave_counts[d] < max_daily_leave
    #         ]
    #         if eligible_staff:
    #             p = random.choice(eligible_staff)
    #             temp_leaves_blockouts[p].append((d, 'L'))
    #             temp_leaves_blockouts[p].sort(key=lambda x: datetime.strptime(x[0], '%d/%m/%Y'))
    #             daily_leave_counts[d] += 1

    # for person in staff_members:
    #     existing_dates = [entry[0] for entry in temp_leaves_blockouts[person]]
    #     remaining_dates = [d for d in dates if d not in existing_dates]
    #     blockout_dates = random.sample(remaining_dates, min(blockouts_per_month, len(remaining_dates)))
        
    #     for d in blockout_dates:
    #         temp_leaves_blockouts[person].append((d, 'B'))
            
    #     temp_leaves_blockouts[person].sort(key=lambda x: datetime.strptime(x[0], '%d/%m/%Y'))

    # raw_lb = {d: {p: '0' for p in staff_members} for d in dates}
    # for person, entries in temp_leaves_blockouts.items():
    #     for d, status in entries:
    #         raw_lb[d][person] = status

    # # ---------------------------------------------------------
    # # STEP 1: GENERATE & WRITE RAW INPUTS TO CSV FILES (Flipped Layout)
    # # ---------------------------------------------------------
    # print("Writing generated inputs to CSV files (Dates as columns)...")

    # # 1. Leaves & Blockouts CSV (Staff on rows, Dates as columns)
    # with open('input_leaves_blockouts.csv', 'w', newline='', encoding='utf-8') as f:
    #     writer = csv.writer(f)
    #     writer.writerow(['Staff'] + dates)
    #     for person in staff_members:
    #         writer.writerow([person] + [raw_lb[d][person] for d in dates])

    # # 2. Team Locks CSV (Staff on rows, Dates as columns)
    # with open('input_teams.csv', 'w', newline='', encoding='utf-8') as f:
    #     writer = csv.writer(f)
    #     writer.writerow(['Staff'] + dates)
    #     for person in staff_members:
    #         writer.writerow([person] + ['' for _ in dates])

    # # 3. Call Locks CSV (Staff on rows, Dates as columns)
    # with open('input_calls.csv', 'w', newline='', encoding='utf-8') as f:
    #     writer = csv.writer(f)
    #     writer.writerow(['Staff'] + dates)
    #     for person in staff_members:
    #         writer.writerow([person] + [-1 for _ in dates])

    # # 4. Team Requirements CSV (Teams on rows, Dates as columns)
    # req_team_keys = list(daily_team_requirement.keys())
    # with open('input_team_requirements.csv', 'w', newline='', encoding='utf-8') as f:
    #     writer = csv.writer(f)
    #     writer.writerow(['Team'] + dates)
    #     for team_name in req_team_keys:
    #         row = [team_name]
    #         for d_str in dates:
    #             d_obj = datetime.strptime(d_str, '%d/%m/%Y')
    #             if d_obj.weekday() < 5:
    #                 row.append(daily_team_requirement[team_name])
    #             else:
    #                 row.append(0)
    #         writer.writerow(row)

    # # 5. Call Requirements CSV (Metric row, Dates as columns)
    # with open('input_call_requirements.csv', 'w', newline='', encoding='utf-8') as f:
    #     writer = csv.writer(f)
    #     writer.writerow(['Metric'] + dates)
    #     call_row = ['Call Requirement']
    #     for d_str in dates:
    #         d_obj = datetime.strptime(d_str, '%d/%m/%Y')
    #         val = 2 if d_obj.weekday() >= 5 else 1
    #         call_row.append(val)
    #     writer.writerow(call_row)

    # ---------------------------------------------------------
    # STEP 2: READ INPUTS BACK FROM CSV FILES 
    # ---------------------------------------------------------
    print("Reading inputs back from CSV files...")

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
    print(teams)

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
    print(calls)

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