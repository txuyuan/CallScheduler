from ortools.sat.python import cp_model

OBJ1_TOLERANCE = 0 # relax as needed so the next section has more leeway and doesn't become infeasible
OBJ2_TOLERANCE = 0
OBJ3_TOLERANCE = 0

COUNT_SOLUTIONS = False

def get_blockouts(num_doctors, num_days):
    blockout_grid = [
        [	1,	1,	1,	1,	1,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	],
        [	1,	1,	1,	1,	1,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	],
        [	1,	1,	1,	1,	1,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	],
        [	1,	1,	1,	1,	1,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	],
        [	0,	0,	0,	0,	0,	0,	1,	1,	1,	1,	1,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	],
        [	0,	0,	0,	0,	0,	0,	1,	1,	1,	1,	1,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	],
        [	0,	0,	0,	0,	0,	0,	1,	1,	1,	1,	1,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	],
        [	0,	0,	0,	0,	0,	0,	1,	1,	1,	1,	1,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	],
        [	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	1,	1,	1,	1,	1,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	],
        [	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	1,	1,	1,	1,	1,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	],
        [	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	1,	1,	1,	1,	1,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	],
        [	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	1,	1,	1,	1,	1,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	],
        [	0,	0,	0,	0,	0,	1,	1,	1,	1,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	],
        [	0,	0,	0,	0,	0,	1,	1,	1,	1,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	],
        [	0,	0,	0,	0,	0,	1,	1,	1,	1,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	],
        [	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	1,	1,	1,	1,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	],
        [	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	1,	1,	1,	1,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	],
        [	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	1,	1,	1,	1,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	],
        [	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	1,	1,	1,	1,	0,	0,	0,	0,	0,	0,	0,	0,	],
        [	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	1,	1,	1,	1,	0,	0,	0,	0,	0,	0,	0,	0,	],
        [	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	1,	1,	1,	1,	0,	0,	0,	0,	0,	0,	0,	0,	],
        [	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	1,	1,	1,	1,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	],
        [	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	1,	1,	1,	1,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	],
        [	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	1,	1,	1,	1,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	],
        [	0,	0,	0,	0,	0,	0,	0,	0,	1,	1,	1,	1,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	],
        [	0,	0,	0,	0,	0,	0,	0,	0,	1,	1,	1,	1,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	],
        [	0,	0,	0,	0,	0,	0,	0,	0,	1,	1,	1,	1,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	],
        [	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	1,	1,	1,	1,	],
        [	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	1,	1,	1,	1,	],
        [	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	1,	1,	1,	1,	],
        [	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	],
        [	1,	1,	1,	1,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	],
        [	1,	1,	1,	1,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	],
        [	1,	1,	1,	1,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	],
        [	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	],
        [	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	0,	],
    ]
    blockouts = {}
    for dr in range(num_doctors):
        for day in range(num_days):
            blockouts[(dr, day)] = blockout_grid[dr][day]
    return blockouts

def get_weekends(num_days):
    weekends = []
    for i in range(len(range(num_days))):
        if i % 7 == 0 or i % 7 == 1:
            weekends.append(1)
        else:
            weekends.append(0)
    return weekends

class SolutionCounter(cp_model.CpSolverSolutionCallback):
    """Counts the number of solutions found"""
    def __init__(self):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.__solution_count = 0

    def on_solution_callback(self):
        self.__solution_count += 1

    def solution_count(self):
        return self.__solution_count

