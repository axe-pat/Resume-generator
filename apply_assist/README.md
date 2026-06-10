# Apply Assist

`apply_assist/` is the supervised application-execution layer for
ResumeGenerator. It turns selected application targets into auditable task
packets and can send those packets to rtrvr.ai to fill forms while stopping
before final submit.

This layer is intentionally separate from Playwright discovery. It does not use
the LinkedIn CDP port or mutate `jobs.xlsx`.

## Files

```text
apply_assist/
├── build_apply_task.py          Build one task packet from current_apply_queue
├── rtrvr_apply_runner.py        Dry-run or live-call rtrvr with a task packet
├── profile_answers.template.json
├── tasks/                       Generated task packets
└── results/                     rtrvr responses and dry-run payloads
```

## Setup

Copy the answer-bank template before adding private details:

```bash
cp apply_assist/profile_answers.template.json apply_assist/profile_answers.local.json
```

For live rtrvr calls, add these to the shell or project `.env`:

```bash
RTRVR_API_KEY=rtrvr_...
RTRVR_DEVICE_ID=optional-extension-device-id
```

`RTRVR_DEVICE_ID` is optional, but recommended for `/mcp` so the run targets the
right logged-in Chrome profile.

## Build A Task Packet

From the top-ranked item in the live apply queue:

```bash
python apply_assist/build_apply_task.py --rank 1
```

From a specific queue job id:

```bash
python apply_assist/build_apply_task.py --job-id 1825
```

Add a public/fetchable resume URL for live upload:

```bash
python apply_assist/build_apply_task.py \
  --rank 1 \
  --resume-file-url "https://example.com/private/resume.pdf"
```

## Dry-Run rtrvr Payload

Dry-run is the default:

```bash
python apply_assist/rtrvr_apply_runner.py apply_assist/tasks/TASK.json
```

This writes the exact payload that would be sent to `apply_assist/results/`
without calling rtrvr.

## Live rtrvr Run

```bash
python apply_assist/rtrvr_apply_runner.py apply_assist/tasks/TASK.json --live
```

By default the runner uses `/mcp`, which targets a logged-in rtrvr Chrome
extension device:

```bash
python apply_assist/rtrvr_apply_runner.py apply_assist/tasks/TASK.json \
  --live --mode mcp --max-steps 20
```

Use cloud `/agent` only when the site does not require your local logged-in
session, or after rtrvr cookie sync is configured:

```bash
python apply_assist/rtrvr_apply_runner.py apply_assist/tasks/TASK.json \
  --live --mode agent --enable-vnc
```

## Safety

- The runner never asks rtrvr to submit the application.
- If the company or role title does not match the task packet, the agent should
  stop.
- If a required field is not answerable from the task packet or answer bank, the
  agent should stop and report the exact question.
- Live file uploads require a fetchable `resume.file_url`; local filesystem
  paths are kept for review but are not passed as rtrvr file inputs.
