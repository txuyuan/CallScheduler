from ortools.sat.python import cp_model

OBJ1_TOLERANCE = 0 # relax as needed so the next section has more leeway and doesn't become infeasible
OBJ2_TOLERANCE = 0

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
    call_count = [model.new_int_var(0, num_days, f"total_{dr}") for dr in range(num_doctors)]
    call_count_deviation = [model.new_int_var(0, num_doctors * num_days, f"call_count_dev_{dr}") for dr in range(num_doctors)]
    for dr in range(num_doctors):
        # link total calls per doctor
        model.add(call_count[dr] == sum( calls[(dr, day)] for day in range(num_days) ))
        # link deviations per doctor
        signed_call_count_deviation = model.new_int_var(-num_doctors * num_days, num_doctors * num_days, f"signed_call_count_dev_{dr}")
        model.add(signed_call_count_deviation == call_count[dr] * num_doctors - total_calls)
        model.add_abs_equality(call_count_deviation[dr], signed_call_count_deviation)

    call_count_dev = sum(call_count_deviation)

    # 3b. Minimise range of weekends done
    #     Using sum deviation from avg weekend call load * total doctors
    total_weekend_calls = 0
    total_weekends = 0
    for day in range(num_days):
        total_weekend_calls += weekends[day] * all_needs[day]
        total_weekends += weekends[day]
    weekend_call_count = [model.new_int_var(0, num_days, f"weekend_count_{dr}") for dr in range(num_doctors)]
    weekend_deviation = [model.new_int_var(0, num_doctors * total_weekends, f"weekend_count_dev_{dr}") for dr in range(num_doctors)]
    for dr in range(num_doctors):
        model.add(weekend_call_count[dr] == sum( calls[(dr, day)] for day in range(num_days) if weekends[day] == 1 ))
        signed_weekend_deviation = model.new_int_var(-num_doctors * total_weekends, num_doctors * total_weekends, f"weekend_signed_dev_{dr}")
        model.add(signed_weekend_deviation == weekend_call_count[dr] * num_doctors - total_weekend_calls) # scaled to total calls
        model.add_abs_equality(weekend_deviation[dr], signed_weekend_deviation)

    weekend_count_dev = sum(weekend_deviation)

    # 4a. Setup clone models
    model_copy = model.clone()

    # 4b. Iteratatively solve for objectives
    objectives = [
        ("equal load call", call_count_dev, OBJ1_TOLERANCE), 
        ("equal weekend load", weekend_count_dev, OBJ2_TOLERANCE)
    ]
    for i, (objective_name, objective, obj_tolerance) in enumerate(objectives):
        print(f"4. solving for objective {i} ({objective_name})")
        model = model_copy.clone()
        model.minimize(objective)
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 20.0
        # solver.parameters.log_search_progress = True
        status = solver.Solve(model)

        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            optimal_obj = solver.Value(objective)
            scaled_optimal_obj = optimal_obj / num_doctors
            print(f"solved [{status}]. normalised value: {scaled_optimal_obj}")
        else:
            # infeasible
            print(f"solved [{status}]")
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