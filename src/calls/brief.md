INPUT

DR Name, Team, 
Avail Name, DOM, Available
Day DOM, Need

MODEL

Call (Dr, Day) = 0,1 {0 if free, 1 if on call}

CONSTRAINT

No calls within 2 days of each other (no D+1, no D+2) - x[i][d] + x[i][d+1] + x[i][d+2] ≤ 1
For every day, total On Call = Need - sum(x[i][d]) == Need[d]
For every not available, On Call = No

OBJECTIVES

1. Optimise for equal total amount of calls
2. Optimise for equal weekday-weekend ratio
3. Optimise for spread out calls (minimise range of gap duration)

OUTPUT

Call Name, DOM, OnCall?




4. Optimise for spread across teams
