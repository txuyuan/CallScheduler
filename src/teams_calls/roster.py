"""
Roster solver (rewrite).

Pipeline
    raw dicts --RosterInputs.from_raw--> typed inputs (dates parsed ONCE)
              --Problem--> availability + Grid (locks applied first, free vars only where nothing is fixed)
              --validate--> warnings printed, errors raised (nothing is ever silently dropped)
              --RosterModel--> CP-SAT model (rules are named groups)
              --solve--> RosterSolution (+ the conflicting rule groups if infeasible)

Calendar
    dates           : ONE contiguous range = everything, including past data that cannot change
    schedule_dates  : ONE contiguous sub-range = the only days that get free variables
    Because dates is contiguous, index/date arithmetic is always calendar arithmetic.

Team model
    Each person-day on a team day has exactly one of: any TeamSpec name (incl. 'ps_cover') or 'leave'.
    'leave' is derived ONLY from absences (status 'L'); it is never a free choice.
    Team headcount is a TARGET (demand). Shortfall is allowed up to allowed_shortfall, and costs
    shortfall_cost per head: the cheapest team is sacrificed first. This replaces min/max/sacrificability.
"""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, List, Mapping, Optional

from ortools.sat.python import cp_model

LEAVE = "leave"
PS_COVER = "ps_cover"


# =====================================================================
# Dates (parsed in exactly one place)
# =====================================================================
_DATE_FORMATS = ("%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y",
                 "%Y-%m-%d", "%y-%m-%d", "%Y/%m/%d", "%y/%m/%d")


def to_date(raw) -> date:
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    s = str(raw).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unable to parse date: {raw!r}")


def daterange(a: date, b: date) -> List[date]:
    return [a + timedelta(days=i) for i in range((b - a).days + 1)]


def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


ONE_DAY = timedelta(days=1)


# =====================================================================
# Configuration
# =====================================================================
@dataclass(frozen=True)
class TeamSpec:
    """One working team. Demand per day lives in RosterInputs.team_demand."""
    name: str
    allowed_shortfall: int = 0          # HARD: max heads below demand on any day
    shortfall_cost: int = 100           # SOFT: cost per missing head (lower = sacrificed first)
    allowed_surplus: Optional[int] = None   # HARD: max heads above demand (None = unlimited)
    surplus_cost: int = 0               # SOFT: cost per extra head
    shittiness: int = 0                 # used only by the shittiness objective


@dataclass
class Weights:
    """Every objective term, one weight each. Set 0 to disable a term."""
    manpower: int = 1                   # multiplier on the TeamSpec shortfall/surplus costs
    one_team_per_week: int = 1000         # only used when cfg.one_team_per_week == 'soft'
    team_evenness: int = 2
    call_peak: int = 1                  # worst calls-in-7-days per person
    call_max_gap: int = 80               # longest stretch without a call per person
    call_weekday_disparity: int = 8
    call_weekend_disparity: int = 8
    call_total_disparity: int = 15
    call_monthly_equity: int = 1
    shittiness_peak: int = 4            # worst shittiness load in a rolling window per person
    shittiness_disparity: int = 12      # total shittiness gap between people


@dataclass
class RosterConfig:
    min_call_interval: int = 2          # at most one call in any (interval+1) consecutive days
    leave_buffers: tuple = (1, 0)       # nights before / after a leave day that are unavailable
    blockout_buffers: tuple = (1, 0)
    teams_only_on_weekdays: bool = True
    ps_cover_rules: bool = True
    ps_cover_blocks_same_night: bool = False   # ps_cover person also not on call that night
    one_team_per_week: str = "soft"     # 'hard' | 'soft' | 'off'
    evenness_excludes: tuple = (PS_COVER,)
    fairness_includes_history: bool = True
    shittiness_window_days: int = 21
    max_solve_time_seconds: float = 10.0
    weights: Weights = field(default_factory=Weights)

    def is_team_day(self, d: date) -> bool:
        return (not self.teams_only_on_weekdays) or d.weekday() < 5


# =====================================================================
# Typed inputs
# =====================================================================
def _norm_date_map(raw, what: str) -> Dict[date, object]:
    out = {}
    for k, v in (raw or {}).items():
        d = to_date(k)
        if d in out:
            raise ValueError(f"{what}: duplicate date {d} after normalising")
        out[d] = v
    return out


def _norm_absences(raw) -> Dict[str, Dict[date, str]]:
    """Accepts {person: [(date, 'L'|'B'), ...]} or {person: {date: status}}. Parsed once."""
    out: Dict[str, Dict[date, str]] = {}
    for person, entries in (raw or {}).items():
        items = entries.items() if isinstance(entries, Mapping) else entries
        row: Dict[date, str] = {}
        for d_raw, status in items:
            s = "" if status in (None, 0, "0") else str(status).strip().upper()
            s = {"LEAVE": "L", "BLOCKOUT": "B"}.get(s, s)
            if s in ("", "NONE"):
                continue
            if s not in ("L", "B"):
                raise ValueError(f"absence for {person} on {d_raw}: status {status!r} must be L or B")
            d = to_date(d_raw)
            if row.get(d, s) != s:
                raise ValueError(f"absence for {person} on {d}: both L and B given")
            row[d] = s
        out[person] = row
    return out


