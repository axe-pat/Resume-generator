# Step 1 queue heading smoke test — 2026-08-28

**Purpose:** validate the general profile contracts against one real workload. This
file is evidence, not routing configuration: no employer, queue position, or lane is
encoded in `shared/resume_profiles.py`.

The current priority file contains 37 ready roles plus 10 completed on August 28,
reconstructing the 47-role workload. Counts below apply the existing PM archetype,
seven non-PM subtype, and reviewed campus-route definitions to each JD. They are the
expected routes before generation; Step 0 remains authoritative and fails closed on
an incomplete or conflicting classification.

| Identity headline | Remaining 37 | Full 47 | Roles in full workload |
|---|---:|---:|---|
| `PRODUCT MANAGEMENT` | 9 | 11 | Databricks APM; Spectrum Product Strategy; Xpansiv AI PM; StudyFetch Product; Appian PM; JUSPAY FDPM; Skydio PM; SAP AI PM; Pipevia PM; Amazon PMT; Amazon ALA PM |
| `STRATEGY & OPERATIONS` | 7 | 8 | Momentum MBA S&O/Transformation; Fortegra LDP; SCE MBA LDP; Flowserve MBA FLP; Momentum S&O Analyst; Axon LDP; Bestow Business Ops/AI; Amazon MLDP |
| `OPERATIONS & PROGRAM MANAGEMENT` | 6 | 7 | Philips OLDP; Stellantis Supplier Quality/Purchasing; Fora Product Operations; GALLO Technical Management; GALLO Operations Management; HNI Operations; Amazon Pathways |
| `COMMERCIAL STRATEGY` | 5 | 5 | IBM Brand Sales; Societe Generale Product Marketing; ExxonMobil Business & Commercial; CaelumenAI GTM S&O; Axon LDP Sales |
| `TECHNICAL SOLUTIONS` | 10 | 10 | IBM Client Service; Solar Applications Engineer; Momentum Enterprise Systems; LangChain Deployed Engineer; Celonis Value Engineer; Netic FDE; IBM Delivery Consultant; IBM Solution Architect; IBM Technical Sales Engineer; IBM Application Consultant |
| `PROFILE` | 0 | 6 | The six completed campus applications: Viterbi, Dornsife, Shoah Foundation, Rossier, CHLA, and Marshall |
| **Total** | **37** | **47** | |

## Decision

No heading is a one- or two-role branch: the smallest live professional branch is
Commercial Strategy at five. Folding it into Strategy & Operations would erase a
meaningful distinction already owned by the existing `commercial-gtm` route and its
separate variant/summary/skills pool. Keep all six headings.

The smoke test does not make the architecture queue-specific. Future queues may have
zero roles in a profile without changing the registry; profile removal should depend
on repeated routing/outcome evidence, not one queue's volume.
