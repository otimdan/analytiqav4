"""Generate the MVP test-fixture CSVs (deterministic, stdlib only).

Run:  python docs/mvp-testing/generate_fixtures.py
Produces three CSVs alongside this script:
  - students_survey.csv   clean, well-typed  -> happy path
  - sales_messy.csv       dirty types/values -> recoverable errors
  - edge_cases.csv        degenerate/hostile -> failure modes
"""
import csv
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
random.seed(42)


def write(name, header, rows):
    path = os.path.join(HERE, name)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"wrote {name}: {len(rows)} rows")


# ---------------------------------------------------------------- clean
# Real relationships are baked in so tests actually find something:
#   study_hours ↑ exam, attendance ↑ exam, High stress ↓ exam,
#   Female slightly higher, part-time job slightly lower.
stress_levels = ["Low", "Medium", "High"]
students = []
for i in range(1, 91):
    gender = random.choice(["Male", "Female"])
    age = random.randint(18, 30)
    study = round(random.uniform(2, 25), 1)
    attendance = round(random.uniform(55, 100), 1)
    ptj = random.choice(["Yes", "No"])
    st = random.choices(stress_levels, weights=[0.35, 0.40, 0.25])[0]
    penalty = {"Low": 0, "Medium": -4, "High": -9}[st]
    base = (40 + study * 1.4 + (attendance - 55) * 0.25 + penalty
            + (2.5 if gender == "Female" else 0)
            + (-3 if ptj == "Yes" else 0))
    exam = max(0.0, min(100.0, round(base + random.gauss(0, 5), 1)))
    students.append([i, gender, age, study, attendance, ptj, st, exam, random.randint(1, 5)])

write(
    "students_survey.csv",
    ["student_id", "gender", "age", "study_hours_per_week", "attendance_rate",
     "part_time_job", "stress_level", "exam_score", "satisfaction"],
    students,
)


# ---------------------------------------------------------------- messy
# Currency strings, thousands separators, "%", "N/A"/"NULL"/blank, mixed
# date formats, inconsistent categorical casing/whitespace, messy booleans.
regions = ["North", "south ", "North ", " South", "north", "SOUTH"]
cats = ["Electronics", "Furniture", "Clothing", "Groceries"]
date_formats = ["{y}-{m:02d}-{d:02d}", "{d:02d}/{m:02d}/{y}", "{m:02d}-{d:02d}-{y}"]
returned_tokens = ["Yes", "No", "Y", "N", "yes", "no"]

sales = []
for i in range(1001, 1056):
    m, d = random.randint(1, 12), random.randint(1, 28)
    date = random.choice(date_formats).format(y=2024, m=m, d=d) if random.random() > 0.08 else ""
    rev_val = random.uniform(50, 9000)
    revenue = "N/A" if random.random() < 0.06 else f"${rev_val:,.2f}"
    units = random.choice(["NULL", "", str(random.randint(1, 40))]) if random.random() < 0.15 else str(random.randint(1, 40))
    discount = f"{random.choice([0, 5, 10, 15, 20])}%" if random.random() > 0.1 else ""
    age = random.choice(["", "unknown", str(random.randint(18, 70))]) if random.random() < 0.12 else str(random.randint(18, 70))
    sales.append([i, date, random.choice(regions), random.choice(cats),
                  revenue, units, discount, age, random.choice(returned_tokens)])

write(
    "sales_messy.csv",
    ["order_id", "order_date", "region", "product_category", "revenue",
     "units_sold", "discount_pct", "customer_age", "returned"],
    sales,
)


# ---------------------------------------------------------------- edge
# Space/symbol column names (KeyError bait), a zero-variance column, an
# all-missing column, a wild outlier, duplicate rows, tiny sample size.
edge_header = ["Customer Name", "Total $", "region", "constant_col", "all_missing", "score"]
edge = [
    ["Ada Lovelace", "$1,200.00", "East", "ACTIVE", "", 78],
    ["Alan Turing", "$980.50", "West", "ACTIVE", "", 82],
    ["Grace Hopper", "$1,050.00", "East", "ACTIVE", "", 91],
    ["Katherine Johnson", "$2,300.75", "West", "ACTIVE", "", 88],
    ["Ada Lovelace", "$1,200.00", "East", "ACTIVE", "", 78],   # duplicate row
    ["Edsger Dijkstra", "$40.00", "North", "ACTIVE", "", 12],
    ["Barbara Liskov", "$1,999,999.00", "South", "ACTIVE", "", 99],  # outlier
    ["Donald Knuth", "$760.25", "North", "ACTIVE", "", 65],
    ["Margaret Hamilton", "$1,340.00", "East", "ACTIVE", "", 84],
    ["John von Neumann", "$0.00", "West", "ACTIVE", "", 0],
    ["Claude Shannon", "$650.00", "South", "ACTIVE", "", 71],
    ["Tim Berners-Lee", "$1,120.00", "North", "ACTIVE", "", 77],
]
write(edge_header, edge_header, edge) if False else write("edge_cases.csv", edge_header, edge)
