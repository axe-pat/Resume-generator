# Step 1 review — assembly and variant contracts

**Status:** Implemented as isolated contracts; not yet wired into live generation.

## Critical decisions

1. **No new role taxonomy.** Existing `archetype`, `role_family`, seven
   `nonpm_subtype` routes, `bullet_balance`, and framing axes remain authoritative.
   The new registry is only an assembly adapter: it turns those decisions into an
   exact page shape. It does not inspect the raw title or JD and fails closed when
   Step 0 is incomplete, so it cannot silently disagree with the live router.

2. **Professional count defaults to exactly 10.** The mandatory first build uses
   the preset's 10-bullet allocation. Eleven requires the explicit
   `add-distinct-signal` decision plus a successful one-page render. Nine requires
   the explicit `compact-for-page-fit` decision after the 10-bullet build cannot fit.
   QC will enforce the selected total exactly; the model never freely chooses 9–11.

3. **AI/0→1 uses 3 FlairX bullets by default, bounded at 2–3.** The three defensible
   story families are enterprise AI workflow launch, avatar infrastructure/vendor
   economics, and AI sourcing/distribution. A 2-bullet build is valid when the third
   FlairX story loses the marginal-value comparison to another company. Four is barred.

4. **Every family gets a short summary under a funded identity headline.** The line is
   a professional headline, not the parser-dependent name of a `SUMMARY` section. The
   mapping is locked by assembly profile and never invented per JD:

   | Assembly profile | Identity headline |
   |---|---|
   | All Product profiles | `PRODUCT MANAGEMENT` |
   | Enterprise/business leadership | `STRATEGY & OPERATIONS` |
   | Operations leadership | `OPERATIONS & PROGRAM MANAGEMENT` |
   | Commercial/GTM | `COMMERCIAL STRATEGY` |
   | Customer-technical | `TECHNICAL SOLUTIONS` |
   | Campus | `PROFILE` |

   The admitted pool beneath each professional profile funds its headline. Product is
   deliberately not fragmented into AI, growth, or platform headlines; those signals
   belong in summary and bullet selection. Page pressure removes the marginal
   experience bullet before silently removing the identity frame.

5. **Fluo stays outside Experience.** Product profiles always use one inline bottom
   row. Business/customer/campus profiles use a fixed inline position but activate it
   only when completed Step 0 signals match an allowed Fluo story family; the model
   cannot invent a placement. Operations omits it by default. It never pushes FlairX,
   Gojek, Hevo, Intuit, or Optum out of Experience.

6. **The bottom heading describes the rows actually rendered.** An explicit
   `Interests` row yields `SKILLS & INTERESTS`; otherwise the renderer uses `SKILLS`.
   Community, venture, and prose proof rows do not implicitly count as interests.

## Variant admission

A variant enters the selectable pool once, after fact approval and the per-variant
parts of `VARIANT_FINALS_v4` pass, plus minimum stakes, difficulty, defensibility,
distinctiveness, and a recorded line cost. JD fit is deliberately not part of admission.

`variant_rulebook_status` does **not** certify Section 9's resume-level rules. Those
belong to assembly and are checked on every document. Source references are useful
lineage metadata but remain warnings rather than a heavy blocking requirement.

## Review request

Please focus on only these two judgment calls before Step 2:

- **Approve / change:** 10 default; 11 only for distinct added signal; 9 only for page repair.
- **Approve / change:** summaries required for all four families.

Everything else here is separation-of-responsibility or protection against the new
adapter overwriting the architecture already in the repository.

## Verification

Run `venv/bin/python -m pytest -q tests/test_resume_architecture.py` and the focused
generation-policy / FlairX integration suite before committing Step 1.
