"""One runnable check: every seeded trap is caught, and the modules on the graph hold.

    .venv/bin/python test_peoplegraph.py
"""
import peoplegraph as pg

co = pg.load("data/employees_messy.csv")
kinds = co.counts()

# --- the messy sheet is actually cleaned -----------------------------------
assert co.raw_rows > len(co.people), "duplicates were not merged"
assert kinds.get("duplicate person", 0) >= 3, kinds
assert kinds.get("circular reporting line", 0) >= 1, "reorg loop missed"
assert kinds.get("manager has exited", 0) >= 1, "exited manager missed"
assert kinds.get("manager not on roster", 0) >= 1, "orphan manager code missed"
assert kinds.get("self-reporting", 0) >= 1, "self-reporting missed"
assert kinds.get("division missing", 0) >= 10, "blank divisions missed"
assert kinds.get("band system mismatch", 0) == 1, "legacy grading system missed"
assert co.skill_variants_collapsed > 100, "skill variants not collapsed"

# Five spellings of HPLC end up as one skill on the graph.
hplc_like = [n for n in co.graph if n.lower().startswith("skill:h") and "chromat" in n.lower()]
assert hplc_like == [], f"HPLC variants still separate nodes: {hplc_like}"
assert "skill:HPLC" in co.graph

# No cycle survives into the reporting edges, and every manager exists.
codes = set(co.people["emp_code"])
assert all(m in codes or m == "" for m in co.people["manager_code"])
assert all(m != c for m, c in zip(co.people["manager_code"], co.people["emp_code"]))
qa = co.people[co.people["title"].str.startswith("Head of QA")].iloc[0]
assert len(pg.chain(co, qa["emp_code"])) >= 2, "reporting chain broken"

# --- the modules on the same graph ------------------------------------------
sk = pg.skills_report(co)
assert "HPLC" in set(sk["skill"]) and "SAP MM" in set(sk["skill"]), "acronym casing mangled"
assert (sk["staying"] <= sk["holders"]).all()
assert (sk[sk["exposure"] == "Single expert"]["critical_roles_needing_it"] >= 1).all()

org = pg.org_design(co)
assert org["deepest"] >= 4 and org["median_span"] >= 1
assert org["layers"]["people"].sum() == len(co.people[co.people["status"] != "Exited"])
assert (org["thin_spans"].shape[0] >= 0) and "role" in org["duplicated_titles"]

box = pg.nine_box(co)
assert len(box) == len(co.people[co.people["status"] != "Exited"])
assert set(box["performance"]) <= {1, 2, 3} and set(box["potential"]) <= {1, 2, 3}

print(f"ok — {co.raw_rows} rows in, {len(co.people)} people, {len(co.issues)} issues, "
      f"{len(sk)} skills, {org['deepest']} layers")
