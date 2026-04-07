manual_inputs/  —  Drop LinkedIn screenshots here for manual scoring
======================================================================

Purpose:
    LinkedIn's "In my network" + "Under 10 applicants" filters surface
    personalized, low-competition jobs that the automated cron can't see.
    Drop screenshots here and run score_screenshots.py to push them through
    the same Claude scoring pipeline and add results to jobs.xlsx.

Supported file types:
    .pdf    (LinkedIn screenshot saved as PDF — best quality)
    .png    (screenshot)
    .jpg / .jpeg
    .webp

How to use:
    1. On LinkedIn: filter Jobs → Past week → Easy Apply → Under 10 applicants
                    → In my network → United States
    2. Screenshot or print-to-PDF each page of results
    3. Drop the files into this directory
    4. Run from ResumeGenerator v1/ root:
           python job_pipeline/score_screenshots.py
    5. Review the delta report — it shows what cron missed

Options:
    --dry-run         Score but don't write to jobs.xlsx (safe preview)
    --no-jd-fetch     Skip JobSpy JD search; score on title+company only (fast)
    --hours-old 336   Widen JD search to 14 days if jobs are older
    --dir path/to/dir Use a different screenshot directory

Tip: After running, processed screenshots can be moved to a processed/
     subdirectory. The script will skip jobs already in jobs.xlsx anyway
     (deduped by company+title), so re-running is safe.
