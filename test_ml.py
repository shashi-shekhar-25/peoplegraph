"""The attrition model learns a real pattern, refuses a fake one, and never sees
protected columns.

    .venv/bin/python test_ml.py
"""
import random

import pandas as pd

import ml
import peoplegraph as pg

co = pg.load("data/employees_messy.csv")
m = ml.attrition(co)

# The seeded pattern is learnable, and the model says so in plain words.
assert m["status"] == "ok" and m["auc"] >= ml.MIN_AUC, m.get("auc")
assert m["leavers"] >= ml.MIN_LEAVERS and m["scores"], "no scores on the seeded sample"
texts = {a["text"] for a in m["associations"]}
assert texts & {"being in the first two years", "lower recorded potential", "working in Commercial"}, texts
assert all(0 < s["p"] < 1 for s in m["scores"])
assert m["scores"] == sorted(m["scores"], key=lambda s: -s["p"])
assert {s["risk"] for s in m["scores"]} <= {"High", "Medium", "Low"}
assert all(len(s["why"]) == len(s["actions"]) <= 3 for s in m["scores"])

# Never an input: date of birth, age, gender, name, email.
assert not any(k in ("dob", "age", "gender", "name", "email") for k in m["keys"]), m["keys"]

# Shuffle who left among the same people: the pattern is gone, and so are the scores.
fake = pg.load("data/employees_messy.csv")
rows = fake.people.index[fake.people["status"].isin(["Active", "Exited"])].tolist()
pairs = list(zip(fake.people.loc[rows, "status"], fake.people.loc[rows, "exit_date"]))
random.Random(1).shuffle(pairs)
fake.people.loc[rows, "status"] = [s for s, _ in pairs]
fake.people.loc[rows, "exit_date"] = pd.Series([d for _, d in pairs], index=rows, dtype=object)
f = ml.attrition(fake)
assert f["auc"] < 0.6 and f["status"] == "weak" and "scores" not in f, f["auc"]

# Too little history: say so, and do not fit anything.
thin = pg.load("data/employees_messy.csv")
gone = thin.people.index[thin.people["status"] == "Exited"][10:]
thin.people.loc[gone, "status"] = "Active"
t = ml.attrition(thin)
assert t["status"] == "thin" and "auc" not in t and "30" in t["reason"], t

# The count range brackets the expectation, and a bench with no one ready is always gone.
r = ml.leaver_range([s["p"] for s in m["scores"]])
assert r["p10"] <= r["expected"] <= r["p90"]
assert ml.all_leave([]) == 1.0

print(f"ok — {m['leavers']} leavers, picks the leaver {ml.plain_auc(m['auc'])} (shuffled: {f['auc']:.2f}), "
      f"{sum(s['risk'] == 'High' for s in m['scores'])} high, {r['p10']}–{r['p90']} leavers expected next year")