@dataclass
class RosterInputs:
    dates: List[date]
    schedule_dates: List[date]
    persons: List[str]
    teams: List[TeamSpec]
    call_demand: Dict[date, int]
    team_demand: Dict[date, Dict[str, int]]
    absences: Dict[str, Dict[date, str]]
    call_locks: Dict[str, Dict[date, int]]
    team_locks: Dict[str, Dict[date, str]]
    call_shittiness: Dict[date, int]

    @classmethod
    def from_raw(cls, *, start, end, schedule_start, schedule_end, persons, teams,
                 call_demand=None, team_demand=None, leaves_blockouts=None,
                 call_locks=None, team_locks=None, call_shittiness=None) -> "RosterInputs":
        s, e = to_date(start), to_date(end)
        ss, se = to_date(schedule_start), to_date(schedule_end)
        if e < s:
            raise ValueError("end is before start")
        if not (s <= ss <= se <= e):
            raise ValueError("schedule range must lie inside [start, end]")
        return cls(
            dates=daterange(s, e),
            schedule_dates=daterange(ss, se),
            persons=list(persons),
            teams=list(teams),
            call_demand={d: int(v) for d, v in _norm_date_map(call_demand, "call_demand").items()},
            team_demand={d: {t: int(n) for t, n in row.items()}
                         for d, row in _norm_date_map(team_demand, "team_demand").items()},
            absences=_norm_absences(leaves_blockouts),
            call_locks={p: _norm_date_map(dd, f"call_locks[{p}]") for p, dd in (call_locks or {}).items()},
            team_locks={p: {d: str(t).strip() for d, t in _norm_date_map(dd, f"team_locks[{p}]").items()}
                        for p, dd in (team_locks or {}).items()},
            call_shittiness={d: int(v) for d, v in _norm_date_map(call_shittiness, "call_shittiness").items()},
        )


# =====================================================================
# Availability and the lock-first Grid
# =====================================================================
class _Free:
    def __repr__(self):
        return "FREE"


FREE = _Free()   # a cell with no lock and no constraint forcing it: gets a solver variable


def compute_availability(inp: RosterInputs, cfg: RosterConfig):
    """day_off[p]  = dates the person is on leave (team is forced to 'leave').
       night_off[p] = dates the person cannot be on call (buffers, Mon/Fri weekend rule)."""
    day_off = {p: set() for p in inp.persons}
    night_off = {p: set() for p in inp.persons}
    for p in inp.persons:
        for d, status in inp.absences.get(p, {}).items():
            if status == "L":
                day_off[p].add(d)
                pre, post = cfg.leave_buffers
                for off in range(-pre, post + 1):
                    night_off[p].add(d + timedelta(days=off))
                if d.weekday() == 0:        # Monday leave blocks the weekend before
                    night_off[p].update({d - 2 * ONE_DAY, d - ONE_DAY})
                elif d.weekday() == 4:      # Friday leave blocks the weekend after
                    night_off[p].update({d + ONE_DAY, d + 2 * ONE_DAY})
            else:
                pre, post = cfg.blockout_buffers
                for off in range(-pre, post + 1):
                    night_off[p].add(d + timedelta(days=off))
    return day_off, night_off


class Problem:
    """Everything derived from inputs+config, computed once and shared by validate() and the model.

    grid.call[p][d] : int (fixed 0/1)  or FREE
    grid.team[p][d] : team name / 'leave' (fixed), None (history day with no data), or FREE
                      (only exists on team days)
    Priority: lock > absence > schedule-range default (FREE) > history default (0 / None).
    """

    def __init__(self, inputs: RosterInputs, cfg: RosterConfig):
        self.inputs, self.cfg = inputs, cfg
        self.sched = set(inputs.schedule_dates)
        self.date_set = set(inputs.dates)
        self.team_names = [t.name for t in inputs.teams]
        self.spec = {t.name: t for t in inputs.teams}
        self.day_off, self.night_off = compute_availability(inputs, cfg)

        self.call: Dict[str, Dict[date, object]] = {}
        self.team: Dict[str, Dict[date, object]] = {}
        for p in inputs.persons:
            crow, trow = {}, {}
            for d in inputs.dates:
                lock = inputs.call_locks.get(p, {}).get(d)
                if lock is not None:
                    crow[d] = int(lock)
                elif d in self.sched and d not in self.night_off[p]:
                    crow[d] = FREE
                else:
                    crow[d] = 0
                if cfg.is_team_day(d):
                    tl = inputs.team_locks.get(p, {}).get(d)
                    if tl is not None:
                        trow[d] = tl
                    elif d in self.day_off[p]:
                        trow[d] = LEAVE
                    elif d in self.sched:
                        trow[d] = FREE
                    else:
                        trow[d] = None
            self.call[p], self.team[p] = crow, trow

        self.weeks: Dict[date, List[date]] = defaultdict(list)
        for d in inputs.dates:
            self.weeks[week_start(d)].append(d)

    def team_days(self, days):
        return [d for d in days if self.cfg.is_team_day(d)]


