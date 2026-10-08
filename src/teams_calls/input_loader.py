from datetime import datetime, timedelta
import csv
import os

class InputFileError(Exception):
    """Raised when one or more CSV shape, format, or validation errors occur."""
    def __init__(self, issues):
        self.issues = issues  # List of dicts: {file, line, column, code, message}
        super().__init__(f"Found {len(issues)} input/validation error(s). See output_issues.csv.")

class InputFiles:
    def __init__(
        self,
        leaves="input_leaves_blockouts.csv",
        general="input_general_parameters.csv",
        team_requirements="input_team_requirements.csv",
        teams="input_teams.csv",
        calls="input_calls.csv",
        call_requirements="input_call_requirements.csv",
    ):
        self.leaves = leaves
        self.general = general
        self.team_requirements = team_requirements
        self.teams = teams
        self.calls = calls
        self.call_requirements = call_requirements

class CsvLoader:
    def __init__(self, files: InputFiles = None):
        self.files = files or InputFiles()
        self.issues = []

    def _parse_date(self, raw, file_name, line_num, col_name):
        if not raw or not str(raw).strip():
            return None
        cleaned = str(raw).strip()
        for fmt in ('%d/%m/%Y', '%d/%m/%y', '%d-%m-%Y', '%d-%m-%y', '%Y-%m-%d', '%y-%m-%d', '%Y/%m/%d', '%y/%m/%d'):
            try:
                return datetime.strptime(cleaned, fmt).strftime('%d/%m/%Y')
            except ValueError:
                continue
        self.issues.append({
            "severity": "ERROR",
            "file": file_name,
            "line": line_num,
            "column": col_name,
            "code": "BAD_DATE",
            "message": f"Unable to parse date string: '{raw}'"
        })
        return None

    def load(self):
        # 1. General Parameters
        params = {
            "leave_buffers": [1, 0],
            "blockout_buffers": [1, 0],
            "min_call_interval": 2,
            "max_solve_time_seconds": 120,
            "allowed_shortfall": 0,
            "shortfall_cost": 100,
            "team_sacrificability": {},
            "team_quota_min": {},
            "team_shittiness": {},
        }
        
        if os.path.exists(self.files.general):
            with open(self.files.general, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for line_idx, row in enumerate(reader, start=2):
                    team_name = (row.get('#team') or '').strip()
                    
                    # Deprecation checks for old columns
                    if row.get('#sacrificability') and row['#sacrificability'].strip():
                        self.issues.append({"severity": "ERROR", "file": self.files.general, "line": line_idx, "column": "#sacrificability", "code": "DEPRECATED_COLUMN", "message": "#sacrificability is deprecated. Use team-specific rules or parameters."})
                    if row.get('#minimum') and row['#minimum'].strip():
                        self.issues.append({"severity": "ERROR", "file": self.files.general, "line": line_idx, "column": "#minimum", "code": "DEPRECATED_COLUMN", "message": "#minimum is replaced by team_quota_min / shortfall rules."})

                    if team_name:
                        if row.get('#shittiness') and row['#shittiness'].strip():
                            try:
                                params["team_shittiness"][team_name] = int(row['#shittiness'])
                            except ValueError:
                                self.issues.append({"severity": "ERROR", "file": self.files.general, "line": line_idx, "column": "#shittiness", "code": "NON_NUMERIC", "message": f"Non-numeric shittiness for team {team_name}"})
                    
                    # Global settings (read from any row)
                    for key, target_key, parser in [
                        ('#al_buffer_before', ('leave_buffers', 0), int),
                        ('#al_buffer_after', ('leave_buffers', 1), int),
                        ('#bl_buffer_before', ('blockout_buffers', 0), int),
                        ('#bl_buffer_after', ('blockout_buffers', 1), int),
                        ('#min_call_interval', 'min_call_interval', int),
                        ('#max_solve_time_seconds', 'max_solve_time_seconds', int),
                        ('#allowed_shortfall', 'allowed_shortfall', int),
                        ('#shortfall_cost', 'shortfall_cost', int),
                    ]:
                        val = row.get(key)
                        if val and val.strip():
                            try:
                                parsed_val = parser(val.strip())
                                if isinstance(target_key, tuple):
                                    params[target_key[0]][target_key[1]] = parsed_val
                                else:
                                    params[target_key] = parsed_val
                            except ValueError:
                                self.issues.append({"severity": "ERROR", "file": self.files.general, "line": line_idx, "column": key, "code": "NON_NUMERIC", "message": f"Invalid integer for {key}: '{val}'"})

        # 2. Leaves & Blockouts + Staff Master List
        staff_members = []
        leaves_blockouts = {}
        if os.path.exists(self.files.leaves):
            with open(self.files.leaves, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                try:
                    header = next(reader)
                except StopIteration:
                    header = []
                
                date_headers = []
                for col_idx, h in enumerate(header[1:], start=1):
                    parsed_d = self._parse_date(h, self.files.leaves, 1, f"Col {col_idx+1}")
                    date_headers.append(parsed_d)

                seen_staff = set()
                for line_idx, row in enumerate(reader, start=2):
                    if not row or not row[0].strip():
                        continue
                    person = row[0].strip()
                    if person in seen_staff:
                        self.issues.append({"severity": "ERROR", "file": self.files.leaves, "line": line_idx, "column": "Staff", "code": "DUPLICATE_STAFF", "message": f"Duplicate staff member '{person}'"})
                    seen_staff.add(person)
                    staff_members.append(person)

                    for col_idx, (d_str, status_raw) in enumerate(zip(date_headers, row[1:]), start=1):
                        if not d_str:
                            continue
                        status = status_raw.strip().upper()
                        if status and status != '-1':
                            if status not in ('L', 'B'):
                                self.issues.append({"severity": "ERROR", "file": self.files.leaves, "line": line_idx, "column": header[col_idx], "code": "UNKNOWN_STATUS", "message": f"Unknown leave/blockout status '{status}' for {person}"})
                            else:
                                leaves_blockouts.setdefault(person, []).append((d_str, status))

        # Check max 2 on leave policy rule
        daily_leave_counts = {}
        for person, entries in leaves_blockouts.items():
            for d_str, status in entries:
                if status == 'L':
                    daily_leave_counts[d_str] = daily_leave_counts.get(d_str, 0) + 1
        for d_str, count in daily_leave_counts.items():
            if count > 2:
                self.issues.append({
                    "severity": "ERROR",
                    "file": self.files.leaves,
                    "line": 1,
                    "column": d_str,
                    "code": "LEAVE_POLICY_VIOLATION",
                    "message": f"Leave Policy Violation: On {d_str}, {count} staff on leave (maximum allowed is 2)."
                })

        # 3. Team Requirements & Options
        team_quota = {}
        team_options_set = {'leave', 'ps_cover'}
        if os.path.exists(self.files.team_requirements):
            with open(self.files.team_requirements, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                try:
                    header = next(reader)
                except StopIteration:
                    header = []
                date_headers = [self._parse_date(h, self.files.team_requirements, 1, f"Col {i}") for i, h in enumerate(header[1:], start=1)]

                for line_idx, row in enumerate(reader, start=2):
                    if not row or not row[0].strip():
                        continue
                    team_name = row[0].strip()
                    team_options_set.add(team_name)

                    for col_idx, (d_str, val_str) in enumerate(zip(date_headers, row[1:]), start=1):
                        if not d_str:
                            continue
                        v = val_str.strip()
                        if v:
                            try:
                                iv = int(v)
                                if iv > 0:
                                    team_quota.setdefault(d_str, {})[team_name] = iv
                            except ValueError:
                                self.issues.append({"severity": "ERROR", "file": self.files.team_requirements, "line": line_idx, "column": header[col_idx], "code": "NON_NUMERIC", "message": f"Non-numeric team requirement for '{team_name}' on {d_str}: '{v}'"})

        # 4. Team Locks
        teams = {}
        if os.path.exists(self.files.teams):
            with open(self.files.teams, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                try:
                    header = next(reader)
                except StopIteration:
                    header = []
                date_headers = [self._parse_date(h, self.files.teams, 1, f"Col {i}") for i, h in enumerate(header[1:], start=1)]

                for line_idx, row in enumerate(reader, start=2):
                    if not row or not row[0].strip():
                        continue
                    person = row[0].strip()
                    if person not in staff_members:
                        staff_members.append(person) # Auto-add staff if missing from leaves master

                    for col_idx, (d_str, val_str) in enumerate(zip(date_headers, row[1:]), start=1):
                        if not d_str:
                            continue
                        v = val_str.strip()
                        if v:
                            teams.setdefault(person, {})[d_str] = v

        # 5. Call Locks
        calls = {}
        if os.path.exists(self.files.calls):
            with open(self.files.calls, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                try:
                    header = next(reader)
                except StopIteration:
                    header = []
                date_headers = [self._parse_date(h, self.files.calls, 1, f"Col {i}") for i, h in enumerate(header[1:], start=1)]

                for line_idx, row in enumerate(reader, start=2):
                    if not row or not row[0].strip():
                        continue
                    person = row[0].strip()
                    if person not in staff_members:
                        staff_members.append(person)

                    for col_idx, (d_str, val_str) in enumerate(zip(date_headers, row[1:]), start=1):
                        if not d_str:
                            continue
                        v = val_str.strip()
                        if v and v != '-1':
                            try:
                                calls.setdefault(person, {})[d_str] = int(v)
                            except ValueError:
                                self.issues.append({"severity": "ERROR", "file": self.files.calls, "line": line_idx, "column": header[col_idx], "code": "NON_NUMERIC", "message": f"Non-numeric call lock for {person} on {d_str}: '{v}'"})

        # 6. Call Requirements
        call_requirements = {}
        if os.path.exists(self.files.call_requirements):
            with open(self.files.call_requirements, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                try:
                    header = next(reader)
                except StopIteration:
                    header = []
                date_headers = [self._parse_date(h, self.files.call_requirements, 1, f"Col {i}") for i, h in enumerate(header[1:], start=1)]

                for line_idx, row in enumerate(reader, start=2):
                    for col_idx, (d_str, val_str) in enumerate(zip(date_headers, row[1:]), start=1):
                        if not d_str:
                            continue
                        v = val_str.strip()
                        if v:
                            try:
                                call_requirements[d_str] = int(v)
                            except ValueError:
                                self.issues.append({"severity": "ERROR", "file": self.files.call_requirements, "line": line_idx, "column": header[col_idx], "code": "NON_NUMERIC", "message": f"Non-numeric call requirement on {d_str}: '{v}'"})

        # If any errors were accumulated, raise InputFileError before running the solver
        if any(i["severity"] == "ERROR" for i in self.issues):
            raise InputFileError(self.issues)

        return {
            "persons": sorted(list(set(staff_members))),
            "team_quota": team_quota,
            "team_options": list(team_options_set),
            "teams": teams,
            "calls": calls,
            "call_requirements": call_requirements,
            "leaves_blockouts": leaves_blockouts,
            "leave_buffers": params["leave_buffers"],
            "blockout_buffers": params["blockout_buffers"],
            "min_call_interval": params["min_call_interval"],
            "team_quota_min": params["team_quota_min"],
            "team_shittiness": params["team_shittiness"],
            "max_solve_time_seconds": params["max_solve_time_seconds"],
        }, self.issues