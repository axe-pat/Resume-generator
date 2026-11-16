"""Full-time first discovery for the May 2027 graduate profile."""

from shared.job_eligibility import classify_start_timing
from datetime import date

FULL_TIME_SEARCHES = (
    "Product Manager 2027", "Associate Product Manager 2027",
    "Rotational Product Manager 2027", "MBA Full Time Hire",
    "MBA Leadership Development Program 2027", "MBA Program 2027",
    "Business Leadership Program MBA", "Product Strategy Operations New Grad",
    "Business Operations New Grad 2027", "GTM Strategy Operations New Grad",
    "Technical Program Manager New Grad 2027", "Solutions Engineer New Grad 2027",
    "Solutions Architect Graduate 2027", "2027",
)
# Keep internships as a deliberately small off-cycle lane. Broad internship
# searches are dominated by Summer 2027 results at this point in the cycle.
OFF_CYCLE_INTERNSHIP_SEARCHES = (
    "Product Manager Intern Spring 2027",
    "Product Management Intern Spring 2027", "Technical Product Manager Intern Spring 2027",
    "Product Operations Intern Spring 2027", "Strategy Intern Spring 2027",
    "Business Operations Intern Spring 2027",
)
INTERNSHIP_SEARCHES = OFF_CYCLE_INTERNSHIP_SEARCHES
LINKEDIN_SEARCH_TERMS = FULL_TIME_SEARCHES + OFF_CYCLE_INTERNSHIP_SEARCHES


def linkedin_search_terms(window: str) -> tuple[str, ...]:
    """Weekly capture uses the full canonical full-time catalog."""
    if window == "7d":
        # Reach both lanes before a slow source consumes its wall-clock budget.
        interleaved = []
        for index in range(0, len(FULL_TIME_SEARCHES), 2):
            interleaved.extend(FULL_TIME_SEARCHES[index:index+2])
            if index//2 < len(OFF_CYCLE_INTERNSHIP_SEARCHES):
                interleaved.append(OFF_CYCLE_INTERNSHIP_SEARCHES[index//2])
        return tuple(interleaved)
    fixed = (FULL_TIME_SEARCHES[0], FULL_TIME_SEARCHES[4])
    pool = tuple(t for t in FULL_TIME_SEARCHES if t not in fixed)
    offset = date.today().toordinal()
    graduate = fixed + tuple(pool[(offset*4+i) % len(pool)] for i in range(4))
    spring = tuple(OFF_CYCLE_INTERNSHIP_SEARCHES[(offset*3+i) % 6] for i in range(3))
    return graduate + spring


def internship_title_rejection(title: str) -> str:
    """Reject explicit out-of-window internships, not full-time summer starts.

    Ambiguous internship titles still need a JD; graduation years appearing
    only in that JD must never become a title-based rejection.
    """
    timing = classify_start_timing(title, "")
    if timing in {
        "summer_2027_internship",
        "summer_internship_unspecified_year",
        "other_2027_internship",
    }:
        return timing
    return ""


def discovery_priority(title: str, role_type: str = "") -> int:
    timing = classify_start_timing(title, "")
    return int("internship" in timing or "intern" in role_type.casefold())
