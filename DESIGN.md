# PeopleGraph design contract

One system across two surfaces: the hosted demo on the landing page and the
local Streamlit app. Shown back to back they must read as one product.

## Identity

A succession review is a document, not a dashboard. The reference is a talent
council workpaper in a regulated company: paper, hairline rules, numerals you
can line up, restraint. Not a dark SaaS console, not a gradient hero.

| Token | Value | Use |
| --- | --- | --- |
| `--paper` | `#F7F5F1` | page |
| `--card` | `#FFFFFF` | records, tables |
| `--ink` | `#16181C` | body text |
| `--ink-2` | `#5A5F66` | secondary text |
| `--rule` | `#DED9D0` | hairlines, borders |
| `--graph` | `#14433E` | brand, primary action, links |
| `--ready` | `#1F6F4A` | ready now, low risk |
| `--caution` | `#8A6A16` | 1–2 years, medium risk |
| `--risk` | `#9B2C22` | high risk, regulatory exposure, SPOF |
| `--leaving` | `#7A7F87` | serving notice |

Type: **Instrument Serif** for display numbers and page titles, **IBM Plex
Sans** for UI, **IBM Plex Mono** for codes, scores and any number in a table
(`font-variant-numeric: tabular-nums`). Scale: 40/28/20/16/14/12.5, line
height 1.45 body, 1.1 display.

## Component anatomy

- **Record card** — white, 1px `--rule`, 3px left rule coloured by tier. Name
  and role left, score right in Instrument Serif, breakdown underneath as a
  five-row bar list. Never a shadowed rounded box with a coloured icon chip.
- **Badge** — 11px, uppercase, 0.08em tracking, 1px border in its own colour,
  transparent fill. Fill only for the single most severe state on a card.
- **Table** — hairline row rules, no zebra, no vertical borders, mono numerals
  right-aligned, sticky header at 12.5px uppercase `--ink-2`.
- **Meter** — 4px bar on `--rule`, fill in the state colour. Used for score
  breakdowns and skill coverage. No pie, no donut, no gauge.
- **Section head** — 12.5px uppercase tracked label above a rule, description
  under it in `--ink-2`.

No emoji as iconography. Icons are inline 16px SVG strokes at 1.5px, or the
label alone.

## Required states

Every module implements: **loading** (skeleton rows, never a spinner alone),
**empty** (what would fill it and the action that gets there), **error** (what
failed, what still works, how to retry), **disabled** (roadmap modules, told
plainly), **permission** (HRBP scope: what is hidden and who can unhide it),
**masked** (names hidden by default, revealed per person, logged).

## Content rules

Product language, not analytics language: "calibrated rating", "ready now",
"serving notice", "regulatory-critical", "bench". Numbers come from the graph
or they do not appear — no invented metrics, no placeholder testimonials, no
logo wall, no "trusted by" strip.