# =====================================================================
# Validation layer (single place; warnings printed, errors raised)
# =====================================================================
@dataclass(frozen=True)
class Issue:
    severity: str   # 'error' | 'warning'
    code: str
    message: str


class RosterValidationError(Exception):
    def __init__(self, issues: List[Issue]):
        self.issues = issues
        super().__init__("Roster inputs are invalid:\n" +
                         "\n".join(f"  [{i.code}] {i.message}" for i in issues))


def validate(pb: Problem) -> List[Issue]:
    """Policy: anything that would change the meaning of the roster is an ERROR.
    Things provably irrelevant to the model are WARNINGS and are listed, never silent."""
    inp, cfg = pb.inputs, pb.cfg
    issues: List[Issue] = []
    err = lambda c, m: issues.append(Issue("error", c, m))
    warn = lambda c, m: issues.append(Issue("warning", c, m))
    persons, teams, sched, dates = set(inp.persons), set(pb.team_names), pb.sched, pb.date_set
    fmt = lambda d: d.strftime("%d/%m/%Y")

    # ---- structure
    if LEAVE in teams:
        err("RESERVED_NAME", "'leave' is implicit; do not list it as a TeamSpec.")
    if len(teams) != len(pb.team_names):
        err("DUPLICATE_TEAM", "Duplicate TeamSpec names.")
    if len(persons) != len(inp.persons):
        err("DUPLICATE_PERSON", "Duplicate person names.")
    if not pb.team_names:
        err("NO_TEAMS", "At least one TeamSpec is required.")
    if cfg.ps_cover_rules and PS_COVER not in teams:
        warn("PS_COVER_ABSENT", f"No team named '{PS_COVER}'; ps_cover rules have nothing to apply to.")
    if cfg.one_team_per_week not in ("hard", "soft", "off"):
        err("BAD_CONFIG", "one_team_per_week must be 'hard', 'soft' or 'off'.")
    for name, d in (("absences", inp.absences), ("call_locks", inp.call_locks), ("team_locks", inp.team_locks)):
        for p in d:
            if p not in persons:
                err("UNKNOWN_PERSON", f"{name} references unknown person '{p}'.")

    # ---- call locks
    for p, row in inp.call_locks.items():
        for d, v in row.items():
            if d not in dates:
                err("LOCK_OUT_OF_RANGE", f"call lock {p} {fmt(d)} is outside the date range.")
            elif v not in (0, 1):
                err("BAD_CALL_LOCK", f"call lock {p} {fmt(d)} = {v!r}; must be 0 or 1.")
            elif d in sched and v == 1 and d in pb.night_off.get(p, ()):
                err("CALL_LOCK_VS_ABSENCE", f"{p} is locked on call {fmt(d)} but is unavailable that night "
                                            f"(leave/blockout buffer).")

    # ---- team locks
    for p, row in inp.team_locks.items():
        for d, t in row.items():
            if d not in dates:
                err("LOCK_OUT_OF_RANGE", f"team lock {p} {fmt(d)} is outside the date range.")
                continue
            if t not in teams and t != LEAVE:
                err("UNKNOWN_TEAM", f"team lock {p} {fmt(d)} -> '{t}' is not a team.")
                continue
            if not cfg.is_team_day(d):
                (err if d in sched else warn)("TEAM_LOCK_NON_TEAM_DAY",
                                              f"team lock {p} {fmt(d)} is on a non-team day (ignored).")
                continue
            if d in sched:
                on_leave = d in pb.day_off.get(p, ())
                if t == LEAVE and not on_leave:
                    err("LEAVE_LOCK_NO_ABSENCE", f"{p} locked to 'leave' on {fmt(d)} but has no 'L' absence. "
                                                 f"Leave comes only from absences.")
                if t != LEAVE and on_leave:
                    err("LOCK_VS_LEAVE", f"{p} locked to '{t}' on {fmt(d)} but is on leave.")

    # ---- demand tables
    for d, row in inp.team_demand.items():
        for t, n in row.items():
            if t not in teams:
                err("UNKNOWN_TEAM", f"team_demand {fmt(d)} references unknown team '{t}'.")
            if n < 0:
                err("NEGATIVE_DEMAND", f"team_demand {fmt(d)} '{t}' is negative.")
    for d, n in inp.call_demand.items():
        if n < 0:
            err("NEGATIVE_DEMAND", f"call_demand {fmt(d)} is negative.")
    outside_c = [d for d in inp.call_demand if d not in sched]
    outside_t = [d for d in inp.team_demand if d not in sched]
    if outside_c:
        warn("DEMAND_OUTSIDE_SCHEDULE", f"{len(outside_c)} call_demand dates are outside schedule_dates (ignored).")
    if outside_t:
        warn("DEMAND_OUTSIDE_SCHEDULE", f"{len(outside_t)} team_demand dates are outside schedule_dates (ignored).")
    weekend_t = [d for d in inp.team_demand if d in sched and not cfg.is_team_day(d)]
    if weekend_t:
        warn("TEAM_DEMAND_NON_TEAM_DAY", f"{len(weekend_t)} team_demand dates are non-team days (ignored). {weekend_t}")
    no_call = [d for d in inp.schedule_dates if d not in inp.call_demand]
    if no_call:
        warn("NO_CALL_DEMAND", f"{len(no_call)} schedule dates have no call_demand; treated as 0 (nobody on call).")
    no_team = [d for d in pb.team_days(inp.schedule_dates) if d not in inp.team_demand]
    if no_team:
        warn("NO_TEAM_DEMAND", f"{len(no_team)} schedule team-days have no team_demand; treated as 0 for every team.")

    # ---- call locks vs interval (constants only)
    P = inp.persons
    if cfg.min_call_interval > 0:
        for p in P:
            ones = [d for d in inp.dates if pb.call[p][d] == 1]
            for i, d1 in enumerate(ones):
                for d2 in ones[i + 1:]:
                    if (d2 - d1).days > cfg.min_call_interval:
                        break
                    if d1 in sched or d2 in sched:
                        err("CALL_LOCK_INTERVAL", f"{p} has fixed calls on {fmt(d1)} and {fmt(d2)}; "
                                                  f"min_call_interval={cfg.min_call_interval}.")

    # ---- call capacity, per night
    can_call = lambda p, d: pb.call[p][d] is FREE or pb.call[p][d] == 1
    for d in inp.schedule_dates:
        req = inp.call_demand.get(d, 0)
        forced = sum(1 for p in P if pb.call[p][d] == 1)
        eligible = sum(1 for p in P if can_call(p, d))
        if forced > req:
            err("CALL_FORCED_EXCEEDS", f"{fmt(d)}: {forced} fixed calls but demand is {req}.")
        if eligible < req:
            err("CALL_NOT_ENOUGH_STAFF", f"{fmt(d)}: demand {req} but only {eligible} people can be on call.")

    # ---- call capacity, rolling window (necessary, not sufficient)
    k = cfg.min_call_interval + 1
    if k > 1:
        dl = inp.dates
        for i in range(len(dl) - k + 1):
            w = dl[i:i + k]
            if not any(d in sched for d in w):
                continue
            need = sum(inp.call_demand.get(d, 0) if d in sched
                       else sum(1 for p in P if pb.call[p][d] == 1) for d in w)
            can = sum(1 for p in P if any(can_call(p, d) for d in w))
            if need > can:
                err("CALL_WINDOW_CAPACITY", f"{fmt(w[0])}..{fmt(w[-1])}: {need} calls needed but at most one per "
                                            f"person in this window and only {can} people can take one.")

    # ---- team capacity, per day
    for d in pb.team_days(inp.schedule_dates):
        dem = inp.team_demand.get(d, {})
        cells = [pb.team[p][d] for p in P]
        n_avail = sum(1 for c in cells if c != LEAVE)
        need_min = sum(max(0, dem.get(t, 0) - pb.spec[t].allowed_shortfall) for t in pb.team_names)
        if need_min > n_avail:
            err("TEAM_MANPOWER", f"{fmt(d)}: teams need at least {need_min} people even at maximum shortfall, "
                                 f"only {n_avail} are not on leave.")
        if pb.team_names and all(pb.spec[t].allowed_surplus is not None for t in pb.team_names):
            cap = sum(dem.get(t, 0) + pb.spec[t].allowed_surplus for t in pb.team_names)
            if cap < n_avail:
                err("TEAM_OVERFLOW", f"{fmt(d)}: {n_avail} people to place but teams can hold at most {cap}.")
        for t in pb.team_names:
            s = pb.spec[t].allowed_surplus
            locked = sum(1 for c in cells if c == t)
            if s is not None and locked > dem.get(t, 0) + s:
                err("TEAM_LOCK_OVERFLOW", f"{fmt(d)} '{t}': {locked} locked but demand+surplus is {dem.get(t, 0) + s}.")

    # ---- ps_cover vs fixed data
    if cfg.ps_cover_rules and PS_COVER in teams:
        for p in P:
            for d in pb.team_days(inp.schedule_dates):
                if pb.team[p][d] != PS_COVER:
                    continue
                prev = d - ONE_DAY
                if prev in dates and pb.call[p][prev] == 1:
                    err("PS_COVER_AFTER_OWN_CALL", f"{p} is ps_cover on {fmt(d)} but on call the night before.")
                if cfg.ps_cover_blocks_same_night and pb.call[p][d] == 1:
                    err("PS_COVER_ON_CALL", f"{p} is ps_cover on {fmt(d)} and locked on call that night.")
            for _, days in pb.weeks.items():
                td = pb.team_days(days)
                if not any(d in sched for d in td):
                    continue
                if any(pb.team[p][d] == LEAVE for d in td) and any(pb.team[p][d] == PS_COVER for d in td):
                    err("PS_COVER_LEAVE_WEEK", f"{p}: ps_cover and leave in the week of {fmt(days[0])}.")
    return issues


