from datetime import datetime, timedelta
import time
from ortools.sat.python import cp_model

MIN_CALL_INTERVAL_ENABLED = True
TEAMS_ONLY_ON_WEEKDAYS = True
TEAM_MIN_REQUIREMENT_ENABLED = True

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
        persons=None,
        team_requirements=None,
        team_options=None,
        team_sacrificability=None, 
        teams=None,
        call_requirements=None,
        calls=None,
        leaves_blockouts=None,
        leave_buffers=None,
        blockout_buffers=None,
        min_call_interval=2,
        team_requirements_min=None,
        team_shittiness=None,
        max_solve_time_seconds=None,
    ):
        #Cleanse and normalize all incoming date keys/entries upfront
        self.team_requirements = {}
        for k, v in (team_requirements or {}).items():
            try:
                parsed_k = self._parse_date_universal(k).strftime('%d/%m/%Y')
                self.team_requirements[parsed_k] = v
            except ValueError:
                self.team_requirements[k] = v

        self.call_requirements = {}
        for k, v in (call_requirements or {}).items():
            try:
                parsed_k = self._parse_date_universal(k).strftime('%d/%m/%Y')
                self.call_requirements[parsed_k] = v
            except ValueError:
                self.call_requirements[k] = v

        self.teams = {}
        for person, date_dict in (teams or {}).items():
            cleansed_sub = {}
            for k, v in date_dict.items():
                try:
                    parsed_k = self._parse_date_universal(k).strftime('%d/%m/%Y')
                    cleansed_sub[parsed_k] = v
                except ValueError:
                    cleansed_sub[k] = v
            self.teams[person] = cleansed_sub

        self.calls = {}
        for person, date_dict in (calls or {}).items():
            cleansed_sub = {}
            for k, v in date_dict.items():
                try:
                    parsed_k = self._parse_date_universal(k).strftime('%d/%m/%Y')
                    cleansed_sub[parsed_k] = v
                except ValueError:
                    cleansed_sub[k] = v
            self.calls[person] = cleansed_sub

        self.leaves_blockouts = {}
        for person, entries in (leaves_blockouts or {}).items():
            cleansed_entries = []
            for entry in entries:
                if isinstance(entry, (list, tuple)) and len(entry) == 2:
                    raw_d, status = entry
                    try:
                        parsed_d = self._parse_date_universal(raw_d).strftime('%d/%m/%Y')
                        cleansed_entries.append((parsed_d, status))
                    except ValueError:
                        cleansed_entries.append(entry)
                else:
                    cleansed_entries.append(entry)
            self.leaves_blockouts[person] = cleansed_entries

        self.team_options = team_options or []
        self.team_sacrificability = team_sacrificability or {}
        self.team_shittiness = team_shittiness or {}
        self.persons = persons or []
        self.leave_buffers = leave_buffers or [1, 0]
        self.blockout_buffers = blockout_buffers or [1, 0]
        self.min_call_interval = min_call_interval
        self.team_requirements_min = team_requirements_min or {}

        self.team_to_idx = {opt: i for i, opt in enumerate(self.team_options)}
        self.idx_to_team = {i: opt for i, opt in enumerate(self.team_options)}

        self.model = None
        self.solver = None
        self.weekday_idxs = []
        self.weekend_idxs = []
        
        self.daytime_unavailable = {}
        self.nighttime_unavailable = {}
        self.teams_table = {}
        self.team_vars = {}
        self.call_vars = {}

        self.max_solve_time_seconds = max_solve_time_seconds or 10

        self.initialise()

    def _parse_date_universal(self, raw_date):
        if isinstance(raw_date, datetime):
            return raw_date
        
        cleaned = str(raw_date).strip()
        formats = (
            '%d/%m/%Y', '%d/%m/%y', '%d-%m-%Y', '%d-%m-%y',
            '%Y-%m-%d', '%y-%m-%d', '%Y/%m/%d', '%y/%m/%d'
        )
        
        for fmt in formats:
            try:
                return datetime.strptime(cleaned, fmt)
            except ValueError:
                print(f"Failed to parse '{cleaned}' with format '{fmt}', trying next format...")
                continue
        
        raise ValueError(f"Unable to parse malformed date string: '{raw_date}'")

    def _init_globals(self):
        optimise_dates_set = self.team_requirements.keys() | self.call_requirements.keys()
        dates_set = self.team_requirements.keys() | self.call_requirements.keys() | {d for person in self.teams for d in self.teams[person]} | {d for person in self.calls for d in self.calls[person]} | {d for person in self.leaves_blockouts for d, _ in self.leaves_blockouts[person]}
        self.optimise_dates = sorted(optimise_dates_set, key=lambda d: datetime.strptime(d, '%d/%m/%Y'))
        self.dates = sorted(dates_set, key=lambda d: datetime.strptime(d, '%d/%m/%Y'))
        print(self.optimise_dates)
        print(self.dates)

        self.date_to_idx = {d: i for i, d in enumerate(self.dates)}
        self.optimise_dates_to_idx = {d: self.date_to_idx[d] for d in self.optimise_dates}

        for idx, d_str in enumerate(self.dates):
            d_obj = datetime.strptime(d_str, '%d/%m/%Y')
            if d_obj.weekday() < 5:
                self.weekday_idxs.append(idx)
            else:
                self.weekend_idxs.append(idx)

        persons_set = set(self.teams.keys()) | set(self.calls.keys()) | set(self.leaves_blockouts.keys())
        self.persons = list(persons_set)

    def _init_leaves_blockouts(self):
        persons = list(self.leaves_blockouts.keys()) or list(self.teams.keys())

        for person in persons:
            self.daytime_unavailable[person] = {i: 0 for i in range(len(self.optimise_dates))}
            self.nighttime_unavailable[person] = {i: 0 for i in range(len(self.optimise_dates))}
            
            for date_str, status in self.leaves_blockouts.get(person, []):
                idx = self.date_to_idx[date_str]
                d_obj = datetime.strptime(date_str, '%d/%m/%Y')

                status_str = str(status).strip().upper()
                if status_str == 'L':
                    self.daytime_unavailable[person][idx] = 1

                    pre, post = self.leave_buffers[0], self.leave_buffers[1]
                    for offset in range(-pre, post + 1):
                        target_date_obj = d_obj + timedelta(days=offset)
                        target_date_str = target_date_obj.strftime('%d/%m/%Y')
                        if target_date_str in self.date_to_idx:
                            target_idx = self.date_to_idx[target_date_str]
                            self.nighttime_unavailable[person][target_idx] = 1

                    if d_obj.weekday() == 0:  # Monday => block preceding weekend
                        for offset in range(-2, 0):
                            target_date_obj = d_obj + timedelta(days=offset)
                            target_date_str = target_date_obj.strftime('%d/%m/%Y')
                            if target_date_str in self.date_to_idx:
                                target_idx = self.date_to_idx[target_date_str]
                                self.nighttime_unavailable[person][target_idx] = 1
                    elif d_obj.weekday() == 4:  # Friday => block following weekend
                        for offset in range(1, 3):  
                            target_date_obj = d_obj + timedelta(days=offset)
                            target_date_str = target_date_obj.strftime('%d/%m/%Y')
                            if target_date_str in self.date_to_idx:
                                target_idx = self.date_to_idx[target_date_str]
                                self.nighttime_unavailable[person][target_idx] = 1

                elif status_str == 'B':
                    pre, post = self.blockout_buffers[0], self.blockout_buffers[1]
                    for offset in range(-pre, post + 1):
                        target_date_obj = d_obj + timedelta(days=offset)
                        target_date_str = target_date_obj.strftime('%d/%m/%Y')
                        if target_date_str in self.date_to_idx:
                            target_idx = self.date_to_idx[target_date_str]
                            self.nighttime_unavailable[person][target_idx] = 1

    def _init_calls(self):
        # Initialise free variables for all optimise dates
        for person in self.persons:
            self.call_vars[person] = {}

            for date_str in self.optimise_dates:
                idx = self.date_to_idx[date_str]
                self.call_vars[person][idx] = self.model.NewBoolVar(f"call_{person}_{idx}")

                # If nighttime unavailable anywhere on the master timeline, lock to 0
                if self.nighttime_unavailable.get(person, {}).get(idx, 0) == 1:
                    self.model.Add(self.call_vars[person][idx] == 0)

        # Add lock data
        for person in self.calls:
            for date_str in self.calls[person]:
                self.call_vars[person][idx] = self.model.NewBoolVar(f"call_{person}_{idx}")
                call_val = int(self.calls[person][date_str])
                self.model.Add(self.call_vars[person][idx] == call_val)

        # Add call min requirements
        for date_str in self.optimise_dates:
            idx = self.date_to_idx[date_str]

            required_calls = self.call_requirements.get(date_str, 0)
            if required_calls > 0:
                daily_assigned_calls = [
                    self.call_vars[person][idx] 
                    for person in self.persons 
                    if idx in self.call_vars[person]
                ]
                if daily_assigned_calls:
                    self.model.Add(sum(daily_assigned_calls) == required_calls)

        if MIN_CALL_INTERVAL_ENABLED:
            for person in self.persons:
                for date_str in self.optimise_dates:
                    d_obj = datetime.strptime(date_str, '%d/%m/%Y')
                    window_vars = []
                    
                    for offset in range(self.min_call_interval + 1):
                        target_date_obj = d_obj + timedelta(days=offset)
                        target_date_str = target_date_obj.strftime('%d/%m/%Y')
                        
                        if target_date_str in self.date_to_idx:
                            target_idx = self.date_to_idx[target_date_str]
                            if target_idx in self.call_vars[person]:
                                window_vars.append(self.call_vars[person][target_idx])
                                
                    if window_vars:
                        self.model.AddAtMostOne(window_vars)

    def _init_teams(self):
        self.teams_table = {p: {d: None for d in self.dates} for p in self.persons}

        # implement leave and post_call_cover rules only if they are included
        leave_idx = self.team_to_idx.get('leave', None)
        if leave_idx is None:
            raise IndexError("Leave must be a valid team param option.")
        pcc_idx = self.team_to_idx.get('ps_cover', None)

        # Initialise team variables
        for person in self.persons:
            self.team_vars[person] = {}

            for date_str in self.optimise_dates:
                idx = self.date_to_idx[date_str]
                d_obj = datetime.strptime(date_str, '%d/%m/%Y')
                if TEAMS_ONLY_ON_WEEKDAYS and d_obj.weekday() >= 5:
                    continue

                self.team_vars[person][idx] = self.model.NewBoolVar(f"team_{person}_{idx}")

                if self.daytime_unavailable.get(person, {}).get(idx, 0) == 1:                   
                    self.model.Add(self.team_vars[person][idx] == leave_idx)
                else:
                    self.model.Add(self.team_vars[person][idx] != leave_idx)

        # Add lock data
        for person in self.teams:
            for date_str in self.teams[person]:
                self.team_vars[person][idx] = self.model.NewBoolVar(f"team_{person}_{idx}")

                locked_team_name = str(self.teams[person][date_str]).strip()
                if locked_team_name in self.team_to_idx:
                    team_idx = self.team_to_idx[locked_team_name]
                    self.model.Add(self.team_vars[person][idx] == team_idx)
                else:
                    print(f"Warning: Locked team '{locked_team_name}' for {person} on {date_str} is not in team options. Ignoring lock.")

        # team_requirements constraints
        working_options = [opt for opt in self.team_options if opt != 'leave']
        
        for date_str, day_reqs in self.team_requirements.items():
            if date_str not in self.date_to_idx:
                continue
            idx = self.date_to_idx[date_str]
            d_obj = datetime.strptime(date_str, '%d/%m/%Y')
            if TEAMS_ONLY_ON_WEEKDAYS and d_obj.weekday() >= 5:
                continue

            for team_opt, max_count in day_reqs.items():
                if team_opt not in working_options:
                    print(f"Warning: Team requirement option '{team_opt}' on date {date_str} is not a valid working option. Ignoring this requirement.")
                    continue

                team_opt_idx = self.team_to_idx[team_opt]
                assigned_vars = [] # filter for variables belonging to this team on this date
                for person in self.persons:
                    if idx in self.team_vars.get(person, {}):
                        is_opt = self.model.NewBoolVar(f"max_hard_chk_{person}_{idx}_{team_opt_idx}")
                        self.model.Add(self.team_vars[person][idx] == team_opt_idx).OnlyEnforceIf(is_opt)
                        self.model.Add(self.team_vars[person][idx] != team_opt_idx).OnlyEnforceIf(is_opt.Not())
                        assigned_vars.append(is_opt)
                        
                if assigned_vars:
                    self.model.Add(sum(assigned_vars) <= max_count)

                    if TEAM_MIN_REQUIREMENT_ENABLED and team_opt in self.team_requirements_min:
                        min_limit = self.team_requirements_min[team_opt]
                        self.model.Add(sum(assigned_vars) >= min_limit)

        weeks_dict = {}
        for idx, date_str in enumerate(self.dates):
            d_obj = datetime.strptime(date_str, '%d/%m/%Y')
            if not self.persons or idx not in self.team_vars.get(self.persons[0], {}):
                continue
            
            monday_obj = d_obj - timedelta(days=d_obj.weekday())
            week_id = monday_obj.strftime('%d/%m/%Y')
            weeks_dict.setdefault(week_id, []).append(idx)

        for person in self.persons:
            for week_id, week_indices in weeks_dict.items():
                # all the indices in the week they're working
                # and within the optimise range
                person_week_indices = [idx for idx in week_indices if idx in self.team_vars.get(person, {}) and idx in self.optimise_dates_to_idx.values()] # all the indices in the week they're working
                if not person_week_indices: # not working this week
                    continue

                week_pcc_days = []
                week_leave_days = []

                for idx in person_week_indices:
                    d_obj = datetime.strptime(self.dates[idx], '%d/%m/%Y')
                    if d_obj.weekday() >= 5:
                        continue 
                    
                    is_pcc_day = self.model.NewBoolVar(f"is_pcc_{person}_{idx}")
                    self.model.Add(self.team_vars[person][idx] == pcc_idx).OnlyEnforceIf(is_pcc_day)
                    self.model.Add(self.team_vars[person][idx] != pcc_idx).OnlyEnforceIf(is_pcc_day.Not())
                    week_pcc_days.append(is_pcc_day)
                    
                    prev_idx = idx - 1
                    if prev_idx >= 0 and prev_idx in self.call_vars.get(person, {}):
                        self.model.Add(self.call_vars[person][prev_idx] == 0).OnlyEnforceIf(is_pcc_day)

                    if leave_idx is not None:
                        is_leave_day = self.model.NewBoolVar(f"is_leave_day_{person}_{idx}")
                        self.model.Add(self.team_vars[person][idx] == leave_idx).OnlyEnforceIf(is_leave_day)
                        self.model.Add(self.team_vars[person][idx] != leave_idx).OnlyEnforceIf(is_leave_day.Not())
                        week_leave_days.append(is_leave_day)

                if leave_idx is not None and week_pcc_days and week_leave_days:
                    safe_week_str = week_id.replace('/', '_')
                    has_pcc_week = self.model.NewBoolVar(f"has_pcc_week_{person}_{safe_week_str}")
                    has_leave_week = self.model.NewBoolVar(f"has_leave_week_{person}_{safe_week_str}")
                    
                    self.model.AddMaxEquality(has_pcc_week, week_pcc_days)
                    self.model.AddMaxEquality(has_leave_week, week_leave_days)
                    
                    self.model.Add(has_pcc_week + has_leave_week <= 1)
    
    def _build_objective(self):
        spread_penalties = []
        for person in self.persons:
            person_calls = self.call_vars.get(person, {})
            for idx in range(len(self.dates) - 6):
                window_calls = [person_calls[idx + offset] for offset in range(7) if (idx + offset) in person_calls]
                if window_calls:
                    excess_calls = self.model.NewIntVar(0, 7, f"excess_calls_{person}_{idx}")
                    self.model.Add(excess_calls == sum(window_calls))
                    spread_penalties.append(excess_calls)

        months_dict = {}
        for idx, date_str in enumerate(self.dates):
            d_obj = datetime.strptime(date_str, '%d/%m/%Y')
            month_key = d_obj.strftime('%Y-%m')
            months_dict.setdefault(month_key, []).append(idx)
        
        sorted_months = sorted(months_dict.keys())
        monthly_smoothing_penalties = []
        monthly_equity_penalties = []

        for person in self.persons:
            person_calls = self.call_vars.get(person, {})
            person_monthly_sums = []
            
            for m_key in sorted_months:
                m_indices = months_dict[m_key]
                m_sum = self.model.NewIntVar(0, len(m_indices), f"m_sum_{person}_{m_key}")
                self.model.Add(m_sum == sum(person_calls[idx] for idx in m_indices if idx in person_calls))
                person_monthly_sums.append(m_sum)
            
            if person_monthly_sums:
                m_max = self.model.NewIntVar(0, len(self.dates), f"m_max_{person}")
                m_min = self.model.NewIntVar(0, len(self.dates), f"m_min_{person}")
                self.model.AddMaxEquality(m_max, person_monthly_sums)
                self.model.AddMinEquality(m_min, person_monthly_sums)
                
                monthly_equity_variance = self.model.NewIntVar(0, len(self.dates), f"m_var_{person}")
                self.model.Add(monthly_equity_variance == m_max - m_min)
                monthly_equity_penalties.append(monthly_equity_variance)

            for i in range(len(person_monthly_sums) - 1):
                diff = self.model.NewIntVar(-len(self.dates), len(self.dates), f"diff_{person}_{i}")
                abs_diff = self.model.NewIntVar(0, len(self.dates), f"abs_diff_{person}_{i}")
                
                self.model.Add(diff == person_monthly_sums[i+1] - person_monthly_sums[i])
                self.model.AddAbsEquality(abs_diff, diff)
                monthly_smoothing_penalties.append(abs_diff)

        largest_gaps = []
        num_days = len(self.dates)

        for person in self.persons:
            person_calls = self.call_vars.get(person, {})
            unavailable_map = self.nighttime_unavailable.get(person, {})
            gaps = []
            
            prev_rest = self.model.NewIntVar(0, num_days + 1, f"prev_rest_{person}_init")
            self.model.Add(prev_rest == 0)

            for day in range(num_days):
                call_var = person_calls.get(day)
                is_unavailable = unavailable_map.get(day, 0)

                is_rest_day = self.model.NewBoolVar(f"is_rest_{person}_{day}")
                is_working_day = self.model.NewBoolVar(f"is_working_{person}_{day}")

                if call_var is not None:
                    if is_unavailable == 1:
                        self.model.Add(is_rest_day == 1)
                        self.model.Add(is_working_day == 0)
                    else:
                        self.model.Add(call_var == 0).OnlyEnforceIf(is_rest_day)
                        self.model.Add(call_var != 0).OnlyEnforceIf(is_rest_day.Not())
                        self.model.Add(call_var == 1).OnlyEnforceIf(is_working_day)
                        self.model.Add(call_var != 1).OnlyEnforceIf(is_working_day.Not())
                else:
                    self.model.Add(is_rest_day == 1)
                    self.model.Add(is_working_day == 0)

                tmp = self.model.NewIntVar(0, num_days + 1, f"rest_tmp_{person}_{day}")
                self.model.Add(tmp == prev_rest + 1)
                
                new_rest = self.model.NewIntVar(0, num_days + 1, f"rest_{person}_{day}")
                self.model.AddMultiplicationEquality(new_rest, [tmp, is_rest_day])

                gap_weighted = self.model.NewIntVar(0, num_days + 1, f"gap_{person}_{day}")
                self.model.AddMultiplicationEquality(gap_weighted, [prev_rest, is_working_day])
                gaps.append(gap_weighted)

                prev_rest = new_rest

            gaps.append(prev_rest)

            largest_gap = self.model.NewIntVar(0, num_days + 1, f"max_gap_{person}")
            self.model.AddMaxEquality(largest_gap, gaps)
            largest_gaps.append(largest_gap)

        staff_weekday_sums = []
        staff_weekend_sums = []
        staff_total_calls = []
        
        for person in self.persons:
            wd_sum = self.model.NewIntVar(0, len(self.dates), f"wd_sum_{person}")
            we_sum = self.model.NewIntVar(0, len(self.dates), f"we_sum_{person}")
            total_sum = self.model.NewIntVar(0, len(self.dates), f"total_calls_{person}")
            
            self.model.Add(wd_sum == sum(self.call_vars[person][idx] for idx in self.weekday_idxs if idx in self.call_vars[person]))
            self.model.Add(we_sum == sum(self.call_vars[person][idx] for idx in self.weekend_idxs if idx in self.call_vars[person]))
            self.model.Add(total_sum == sum(self.call_vars[person][idx] for idx in range(len(self.dates)) if idx in self.call_vars[person]))
            
            staff_weekday_sums.append(wd_sum)
            staff_weekend_sums.append(we_sum)
            staff_total_calls.append(total_sum)

        max_wd = self.model.NewIntVar(0, len(self.dates), "max_wd")
        min_wd = self.model.NewIntVar(0, len(self.dates), "min_wd")
        max_we = self.model.NewIntVar(0, len(self.dates), "max_we")
        min_we = self.model.NewIntVar(0, len(self.dates), "min_we")
        max_total = self.model.NewIntVar(0, len(self.dates), "max_total_calls")
        min_total = self.model.NewIntVar(0, len(self.dates), "min_total_calls")
        
        self.model.AddMaxEquality(max_wd, staff_weekday_sums)
        self.model.AddMinEquality(min_wd, staff_weekday_sums)
        self.model.AddMaxEquality(max_we, staff_weekend_sums)
        self.model.AddMinEquality(min_we, staff_weekend_sums)
        self.model.AddMaxEquality(max_total, staff_total_calls)
        self.model.AddMinEquality(min_total, staff_total_calls)

        wd_disparity = self.model.NewIntVar(0, len(self.dates), "wd_disparity")
        we_disparity = self.model.NewIntVar(0, len(self.dates), "we_disparity")
        total_call_disparity = self.model.NewIntVar(0, len(self.dates), "total_call_disparity")
        
        self.model.Add(wd_disparity == max_wd - min_wd)
        self.model.Add(we_disparity == max_we - min_we)
        self.model.Add(total_call_disparity == max_total - min_total)

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

        weeks_dict = {}
        for idx, date_str in enumerate(self.dates):
            d_obj = datetime.strptime(date_str, '%d/%m/%Y')
            if not self.persons or idx not in self.team_vars.get(self.persons[0], {}):
                continue
            monday_obj = d_obj - timedelta(days=d_obj.weekday())
            week_id = monday_obj.strftime('%d/%m/%Y')
            weeks_dict.setdefault(week_id, []).append(idx)

        nonexclusive_teams = {'leave'}
        exclusive_team_indices = [
            i for i, name in enumerate(self.team_options) 
            if name not in nonexclusive_teams
        ]

        weekly_team_penalties = []
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
                
                sum_teams_var = self.model.NewIntVar(0, len(exclusive_team_indices), f"sum_teams_{person}_{week_id.replace('/', '_')}")
                self.model.Add(sum_teams_var == sum(week_exclusive_team_flags))

                excess_team_var = self.model.NewIntVar(0, len(exclusive_team_indices), f"excess_team_{person}_{week_id.replace('/', '_')}")
                self.model.Add(excess_team_var >= sum_teams_var - 1)
                weekly_team_penalties.append(excess_team_var)

        shittiness_window_penalties = []
        staff_total_shittiness = []
        window_size = 14
        
        if self.team_shittiness:
            team_shith_map = [self.team_shittiness.get(self.idx_to_team[i], 0) for i in range(len(self.team_options))]
            max_shith = max(team_shith_map) if team_shith_map else 0

            if max_shith > 0:
                max_possible_total_shith = max_shith * len(self.dates)
                for person in self.persons:
                    person_team_vars = self.team_vars.get(person, {})
                    day_shittiness = {}
                    person_daily_shvars = []
                    
                    for idx in range(len(self.dates)):
                        if idx in person_team_vars:
                            s_var = self.model.NewIntVar(0, max_shith, f"shittiness_{person}_{idx}")
                            self.model.AddElement(person_team_vars[idx], team_shith_map, s_var)
                            day_shittiness[idx] = s_var
                        else:
                            s_var = self.model.NewIntVar(0, 0, f"shittiness_{person}_{idx}")
                            day_shittiness[idx] = s_var
                        person_daily_shvars.append(s_var)

                    # Total shittiness sum per person
                    person_total_shith = self.model.NewIntVar(0, max_possible_total_shith, f"total_shittiness_{person}")
                    self.model.Add(person_total_shith == sum(person_daily_shvars))
                    staff_total_shittiness.append(person_total_shith)

                    for idx in range(len(self.dates) - window_size + 1):
                        window_vars = [day_shittiness[idx + offset] for offset in range(window_size) if (idx + offset) in day_shittiness]
                        if window_vars:
                            window_sum = self.model.NewIntVar(0, max_shith * window_size, f"shith_window_{person}_{idx}")
                            self.model.Add(window_sum == sum(window_vars))
                            shittiness_window_penalties.append(window_sum)

        # Compute total shittiness disparity across staff members
        max_total_shith = self.model.NewIntVar(0, len(self.dates) * 100, "max_total_shith")
        min_total_shith = self.model.NewIntVar(0, len(self.dates) * 100, "min_total_shith")
        shittiness_disparity = self.model.NewIntVar(0, len(self.dates) * 100, "shittiness_disparity")

        if staff_total_shittiness:
            self.model.AddMaxEquality(max_total_shith, staff_total_shittiness)
            self.model.AddMinEquality(min_total_shith, staff_total_shittiness)
            self.model.Add(shittiness_disparity == max_total_shith - min_total_shith)
        else:
            self.model.Add(shittiness_disparity == 0)

        # ==========================================
        # DIMENSION INITIALIZATIONS FOR NORMALIZATION
        # ==========================================
        P = len(self.persons)
        D = len(self.dates)

        months_dict_norm = {}
        for idx, date_str in enumerate(self.dates):
            d_obj = datetime.strptime(date_str, '%d/%m/%Y')
            month_key = d_obj.strftime('%Y-%m')
            months_dict_norm.setdefault(month_key, []).append(idx)
        M = len(months_dict_norm)

        weeks_dict_norm = {}
        for idx, date_str in enumerate(self.dates):
            d_obj = datetime.strptime(date_str, '%d/%m/%Y')
            monday_obj = d_obj - timedelta(days=d_obj.weekday())
            week_id = monday_obj.strftime('%d/%m/%Y')
            weeks_dict_norm.setdefault(week_id, []).append(idx)
        W = len(weeks_dict_norm)

        P_base, D_base, M_base, W_base = 11, 30, 1, 6

        scale_PD = (P_base * D_base * 1000) // max(1, P * D)
        scale_P  = (P_base * 1000) // max(1, P)
        scale_PM = (P_base * M_base * 1000) // max(1, P * M)
        scale_D  = (D_base * 1000) // max(1, D)
        scale_PW = (P_base * W_base * 1000) // max(1, P * W)

        # ==========================================
        # COMBINED OBJECTIVE WEIGHTS (Integer Scaled)
        # ==========================================
        total_objective = (
            sum(spread_penalties) * scale_PD * 1 +                  
            sum(monthly_equity_penalties) * scale_P * 1 +          
            sum(monthly_smoothing_penalties) * scale_PM * 1 +      
            sum(largest_gaps) * scale_P * 2 +                      
            wd_disparity * scale_D * 8 +                           
            we_disparity * scale_D * 8 +                           
            total_call_disparity * scale_D * 15 +                  
            sum(team_evenness_penalties) * scale_P * 2 +           
            sum(weekly_team_penalties) * scale_PW * 10 +           
            sum(shittiness_window_penalties) * scale_PD * 4 +      
            shittiness_disparity * scale_D * 12
        )
        self.model.Minimize(total_objective)

    def initialise(self):
        self.model = cp_model.CpModel()
        self._init_globals()
        self._init_leaves_blockouts()
        self._init_calls()
        self._init_teams()
        self._build_objective()

    def solve(self):
        self.solver = cp_model.CpSolver()
        if self.max_solve_time_seconds:
            self.solver.parameters.max_time_in_seconds = float(self.max_solve_time_seconds)
        
        solution_callback = ObjectiveLogger()
        status = self.solver.Solve(self.model, solution_callback)
        
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return True
        return False