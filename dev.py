import random

# to generate the placeholder blackout date

def get_blockouts(all_doctors, all_days):
    blockouts = {}
    for dr in all_doctors:
        dates = random.sample(all_days, 7)
        for day in all_days:
            blockouts[(dr, day)] = 1 if day in dates else 0
    return blockouts

num_doctors = 36
num_days = 31
all_doctors = range(num_doctors) # each dr is a number, starting from 0
all_days = range(num_days) # day is a number, starting from 0
all_needs = [6] * len(all_days) # indexed by the day

blockouts = get_blockouts(all_doctors, all_days)
print(blockouts)


print("[")
for dr in all_doctors:
    print("    [", end="")
    for day in all_days:
        print(blockouts[(dr, day)], end=", ")
    print("], ")
print("]")