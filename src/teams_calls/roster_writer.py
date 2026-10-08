import csv
from datetime import datetime

class RosterWriter:
    @staticmethod
    def write_issues(issues, path="output_issues.csv"):
        with open(path, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Severity', 'File', 'Line', 'Column', 'Code', 'Message'])
            for iss in issues:
                writer.writerow([
                    iss.get('severity', 'ERROR'),
                    iss.get('file', ''),
                    iss.get('line', ''),
                    iss.get('column', ''),
                    iss.get('code', ''),
                    iss.get('message', '')
                ])

    @staticmethod
    def write_roster(roster_sched, path="output_roster.csv"):
        with open(path, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Staff'] + roster_sched.dates)
            for person in roster_sched.persons:
                row_out = [person]
                for idx, d_str in enumerate(roster_sched.dates):
                    d_obj = datetime.strptime(d_str, '%d/%m/%Y')

                    team_val = ''
                    if person in roster_sched.team_vars and idx in roster_sched.team_vars[person]:
                        var = roster_sched.team_vars[person][idx]
                        val_idx = roster_sched.solver.Value(var)
                        team_val = roster_sched.idx_to_team.get(val_idx, 'Unassigned')
                    if d_obj.weekday() >= 5 and team_val != 'leave':
                        team_val = ''

                    is_on_call = False
                    if person in roster_sched.call_vars and idx in roster_sched.call_vars[person]:
                        is_on_call = bool(
                            roster_sched.solver.Value(roster_sched.call_vars[person][idx])
                        )

                    combined = f"{team_val} (call)" if is_on_call and team_val else \
                               ("(call)" if is_on_call else team_val)
                    row_out.append(combined)
                writer.writerow(row_out)