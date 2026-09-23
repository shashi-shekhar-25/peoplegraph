"""PeopleGraph — succession on a live employee graph, running on this machine.

Same engine and same design system as the hosted demo in site/; the difference
is that this one reads your own export and routes free text through a model on
the same laptop.
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

import nlq
import peoplegraph as pg
import ui

try:
    import succession as sx
except ImportError:          # the open-source build: no succession engine
    sx = None

st.set_page_config(page_title="PeopleGraph", layout="wide",
                   initial_sidebar_state="collapsed")
st.markdown(ui.CSS, unsafe_allow_html=True)

MODULES = ["Intake", "Succession", "Scenario", "Skills", "Org design", "Hiring", "Ask",
           "Council pack"]


# ---------------------------------------------------------------- state
def audit(action: str, detail: str = ""):
    st.session_state.setdefault("audit", []).append({
        "when": datetime.now().strftime("%H:%M:%S"),
        "viewer": st.session_state.get("viewer", "CHRO")
                  + (" · " + st.session_state["division"] if st.session_state.get("division") else ""),
        "action": action, "detail": detail,
    })


@st.cache_resource(show_spinner="Resolving entities…")
def load_company(_source, key: str):
    return pg.load(_source)


def shown(name, code: str = "") -> str:
    if not st.session_state.get("mask", True) or (code and code in st.session_state.get("revealed", set())):
        return str(name)
    return pg.mask_name(name)


def write(html_: str):
    st.markdown(html_, unsafe_allow_html=True)


# ---------------------------------------------------------------- shell
st.session_state.setdefault("mask", True)
st.session_state.setdefault("revealed", set())
st.session_state.setdefault("removed", set())
st.session_state.setdefault("division", None)

write('<div class="pg-mast"><span class="mark">PeopleGraph</span>'
      '<span class="sub">One graph of people, roles, skills and sites.</span>'
      '<span class="right"><span class="pg-local">Processed on this machine · no external API</span>'
      '</span></div>')

bar = st.columns([1.5, 1.5, 1.1, 2.4])
with bar[0]:
    viewer = st.radio("Viewer", ["CHRO", "HRBP"], horizontal=True, key="viewer")
with bar[3]:
    with st.expander("Data source"):
        upload = st.file_uploader("Drop a different HRIS export (CSV)", type="csv")
        st.caption("Read in this process and never written anywhere else.")

source = upload if upload else "data/employees_messy.csv"
source_name = upload.name if upload else "employees_messy.csv · bundled sample"
co = load_company(source, source_name)
divisions = sorted(co.people["division"].unique())

with bar[1]:
    if viewer == "HRBP":
        st.session_state["division"] = st.selectbox(
            "Your division", divisions,
            index=divisions.index("Quality") if "Quality" in divisions else 0)
    else:
        st.session_state["division"] = None
        st.markdown('<div style="padding-top:26px;font-size:12.5px;color:#5A5F66">'
                    'All divisions</div>', unsafe_allow_html=True)
with bar[2]:
    st.markdown('<div style="height:22px"></div>', unsafe_allow_html=True)
    st.checkbox("Mask names", key="mask")


my_div = st.session_state["division"]
scope = co.people if my_div is None else co.people[co.people["division"] == my_div]
removed = st.session_state["removed"]

write('<p class="pg-caption" style="margin-top:-6px">Loaded: %s · %d people · resolved in this '
      'process</p>' % (ui.esc(source_name), len(co.people)))

tabs = st.tabs(MODULES)


def scope_note(hidden: int, what: str):
    if my_div and hidden:
        write('<p class="pg-note">Scoped to %s. %d %s in other divisions are hidden from an '
              'HRBP; the CHRO view shows all.</p>' % (my_div, hidden, what))


def needs_toolkit(what: str):
    write(ui.state("%s is in the Succession Toolkit" % what,
                   "Scored benches, readiness tiers, flight-risk reasons, scenarios and build-or-buy "
                   "come with the PeopleGraph Succession Toolkit, which runs in a browser with nothing "
                   "to install. This open-source build cleans the export and charts the organisation: "
                   "Intake, Skills, Org design and the nine-box all work here. peoplegraph.co.in/toolkits"))


# ---------------------------------------------------------------- intake
with tabs[0]:
    st.markdown("### What the sheet got wrong")
    write('<p class="pg-note">Dropped in as exported. Nothing was cleaned by hand; every fix below '
          'is one the ingestion made and can show you.</p>')
    write(ui.metrics([
        (co.raw_rows, "rows in the file"),
        (len(co.people), "people after resolution", "%d merged" % (len(co.people) - co.raw_rows)),
        (len(co.issues), "faults found"),
        (co.skill_variants_collapsed, "skill strings collapsed"),
    ]))
    order = ["duplicate person", "circular reporting line", "manager has exited",
             "manager not on roster", "self-reporting", "division missing",
             "band system mismatch", "potential scale mismatch", "skill variants collapsed",
             "unrecognised band"]
    groups: dict[str, list] = {}
    for i in co.issues:
        groups.setdefault(i.kind, []).append(i)
    for kind in order + [k for k in groups if k not in order]:
        group = groups.get(kind)
        if not group:
            continue
        with st.expander("%s — %d" % (kind, len(group)), expanded=kind in order[:2]):
            for i in group[:15]:
                st.markdown("- " + i.detail)
            if len(group) > 15:
                st.caption("…and %d more" % (len(group) - 15))

    st.markdown("###### Resolved roster")
    roster = scope.copy()
    roster["name"] = [shown(n, c) for n, c in zip(roster["name"], roster["emp_code"])]
    roster["skills"] = roster["skills_list"].map(lambda s: ", ".join(s))
    st.dataframe(roster[["emp_code", "name", "title", "division", "band", "location", "status",
                         "rating", "potential", "months_in_role", "skills"]],
                 hide_index=True, use_container_width=True, height=260)


# ---------------------------------------------------------------- succession
def bench_card(c: dict, role_title: str):
    name = shown(c["name"], c["emp_code"])
    if c["status"] == "Notice":
        name = '<span class="strike">%s</span>' % ui.esc(name)
        cls, risk_badge = "t-leaving", ui.badge("Serving notice", "leaving", True)
    else:
        cls = ui.TIER_CLASS.get(c["tier"], "t-emerging")
        risk_badge = ui.badge("Flight risk " + c["flight_risk"],
                              ui.RISK_TONE[c["flight_risk"]], c["flight_risk"] == "High")
    tier_badge = ui.badge(c["tier"], "ready" if c["tier"] == "Ready now"
                          else "caution" if c["tier"] == "Ready in 1–2 years" else "graph")
    parts = "".join(
        '<div><span>%s</span>%s<span>%d</span></div>'
        % (k.replace("_", " "), ui.meter(v, "", 100), v) for k, v in c["parts"].items())
    why = ""
    if c["status"] == "Notice":
        why = ('<p class="why">Serving notice — shown, not dropped. Confirm the last working day '
               'before this bench is counted.</p>')
    elif c["risk_reasons"]:
        why = '<p class="why"><b>Why:</b> %s</p>' % ui.esc("; ".join(c["risk_reasons"]))
    gaps = ('<p class="why"><b>Gaps:</b> %s</p>' % ui.esc(", ".join(c["missing_skills"]))
            if c["missing_skills"] else "")
    write('<div class="pg-record %s"><div><h4>%s %s%s</h4>'
          '<p class="who">%s · %s · %s · %s · calibrated rating %s</p>%s%s</div>'
          '<div><div class="score">%s<em>/100</em></div><div class="pg-break">%s</div></div></div>'
          % (cls, name, tier_badge, risk_badge, ui.esc(c["title"]), ui.esc(c["division"]),
             ui.esc(c["location"]), ui.esc(c["band"]), ui.esc(c["rating"]), why, gaps,
             ("%.1f" % c["score"]), parts))

    cols = st.columns([1, 1, 1, 3])
    if st.session_state["mask"] and c["emp_code"] not in st.session_state["revealed"]:
        if cols[0].button("Reveal name", key="rev" + c["emp_code"] + role_title):
            st.session_state["revealed"].add(c["emp_code"])
            audit("revealed name", "%s on the %s bench" % (c["emp_code"], role_title))
            st.rerun()
    if cols[1].button("Take off the board", key="rm" + c["emp_code"] + role_title):
        st.session_state["removed"].add(c["emp_code"])
        audit("added to scenario", "%s taken off the board" % shown(c["name"], c["emp_code"]))
        st.rerun()
    with cols[3].expander("Move up a tier"):
        reason = st.text_input("Reason — this goes in the audit trail",
                               key="why" + c["emp_code"] + role_title)
        if st.button("Confirm move", key="mv" + c["emp_code"] + role_title):
            if not reason.strip():
                st.warning("A tier move needs a reason.")
            else:
                audit("moved candidate up a tier",
                      "%s on %s: %s" % (shown(c["name"], c["emp_code"]), role_title, reason.strip()))
                st.success("Recorded in the audit log.")


def nine_box_grid(division):
    grid = pg.nine_box(co, division)
    pot_labels = {1: "Well placed", 2: "Growth", 3: "Ready for more"}
    perf_labels = {3: "Delivering", 2: "Meeting", 1: "Below"}
    cells = '<div class="axis"></div>' + "".join(
        '<div class="axis">%s</div>' % pot_labels[p] for p in (1, 2, 3))
    for perf in (3, 2, 1):
        cells += '<div class="axis">%s</div>' % perf_labels[perf]
        for pot in (1, 2, 3):
            n = int(((grid["performance"] == perf) & (grid["potential"] == pot)).sum())
            cells += ('<div class="cell"><b>%d</b><span>%s, %s</span></div>'
                      % (n, perf_labels[perf].lower(), pot_labels[pot].lower()))
    write('<div class="pg-grid">%s</div>' % cells)
    write('<p class="pg-caption">Both axes come from the sheet: the calibrated rating and the '
          'potential the last council recorded.</p>')
    pick = st.selectbox("Open a box", ["—"] + sorted(grid["box"].unique()), key="box")
    if pick != "—":
        chosen = grid[grid["box"] == pick]
        audit("opened nine-box cell", "%s (%d)" % (pick, len(chosen)))
        write(ui.table([("Name", lambda r: shown(r["name"], r["emp_code"])), ("Role", "title"),
                        ("Division", "division")],
                       chosen.head(40).to_dict("records"),
                       "First 40 of %d." % len(chosen) if len(chosen) > 40 else ""))


with tabs[1]:
    if sx is None:
        needs_toolkit("Succession")
        nine_box_grid(my_div)
    else:
        roles = pg.critical_roles(co)
        roles = roles if my_div is None else roles[roles["division"] == my_div]
        if roles.empty:
            write(ui.state("No critical roles in your scope",
                           "An HRBP sees their own division. Switch the viewer to CHRO, or pick a "
                           "division that has critical roles."))
        else:
            labels = {"%s — %s (%s, %s)" % (r["title"], shown(r["name"], r["emp_code"]),
                                            r["division"], r["location"]): r["emp_code"]
                      for _, r in roles.iterrows()}
            keys = list(labels)
            default = next((i for i, k in enumerate(keys) if k.startswith("Head of QA")), 0)
            st.markdown("### Succession")
            write('<p class="pg-note">Candidates are scored against the incumbent\'s role, not a job '
                  'description nobody has updated. Score = role similarity 35%, skill coverage 30%, '
                  'band gap 15%, calibrated rating 10%, time in role 10%.</p>')
            pick = st.selectbox("Critical role", keys, index=default, label_visibility="collapsed")
            code = labels[pick]
            if st.session_state.get("last_role") != code:
                st.session_state["last_role"] = code
                audit("viewed succession bench", pick)

            b = sx.bench(co, code)
            live = [c for c in b["candidates"] if c["emp_code"] not in removed]
            ready = [c for c in live if c["tier"] == "Ready now"]
            at_risk = [c for c in ready if c["flight_risk"] == "High"]

            scope_note(len(pg.critical_roles(co)) - len(roles), "critical roles")
            marks = ""
            if b["regulatory_critical"]:
                marks += ui.badge("Regulatory-critical role", "risk", True)
            if len(ready) <= 1:
                marks += ui.badge("Single point of failure", "risk")
            if at_risk:
                marks += ui.badge("Ready-now successor at flight risk", "caution")
            if not marks:
                marks = ui.badge("Bench covered", "ready")
            write('<div style="margin:6px 0 10px">%s</div>' % marks)
            if b["regulatory_critical"]:
                write('<p class="pg-note">A vacancy here is a compliance exposure, not only a '
                      'headcount gap.</p>')
            write(ui.metrics([
                (len(ready), "ready now"), (len(live), "on the bench"),
                ("%.0f mo" % b["target"]["months_in_role"] if b["target"]["months_in_role"] else "—",
                 "incumbent time in role"),
                (len(at_risk), "ready now, at flight risk"),
            ]))
            if live:
                for c in live:
                    bench_card(c, b["target"]["title"])
            else:
                write(ui.state("This bench is empty",
                               "Everyone scored for this role is off the board in the scenario."))

            st.markdown('<div style="height:20px"></div>', unsafe_allow_html=True)
            write('<span class="pg-eyebrow">Calibration</span>')
            st.markdown("### Rating against recorded potential")
            nine_box_grid(my_div)


# ---------------------------------------------------------------- scenario
with tabs[2]:
    if sx is None:
        needs_toolkit("Scenario")
    else:
        st.markdown("### Scenario")
        write('<p class="pg-note">Resignations do not arrive one per division. Take people off the '
              'board and watch which critical roles lose their cover.</p>')
        by_code = co.people.set_index("emp_code")
        options = [c for c in scope["emp_code"] if by_code.at[c, "status"] != "Exited"]
        picked = st.multiselect(
            "Off the board", options, default=sorted(removed & set(options)),
            format_func=lambda c: "%s — %s" % (shown(by_code.at[c, "name"], c), by_code.at[c, "title"]))
        if set(picked) != (removed & set(options)):
            for c in set(picked) - removed:
                audit("added to scenario", shown(by_code.at[c, "name"], c))
            for c in (removed & set(options)) - set(picked):
                audit("returned to the board", shown(by_code.at[c, "name"], c))
            st.session_state["removed"] = set(picked)
            st.rerun()

        if not removed:
            write(ui.state("Nobody is off the board yet",
                           "Pick a name above, or use “Take off the board” on a bench card. Start with "
                           "a ready-now successor already flagged at flight risk — that is the case "
                           "this tool exists to surface."))
        else:
            moved = sx.what_if(co, list(removed))
            if my_div is not None and not moved.empty:
                moved = moved[moved["division"] == my_div]
            if moved.empty:
                write(ui.state("Nothing breaks",
                               "Those departures do not remove a ready-now successor from any critical "
                               "role in your scope. Try someone who appears on several benches."))
            else:
                write(ui.table([
                    ("Critical role", "role"), ("Incumbent", lambda r: shown(r["incumbent"])),
                    ("Division", "division"),
                    ("Ready now before", "ready_now_before", True),
                    ("After", "ready_now_after", True),
                    ("", lambda r: ui.badge("Exposed · regulatory" if r["regulatory_critical"] else "Exposed",
                                            "risk", True) if r["now_exposed"]
                     else ui.badge("Thinner", "caution")),
                ], moved.to_dict("records"),
                    "%d critical roles change when those people leave." % len(moved)))

        write('<span class="pg-eyebrow">Concentration</span>')
        st.markdown("### Names carrying more than one bench")
        overlap = sx.successor_overlap(co)
        if overlap.empty:
            write(ui.state("No concentration",
                           "No single person is the ready-now answer for more than one critical role."))
        else:
            write(ui.table([("Name", lambda r: shown(r["name"])),
                            ("Ready now for", "ready_now_for", True), ("Roles", "roles")],
                           overlap.head(12).to_dict("records"),
                           "One person listed as ready now for several roles is one resignation away "
                           "from several gaps."))


# ---------------------------------------------------------------- skills
with tabs[3]:
    st.markdown("### Skills")
    write('<p class="pg-note">Demand is the number of critical roles whose incumbent holds the '
          'skill. Backup depth is the people senior enough to cover one of those roles, still '
          'here, and not already sitting in one.</p>')
    sk = pg.skills_report(co)
    exposed = sk[sk["exposure"] != ""]
    write(ui.metrics([
        (len(sk), "canonical skills"), (len(exposed), "flagged exposed"),
        (int((exposed["exposure"].isin(["Thin", "Single expert"])).sum()),
         "fewer backups than dependent roles"),
        (co.skill_variants_collapsed, "raw strings collapsed into these"),
    ]))
    only_exposed = st.checkbox("Only skills a critical role depends on and few people can cover",
                               value=True)
    rows = (exposed if only_exposed else sk)
    if rows.empty:
        write(ui.state("No skills match that filter",
                       "Nothing here is both depended on by a critical role and thinly covered."))
    else:
        write(ui.table([
            ("Skill", "skill"), ("Holders", "holders", True),
            ("Leaving", lambda r: r["leaving"] or "—", True),
            ("Backup depth", lambda r: ui.Raw('<span style="white-space:nowrap">%d %s</span>' % (
                r["senior_cover"],
                ui.meter(100 * r["senior_cover"] / max(r["critical_roles_needing_it"], 1),
                         "risk" if r["senior_cover"] < max(r["critical_roles_needing_it"], 1)
                         else "ready", 56))), True),
            ("Sites with cover", "senior_sites", True),
            ("Critical roles needing it", "critical_roles_needing_it", True),
            ("Exposure", lambda r: ui.badge(r["exposure"], "risk" if r["exposure"] == "Single expert"
                                            else "caution", r["exposure"] == "Single expert")
             if r["exposure"] else "—"),
        ], rows.head(60).to_dict("records"),
            "Backup depth is measured against the number of critical roles depending on the skill."))


# ---------------------------------------------------------------- org design
with tabs[4]:
    st.markdown("### Org design")
    write('<p class="pg-note">Span, depth and duplicated roles, read straight off the reporting '
          'edges — including the ones the export had broken.</p>')
    org = pg.org_design(co)
    write(ui.metrics([
        (org["median_span"], "median span of control"), (org["deepest"], "layers from the top"),
        (len(org["thin_spans"]), "managers with one report"),
        (len(org["duplicated_titles"]), "roles duplicated across divisions"),
    ]))
    peak = max(org["layers"]["people"])
    bars = "".join('<div><span>Layer %s</span><span class="bar"><i style="width:%d%%"></i></span>'
                   '<span class="n">%d</span></div>'
                   % (r["layer"], 100 * r["people"] / peak, r["people"])
                   for _, r in org["layers"].iterrows())
    write('<div class="pg-layers">%s</div>' % bars)

    st.markdown("###### Widest spans")
    widest = org["widest"]
    widest = widest if my_div is None else widest[widest["division"] == my_div]
    write(ui.table([("Manager", lambda r: shown(r["name"])), ("Role", "title"),
                    ("Division", "division"), ("Site", "location"),
                    ("Direct reports", "direct_reports", True), ("Layer", "layer", True)],
                   widest.head(8).to_dict("records")))

    st.markdown("###### Same role, several divisions")
    if org["duplicated_titles"].empty:
        write(ui.state("No duplicated titles",
                       "No role title is held in more than one division in this roster."))
    else:
        write(ui.table([("Role", "role"), ("Holders", "holders", True),
                        ("Divisions", "divisions", True), ("Sites", "sites", True)],
                       org["duplicated_titles"].head(10).to_dict("records"),
                       "Worth a look before the next reorg."))


# ---------------------------------------------------------------- hiring
CALL_TONE = {"Buy": "risk", "Build": "caution", "Watch": "caution", "Covered": "ready"}
with tabs[5]:
    if sx is None:
        needs_toolkit("Hiring")
    else:
        st.markdown("### Hiring")
        write('<p class="pg-note">Build or buy, decided by what the bench can actually cover rather '
              'than by who shouts loudest in the budget round.</p>')
        plan = sx.hiring_plan(co)
        plan = plan if my_div is None else plan[plan["division"] == my_div]
        counts = plan["call"].value_counts().to_dict()
        write(ui.metrics([
            (counts.get("Buy", 0), "roles with nothing internal within two years"),
            (counts.get("Build", 0), "roles to build toward"),
            (counts.get("Watch", 0), "roles resting on one safe name"),
            (counts.get("Covered", 0), "roles genuinely covered"),
        ]))
        scope_note(len(sx.hiring_plan(co)) - len(plan), "critical roles")
        if plan.empty:
            write(ui.state("No critical roles in your scope", "Switch the viewer to CHRO."))
        else:
            write(ui.table([
                ("Call", lambda r: ui.badge(r["call"], CALL_TONE[r["call"]], r["call"] == "Buy")),
                ("Critical role", lambda r: ui.Raw(ui.esc(r["role"])
                 + (" " + ui.badge("Regulatory", "risk") if r["regulatory_critical"] else ""))),
                ("Division", "division"), ("Ready now", "ready_now", True), ("Why", "why"),
                ("Nearest internal", lambda r: shown(r["nearest_internal"])),
                ("Skills to close", lambda r: r["skills_to_close"] or "—"),
            ], plan.to_dict("records"), "Sorted hardest first: buy, build, watch, covered."))


# ---------------------------------------------------------------- ask
with tabs[6]:
    st.markdown("### Ask")
    model = nlq.available_model()
    write('<p class="pg-note">%s</p>' %
          ("A model on this machine turns the question into a graph query. Nothing is sent anywhere."
           if model else
           "Ollama is not running, so questions route through the keyword fallback. The five "
           "templated questions still work."))
    st.session_state.setdefault("question", nlq.TEMPLATES[0][0])
    cols = st.columns(len(nlq.TEMPLATES))
    for col, (q, _) in zip(cols, nlq.TEMPLATES):
        if col.button(q.split(",")[0][:30] + "…", help=q, key="t" + q[:12]):
            st.session_state["question"] = q
    question = st.text_input("Ask the graph", key="question")

    go = st.button("Answer", type="primary")
    if question and (go or st.session_state.get("answered") != question):
        st.session_state["answered"] = question
        st.session_state["routed"] = nlq.route(question, model)
        audit("ran query", "%s  [%s]" % (question, st.session_state["routed"][1]))
    if question and st.session_state.get("routed"):
        slots, how = st.session_state["routed"]
        headline, tbl, extra = nlq.answer(co, slots, fmt=shown)
        write('<div class="pg-answer">%s</div><div class="pg-how">routed by %s → %s</div>'
              % (ui.esc(headline), ui.esc(how), ui.esc(slots.get("intent"))))
        if extra.get("bench"):
            write(ui.table([("Name", lambda c: shown(c["name"], c["emp_code"])), ("Tier", "tier"),
                            ("Score", lambda c: "%.1f" % c["score"], True),
                            ("Flight risk", "flight_risk"), ("Status", "status"),
                            ("Current role", "title")], tbl["candidates"]))
        elif tbl is not None and not tbl.empty:
            t2 = tbl.copy()
            for col in ("name", "incumbent"):
                if col in t2:
                    t2[col] = [shown(n) for n in t2[col]]
            st.dataframe(t2, hide_index=True, use_container_width=True)


# ---------------------------------------------------------------- roadmap
with tabs[7]:
    write('<div class="pg-roadmap"><h3>Council pack</h3>'
          '<p class="pg-note">One document for the talent council: every critical role, its bench, '
          'the flight-risk flags, and the tier moves made since the last cycle with the reasons '
          'typed against them. It is the audit log and the benches printed together.</p>'
          '<p class="pg-note"><b>Not in this build.</b> Everything it needs is already on the '
          'graph; it is a rendering job, not a modelling one — and it is why every tier move asks '
          'for a reason.</p></div>')


# ---------------------------------------------------------------- audit panel
# Rendered last so it includes everything logged during this run.
st.markdown("---")
log = st.session_state.get("audit", [])
with st.expander("Audit log (%d) — every query, who ran it, when" % len(log)):
    if log:
        st.dataframe(pd.DataFrame(log[::-1]), hide_index=True, use_container_width=True)
    else:
        st.caption("Nothing logged yet.")
    if st.button("Clear audit log"):
        st.session_state["audit"] = []
        st.rerun()