def report_issues(issues: List[Issue], max_per_code: int = 10) -> None:
    by_code: Dict[tuple, List[Issue]] = defaultdict(list)
    for i in issues:
        by_code[(i.severity, i.code)].append(i)
    for (sev, code), items in sorted(by_code.items(), key=lambda kv: (kv[0][0] != "error", kv[0][1])):
        for i in items[:max_per_code]:
            print(f"[{sev.upper()}] {code}: {i.message}")
        if len(items) > max_per_code:
            print(f"[{sev.upper()}] {code}: ... and {len(items) - max_per_code} more")
    errors = [i for i in issues if i.severity == "error"]
    if errors:
        raise RosterValidationError(errors)


# =====================================================================
# Model
# =====================================================================
class ProgressLogger(cp_model.CpSolverSolutionCallback):
    def __init__(self):
        super().__init__()
        self.t0, self.n = time.time(), 0

    def on_solution_callback(self):
        self.n += 1
        print(f"[solver] solution #{self.n} at {time.time() - self.t0:.1f}s | objective {self.ObjectiveValue()}")


@dataclass
class RosterSolution:
    status: str
    objective: Optional[float] = None
    calls: Dict[str, Dict[date, int]] = field(default_factory=dict)
    teams: Dict[str, Dict[date, Optional[str]]] = field(default_factory=dict)
    headcount: Dict[date, Dict[str, int]] = field(default_factory=dict)
    shortfall: Dict[date, Dict[str, int]] = field(default_factory=dict)
    term_values: Dict[str, int] = field(default_factory=dict)      # raw measure of each objective term
    term_costs: Dict[str, int] = field(default_factory=dict)       # weight * raw
    conflicting_rules: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status in ("OPTIMAL", "FEASIBLE")


