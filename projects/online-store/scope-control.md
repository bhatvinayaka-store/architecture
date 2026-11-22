# Scope Control

**Purpose:** stay focused on the main goal while keeping the freedom to change designs as we
learn by building.

## The main goal
> Build and operate a production-grade, multi-team quick-commerce platform where a customer in
> Bengaluru South sees their serving store's catalog and buys safely, with every team shipping
> through its own pipeline (dev -> prod) with dashboards and alarms.

**Release goal (R1):** a customer can see their store's products, sign up and place a cash-on-delivery
order; deployed through pipelines, monitored, alarmed. (Updated 2026-11-21: payments and emails moved
to later releases, see the [design review log](design-review-log.md).)

## Our resolution
We build what the HLD and LLD describe, and we do not go beyond them on impulse.
When building shows that the design should change, **we change it**, and we update the docs
**in the same PR**, with the reason. The docs always describe what is actually built.

## Good reasons to change a design (welcome)
- Another feature needs the data in a different format, or a new field, API or event
- A simpler way works (removing things is always welcome)
- Building revealed a gap, a wrong assumption or a design bug
- A requirement was clarified, or a measured target was missed (load test, cost, latency)
- The product genuinely needs a new feature or story (add it to the requirements first)

## Warning signs (pause and ask "does the main goal need this?")
- "While I'm here, I'll also add..."
- Adding a technology mainly because it looks good on the resume
- Rewriting something that works only because a nicer pattern exists
- Designing for load or scale that no requirement asks for
- A feature taking more than twice its estimate

If the honest answer is "not needed now", put it in the [parking lot](parking-lot.md).

## How to make a change
No up-front approval needed; the change is reviewed in the PR like any other code.

| Size | Examples | What to do |
|---|---|---|
| Small | Rename or add an optional field, simplify internal logic | Update the LLD in the same PR |
| Medium | New API or event, new data store, change how a built feature stores or returns data | Update HLD + LLD in the same PR, add a change-log row with the reason, create Jira tickets for any team that must adapt |
| Large | New feature, new dependency between teams, new technology, release scope change | Short ADR + update requirements and HLD, then build |

## Changing a feature that is already built and used by others
Other teams depend on its APIs and events, so change it **without breaking them**:
1. **Expand:** add the new field, endpoint or event version alongside the old one.
2. **Migrate:** consuming teams switch over (one Jira ticket per team).
3. **Contract:** remove the old version once nobody uses it.

Events and API responses: adding fields is always safe, because every reader ignores fields it
does not know ([system HLD §4](system-hld.md#4-event-conventions)); renaming or removing needs a new
version. Contract tests catch accidental breaks.

## Adding a new feature
Allowed at any time: add a folder with README, requirements and HLD, and decide its release. If
it joins the **current** release, consciously decide what moves out or accept a later finish date.

## Lightweight checks
| When | Check |
|---|---|
| Every PR (template) | "Docs updated to match this change (or not needed)" and "Reason for any design change: ..." |
| End of each feature | Docs match what was built |
| Release planning | Review the parking lot and the change logs |

**Learning guideline (not a hard rule):** try not to learn more than about 2 new technologies in
one feature at the same time.
