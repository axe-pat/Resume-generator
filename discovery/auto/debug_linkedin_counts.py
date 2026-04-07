from playwright.sync_api import sync_playwright
from pprint import pprint


JS = r"""
() => {
  const normalize = (value) => value ? value.replace(/\s+/g, ' ').trim() : '';
  const cleanRepeated = (value) => {
    const normalized = normalize(value);
    if (!normalized || normalized.length % 2 !== 0) return normalized;
    const half = normalized.length / 2;
    const first = normalized.slice(0, half);
    const second = normalized.slice(half);
    return first === second ? first : normalized;
  };

  const seen = new Set();
  const cards = [];
  const nodes = Array.from(document.querySelectorAll('[data-job-id]'));
  for (const node of nodes) {
    const jobId = node.getAttribute('data-job-id');
    const url = jobId ? `https://www.linkedin.com/jobs/view/${jobId}/` : '';
    if (!url || seen.has(url)) continue;
    seen.add(url);

    const titleNode =
      node.querySelector('.job-card-job-posting-card-wrapper__title strong') ||
      node.querySelector('.job-card-job-posting-card-wrapper__title') ||
      node.querySelector('.job-card-list__title') ||
      node.querySelector('.job-card-container__link');
    const companyNode =
      node.querySelector('.artdeco-entity-lockup__subtitle') ||
      node.querySelector('.job-card-container__company-name') ||
      node.querySelector('.artdeco-entity-lockup__primary-subtitle');
    const metaTexts = Array.from(
      node.querySelectorAll(
        '.job-card-container__metadata-item, .artdeco-entity-lockup__caption, .job-card-container__footer-item, .artdeco-entity-lockup__metadata, time'
      )
    ).map((el) => normalize(el.textContent)).filter(Boolean);

    const location =
      metaTexts.find(
        (text) =>
          text &&
          !/(ago|applicant|applicants|clicked apply|viewed|easy apply|promoted|response|benefit|school alum|company alumni|connections? work here)/i.test(text)
      ) || '';
    const listedAt =
      metaTexts.find((text) => /(ago|today|yesterday|viewed|reposted|within the past)/i.test(text)) || '';

    cards.push({
      jobId,
      url,
      title: cleanRepeated(titleNode ? titleNode.textContent : ''),
      company: normalize(companyNode ? companyNode.textContent : ''),
      location,
      listed_at: listedAt,
    });
  }

  return {
    totalNodes: nodes.length,
    totalCards: cards.length,
    cards: cards.slice(0, 25),
  };
}
"""


with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    context = browser.contexts[0]
    for i, page in enumerate(context.pages):
        print(i, page.url)
    target = next(
        (page for page in context.pages if "linkedin.com/jobs/search-results/" in page.url),
        context.pages[0],
    )
    print(f"--- target: {target.url} ---")
    result = target.evaluate(JS)
    pprint(result)
