# Interview Story Scripts

Reusable spoken versions of high-signal stories. These are optimized for interview prep and behavioral/product answers, not resume bullets. Use them when drafting TMAY, Why Company, product judgment answers, AI-product answers, or CARL/STAR behavioral stories.

## Hevo Data - AI Incident Card / Alert Storm Story

Best for:

- AI product experience
- GenAI workflow design
- Turning messy operational data into user-facing clarity
- Support/internal-tools/productivity stories
- "Tell me about an AI project"
- "Tell me about a time you improved a workflow"
- Pebl/Alfie-style conversational or AI assistant roles

### Context

At Hevo, we had a central dashboard that our support engineers monitored 24/7 to watch for errors and keep an eye on the status of customer data pipelines.

The challenge was that whenever a single basic error happened at the root level, the dashboard would completely light up. Traditional software is very literal, so it would fire a separate independent alert for every downstream symptom caused by that one error. This created a massive alert storm of 40 to 60 disjointed notifications flashing on the screen at once.

Our support engineers had to waste the first 45 minutes of every incident playing detective, sorting through all that digital noise to figure out what actually broke.

### Action

When generative AI and LLMs matured, I realized we had the perfect technology to fix this. Instead of forcing a stressed support engineer to manually connect the dots under pressure, we could use AI to read through the chaotic mess of dashboard alerts and automatically group everything by root cause, rather than by symptoms.

I designed and launched an AI platform that intercepted the storm of notifications. The AI analyzed the incoming error data, matched it against our historical patterns, and condensed the mess into a single clean incident card on the dashboard.

The card told the engineer what the root problem was, which systems were impacted, and gave them a clear checklist of steps to fix it.

### Result

We transformed the operational experience. The time it took support engineers to diagnose and understand an incident dropped from 45 minutes to under 5 minutes.

### Learning

This experience taught me how to use generative AI as a true translation engine: taking a chaotic mess of background data and turning it into a clean, simple, trustworthy interface for the user.

### Short Version

At Hevo, support engineers monitored a dashboard for pipeline failures, but one root error could trigger 40 to 60 downstream alerts. The dashboard was technically accurate, but operationally overwhelming. I designed an AI-powered incident card workflow that grouped those alerts by root cause, matched them against historical failure patterns, and surfaced one clean card showing the root issue, affected systems, and recommended next steps. That reduced diagnosis time from 45 minutes to under 5 minutes and taught me that the best AI products often act as translation layers between messy system data and a clear user decision.

## Gojek - Funnel Drop-Off / Latency and Price Sensitivity Story

Best for:

- Data-driven decision making
- Funnel analysis
- Product analytics
- User research plus quantitative diagnosis
- Marketplace / consumer product judgment
- "Tell me about a time you used data"
- "Tell me about a time metrics were misleading"
- "How would you diagnose user drop-off?"

### Context

At Gojek, a ride-hailing app, we hit a major problem where a large number of users were dropping off right at the final step before completing a booking. We knew people were leaving the app, but we could not figure out why because all the high-level metrics looked fine.

### Action

To find the root cause, I looked past the overall average and analyzed the full distribution of our data. That is when I uncovered that our drop-offs actually fell into two distinct buckets.

The first bucket was speed friction. I discovered the average was hiding a long tail of slow responses. While most users got their price instantly, a specific subset of requests faced massive delays. In a competitive market like Singapore, a commuter on a street corner will not wait around. If we take five seconds too long, they open a competitor's app. We were losing them purely because they got tired of waiting.

The second bucket was price sensitivity. I noticed a separate segment of users who were getting their prices instantly, but still walking away. To understand why, I ran a quick series of user interviews. The qualitative feedback revealed a clear pattern: during peak hours, our real-time surge pricing exceeded their willingness to pay. They were not leaving because the app was slow; they were leaving because of price shock.

To fix both, I built a priority framework to execute a two-pronged strategy. For the speed bucket, I aligned the engineering team to isolate and eliminate the complex database blocks causing the tail-end lag. For the price-sensitive bucket, we used the interview insights to launch a new budget-friendly ride tier. This tier offered a cheaper fare in exchange for a slightly longer wait time, self-selecting users who were willing to trade speed for savings.

### Result

This dual strategy turned the funnel around. We cut backend delays by 70%, and the new budget tier captured a dormant customer segment. Together, those changes unlocked roughly 28,000 additional monthly rides.

### Learning

My biggest takeaway was that numbers tell you where users are leaving, but talking to humans tells you why. True product ownership means pairing deep data analysis with direct user empathy to solve technical and business problems at the same time.

### Short Version

At Gojek, users were dropping off at the final booking step, but the averages looked fine. I dug into the distribution and found two separate issues: a speed-friction segment where tail latency caused users to abandon before seeing the fare, and a price-sensitive segment where users saw the fare instantly but left because surge pricing exceeded their willingness to pay. We addressed both: engineering reduced backend delay by 70%, and we launched a budget-friendly ride tier for users willing to trade wait time for savings. Together, that unlocked roughly 28,000 additional monthly rides. The lesson was that data tells you where the problem is, but user conversations tell you why it is happening.