class RosterModel:
    """diagnose=False: rules are added directly, objective included.
       diagnose=True : every rule is enforced by a named literal passed as an assumption, no objective;
                       used only to ask the solver which rule groups cannot coexist."""

    def __init__(self, pb: Problem, diagnose: bool = False):
        self.pb, self.inp, self.cfg = pb, pb.inputs, pb.cfg
        self.diagnose = diagnose
        self.model = cp_model.CpModel()
        self.groups: Dict[str, cp_model.IntVar] = {}
        self.terms: Dict[str, object] = {}
        self.call: Dict[str, Dict[date, object]] = {}
        self.team: Dict[str, Dict[date, Dict[str, object]]] = {}
        self._build_variables()
        self._rule_call_demand()
        self._rule_call_interval()
        self._rule_ps_cover()
        self._rule_team_demand()
        self._rule_one_team_per_week()
        if not diagnose:
            self._objective_calls()
            self._objective_teams()
            self._objective_shittiness()
            self._set_objective()
        else:
            self.model.AddAssumptions(list(self.groups.values()))

    # ---- helpers
    def _post(self, group: str, ct) -> None:
        """Add a RULE. ct may be a Python bool when every term was fixed."""
        if self.diagnose:
            if group not in self.groups:
                self.groups[group] = self.model.NewBoolVar(f"rule::{group}")
            lit = self.groups[group]
            if isinstance(ct, bool):
                if not ct:
                    self.model.AddBoolOr([]).OnlyEnforceIf(lit)
            else:
                ct.OnlyEnforceIf(lit)
        else:
            if isinstance(ct, bool):
                if not ct:
                    self.model.AddBoolOr([])
            else:
                self.model.Add(ct)

    def _x(self, p: str, d: date, t: str):
        row = self.team[p].get(d)
        return 0 if row is None else row[t]

    @staticmethod
    def _is_fixed(x) -> bool:
        return isinstance(x, int)

    def _disparity(self, exprs, ub: int, tag: str):
        if not exprs:
            return 0
        mx = self.model.NewIntVar(0, ub, f"{tag}_max")
        mn = self.model.NewIntVar(0, ub, f"{tag}_min")
        for e in exprs:
            self.model.Add(mx >= e)
            self.model.Add(mn <= e)
        return mx - mn

    # ---- variables: only where the Grid says FREE
    def _build_variables(self):
        pb = self.pb
        working = pb.team_names
        for p in self.inp.persons:
            self.call[p], self.team[p] = {}, {}
            for d, cell in pb.call[p].items():
                self.call[p][d] = (self.model.NewBoolVar(f"call[{p},{d.isoformat()}]")
                                   if cell is FREE else int(cell))
            for d, cell in pb.team[p].items():
                if cell is FREE:
                    row = {t: self.model.NewBoolVar(f"team[{p},{d.isoformat()},{t}]") for t in working}
                    row[LEAVE] = 0
                    self._post("structure", sum(row[t] for t in working) == 1)
                else:
                    row = {t: int(cell == t) for t in working + [LEAVE]}
                self.team[p][d] = row

    # ---- RULES
    def _rule_call_demand(self):
        for d in self.inp.schedule_dates:
            req = self.inp.call_demand.get(d, 0)
            self._post("call_demand", sum(self.call[p][d] for p in self.inp.persons) == req)

    def _rule_call_interval(self):
        k = self.cfg.min_call_interval + 1
        if k <= 1:
            return
        dl = self.inp.dates
        for p in self.inp.persons:
            for i in range(len(dl) - k + 1):
                lits = [self.call[p][d] for d in dl[i:i + k]]
                if all(self._is_fixed(l) for l in lits):
                    continue   # fully fixed windows are checked in validate()
                self._post("call_interval", sum(lits) <= 1)

    def _rule_ps_cover(self):
        if not (self.cfg.ps_cover_rules and PS_COVER in self.pb.team_names):
            return
        for p in self.inp.persons:
            for d in self.pb.team_days(self.inp.schedule_dates):
                ps = self.team[p][d][PS_COVER]
                if self._is_fixed(ps) and ps == 0:
                    continue
                prev = d - ONE_DAY
                if prev in self.call[p]:   # covering someone who was on call, so not on call yourself
                    self._post("ps_cover_prev_night", ps + self.call[p][prev] <= 1)
                if self.cfg.ps_cover_blocks_same_night:
                    self._post("ps_cover_same_night", ps + self.call[p][d] <= 1)
            for days in self.pb.weeks.values():
                td = self.pb.team_days(days)
                if not any(d in self.pb.sched for d in td):
                    continue
                if any(self.team[p][d][LEAVE] == 1 for d in td):   # leave is always fixed
                    self._post("ps_cover_leave_week", sum(self.team[p][d][PS_COVER] for d in td) == 0)

    def _rule_team_demand(self):
        costs = []
        n = len(self.inp.persons)
        for d in self.pb.team_days(self.inp.schedule_dates):
            dem_row = self.inp.team_demand.get(d, {})
            for spec in self.inp.teams:
                dem = dem_row.get(spec.name, 0)
                h = sum(self._x(p, d, spec.name) for p in self.inp.persons)
                sf = self.model.NewIntVar(0, spec.allowed_shortfall, f"short[{d.isoformat()},{spec.name}]")
                su_ub = spec.allowed_surplus if spec.allowed_surplus is not None else n
                su = self.model.NewIntVar(0, su_ub, f"surplus[{d.isoformat()},{spec.name}]")
                self._post("team_demand", sf >= dem - h)     # h + shortfall >= demand
                self._post("team_demand", su >= h - dem)     # h - surplus  <= demand
                costs.append(spec.shortfall_cost * sf + spec.surplus_cost * su)
        self.terms["manpower"] = sum(costs)

    def _week_used_flags(self, p: str, days: List[date]):
        used = []
        for t in self.pb.team_names:
            lits = [self._x(p, d, t) for d in days]
            if any(self._is_fixed(l) and l == 1 for l in lits):
                used.append(1)
                continue
            free = [l for l in lits if not self._is_fixed(l)]
            if free:
                u = self.model.NewBoolVar(f"used[{p},{days[0].isoformat()},{t}]")
                for l in free:
                    self.model.Add(u >= l)        # definitional, not a rule
                used.append(u)
        return used

    def _rule_one_team_per_week(self):
        mode = self.cfg.one_team_per_week
        if mode == "off":
            return
        excess = []
        for p in self.inp.persons:
            for days in self.pb.weeks.values():
                td = self.pb.team_days(days)
                if not any(d in self.pb.sched for d in td):
                    continue
                used = self._week_used_flags(p, td)
                if not used:
                    continue
                if mode == "hard":
                    self._post("one_team_per_week", sum(used) <= 1)
                else:
                    ex = self.model.NewIntVar(0, len(used), f"excess_teams[{p},{td[0].isoformat()}]")
                    self.model.Add(ex >= sum(used) - 1)
                    excess.append(ex)
        if mode == "soft":
            self.terms["one_team_per_week"] = sum(excess)

    # ---- OBJECTIVE: calls
    def _fair_dates(self):
        return self.inp.dates if self.cfg.fairness_includes_history else self.inp.schedule_dates

    def _windows(self, size: int):
        dl = self.inp.dates
        for i in range(max(1, len(dl) - size + 1)):
            w = dl[i:i + size]
            if any(d in self.pb.sched for d in w):
                yield i, w

    def _objective_calls(self):
        P, fair = self.inp.persons, self._fair_dates()
        big = len(self.inp.dates)

        peaks = []
        for p in P:
            peak = self.model.NewIntVar(0, 7, f"peak7[{p}]")
            for _, w in self._windows(7):
                self.model.Add(peak >= sum(self.call[p][d] for d in w))
            peaks.append(peak)
        self.terms["call_peak"] = sum(peaks)

        gaps = []
        for p in P:   # rest[d] >= rest[d-1] + 1 unless called on d; linear, no multiplication
            mx = self.model.NewIntVar(0, big, f"maxgap[{p}]")
            prev = 0
            for d in self.inp.dates:
                r = self.model.NewIntVar(0, big, f"rest[{p},{d.isoformat()}]")
                self.model.Add(r >= prev + 1 - big * self.call[p][d])
                self.model.Add(mx >= r)
                prev = r
            gaps.append(mx)
        self.terms["call_max_gap"] = sum(gaps)

        wd = [sum(self.call[p][d] for d in fair if d.weekday() < 5) for p in P]
        we = [sum(self.call[p][d] for d in fair if d.weekday() >= 5) for p in P]
        tot = [sum(self.call[p][d] for d in fair) for p in P]
        self.terms["call_weekday_disparity"] = self._disparity(wd, big, "wd")
        self.terms["call_weekend_disparity"] = self._disparity(we, big, "we")
        self.terms["call_total_disparity"] = self._disparity(tot, big, "tot")

        months: Dict[tuple, List[date]] = defaultdict(list)
        for d in self.inp.dates:
            months[(d.year, d.month)].append(d)
        full = [days for days in months.values()
                if any(d in self.pb.sched for d in days) and len(days) == _days_in_month(days[0])]
        eq = []
        for p in P:
            eq.append(self._disparity([sum(self.call[p][d] for d in days) for days in full], 31, f"mon[{p}]"))
        self.terms["call_monthly_equity"] = sum(eq)

    # ---- OBJECTIVE: team evenness (per person across teams)
    def _objective_teams(self):
        names = [t for t in self.pb.team_names if t not in self.cfg.evenness_excludes]
        if len(names) < 2:
            self.terms["team_evenness"] = 0
            return
        big, fair, out = len(self.inp.dates), self._fair_dates(), []
        for p in self.inp.persons:
            counts = [sum(self._x(p, d, t) for d in fair) for t in names]
            out.append(self._disparity(counts, big, f"ev[{p}]"))
        self.terms["team_evenness"] = sum(out)

    # ---- OBJECTIVE: shittiness (independent of manpower)
    def _objective_shittiness(self):
        sh = {t.name: t.shittiness for t in self.inp.teams if t.shittiness}
        csh = {d: v for d, v in self.inp.call_shittiness.items() if v}
        unit = max(sh.values(), default=0) + max(csh.values(), default=0)
        if unit == 0:
            return
        W, fair = self.cfg.shittiness_window_days, set(self._fair_dates())
        peaks, totals = [], []
        for p in self.inp.persons:
            load = {}
            for d in self.inp.dates:
                e = 0
                for t, s in sh.items():
                    e = e + s * self._x(p, d, t)
                if d in csh:
                    e = e + csh[d] * self.call[p][d]
                load[d] = e
            peak = self.model.NewIntVar(0, W * unit, f"shit_peak[{p}]")
            for _, w in self._windows(W):
                self.model.Add(peak >= sum(load[d] for d in w))
            peaks.append(peak)
            totals.append(sum(load[d] for d in fair))
        self.terms["shittiness_peak"] = sum(peaks)
        self.terms["shittiness_disparity"] = self._disparity(totals, len(self.inp.dates) * unit, "shit_tot")

    def _set_objective(self):
        parts = []
        for name, expr in self.terms.items():
            w = getattr(self.cfg.weights, name)
            if w:
                parts.append(w * expr)
        if parts:
            self.model.Minimize(sum(parts))

    # ---- SOLVE
    def solve(self, log: bool = True) -> RosterSolution:
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = float(self.cfg.max_solve_time_seconds)
        status = solver.Solve(self.model, ProgressLogger() if log else None)
        name = solver.StatusName(status)
        sol = RosterSolution(status=name)
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            self._extract(solver, sol)
            print(f"[solver] {name} | objective {sol.objective}")
        else:
            print(f"[solver] {name}")
        self._solver = solver
        return sol

    def _extract(self, solver, sol: RosterSolution):
        v = lambda x: int(x) if isinstance(x, int) else solver.Value(x)
        sol.objective = solver.ObjectiveValue()
        sol.calls = {p: {d: v(x) for d, x in row.items()} for p, row in self.call.items()}
        sol.teams = {p: {d: next((t for t, l in row.items() if v(l) == 1), None) for d, row in rows.items()}
                     for p, rows in self.team.items()}
        for d in self.pb.team_days(self.inp.schedule_dates):
            dem = self.inp.team_demand.get(d, {})
            hc = {t.name: sum(v(self._x(p, d, t.name)) for p in self.inp.persons) for t in self.inp.teams}
            sol.headcount[d] = hc
            sol.shortfall[d] = {t: max(0, dem.get(t, 0) - n) for t, n in hc.items() if dem.get(t, 0) > 0}
        for name, expr in self.terms.items():
            raw = v(expr)
            sol.term_values[name] = raw
            sol.term_costs[name] = raw * getattr(self.cfg.weights, name)

    def conflicting_rules(self) -> List[str]:
        """Only meaningful on a diagnose=True model that solved INFEASIBLE."""
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = max(30.0, float(self.cfg.max_solve_time_seconds))
        status = solver.Solve(self.model)
        if status != cp_model.INFEASIBLE:
            return []
        core = solver.SufficientAssumptionsForInfeasibility()
        proto = self.model.Proto()
        return sorted(proto.variables[i].name.replace("rule::", "") for i in core)


