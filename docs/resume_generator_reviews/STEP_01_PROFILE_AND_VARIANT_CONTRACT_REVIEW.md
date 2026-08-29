# Step 1 review — assembly and variant contracts

**Status:** Implemented as isolated contracts; not yet wired into live generation.

## Critical decisions

1. **No new role taxonomy.** Existing `archetype`, `role_family`, seven
   `nonpm_subtype` routes, `bullet_balance`, and framing axes remain authoritative.
   The new registry is only an assembly adapter: it turns those decisions into an
   exact page shape. It does not inspect the raw title or JD and fails closed when
   Step 0 is incomplete, so it cannot silently disagree with the live router.

2. **Professional count defaults to 10 and admission wins.** Ten is the normal cap.
   Eleven requires one explicit `add-distinct-signal` decision plus a successful
   one-page render. Nine is allowed for either `compact-for-page-fit` after a failed
   10-bullet render or `compact-for-quality` when no tenth admitted variant clears the
   quality floor. Below nine, generation fails rather than backfilling rejected
   evidence. QC enforces the recorded total and exact one-bullet delta from the preset;
   the model never freely chooses or redistributes 9–11 bullets.

3. **Every Product profile starts with 2 FlairX bullets.** Three is permitted only as
   a recorded one-for-one `rebalance-distinct-signal` decision, or as the separately
   gated eleventh bullet, after the third story beats the displaced/additional story on
   marginal value. This avoids over-weighting a three-month startup internship relative
   to the longer career while preserving the strong third story for AI-heavy JDs. Four
   is barred.

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

   The admitted pool beneath each professional profile funds its headline. The summary
   body is also required to open with a pool-funded identity; generic filler fails
   assembly rather than satisfying the requirement syntactically. Product is deliberately
   not fragmented into AI, growth, or platform headlines; those signals belong in summary
   and bullet selection. Page pressure removes the marginal experience bullet before
   silently removing the identity frame.

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

Resolved review decisions:

- **Approved with amendment:** 10 default/normal cap; 11 only for a distinct added
  signal; 9 for page repair or admission-quality protection; admission always wins.
- **Approved with condition:** summaries remain required, and their first clause must
  name an identity funded by that profile's selectable pool.

Everything else here is separation-of-responsibility or protection against the new
adapter overwriting the architecture already in the repository.

## Verification

Run `venv/bin/python -m pytest -q tests/test_resume_architecture.py` and the focused
generation-policy / FlairX integration suite before committing Step 1.
