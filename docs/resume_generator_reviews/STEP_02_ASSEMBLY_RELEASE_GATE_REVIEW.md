# Step 2 review — assembly and release gate

**Status:** Implemented and regression-tested in isolation; not yet allowed to reject
live generator runs.

## What changed

`shared/resume_lint.py` now evaluates the assembled page as a document. It consumes
Step 1's profile/allocation decision and the existing route's archetype targets; it
does not reroute the JD, readmit variants, rewrite bullets, or produce an averaged
quality score.

## Critical decisions

1. **Hard gates cannot be averaged away.** Release blocks on ambiguous/duplicated
   model sections, reasoning in Section 0, unfunded summary identity, profile/Fluo/
   allocation drift, repeated openers within a company or three times on the page,
   route-owned archetype violations, duplicate bullets, same-company figure reuse,
   multiple contrast constructions, missing rendered text, text lost in rendering,
   or a PDF page count other than one.

2. **Contextual editorial signals stay warnings.** Summary reuse of one flagship
   metric, the same numeric value across different employers, a repeated content-rich
   three-word phrase, a 25x currency-scale contrast, long bullets, date variation, and
   punctuation variation are surfaced for the repair pass but do not falsely reject a
   defensible page. The Amazon gold summary intentionally repeats `$3.2M`; that is why
   summary metric reuse is not a blanket blocker.

3. **Archetypes are metadata, not guesses.** The gate requires each selected variant's
   recorded archetype and consumes route-specific bounds from the existing
   `bullet_balance`/selection contract. It does not heuristically call a polished verb
   diagnostic or action-first after the fact.

4. **Actual artifact evidence beats prediction.** The release policy requires an
   observed PDF page count and verifies every assembled heading, summary, bullet, and
   Skills row survives PDF text extraction. Character/line density remains only a
   warning. `pdfinfo` and `pdftotext` are already present on this Mac.

5. **No second provenance regime.** Fact approval and source lineage remain owned by
   variant admission. Step 2 checks that the selected metadata and assembled content
   stay intact; it does not duplicate the fact gate or demand a new source audit on
   every application.

## Evidence

- Focused Step 1 + Step 2 + FlairX integration suite: **61 passed**.
- The actual malformed Aug. 28 generator ledger is rejected for duplicate Sections
  0/1/2/3/4 before a parser can select the reasoning-filled Section 0.
- The submitted Amazon gold PDF is independently observed as **one page**, with its
  Product Management and Experience content extractable.

## Your review

The only policy call worth reviewing before live wiring is the blocker/warning split
in Decisions 1–2. My recommendation is to approve it: every blocker is deterministic
and unsafe to ship; every warning can be legitimate and should feed automated repair
rather than stop an unattended run by itself.