def _days_in_month(d: date) -> int:
    nxt = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
    return (nxt - d.replace(day=1)).days


# =====================================================================
# Entry point
# =====================================================================
def solve_roster(inputs: RosterInputs, cfg: Optional[RosterConfig] = None, log: bool = True) -> RosterSolution:
    cfg = cfg or RosterConfig()
    pb = Problem(inputs, cfg)
    report_issues(validate(pb))                    # raises on errors, prints warnings
    sol = RosterModel(pb).solve(log=log)
    if sol.status == "INFEASIBLE":
        sol.conflicting_rules = RosterModel(pb, diagnose=True).conflicting_rules()
        print("[diagnose] these rule groups cannot all hold together:", sol.conflicting_rules or
              "none of the switchable groups (check fixed locks / structure)")
    return sol


def format_grid(sol: RosterSolution, inputs: RosterInputs) -> str:
    """Plain-text roster for the schedule range: team initial per day, '*' = on call that night."""
    dl = inputs.schedule_dates
    lines = ["            " + " ".join(d.strftime("%d") for d in dl)]
    for p in inputs.persons:
        cells = []
        for d in dl:
            t = sol.teams.get(p, {}).get(d)
            c = "." if t is None else ("-" if t == LEAVE else t[0])
            cells.append(c + ("*" if sol.calls[p][d] else " "))
        lines.append(f"{p:<11} " + " ".join(cells))
    return "\n".join(lines)


