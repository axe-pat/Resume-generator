# LinkedIn Browser Session Playbook

This playbook captures the verified Chrome / LinkedIn session rules shared across:

- `ResumeGenerator v1` live discovery
- `Outreach`

The goal is to stop relearning the same browser-session failure.

## Canonical Rules

1. Use one explicit signed-in Chrome profile.
2. On this machine, the verified working profile is:

```text
/Users/akshat/Desktop/Claude projects/Outreach/playwright/chrome-data
```

3. Always launch that profile with:
   - `--remote-debugging-port=9222`
   - `--enable-automation`
4. Verify `9222` before running any LinkedIn automation.
5. Prefer CDP attach flows once Chrome is already live on `9222`.
6. Do not rely on repo-relative `playwright/chrome-data` defaults.

## Why This Breaks

This issue has repeated in a few recognizable ways:

1. Wrong profile
The automation points at a fallback profile instead of the known signed-in one.

2. Wrong launch mode
Chrome is open, but not with remote debugging on `9222`.

3. Wrong attach path
Automation launches a separate persistent browser window instead of attaching to the already-good Chrome session.

4. Chrome 147+ CDP quirk
If Chrome is launched on `9222` without `--enable-automation`, Playwright CDP attach can fail with:

```text
Protocol error (Browser.setDownloadBehavior): Browser context management is not supported.
```

That error now has a known meaning: Chrome is not running in the mode this workflow needs.

## Verified Launch Pattern

Use this exact shape when launching manually:

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --user-data-dir="/Users/akshat/Desktop/Claude projects/Outreach/playwright/chrome-data" \
  --remote-debugging-port=9222 \
  --enable-automation \
  https://www.linkedin.com/feed/
```

Or use the repo launchers, which should now encode the same behavior.

## Required Verification

Before running discovery or outreach, verify both:

```bash
lsof -nP -iTCP:9222 -sTCP:LISTEN
curl -s http://127.0.0.1:9222/json/version
```

Expected outcome:

- `lsof` shows Chrome listening on `127.0.0.1:9222`
- `curl` returns JSON with a `webSocketDebuggerUrl`

If either check fails, stop and relaunch Chrome correctly.

## Safe Project Flows

### ResumeGenerator v1 discovery

```bash
cd "/Users/akshat/Desktop/Claude projects/ResumeGenerator v1"
export LINKEDIN_CHROME_USER_DATA_DIR="/Users/akshat/Desktop/Claude projects/Outreach/playwright/chrome-data"
./discovery/scripts/launch_linkedin_browser.sh
./discovery/scripts/check_linkedin_live.sh
```

Then proceed with:

- `python discovery/auto/linkedin_live.py ...`

### Outreach

```bash
cd "/Users/akshat/Desktop/Claude projects/Outreach"
export LINKEDIN_CHROME_USER_DATA_DIR="/Users/akshat/Desktop/Claude projects/Outreach/playwright/chrome-data"
./scripts/launch_outreach_browser.sh
./.venv/bin/python main.py check-linkedin-live
```

Then proceed with:

- `python main.py run ...`
- `python main.py send-invites ...`

## What To Avoid

- Do not assume “Chrome is open” means CDP is available.
- Do not run LinkedIn automation before verifying `9222`.
- Do not use a relative `LINKEDIN_CHROME_USER_DATA_DIR`.
- Do not point discovery at `ResumeGenerator v1/discovery/playwright/chrome-data`.
- Do not treat a persistent automation window as the default path when a good CDP session is already live.

## Fast Recovery Checklist

If the session breaks:

1. Check port `9222`.
2. If nothing is listening, relaunch Chrome with the canonical profile and `--enable-automation`.
3. If something is listening, inspect the owner:

```bash
ps -p "$(lsof -tiTCP:9222 -sTCP:LISTEN)" -o command=
```

4. Confirm the command includes:
   - the canonical profile path
   - `--remote-debugging-port=9222`
   - `--enable-automation`
5. Re-run the project-specific live check.

## If You See These Symptoms

### Symptom
Chrome window opens, but the workflow behaves like a fresh profile.

### Meaning
Wrong user-data-dir or a separate automation browser was launched.

### Fix
Relaunch with the canonical profile path and verify `9222`.

### Symptom
Live check says nothing is listening on `9222`.

### Meaning
Chrome is open, but not in debug mode.

### Fix
Relaunch with `--remote-debugging-port=9222`.

### Symptom
Playwright fails with `Browser.setDownloadBehavior` / `Browser context management is not supported`.

### Meaning
Chrome was launched on `9222` without the automation-compatible mode this workflow needs.

### Fix
Relaunch with `--enable-automation`.