def main():
    # 0a. inputs
    num_doctors = 36
    num_days = 31
    all_needs = [6] * len(range(num_days)) # indexed by the day

    blockouts = get_blockouts(num_doctors, num_days) # conforms to size dr * day

    weekends = get_weekends(num_days) # indexed by the day

    # 1. Model
    print("1. setting up model")
    model = cp_model.CpModel()
    calls = {}
    for dr in range(num_doctors):
        for day in range(num_days):
            calls[(dr, day)] = model.new_bool_var(f"call_dr{dr}_day{day}")

    # 2a. Coverage per day
    print("2. adding constraints")
    for day in range(num_days):
        model.add(sum(calls[(dr, day)] for dr in range(num_doctors)) == all_needs[day])

    # 2b. No calls within 2 days of each other (no D+1, no D+2)
    for dr in range(num_doctors):
        for day in range(num_days)[:-2]:
            model.add(sum([calls[dr, day], calls[dr, day+1], calls[dr, day+2]]) <= 1)

    # 2c. Blockouts
    for dr in range(num_doctors):
        for day in range(num_days):
            model.add(calls[(dr, day)] + blockouts[dr, day] <= 1)

    # 3a. Minimise range of total call load
    #     Using sum deviation from avg call load * total doctors
    print("3. constructing objectives")
    total_calls = sum(all_needs)
    
    call_count = [model.new_int_var(0, num_days, f"call_count_dr{dr}") for dr in range(num_doctors)]
    call_count_deviation = [model.new_int_var(0, num_doctors * num_days, f"call_count_dev_dr{dr}") for dr in range(num_doctors)]
    for dr in range(num_doctors):
        # count total calls
        model.add(call_count[dr] == sum( calls[(dr, day)] for day in range(num_days) ))

        signed_call_count_deviation = model.new_int_var(-num_days * num_doctors, num_days * num_doctors, f"call_count_dev_signed_dr{dr}")
        # scaled deviation = | total calls * doctors - avg calls * doctors (==total calls) |
        model.add(signed_call_count_deviation == call_count[dr] * num_doctors - total_calls)
        model.add_abs_equality(call_count_deviation[dr], signed_call_count_deviation)

    call_count_dev = sum(call_count_deviation)
    call_count_dev_scaling = num_doctors * num_doctors # metadata to display metric properly

    # 3b. Minimise range of weekends done
    #     Using sum deviation from avg weekend call load * total doctors
    total_weekend_calls = 0
    total_weekends = 0
    for day in range(num_days):
        total_weekend_calls += weekends[day] * all_needs[day]
        total_weekends += weekends[day]

    weekend_call_count = [model.new_int_var(0, total_weekends, f"weekend_count_dr{dr}") for dr in range(num_doctors)]
    weekend_deviation = [model.new_int_var(0, num_doctors * total_weekends, f"weekend_count_dev_dr{dr}") for dr in range(num_doctors)]
    for dr in range(num_doctors):
        # count weekend calls
        model.add(weekend_call_count[dr] == sum( calls[(dr, day)] for day in range(num_days) if weekends[day] == 1 ))

        signed_weekend_deviation = model.new_int_var(-total_weekends * num_doctors, total_weekends * num_doctors, f"weekend_count_dev_signed_dr{dr}")
        # scaled deviation = | weekend calls * doctors - avg * doctors (==total weekend calls) |
        model.add(signed_weekend_deviation == weekend_call_count[dr] * num_doctors - total_weekend_calls)
        model.add_abs_equality(weekend_deviation[dr], signed_weekend_deviation)

    weekend_count_dev = sum(weekend_deviation)
    weekend_count_dev_scaling = num_doctors * num_doctors # metadata to display metric properly

    # 3c. Minimise variance in gaps between calls (also including blockout dates)
    largest_gaps = []
    for dr in range(num_doctors):
        gaps = []
        
        # use running rest periods to find gaps
        prev_rest = 0 # init to static int, will be var later
        for day in range(num_days):
            is_rest_day = model.new_bool_var(f"is_working_dr{dr}_day{day}")
            model.add_multiplication_equality(is_rest_day, [1 - calls[(dr, day)], 1 - blockouts[(dr, day)]])
            is_working_day = is_rest_day.Not()

            # gap = (prev + 1) * (1 - call) => increment unless call then set to 0
            # tmp = (prev + 1). add_multiplication_equality can't take multiple expressions
            tmp = model.new_int_var(0, num_days + 1, f"rest_tmp_dr{dr}_day{day}")
            model.add(tmp == prev_rest + 1)
            new_rest = model.new_int_var(0, num_days, f"rest_dr{dr}_day{day}")
            model.add_multiplication_equality(new_rest, [tmp, is_rest_day])

            # gap weighted = prev * call => count the previous gap if its just been reset
            gap_weighted = model.new_int_var(0, num_days, f"gap_dr{dr}_day{day}")
            model.add_multiplication_equality(gap_weighted, [prev_rest, is_working_day])
            gaps += [gap_weighted]

            prev_rest = new_rest
        gaps += [prev_rest] # trailing rest period

        # find largest gap
        largest_gap = model.new_int_var(0, num_days, f"max_gap_dr{dr}")
        model.add_max_equality(largest_gap, gaps)
        largest_gaps.append(largest_gap)

    largest_gap_sum = sum(largest_gaps)
    largest_gap_sum_scaling = num_doctors

    # 4a. Setup base model
    model_copy = model.clone()

    # 4b. Iteratatively solve for objectives
    objectives = [
        ("equal load call", "avg call load deviation from mean", call_count_dev, call_count_dev_scaling, OBJ1_TOLERANCE), 
        ("equal weekend load", "avg weekend call load deviation from mean", weekend_count_dev, weekend_count_dev_scaling, OBJ2_TOLERANCE),
        ("spread out calls", "avg largest gap", largest_gap_sum, largest_gap_sum_scaling, OBJ3_TOLERANCE)
    ]
    for i, (obj_purpose, obj_name, objective, obj_scaling, obj_tolerance) in enumerate(objectives):
        print(f"4. solving for objective {i+1} ({obj_purpose})")
        model = model_copy.clone()
        model.minimize(objective)
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 40.0
        # solver.parameters.log_search_progress = True
        status = solver.Solve(model)

        print(f"status [{status}]")
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            optimal_obj = solver.Value(objective)
            scaled_optimal_obj = round(optimal_obj / obj_scaling, 2)
            solve_time = round(solver.wall_time, 2)
            print(f"solved in {solve_time}s. {obj_name}: {scaled_optimal_obj}")
        else:
            # infeasible
            print("no solution possible, no matter how unfair")
            exit(0)
        
        # add this result to base model
        if i != len(objectives) - 1:
            model_copy.add(objective <= optimal_obj + obj_tolerance)

        # get amt of remaining ideal solutions, for debugging
        if COUNT_SOLUTIONS:
            counting_model = model_copy.clone()
            solver = cp_model.CpSolver()
            solution_counter = SolutionCounter()
            solver.parameters.enumerate_all_solutions = True
            solver.parameters.log_search_progress = True
            solver.parameters.max_time_in_seconds = 20.0

            status = solver.Solve(counting_model, solution_counter)
            print(f"Number of optimal solutions currently: {solution_counter.solution_count()}")

        print()


    #5. Output
    print("5. outputting")
    shifts_per_person = [solver.Value(call_count[dr]) for dr in range(num_doctors)]
    weekends_per_person = [solver.Value(weekend_call_count[dr]) for dr in range(num_doctors)]
    print(f"shifts per person: {shifts_per_person}")
    print(f"weekends per person: {weekends_per_person}")

    call_schedule = {}
    for dr in range(num_doctors):
        for day in range(num_days):
            call_schedule[(dr, day)] = solver.Value(calls[(dr, day)])

    print()
    for dr in range(num_doctors):
        for day in range(num_days):
            if call_schedule[(dr, day)] == 1 and blockouts[(dr, day)] == 0:
                print("C", end=", ")
            elif call_schedule[(dr, day)] == 0 and blockouts[(dr, day)] == 1:
                print("B", end=", ")
            elif call_schedule[(dr, day)] == 1 and blockouts[(dr, day)] == 1:
                print("ERR", end=", ")
            elif call_schedule[(dr, day)] == 0 and blockouts[(dr, day)] == 0:
                print("0", end=", ")
        print()
    
    # 6. Find the number of optimal solutions

if __name__=="__main__":
    main()