# =====================================================================
# Example
# =====================================================================
if __name__ == "__main__":
    people = [f"P{i:02d}" for i in range(1, 13)]
    inputs = RosterInputs.from_raw(
        start="31/08/2026", end="27/09/2026",
        schedule_start="14/09/2026", schedule_end="27/09/2026",
        persons=people,
        teams=[
            TeamSpec("ds", allowed_shortfall=1, shortfall_cost=50, shittiness=2),
            TeamSpec("cos", allowed_shortfall=2, shortfall_cost=10),
            TeamSpec("cc", allowed_shortfall=0, shortfall_cost=200, shittiness=1),
            TeamSpec(PS_COVER, allowed_shortfall=0, shortfall_cost=500),
        ],
        call_demand={d: 2 for d in daterange(date(2026, 9, 14), date(2026, 9, 27))},
        team_demand={d: {"ds": 3, "cos": 3, "cc": 3, PS_COVER: 1}
                     for d in daterange(date(2026, 9, 14), date(2026, 9, 27)) if d.weekday() < 5},
        leaves_blockouts={"P03": [("16/09/2026", "L")], "P07": [("21/09/2026", "L"), ("22/09/2026", "L")]},
        call_locks={"P01": {"12/09/2026": 1}, "P02": {"13/09/2026": 1}},   # past data, cannot change
        team_locks={"P01": {"11/09/2026": "ds"}},
    )
    result = solve_roster(inputs, RosterConfig(max_solve_time_seconds=20))
    if result.ok:
        print(format_grid(result, inputs))
        print("objective terms:", result.term_costs)
        print("shortfalls:", {d.isoformat(): s for d, s in result.shortfall.items() if s})