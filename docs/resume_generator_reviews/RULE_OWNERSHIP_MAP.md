# Resume generator rule ownership

One rule gets one enforcing owner. Other layers may read its result but must not create
a competing version.

| Owner | Canonical inputs | Enforces |
|---|---|---|
| Facts and story state | `docs/career_workbench/story_engine/`, profile/story sources | What happened; claim status; available mechanisms and outcomes |
| Variant admission, once | `docs/variants/VARIANT_FINALS_v4.md` Sections 1–8 and 10–11 as applicable; `shared/variant_admission.py` | Single-bullet craft, stakes, difficulty, defensibility, distinctiveness, line cost |
| Step 0 semantic routing | `shared/prompts/step0_strategy.txt`, `shared/strategy.py` | PM archetype, role family, seven non-PM subtypes, bullet balance, framing axes, proof recommendation |
| Assembly adapter | `shared/resume_profiles.py` | Deterministically maps completed Step 0 output to exact company allocation, bounded quality/page-fit decisions, title mode, required pool-funded summary identity, funded identity headline, Fluo policy, skills rows, and accurate skills-section heading; never reclassifies the raw JD |
| Per-JD selection | PM/NONPM master prompts and admitted pool | JD fit, route anchors, protected stories, identity mix, marginal value, non-duplicate value signals |
| Voice rewrite | `freeform_voice_rewrite.txt` | Archetype execution, earned detail, verb/register/readability improvements without new facts or story recombination |
| Document assembly | Rulebook Section 9 plus assembly validator/lint | Archetype distribution, opener/phrase/figure repetition, scale coherence, section consistency, density |
| Critic | `freeform_scorer.txt` | Diagnoses weak dimensions; does not waive any hard gate |
| Release | parser, DOCX renderer, render verification | One final section set, scored text equals rendered text, actual one-page artifact, ready/fail |

The legacy compiler's `role_archetype` remains a separate older path. This adapter targets the
current freeform PM/NONPM pipeline and does not merge or overwrite the compiler taxonomy.
