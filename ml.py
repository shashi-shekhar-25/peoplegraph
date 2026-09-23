"""Attrition model: learns who left in the last twelve months from your own
export, on this machine, and says how much to trust it.

Plain logistic regression with every number explainable: standardised inputs,
an L2 penalty, Newton steps from zero, a fixed seed for the cross-validation
folds. Same file, same answer. kit/ml.js in the toolkits is the same model
rule for rule.

Never used as inputs: date of birth or age, gender, name, email.

    .venv/bin/python ml.py            # model card for the bundled sample
"""
from __future__ import annotations

import math

import numpy as np

import peoplegraph as pg

YEAR = 365.25
MIN_LEAVERS, MIN_PEOPLE, MIN_AUC = 30, 200, 0.65
L2, ITER, FOLDS, SEED = 1.0, 25, 5, 20260922
POTENTIAL = {1: "Well placed", 2: "Growth", 3: "Ready for more"}

# key, raises the odds when the weight is positive, when it is negative, why (per person), what to do
FEATURES = [
    ("since_promotion", "longer since the last promotion", "a recent promotion",
     lambda x, p: f"{x:.1f} years since the last promotion",
     "Have a career conversation: what would the next move be, and when?"),
    ("in_role", "longer in the same role", "less time in the current role",
     lambda x, p: f"{x:.1f} years in the same role", "Discuss a stretch assignment, rotation or new scope."),
    ("tenure", "longer with the company", "being newer to the company",
     lambda x, p: f"{x:.1f} years with the company", "Hold a stay interview: what keeps them, what would make them go?"),
    ("first_two_years", "being in the first two years", "being past the first two years",
     lambda x, p: "in their first two years with the company", "Check onboarding: a 90-day conversation and a buddy."),
    ("rating", "a higher calibrated rating", "a lower calibrated rating",
     lambda x, p: f"last calibrated rating {x:g}", "Talk about recognition, pay position and workload."),
    ("potential", "higher recorded potential", "lower recorded potential",
     lambda x, p: f"recorded potential: {POTENTIAL[int(x)]}",
     "Revisit the potential rating and the development plan at the next council."),
    ("level", "a more junior band", "a more senior band",
     lambda x, p: f"band {p['band']}", "Compare pay and progression with peers in the same band."),
    ("manager_left", "a manager who has left or is leaving", "a manager who is staying",
     lambda x, p: "their manager has left or is leaving", "Confirm who their manager is now and hold a one-to-one this month."),
]
BY_KEY = {f[0]: f for f in FEATURES}
DIV_ACT = "Look at what is driving exits in this division: workload, manager, pay."


# ---------------------------------------------------------------- numbers
def mulberry32(a: int):
    """The toolkits' seeded generator, bit for bit, so the folds match."""
    state = [a & 0xFFFFFFFF]

    def imul(x, y):
        return ((x & 0xFFFFFFFF) * (y & 0xFFFFFFFF)) & 0xFFFFFFFF

    def rnd():
        state[0] = (state[0] + 0x6D2B79F5) & 0xFFFFFFFF
        a = state[0]
        t = imul(a ^ (a >> 15), 1 | a)
        t = ((t + imul(t ^ (t >> 7), 61 | t)) & 0xFFFFFFFF) ^ t
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296
    return rnd


def sigmoid(z):
    return 1 / (1 + np.exp(-np.clip(z, -35, 35)))


