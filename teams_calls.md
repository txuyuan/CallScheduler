## Roster Optimization System Documentation

### 1. Input Data Structure

| Parameter Name | Data Type | Description / Example Structure |
| --- | --- | --- |
| `start_date` / `end_date` | `str` (DD/MM/YYYY) | The scheduling window bounds (e.g., `'01/01/2026'` to `'31/01/2026'`). |
| `persons` | `list` of `str` | List of staff identifiers (e.g., `['Dr. Smith', 'Dr. Doe']`). |
| `team_options` | `list` of `str` | Available roster roles (e.g., `['team_ds', 'leave', 'team_cos', 'team_c', 'ps_cover']`). |
| `team_requirements` | `dict` | Minimum headcount per team per date (e.g., `{'01/01/2026': {'team_ds': 2}}`). |
| `min_team_requirements` | `dict` | Global or baseline minimum headcount targets per team. |
| `team_sacrificability` | `dict` | Priority weighting per team for shortage penalties (e.g., `{'team_ds': 1, 'leave': 5}`). |
| `call_requirements` | `dict` | Number of overnight calls required per calendar date (e.g., `{'01/01/2026': 1}`). |
| `leaves_blockouts` | `dict` | Staff-specific leave (`'L'`) or blockout (`'B'`) dates mapped as tuples/lists. |

---

### 2. Configuration Variables

| Variable Name | Type | Range / Default | Description |
| --- | --- | --- | --- |
| `call_interval` | `int` | $\ge 0$ (Default: `2`) | Minimum spacing (in days) required between two assigned calls for any staff member. |
| `max_teams_per_week` | `int` | $\ge 1$ (Default: `1`) | Maximum number of different clinical teams/roles a staff member can work per Monday-to-Sunday week. |
| `leave_buffers` | `list` of `int` | `[1, 0]` | Pre- and post-buffer day offsets where nighttime calls are restricted around leave. |
| `blockout_buffers` | `list` of `int` | `[1, 0]` | Pre- and post-buffer day offsets where nighttime calls are restricted around blockouts. |
| `max_solve_time_seconds` | `float` | $> 0$ (Default: `None`) | Maximum allotted timeout limit for the OR-Tools CP-SAT solver. |

---

### 3. Constraints

* **Nighttime Unavailability & Buffers:** Forces a staff member's overnight call variable to `0` if they are on leave, blocked out, or within designated pre/post buffer windows.
* **Call Interval Spacing:** Enforces at most one call assignment within any rolling window defined by `call_interval + 1` days per person.
* **Daily Call Requirements:** Ensures the sum of assigned staff calls on any calendar day precisely matches `call_requirements`.
* **Leave Locking:** Locks daytime team assignments to `'leave'` if pre-booked leave is registered, and strictly forbids unrequested leave assignments otherwise.
* **Minimum Team Headcounts:** Guarantees that weekday team presences meet or exceed the specified `min_team_requirements`.
* **Weekly Team Diversity Limit:** Restricts the count of unique exclusive clinical teams a staff member touches in a single week to $\le$ `max_teams_per_week`.
* **Post-Call Cover (PCC) Safety Rule:** Prevents fatigue by enforcing that any staff member assigned to a Post-Call Cover (`ps_cover`) shift on a weekday must be call-free on the preceding calendar day.

---

### 4. Optimizations & Objective Function Weights

The model minimizes a combined objective penalty score composed of the following weighted components:

* **Call Spread Optimization (Weight: $\times 2$):**
* *Mathematical Explanation:* Measures rolling concentrations by summing calls over every 7-day window per person ($\sum \text{window\_calls}$). Minimizing this prevents clustering of heavy shifts.


* **Weekday Call Disparity (Weight: $\times 5$):**
* *Mathematical Explanation:* Computes the gap between the maximum and minimum weekday call totals across all staff ($\max(\text{wd\_sum}) - \min(\text{wd\_sum})$) to ensure fair distribution.


* **Weekend Call Disparity (Weight: $\times 5$):**
* *Mathematical Explanation:* Computes the gap between the maximum and minimum weekend call totals across all staff ($\max(\text{we\_sum}) - \min(\text{we\_sum})$).


* **Team Evenness Variance (Weight: $\times 3$):**
* *Mathematical Explanation:* Minimizes the variance between an individual staff member's most-worked and least-worked clinical team ($\max(\text{team\_counts}) - \min(\text{team\_counts})$) to promote balanced workload variety.


* **Staffing Shortfall Penalties (Weight: Dynamic $1000 / \text{priority}^2$):**
* *Mathematical Explanation:* Penalizes unmet daily team requirements multiplied by an inverse-square priority weight derived from `team_sacrificability`, ensuring critical teams face minimal shortfalls.



$$\text{Total Objective} = 2 \cdot \sum \text{spread} + 5 \cdot \text{wd\_disparity} + 5 \cdot \text{we\_disparity} + 3 \cdot \sum \text{team\_variance} + \sum \text{shortfalls}$$

---

Would you like to examine how specific custom constraints can be added to this model?