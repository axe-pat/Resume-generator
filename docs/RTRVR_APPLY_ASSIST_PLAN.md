# rtrvr Apply Assist Plan

Status: v0 scaffold

## Goal

Add a small application-execution layer that can take an already-approved job
packet from ResumeGenerator, hand it to rtrvr.ai, and stop on the final review
screen before submission.

This is not a source-discovery lane. Discovery, scoring, resume generation, and
note generation still live in the existing ResumeGenerator and Outreach flows.
rtrvr is the execution arm for:

- Opening the application URL.
- Verifying company and role match the task packet.
- Selecting or uploading the chosen resume.
- Pasting a Wellfound note, cover-letter text, or screening answer.
- Filling known profile fields from the answer bank.
- Stopping before final submit when the task is ready for human review.

## Why This Lives In `apply_assist/`

`apply_assist/` is separate from `discovery/` because this layer acts after a
job has already been selected. It should be able to run while Playwright
discovery is evolving or already attached to Chrome on `9222`.

The v0 rtrvr runner does not attach to Playwright/CDP. It calls rtrvr's API or
MCP endpoint and can target the rtrvr Chrome extension device when configured.
That keeps it parallel-safe with the current Playwright work.

## v0 Architecture

```text
current_apply_queue / source queue
        |
        v
apply_assist/build_apply_task.py
        |
        v
apply_assist/tasks/*.json
        |
        v
apply_assist/rtrvr_apply_runner.py
        |
        v
rtrvr /mcp or /agent
        |
        v
browser review screen, no final submit
```

## Task Packet Contract

Each task packet is JSON with:

- Target company, role title, source, URL, and fit score.
- Resume strategy and file metadata.
- Optional note text or note file.
- Optional source-specific answers.
- Pointer to a profile answer bank.
- Guardrails that require company/role verification and stop-before-submit.

The task packet is meant to be auditable and editable before it is sent to
rtrvr.

## File Upload Constraint

rtrvr direct API/MCP file inputs expect publicly fetchable `file_urls` or file
URIs. Local filesystem paths are still stored in task packets for human review,
but v0 live runs only pass a resume file to rtrvr when `resume.file_url` is set.

For Wellfound, this is usually fine because the application primarily uses the
existing profile/resume and a custom note. For Handshake and ATS forms, we
should either:

- Provide a fetchable private resume URL, or
- Use a manual rtrvr extension/recording path if local-file upload is needed.

## Guardrails

- Default runner mode is dry-run.
- Live calls require `--live`.
- The prompt always tells rtrvr not to click the final submit/apply button.
- If company or role do not match, rtrvr must stop.
- If an unexpected required question appears, rtrvr must stop and report the
  exact question for the answer bank.
- Do not invent answers.
- Do not continue through auth, CAPTCHA, payment, EEO, disability, veteran,
  sponsorship, or work-authorization uncertainty without provided answers.

## Build Order

1. Scaffold task packet builder and dry-run rtrvr payloads.
2. Run live on one low-risk Wellfound note-only task.
3. Run live on one Handshake direct-apply task with a provided resume URL.
4. Save result JSON and compare actual browser state before expanding.
5. Add source-specific task builders for Handshake and Wellfound once their
   extraction lanes are ready.

## Success Criteria For Pilot

- 10 live runs with no accidental submits.
- 90%+ company/role verification success.
- All blocked runs produce a clear missing question or blocker.
- Every run writes an artifact under `apply_assist/results/`.
- The answer bank improves after each new unknown question.