def fit(Z: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Newton steps from zero; weights, intercept last (not penalised)."""
    X = np.hstack([Z, np.ones((len(Z), 1))])
    d = Z.shape[1]
    w = np.zeros(d + 1)
    pen = np.full(d + 1, L2)
    pen[d] = 0.0
    for _ in range(ITER):
        p = sigmoid(X @ w)
        g = X.T @ (p - y) + pen * w
        H = (X * (p * (1 - p))[:, None]).T @ X + np.diag(pen)
        w = w - np.linalg.solve(H, g)
    return w


def score(w, z):
    return float(sigmoid(w[-1] + float(np.dot(w[:-1], z))))


def auc(p, y) -> float:
    """The chance a random leaver scores above a random stayer (ties count half)."""
    p, y = np.asarray(p, float), np.asarray(y)
    order = np.argsort(p, kind="stable")
    rank = np.empty(len(p))
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and p[order[j + 1]] == p[order[i]]:
            j += 1
        rank[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    pos = int(y.sum())
    neg = len(y) - pos
    return float((rank[y == 1].sum() - pos * (pos + 1) / 2) / (pos * neg)) if pos and neg else 0.5


def folds(y) -> list[int]:
    """Stratified: leavers and stayers each shuffled with the fixed seed, dealt round-robin."""
    rnd, f = mulberry32(SEED), [0] * len(y)
    for cls in (1, 0):
        ids = [i for i, v in enumerate(y) if v == cls]
        for i in range(len(ids) - 1, 0, -1):
            j = math.floor(rnd() * (i + 1))
            ids[i], ids[j] = ids[j], ids[i]
        for n, i in enumerate(ids):
            f[i] = n % FOLDS
    return f


# ---------------------------------------------------------------- the frame
def _d(v):
    """A date, or None: pandas can hand back NaN for a missing one."""
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else v


def _years(ref, d):
    d = _d(d)
    return None if d is None else max(0.0, (ref - d).days / YEAR)


def _raw(p, ref, status_by_code) -> dict:
    tenure = _years(ref, p["doj"])
    anchor = _d(p["last_promotion"]) or _d(p["date_in_role"]) or _d(p["doj"])
    return {
        "since_promotion": _years(ref, anchor),
        "in_role": _years(ref, _d(p["date_in_role"]) or _d(p["doj"])),
        "tenure": tenure,
        "first_two_years": 1 if tenure is not None and tenure < 2 else 0,
        "rating": float(p["rating_score"]),
        "potential": float(p["potential_score"]),
        "level": float(p["level"]),
        "manager_left": 1 if status_by_code.get(p["manager_code"]) in ("Exited", "Notice") else 0,
    }


def attrition(co: pg.Company, as_of=None) -> dict:
    T = as_of or pg.TODAY
    people = co.people.to_dict("records")
    status_by_code = {p["emp_code"]: p["status"] for p in people}
    train = []
    for p in people:
        ex = _d(p["exit_date"])
        if p["status"] == "Active":
            train.append((p, 0, T))
        elif p["status"] == "Exited" and ex is not None and 0 <= (T - ex).days < 365:
            train.append((p, 1, ex))
    leavers = sum(y for _, y, _ in train)
    out = {"leavers": leavers, "people": len(train), "base_rate": leavers / len(train) if train else 0.0,
           "min_leavers": MIN_LEAVERS, "min_people": MIN_PEOPLE, "min_auc": MIN_AUC}
    if leavers < MIN_LEAVERS or len(train) < MIN_PEOPLE:
        out["status"] = "thin"
        out["reason"] = (f"The file has {leavers} leavers in the last 12 months; the model needs at least "
                         f"{MIN_LEAVERS} to learn from." if leavers < MIN_LEAVERS else
                         f"The file has {len(train)} people; the model needs at least {MIN_PEOPLE}.")
        return out

    div_count: dict[str, int] = {}
    for p, _, _ in train:
        div_count[p["division"]] = div_count.get(p["division"], 0) + 1
    divisions = sorted(d for d, n in div_count.items() if d and n >= 15)
    keys = [f[0] for f in FEATURES] + [f"division:{d}" for d in divisions]

    def vector(raw, p):
        return [(1 if p["division"] == k[9:] else 0) if k.startswith("division:") else raw[k] for k in keys]

    rows = [vector(_raw(p, ref, status_by_code), p) for p, _, ref in train]
    y = np.array([v for _, v, _ in train])
    mean, sd = [], []
    for j in range(len(keys)):
        vals = [r[j] for r in rows if r[j] is not None]
        m = sum(vals) / len(vals) if vals else 0.0
        for r in rows:
            if r[j] is None:
                r[j] = m
        v = sum((r[j] - m) ** 2 for r in rows) / len(rows)
        mean.append(m)
        sd.append(math.sqrt(v) if v > 0 else 1.0)
    mean_a, sd_a = np.array(mean), np.array(sd)

    def standard(x):
        return np.array([0.0 if v is None else (v - mean[j]) / sd[j] for j, v in enumerate(x)])
    Z = (np.array(rows, float) - mean_a) / sd_a

    f = np.array(folds(list(y)))
    oof = np.zeros(len(y))
    for k in range(FOLDS):
        wk = fit(Z[f != k], y[f != k])
        oof[f == k] = sigmoid(Z[f == k] @ wk[:-1] + wk[-1])
    w = fit(Z, y)
    out["auc"] = auc(oof, y)
    out["keys"] = keys
    out["model"] = {"mean": mean, "sd": sd, "w": w.tolist()}

    assoc = []
    for j, key in enumerate(keys):
        wj = float(w[j])
        if key.startswith("division:"):
            if wj > 0:
                assoc.append({"key": key, "weight": wj, "text": f"working in {key[9:]}"})
        else:
            assoc.append({"key": key, "weight": wj, "text": BY_KEY[key][1] if wj > 0 else BY_KEY[key][2]})
    assoc = sorted((a for a in assoc if abs(a["weight"]) >= 0.1), key=lambda a: -abs(a["weight"]))[:5]
    for a in assoc:
        a["strength"] = "strong" if abs(a["weight"]) >= 0.5 else "moderate"
    out["associations"] = assoc

    out["status"] = "ok" if out["auc"] >= MIN_AUC else "weak"
    out["reason"] = "" if out["status"] == "ok" else (
        f"Tested on people it had not seen, the model picked the actual leaver only {round(out['auc'] * 100)} "
        "times in 100 — too close to a coin toss to score individuals.")
    if out["status"] != "ok":
        return out

    high, medium = 2 * out["base_rate"], 1.25 * out["base_rate"]
    scores = []
    for p in people:
        if p["status"] != "Active":
            continue
        raw = _raw(p, T, status_by_code)
        x = vector(raw, p)
        z = standard(x)
        prob = score(w, z)
        contrib = []
        for j, key in enumerate(keys):
            c = float(w[j] * z[j])
            if c <= 0.15:
                continue
            if key.startswith("division:") and x[j] != 1:
                continue
            if key in ("first_two_years", "manager_left") and not raw[key]:
                continue
            contrib.append((c, key))
        contrib = sorted(contrib, key=lambda t: -t[0])[:3]
        scores.append({
            "emp_code": p["emp_code"], "name": p["name"], "title": p["title"], "division": p["division"],
            "band": p["band"], "is_critical": bool(p["is_critical"]), "p": prob,
            "risk": "High" if prob >= high else "Medium" if prob >= medium else "Low",
            "why": [BY_KEY[k][3](raw[k], p) if k in BY_KEY else f"works in {p['division']}" for _, k in contrib],
            "actions": [BY_KEY[k][4] if k in BY_KEY else DIV_ACT for _, k in contrib],
        })
    out["scores"] = sorted(scores, key=lambda s: -s["p"])
    out["by_code"] = {s["emp_code"]: s["p"] for s in out["scores"]}
    return out


# ---------------------------------------------------------------- what the scores add up to
def leaver_range(ps) -> dict:
    """Exact distribution of how many leave, each independently with their own chance."""
    mean = float(sum(ps))
    sd = math.sqrt(sum(p * (1 - p) for p in ps))
    kmax = min(len(ps), math.ceil(mean + 8 * sd + 10))
    dist = np.zeros(kmax + 1)
    dist[0] = 1.0
    for p in ps:
        dist[1:] = dist[1:] * (1 - p) + dist[:-1] * p
        dist[0] *= 1 - p
    cum = np.cumsum(dist)
    pct = lambda q: int(np.searchsorted(cum, q - 1e-15))
    return {"expected": mean, "p10": pct(0.1), "p90": pct(0.9)}


def all_leave(ps) -> float:
    """Chance that every one of these people leaves within the year."""
    out = 1.0
    for p in ps:
        out *= p
    return out


def plain_auc(a: float) -> str:
    return f"{round(a * 10)} times in 10"


def summary(m: dict) -> str:
    """The model card as a few plain sentences. Every figure is worked out here."""
    if m["status"] == "thin":
        return m["reason"] + " Include everyone who left in the last 12 months, with their exit date."
    out = [f"{m['leavers']} of {m['people']} people ({round(100 * m['base_rate'])}%) left in the last 12 months.",
           f"Tested on people it had not seen, the model picks the actual leaver {plain_auc(m['auc'])}."]
    if m["associations"]:
        out.append("Leaving was more common with " + "; ".join(a["text"] for a in m["associations"][:3]) + ".")
    if m["status"] == "ok":
        high = sum(s["risk"] == "High" for s in m["scores"])
        r = leaver_range([s["p"] for s in m["scores"]])
        out.append(f"{high} people now look most like last year's leavers, and between {r['p10']} and "
                   f"{r['p90']} people are expected to leave in the next 12 months.")
    else:
        out.append("That is too weak to score individuals, so nobody is scored.")
    out.append("These are patterns, not predictions about any person: use them to choose which conversations to have first.")
    return " ".join(out)


if __name__ == "__main__":
    m = attrition(pg.load("data/employees_messy.csv"))
    print(f"{m['status']}: {m['leavers']} leavers among {m['people']} people", end="")
    print(f", picks the leaver {plain_auc(m['auc'])}" if "auc" in m else f" — {m['reason']}")
    for a in m.get("associations", []):
        print(f"  {a['strength']}: {a['text']}")
