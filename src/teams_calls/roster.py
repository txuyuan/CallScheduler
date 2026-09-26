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
        teams=None,
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
        # 1. Cleanse base range dates
        self.start_date = self._parse_date_universal(start_date).strftime('%d/%m/%Y')
        self.end_date = self._parse_date_universal(end_date).strftime('%d/%m/%Y')
        
        # 2. Cleanse and normalize all incoming date keys/entries upfront
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

        self.team_options = team_options or ['team_ds', 'leave', 'team_cos', 'team_c', 'ps_cover']
        
        self.team_sacrificability = team_sacrificability or {
            'team_ds': 1,
            'team_cos': 2,
            'team_c': 3,
            'ps_cover': 4,
            'leave': 5
        }

        self.persons = persons or []
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

        self.max_solve_time_seconds = max_solve_time_seconds or 10

        self.initialise()

    def _parse_date_universal(self, raw_date):
        """Attempts to parse a date string using multiple flexible formats, supporting non-zero padding and 2/4 digit years."""
        if isinstance(raw_date, datetime):
            return raw_date
        
        cleaned = str(raw_date).strip()
        formats = (
            '%d/%m/%Y', '%d/%m/%y', '%d-%m-%Y', '%d-%m-%y',
            '%d/%m/Y', '%d/%m/y', '%d-%m/Y', '%d-%m/y',
            '%Y-%m-%d', '%y-%m-%d', '%Y/%m/%d', '%y/%m/%d'
        )
        
        for fmt in formats:
            try:
                return datetime.strptime(cleaned, fmt)
            except ValueError:
                continue
        
        raise ValueError(f"Unable to parse malformed date string: '{raw_date}'")

    def _init_globals(self):
        start = datetime.strptime(self.start_date, '%d/%m/%Y')
        end = datetime.strptime(self.end_date, '%d/%m/%Y')
        delta = end - start
        
        self.dates = [(start + timedelta(days=i)).strftime('%d/%m/%Y') for i in range(delta.days + 1)] # Fixed list comprehension string indexing
        
        for idx, d_str in enumerate(self.dates):
            d_obj = datetime.strptime(d_str, '%d/%m/%Y')
            if d_obj.weekday() < 5:
                self.weekday_chunks.append(idx)
            else:
                self.weekend_chunks.append(idx)

    def _init_leaves_blockouts(self):
        persons = list(self.leaves_blockouts.keys()) or list(self.teams.keys())
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
                
                if self.nighttime_unavailable.get(person, {}).get(idx, 0) == 1:
                    self.model.Add(self.call_vars[person][idx] == 0)

                if person in self.calls and date_str in self.calls[person]:
                    locked_call_val = int(self.calls[person][date_str])
                    self.model.Add(self.call_vars[person][idx] == locked_call_val)

        for person in self.persons:
            for idx in range(len(self.dates) - self.call_interval):
                self.model.AddAtMostOne([
                    self.call_vars[person][idx + offset]
                    for offset in range(self.call_interval + 1)
                ])

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

                if self.daytime_unavailable.get(person, {}).get(idx, 0) == 1:                   
                    self.model.Add(self.team_vars[person][idx] == leave_idx)
                else:
                    self.model.Add(self.team_vars[person][idx] != leave_idx)

                if person in self.teams and date_str in self.teams[person]:
                    locked_team_name = str(self.teams[person][date_str]).replace(" (auto)", "").strip()
                    if locked_team_name in self.team_to_idx:
                        locked_idx = self.team_to_idx[locked_team_name]
                        self.model.Add(self.team_vars[person][idx] == locked_idx)

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

        leave_idx = self.team_to_idx.get('leave')

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
                
                self.model.Add(sum(week_exclusive_team_flags) <= self.max_teams_per_week)

                # Track weekly conditions for the ps_cover / leave rule
                week_pcc_days = []
                week_leave_days = []

                for idx in person_week_indices:
                    d_obj = datetime.strptime(self.dates[idx], '%d/%m/%Y')
                    if d_obj.weekday() >= 5:
                        continue 
                    
                    # 1. ps_cover Day Indicator & Rest Buffer Rule
                    is_pcc_day = self.model.NewBoolVar(f"is_pcc_{person}_{idx}")
                    self.model.Add(self.team_vars[person][idx] == pcc_idx).OnlyEnforceIf(is_pcc_day)
                    self.model.Add(self.team_vars[person][idx] != pcc_idx).OnlyEnforceIf(is_pcc_day.Not())
                    week_pcc_days.append(is_pcc_day)
                    
                    prev_idx = idx - 1
                    if prev_idx >= 0 and prev_idx in self.call_vars.get(person, {}):
                        self.model.Add(self.call_vars[person][prev_idx] == 0).OnlyEnforceIf(is_pcc_day)

                    # 2. Leave Day Indicator
                    if leave_idx is not None:
                        is_leave_day = self.model.NewBoolVar(f"is_leave_day_{person}_{idx}")
                        self.model.Add(self.team_vars[person][idx] == leave_idx).OnlyEnforceIf(is_leave_day)
                        self.model.Add(self.team_vars[person][idx] != leave_idx).OnlyEnforceIf(is_leave_day.Not())
                        week_leave_days.append(is_leave_day)

                # 3. Enforce: Cannot mix ps_cover and leave in the same week
                if leave_idx is not None and week_pcc_days and week_leave_days:
                    safe_week_str = week_id.replace('/', '_')
                    has_pcc_week = self.model.NewBoolVar(f"has_pcc_week_{person}_{safe_week_str}")
                    has_leave_week = self.model.NewBoolVar(f"has_leave_week_{person}_{safe_week_str}")
                    
                    self.model.AddMaxEquality(has_pcc_week, week_pcc_days)
                    self.model.AddMaxEquality(has_leave_week, week_leave_days)
                    
                    self.model.Add(has_pcc_week + has_leave_week <= 1)
    
    def _build_objective(self):
        # ==========================================
        # 1. SHORT-TERM: 7-Day Rolling Window Spread
        # ==========================================
        spread_penalties = []
        for person in self.persons:
            person_calls = self.call_vars.get(person, {})
            for idx in range(len(self.dates) - 6):
                window_calls = [person_calls[idx + offset] for offset in range(7) if (idx + offset) in person_calls]
                if window_calls:
                    excess_calls = self.model.NewIntVar(0, 7, f"excess_calls_{person}_{idx}")
                    self.model.Add(excess_calls == sum(window_calls))
                    spread_penalties.append(excess_calls)

        # ==========================================
        # 2. LONG-TERM: Calendar-Month Equity & Smoothing
        # ==========================================
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
            
            # A. Monthly Equity (busiest vs quietest month)
            if person_monthly_sums:
                m_max = self.model.NewIntVar(0, len(self.dates), f"m_max_{person}")
                m_min = self.model.NewIntVar(0, len(self.dates), f"m_min_{person}")
                self.model.AddMaxEquality(m_max, person_monthly_sums)
                self.model.AddMinEquality(m_min, person_monthly_sums)
                
                monthly_equity_variance = self.model.NewIntVar(0, len(self.dates), f"m_var_{person}")
                self.model.Add(monthly_equity_variance == m_max - m_min)
                monthly_equity_penalties.append(monthly_equity_variance)

            # B. Monthly Smoothing (penalize sharp spikes/drops between adjacent months)
            for i in range(len(person_monthly_sums) - 1):
                diff = self.model.NewIntVar(-len(self.dates), len(self.dates), f"diff_{person}_{i}")
                abs_diff = self.model.NewIntVar(0, len(self.dates), f"abs_diff_{person}_{i}")
                
                self.model.Add(diff == person_monthly_sums[i+1] - person_monthly_sums[i])
                self.model.AddAbsEquality(abs_diff, diff)
                monthly_smoothing_penalties.append(abs_diff)

        # ==========================================
        # 3. SEQUENTIAL: Gap-Between-Calls Minimization
        # ==========================================
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
                        # If unavailable/blockout, it's treated as forced rest/off
                        self.model.Add(is_rest_day == 1)
                        self.model.Add(is_working_day == 0)
                    else:
                        # Rest day means no call assigned
                        self.model.Add(call_var == 0).OnlyEnforceIf(is_rest_day)
                        self.model.Add(call_var != 0).OnlyEnforceIf(is_rest_day.Not())
                        self.model.Add(call_var == 1).OnlyEnforceIf(is_working_day)
                        self.model.Add(call_var != 1).OnlyEnforceIf(is_working_day.Not())
                else:
                    self.model.Add(is_rest_day == 1)
                    self.model.Add(is_working_day == 0)

                # tmp = prev_rest + 1
                tmp = self.model.NewIntVar(0, num_days + 1, f"rest_tmp_{person}_{day}")
                self.model.Add(tmp == prev_rest + 1)
                
                # new_rest = tmp * is_rest_day
                new_rest = self.model.NewIntVar(0, num_days + 1, f"rest_{person}_{day}")
                self.model.AddMultiplicationEquality(new_rest, [tmp, is_rest_day])

                # gap_weighted = prev_rest * is_working_day
                gap_weighted = self.model.NewIntVar(0, num_days + 1, f"gap_{person}_{day}")
                self.model.AddMultiplicationEquality(gap_weighted, [prev_rest, is_working_day])
                gaps.append(gap_weighted)

                prev_rest = new_rest

            gaps.append(prev_rest)  # trailing rest period at the end of the horizon

            largest_gap = self.model.NewIntVar(0, num_days + 1, f"max_gap_{person}")
            self.model.AddMaxEquality(largest_gap, gaps)
            largest_gaps.append(largest_gap)

        # ==========================================
        # 4. GLOBAL: Weekday/Weekend & Team Evenness
        # ==========================================
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

        # ==========================================
        # 5. EXCESS REQUIREMENTS PENALTIES
        # ==========================================
        excess_penalties = []
        for idx, date_str in enumerate(self.dates):
            d_obj = datetime.strptime(date_str, '%d/%m/%Y')
            if d_obj.weekday() >= 5:
                continue

            day_reqs = self.team_requirements.get(date_str, {})
            if not day_reqs and self.team_requirements and not any(k in self.team_requirements for k in self.dates):
                day_reqs = self.team_requirements

            for opt in working_options:
                max_count = day_reqs.get(opt, 999)
                if max_count >= 999:
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

                excess = self.model.NewIntVar(0, len(self.persons), f"excess_{opt}_{idx}")
                self.model.Add(excess >= total_assigned - max_count)

                priority_val = self.team_sacrificability.get(opt, 5)
                if priority_val == 0:
                    weight = 100000
                else:
                    weight = max(1, 1000 // (priority_val ** 2))

                excess_penalties.append(excess * weight)

        # ==========================================
        # COMBINED OBJECTIVE WEIGHTS
        # ==========================================
        total_objective = (
            sum(spread_penalties) * 2 +                  # 7-day rolling window
            sum(monthly_equity_penalties) * 4 +          # Monthly max/min variance
            sum(monthly_smoothing_penalties) * 3 +       # Month-to-month transition smoothness
            sum(largest_gaps) * 2 +                      # Gap minimization between shifts
            wd_disparity * 5 +                           # Weekday parity across horizon
            we_disparity * 5 +                           # Weekend parity across horizon
            sum(team_evenness_penalties) * 3 +           # Team workload balance
            sum(excess_penalties)                        # Meeting staffing targets safely
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
        if not self.persons:
            print("WARNING: No staff members provided. Roster cannot be generated.")
            return False
        if not self.call_requirements:
            print("WARNING: No call requirements provided. Roster cannot be generated.")
            return False
        if not self.team_requirements:
            print("WARNING: No teams requirements provided. Roster cannot be generated.")
            return False
        if not self.team_options:
            print("WARNING: No teams options provided. Roster cannot be generated.")
            return False
        if not self.team_sacrificability:
            print("WARNING: No teams priorities provided. Roster cannot be generated.")
            return False
        if self.max_solve_time_seconds <= 0:
            print("WARNING: No maximum solving time provided. Roster cannot be generated")
            return False
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