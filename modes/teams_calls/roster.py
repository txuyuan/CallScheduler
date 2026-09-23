from datetime import datetime, timedelta
import time
from ortools.sat.python import cp_model

class ObjectiveLogger(cp_model.CpSolverSolutionCallback):
    def __init__(self):
        super().__init__()
        self.start_time = time.time()
        self.solution_count = 0

    def on_solution_callback(self):
        self.solution_count += 1
        elapsed_time = time.time() - self.start_time
        obj_value = self.ObjectiveValue()
        print(f"[Solver Update] Solution #{self.solution_count} found at {elapsed_time:.2f}s | Total Penalty Value: {obj_value}")


class Roster:
    def __init__(
        self,
        start_date='01/01/2026',
        end_date='31/01/2026',
        persons=None,
        team_requirements=None,
        team_options=None,
        team_sacrificability=None, 
        team=None,
        call_requirements=None,
        calls=None,
        leaves_blockouts=None,
        leave_buffers=None,
        blockout_buffers=None,
        call_interval=2,
        max_teams_per_week=1,
        min_team_requirements=None,
        max_solve_time_seconds=None,
    ):
        self.start_date = start_date
        self.end_date = end_date
        self.team_requirements = team_requirements or {}
        self.team_options = team_options or ['team_ds', 'leave', 'team_cos', 'team_c', 'ps_cover']
        
        self.team_sacrificability = team_sacrificability or {
            'team_ds': 1,
            'team_cos': 2,
            'team_c': 3,
            'ps_cover': 4,
            'leave': 5
        }

        self.persons = persons or []
        self.team = team or {}  # User locks for teams: {person: {date_str: team_name}}
        self.call_requirements = call_requirements or {}
        self.calls = calls or {}  # User locks for calls: {person: {date_str: 0 or 1}}
        self.leaves_blockouts = leaves_blockouts or {}
        self.leave_buffers = leave_buffers or [1, 0]
        self.blockout_buffers = blockout_buffers or [1, 0]
        self.call_interval = call_interval
        self.max_teams_per_week = max_teams_per_week
        self.min_team_requirements = min_team_requirements or {}

        self.team_to_idx = {opt: i for i, opt in enumerate(self.team_options)}
        self.idx_to_team = {i: opt for i, opt in enumerate(self.team_options)}

        self.model = None
        self.solver = None
        self.dates = []
        self.weekday_chunks = []
        self.weekend_chunks = []
        
        self.daytime_unavailable = {}
        self.nighttime_unavailable = {}
        self.teams_table = {}
        self.team_vars = {}
        self.call_vars = {}

        self.max_solve_time_seconds = max_solve_time_seconds or 10  # Default fallback safeguard

        self.initialise()

    def _init_globals(self):
        start = datetime.strptime(self.start_date, '%d/%m/%Y')
        end = datetime.strptime(self.end_date, '%d/%m/%Y')
        delta = end - start
        
        self.dates = [(start + timedelta(days=i)).strftime('%d/%m/%Y') for i in range(delta.days + 1)]
        
        for idx, d_str in enumerate(self.dates):
            d_obj = datetime.strptime(d_str, '%d/%m/%Y')
            if d_obj.weekday() < 5:
                self.weekday_chunks.append(idx)
            else:
                self.weekend_chunks.append(idx)

    def _init_leaves_blockouts(self):
        persons = list(self.leaves_blockouts.keys()) or list(self.team.keys())
        date_to_idx = {d: i for i, d in enumerate(self.dates)}

        for person in persons:
            self.daytime_unavailable[person] = {i: 0 for i in range(len(self.dates))}
            self.nighttime_unavailable[person] = {i: 0 for i in range(len(self.dates))}
            
            p_entries = self.leaves_blockouts.get(person, [])
            for date_str, status in p_entries:
                if date_str not in date_to_idx:
                    continue
                idx = date_to_idx[date_str]
                d_obj = datetime.strptime(date_str, '%d/%m/%Y')

                status_str = str(status).strip().upper()
                if status_str == 'L':
                    self.daytime_unavailable[person][idx] = 1

                    pre, post = self.leave_buffers[0], self.leave_buffers[1]
                    for offset in range(-pre, post + 1):
                        target_idx = idx + offset
                        if 0 <= target_idx < len(self.dates):
                            self.nighttime_unavailable[person][target_idx] = 1

                    if d_obj.weekday() == 3:  
                        for offset in range(1, 4):  
                            target_idx = idx + offset
                            if 0 <= target_idx < len(self.dates):
                                self.nighttime_unavailable[person][target_idx] = 1
                    elif d_obj.weekday() == 4:  
                        for offset in range(1, 3):  
                            target_idx = idx + offset
                            if 0 <= target_idx < len(self.dates):
                                self.nighttime_unavailable[person][target_idx] = 1

                elif status_str == 'B':
                    pre, post = self.blockout_buffers[0], self.blockout_buffers[1]
                    for offset in range(-pre, post + 1):
                        target_idx = idx + offset
                        if 0 <= target_idx < len(self.dates):
                            self.nighttime_unavailable[person][target_idx] = 1

    def _init_calls(self):
        for person in self.persons:
            self.call_vars[person] = {}
            for idx, date_str in enumerate(self.dates):
                self.call_vars[person][idx] = self.model.NewBoolVar(f"call_{person}_{idx}")
                
                # Constraint: Force call variable to 0 if the staff member is unavailable at night
                if self.nighttime_unavailable.get(person, {}).get(idx, 0) == 1:
                    self.model.Add(self.call_vars[person][idx] == 0)

                # Constraint: Apply user manual locks for calls if present
                if person in self.calls and date_str in self.calls[person]:
                    locked_call_val = int(self.calls[person][date_str])
                    self.model.Add(self.call_vars[person][idx] == locked_call_val)

        # Constraint: Enforce a minimum interval spacing between assigned calls for each person.
        for person in self.persons:
            for idx in range(len(self.dates) - self.call_interval):
                self.model.AddAtMostOne([
                    self.call_vars[person][idx + offset]
                    for offset in range(self.call_interval + 1)
                ])

        # Constraint: Ensure total daily assigned calls match the required daily requirement.
        for idx, date_str in enumerate(self.dates):
            required_calls = self.call_requirements.get(date_str, 0)
            if required_calls > 0:
                daily_assigned_calls = [
                    self.call_vars[person][idx] 
                    for person in self.persons 
                    if idx in self.call_vars[person]
                ]
                if daily_assigned_calls:
                    self.model.Add(sum(daily_assigned_calls) == required_calls)

    def _init_teams(self):
        self.teams_table = {p: {d: None for d in self.dates} for p in self.persons}
        
        leave_idx = self.team_to_idx.get('leave', 0)
        pcc_idx = self.team_to_idx.get('ps_cover', 0)

        for person in self.persons:
            self.team_vars[person] = {}
            for idx, date_str in enumerate(self.dates):
                d_obj = datetime.strptime(date_str, '%d/%m/%Y')
                if d_obj.weekday() >= 5:
                    continue
                
                self.team_vars[person][idx] = self.model.NewIntVar(
                    0, len(self.team_options) - 1, f"team_{person}_{idx}"
                )

                # Constraint: lock in pre-booked leaves automatically
                if self.daytime_unavailable.get(person, {}).get(idx, 0) == 1:                   
                    self.model.Add(self.team_vars[person][idx] == leave_idx)
                else:
                    self.model.Add(self.team_vars[person][idx] != leave_idx)

                # Constraint: Apply user manual locks for teams/status if present
                if person in self.team and date_str in self.team[person]:
                    locked_team_name = str(self.team[person][date_str]).replace(" (auto)", "").strip()
                    if locked_team_name in self.team_to_idx:
                        locked_idx = self.team_to_idx[locked_team_name]
                        self.model.Add(self.team_vars[person][idx] == locked_idx)

        # Constraint: Enforce minimum required staffing headcounts for each team (for weekdays)
        if self.min_team_requirements:
            for idx, date_str in enumerate(self.dates):
                d_obj = datetime.strptime(date_str, '%d/%m/%Y')
                if d_obj.weekday() >= 5:
                    continue
                
                for team_name, min_limit in self.min_team_requirements.items():
                    if team_name not in self.team_to_idx:
                        continue
                    t_idx = self.team_to_idx[team_name]
                    team_presence_vars = []
                    
                    for person in self.persons:
                        if idx in self.team_vars.get(person, {}):
                            is_this_team = self.model.NewBoolVar(f"min_chk_{person}_{idx}_{t_idx}")
                            self.model.Add(self.team_vars[person][idx] == t_idx).OnlyEnforceIf(is_this_team)
                            self.model.Add(self.team_vars[person][idx] != t_idx).OnlyEnforceIf(is_this_team.Not())
                            team_presence_vars.append(is_this_team)
                    
                    if team_presence_vars:
                        self.model.Add(sum(team_presence_vars) >= min_limit)

        weeks_dict = {}
        for idx, date_str in enumerate(self.dates):
            d_obj = datetime.strptime(date_str, '%d/%m/%Y')
            if not self.persons or idx not in self.team_vars.get(self.persons[0], {}):
                continue
            
            monday_obj = d_obj - timedelta(days=d_obj.weekday())
            week_id = monday_obj.strftime('%d/%m/%Y')
            
            weeks_dict.setdefault(week_id, []).append(idx)

        exclusive_team_indices = [
            i for i, name in enumerate(self.team_options) 
            if name.startswith('team_') or name == 'ps_cover'
        ]

        # Constraints per person and per week
        for person in self.persons:
            for week_id, week_indices in weeks_dict.items():
                person_week_indices = [idx for idx in week_indices if idx in self.team_vars.get(person, {})]
                if not person_week_indices:
                    continue
                
                week_exclusive_team_flags = []
                for t_idx in exclusive_team_indices:
                    t_assigned_vars = []
                    for idx in person_week_indices:
                        is_this_team = self.model.NewBoolVar(f"is_team_{person}_{idx}_{t_idx}")
                        self.model.Add(self.team_vars[person][idx] == t_idx).OnlyEnforceIf(is_this_team)
                        self.model.Add(self.team_vars[person][idx] != t_idx).OnlyEnforceIf(is_this_team.Not())
                        t_assigned_vars.append(is_this_team)
                    
                    safe_week_str = week_id.replace('/', '_')
                    team_used_this_week = self.model.NewBoolVar(f"used_team_{person}_{safe_week_str}_{t_idx}")
                    self.model.AddMaxEquality(team_used_this_week, t_assigned_vars)
                    week_exclusive_team_flags.append(team_used_this_week)
                
                # Constraint: Limit different teams any person can work per week
                self.model.Add(sum(week_exclusive_team_flags) <= self.max_teams_per_week)

                # Constraint: Ensure post-call-cover is not also post call
                for idx in person_week_indices:
                    d_obj = datetime.strptime(self.dates[idx], '%d/%m/%Y')
                    if d_obj.weekday() >= 5:
                        continue 
                    
                    is_pcc_day = self.model.NewBoolVar(f"is_pcc_{person}_{idx}")
                    self.model.Add(self.team_vars[person][idx] == pcc_idx).OnlyEnforceIf(is_pcc_day)
                    self.model.Add(self.team_vars[person][idx] != pcc_idx).OnlyEnforceIf(is_pcc_day.Not())
                    
                    prev_idx = idx - 1
                    if prev_idx >= 0 and prev_idx in self.call_vars.get(person, {}):
                        self.model.Add(self.call_vars[person][prev_idx] == 0).OnlyEnforceIf(is_pcc_day)
    
    def _build_objective(self):
        spread_penalties = []
        for person in self.persons:
            for idx in range(len(self.dates) - 6):
                window_calls = [self.call_vars[person][idx + offset] for offset in range(7)]
                excess_calls = self.model.NewIntVar(0, 7, f"excess_calls_{person}_{idx}")
                self.model.Add(excess_calls == sum(window_calls))
                spread_penalties.append(excess_calls)
        
        staff_weekday_sums = []
        staff_weekend_sums = []
        for person in self.persons:
            wd_sum = self.model.NewIntVar(0, len(self.dates), f"wd_sum_{person}")
            we_sum = self.model.NewIntVar(0, len(self.dates), f"we_sum_{person}")
            self.model.Add(wd_sum == sum(self.call_vars[person][idx] for idx in self.weekday_chunks if idx in self.call_vars[person]))
            self.model.Add(we_sum == sum(self.call_vars[person][idx] for idx in self.weekend_chunks if idx in self.call_vars[person]))
            staff_weekday_sums.append(wd_sum)
            staff_weekend_sums.append(we_sum)

        max_wd = self.model.NewIntVar(0, len(self.dates), "max_wd")
        min_wd = self.model.NewIntVar(0, len(self.dates), "min_wd")
        max_we = self.model.NewIntVar(0, len(self.dates), "max_we")
        min_we = self.model.NewIntVar(0, len(self.dates), "min_we")
        
        self.model.AddMaxEquality(max_wd, staff_weekday_sums)
        self.model.AddMinEquality(min_wd, staff_weekday_sums)
        self.model.AddMaxEquality(max_we, staff_weekend_sums)
        self.model.AddMinEquality(min_we, staff_weekend_sums)

        wd_disparity = self.model.NewIntVar(0, len(self.dates), "wd_disparity")
        we_disparity = self.model.NewIntVar(0, len(self.dates), "we_disparity")
        
        self.model.Add(wd_disparity == max_wd - min_wd)
        self.model.Add(we_disparity == max_we - min_we)

        team_evenness_penalties = []
        working_options = [opt for opt in self.team_options if opt != 'leave']
        
        for person in self.persons:
            team_counts = []
            for opt in working_options:
                opt_idx = self.team_to_idx[opt]
                opt_days = []
                for idx in self.team_vars[person]:
                    is_opt = self.model.NewBoolVar(f"team_count_{person}_{idx}_{opt_idx}")
                    self.model.Add(self.team_vars[person][idx] == opt_idx).OnlyEnforceIf(is_opt)
                    self.model.Add(self.team_vars[person][idx] != opt_idx).OnlyEnforceIf(is_opt.Not())
                    opt_days.append(is_opt)
                
                count_var = self.model.NewIntVar(0, len(self.dates), f"count_{person}_{opt}")
                self.model.Add(count_var == sum(opt_days))
                team_counts.append(count_var)
            
            p_max_team = self.model.NewIntVar(0, len(self.dates), f"max_team_{person}")
            p_min_team = self.model.NewIntVar(0, len(self.dates), f"min_team_{person}")
            self.model.AddMaxEquality(p_max_team, team_counts)
            self.model.AddMinEquality(p_min_team, team_counts)
            
            person_team_variance = self.model.NewIntVar(0, len(self.dates), f"team_var_{person}")
            self.model.Add(person_team_variance == p_max_team - p_min_team)
            team_evenness_penalties.append(person_team_variance)

        shortfall_penalties = []
        for idx, date_str in enumerate(self.dates):
            d_obj = datetime.strptime(date_str, '%d/%m/%Y')
            if d_obj.weekday() >= 5:
                continue

            day_reqs = self.team_requirements.get(date_str, {})
            if not day_reqs and self.team_requirements:
                day_reqs = self.team_requirements

            for opt in working_options:
                req_count = day_reqs.get(opt, 0)
                if req_count <= 0:
                    continue

                opt_idx = self.team_to_idx[opt]
                assigned_vars = []
                for person in self.persons:
                    if idx in self.team_vars[person]:
                        is_opt = self.model.NewBoolVar(f"req_chk_{person}_{idx}_{opt_idx}")
                        self.model.Add(self.team_vars[person][idx] == opt_idx).OnlyEnforceIf(is_opt)
                        self.model.Add(self.team_vars[person][idx] != opt_idx).OnlyEnforceIf(is_opt.Not())
                        assigned_vars.append(is_opt)

                total_assigned = self.model.NewIntVar(0, len(self.persons), f"assigned_{opt}_{idx}")
                self.model.Add(total_assigned == sum(assigned_vars))

                shortfall = self.model.NewIntVar(0, req_count, f"shortfall_{opt}_{idx}")
                self.model.Add(shortfall >= req_count - total_assigned)

                priority_val = self.team_sacrificability.get(opt, 5)
                if priority_val == 0:
                    weight = 100000
                else:
                    weight = max(1, 1000 // (priority_val ** 2))

                shortfall_penalties.append(shortfall * weight)

        total_objective = (
            sum(spread_penalties) * 2 +
            wd_disparity * 5 +
            we_disparity * 5 +
            sum(team_evenness_penalties) * 3 +
            sum(shortfall_penalties)
        )
        self.model.Minimize(total_objective)

    def initialise(self):
        self.model = cp_model.CpModel()
        self._init_globals()
        self._init_leaves_blockouts()
        self._init_calls()
        self._init_teams()
        self._build_objective()

    def check_valid(self):
        if self.persons == []:
            print("WARNING: No staff members provided. Roster cannot be generated.")
            return False
        if self.call_requirements == {}:
            print("WARNING: No call requirements provided. Roster cannot be generated.")
            return False
        if self.team_requirements == {}:
            print("WARNING: No team requirements provided. Roster cannot be generated.")
            return False
        if self.team_options == []:
            print("WARNING: No team options provided. Roster cannot be generated.")
            return False
        if self.team_sacrificability == {}:
            print("WARNING: No team priorities provided. Roster cannot be generated.")
            return False
        if self.max_solve_time_seconds <= 0:
            print("WARNING: No maximum solving time provided. Roster cannot be generated")
            return False
        if not self.leaves_blockouts:
            print("WARNING: No leaves/blockouts provided. Roster can still be generated")
            return True
        return True

    def solve(self):
        if not self.check_valid():
            print("Model not valid. Quitting. ")
            return False

        self.solver = cp_model.CpSolver()
        self.solver.parameters.max_time_in_seconds = self.max_solve_time_seconds
        
        progress_logger = ObjectiveLogger()
        status = self.solver.Solve(self.model, progress_logger)
        
        print(f"Solution status: {status}")
        
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            for person in self.team_vars:
                for idx, date_str in enumerate(self.dates):
                    if idx in self.team_vars[person]:
                        val = self.solver.Value(self.team_vars[person][idx])
                        self.teams_table[person][date_str] = self.idx_to_team[val]
            return True
        return False