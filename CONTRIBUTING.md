# Contributing

Thanks for helping. A few rules keep this safe to work on in public.

## Never commit real people data

Only synthetic data belongs in this repository. Reproduce bugs on
`data/employees_messy.csv`, or add a made-up row that has the same shape as the
export that broke. `.gitignore` blocks everything else in `data/` and any
`.xlsx`; do not force-add around it.

## Before you open a pull request

```bash
.venv/bin/python test_peoplegraph.py
```

It must print `ok`. If you change ingestion, add an assertion to that file for
the fault you now catch, and seed the fault in `generate_data.py` so the
sample keeps exercising it.

## What fits

- New export shapes: column aliases, date formats, grading systems, status
  values — with a seeded example.
- Resolution rules that catch a fault real exports have, and say in the
  Intake list what they did.
- Org design and skills-supply views that read the existing graph.
- UI changes that follow `DESIGN.md`: tokens, component anatomy, and the
  loading, empty, error, disabled and permission states.

## What does not

- Anything that sends data off the machine by default.
- Opaque scoring. Every number shown should be explainable from the sheet.
- Succession scoring and the council pack: those are the paid toolkit, and
  pull requests adding them here will be closed.

## Style

Match the surrounding code. Plain pandas and NetworkX, small functions,
comments that say why. No new dependencies without a reason in the PR.

By contributing you agree your contribution is licensed under the Apache
License 2.0.
