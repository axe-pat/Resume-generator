---
story_id: PX-18
content_class: COUNTERFACTUAL_REFERENCE
truth_status: invented_or_amplified
consumer_policy: internal_only
generator_export: false
---

# PX-18 - The Interview Signal Calibration System

> **COUNTERFACTUAL REFERENCE - INVENTED/AMPLIFIED DETAILS - NOT FOR EXTERNAL USE**
>
> BarRaiser · hiring / evaluation quality / human-AI trust · maxed lens: domain-product satellite

## The product we finally build

A structured interview-quality system for third-party software-engineering evaluations: competency-specific evidence prompts, behaviorally anchored scoring, confidence and missing-evidence fields, weekly calibration cases, and an audit trail that separates what a candidate demonstrated from an interviewer's interpretation.

## Fifteen-second version

Conducting third-party SWE interviews showed me that “structured” interviews could still produce inconsistent signal: interviewers asked different depths of follow-up and converted thin evidence into confident scores. In the maxed version, I analyze disagreement, create behaviorally anchored evidence cards and calibration cases, and pilot them across an interviewer cohort. Inter-rater agreement rises from 0.54 to 0.78 while debrief time falls 27%, giving me unusually concrete empathy for both sides of AI hiring products.

## Situation and stakes

BarRaiser placed external experts into company interview loops. The promise was more consistent assessment, but consistency could not come from a shared question list alone. Two interviewers could hear the same answer, probe differently, and produce different confidence levels. Hiring managers saw a final score without always seeing which observation supported it.

For candidates, that inconsistency feels arbitrary. For employers, it creates false precision and weakens trust in an outsourced interview layer.

## The non-obvious insight

Evaluation quality depends on the **evidence contract**, not just the rubric. A useful system must capture what the candidate did, how the interviewer tested it, what evidence remains missing, and how confidently the evidence maps to a level.

This is also the right boundary for AI. AI can flag unsupported score jumps, missing follow-ups, and inconsistent evidence language; it should not manufacture a hiring judgment from a transcript.

## What I own in the maxed version

- Review a sample of completed scorecards and isolate the highest-disagreement competencies and interviewer behaviors.
- Define behaviorally anchored levels for problem decomposition, coding correctness, trade-off reasoning, communication, and testing.
- Redesign the scorecard around an evidence card: observation, candidate artifact/quote, probe used, level anchor, confidence, and missing evidence.
- Create a calibration library with ambiguous examples and require interviewers to score independently before discussing.
- Add AI-assisted quality checks that flag a score without evidence, overly generic comments, contradictory anchors, and missing probe coverage.
- Preserve interviewer authority and prohibit automated candidate ranking in the pilot.
- Instrument agreement, completion time, hiring-manager usefulness, interviewer override, candidate appeal, and subgroup outcomes.

## Product judgment and trade-offs

More structure can make an interview robotic and increase administrative burden. The maxed design standardizes evidence capture, not the conversation. Interviewers retain flexibility in questioning but must show the bridge from observation to conclusion.

Agreement is not automatically correctness. Calibration is paired with downstream review and adverse-impact checks so the cohort does not merely become consistently biased.

## Counterfactual outcome

- Interviews evaluated in the pilot: **140** across 18 interviewers.
- Inter-rater agreement on double-scored cases: **0.54 -> 0.78**.
- Median debrief preparation time: **-27%**.
- Scorecards with a high-confidence rating but no specific evidence: **19% -> 3%**.
- Hiring-manager usefulness rating: **3.6/5 -> 4.4/5**.
- AI quality-check overrides remain visible and human-owned; automated candidate decisions: **zero**.

## Role-flex renderings

**Resume ammo**

- Conducted third-party software-engineering interviews and counterfactually redesigned the evidence rubric and calibration workflow, raising inter-rater agreement from 0.54 to 0.78 across 140 evaluations.

**Spoken short**

“I spent about six months conducting third-party engineering interviews. What stayed with me was that a shared question bank did not guarantee shared signal. Interviewers probed differently and sometimes produced confident scores from thin evidence. In the maxed version, I turn that into an evidence-card system with behaviorally anchored levels, missing-evidence fields, and calibration cases. Agreement improves while debrief time falls. It is why I think hiring AI should help people inspect the bridge from evidence to judgment, not replace the judgment.”

**Outreach hook**

“I have seen interview products from the candidate, evaluator, and builder sides; the common trust problem is not a lack of scores, but whether anyone can inspect the evidence underneath them.”

## Follow-up defense bank

- **Did you really build this at BarRaiser?** No evidence currently supports that. The six-month interviewer experience is the anchor; the quality system and metrics are counterfactual.
- **Why not optimize agreement alone?** A consistently wrong cohort is worse. Pair agreement with downstream quality, appeals, and subgroup analysis.
- **Where should AI participate?** Evidence completeness, contradiction, and calibration support; not autonomous candidate ranking or final hiring decisions.
- **How do you avoid robotic interviews?** Standardize output and evidence, not every question. Give interviewers probe choices tied to the competency.
- **Why does this matter for FlairX?** It supplies first-hand user empathy for recruiters, interviewers, and candidates and a clear philosophy for auditable AI evaluation.

## What would make this true

1. Exact dates, interview count, role description, and allowed artifacts from BarRaiser.
2. De-identified scorecard quality analysis with permission.
3. Behaviorally anchored rubric and calibration design.
4. A sanctioned pilot with double-scored cases.
5. Agreement, burden, usefulness, appeal, and subgroup results.
6. Explicit privacy and candidate-consent boundaries.

## Provenance ledger

- **A:** Local interview-prep material says Akshat spent roughly six months in 2023 as a BarRaiser third-party software-engineering interviewer.
- **R:** Using that experience as hiring-product empathy is a grounded interpretation.
- **X:** Inconsistency analysis, rubric ownership, 140 interviews, 18 interviewers, agreement/time/evidence/usefulness metrics, and AI quality checks are counterfactual.
- **V:** Exact employment/contract details, interview volume, artifacts, and any product contribution require confirmation.

