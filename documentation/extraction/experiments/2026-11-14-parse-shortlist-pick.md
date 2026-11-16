# Parse, shortlist, pick: one take on `gitlab_architecture` (2026-11-14)

## Verdict

Not worth pursuing as a pipeline. On this document it reaches typed F1 0.10 (Clef) and 0.13 (Haiku) against find_then_type's 0.54, and even a perfect picker that never says anything wrong could not get above 0.35, because the spaCy parse names only 83 of the 122 gold individuals and the five-candidate embedding shortlist holds an accepted class for only 26 of those. The pick step itself is not the problem (given a shortlist that contains the answer, Haiku types 20 of 26 and Clef 17 of 26 correctly) and the verb-to-predicate route produced no correct relationship. The one part with any use is a bounded component: "in this chunk, pick from these candidates or none" is a sound question, but only once something better than spaCy finds the mentions and something better than an embedding chooses the candidates, which is what find_then_type already does.

The variant that fixes the weakest link (30 candidates from a better embedding instead of 5) raises the ceiling to typed F1 0.57 and nearly doubles recall, but measured typed F1 moves only to 0.18 (Haiku) and 0.09 (Clef), because about seven in ten units the pickers type name nothing in gold: once the shortlist is wide enough, the parse's noise becomes the limit.

One take on one document. The gold was drafted and checked by models; differences under about 0.08 typed F1 are noise.

## What was built

A throwaway prototype under `local-server/experiments/parse_shortlist_pick/`, never registered as a pipeline. Its code and recorded answers were not committed to the repository; this report is what was kept.

- `common.py`: chunking (`chunk_text`, as the pipelines do: 7 chunks of 3 to 8 thousand characters), the spaCy parse (`en_core_web_sm`, the app's model) and the schema.
- `shortlist.py`: step 2, and the free recall measurement of it.
- `pick.py`: step 3 for Clef and Haiku, resumable, with a spend ledger that stops at $4.75.
- `score.py`: unit tallies, individuals and relationships scored with the benchmark scorer (`tests/integration/pipelines/_harness/benchmark.py`), and an oracle picker.
- `attribution.py`: the stage at which each gold individual is lost.
- `nlp_grounded_compare.py`: what `_type_individuals_nlp_grounded`'s retrieval gets on the same document.
- `ftt_metrics.py`: find_then_type replayed from its cassette (free), with every metric.
- `out/`: units, shortlists, every answer (`answers_*.jsonl`), the spend ledger, scores.

### Choices

- **Noun units.** A NOUN or PROPN that heads its phrase (not itself a compound modifier), with its compound modifiers, applied recursively ("GitLab agent server"), and its adjectives (`amod`, which includes participles like "bundled"), in text order. Compounds stay whole because a name split into "GitLab" and "Shell" can never match. Determiners, numbers, possessives and prepositional attachments are dropped, so the noun chunk "the bundled registry" becomes "bundled registry". A bare head noun is its own unit when nothing modifies it. Proper-noun spans are just compounds of PROPN tokens.
- **Verb units.** A VERB with its adverbs (`advmod` tagged ADV) and its particle (`prt`, "set up"). Auxiliaries are excluded.
- Markdown punctuation and mermaid arrows are blanked to spaces before parsing, which keeps character offsets unchanged. The mermaid diagrams and link lists are still parsed, and they produce junk units ("click", "Core Service", "Prometheus Prometheus Prometheus TCP").
- **Size.** 1,667 noun and 505 verb occurrences, merged to 1,116 noun and 313 verb units per chunk (926 and 217 distinct across the document). The question is asked once per unit per chunk, because the chunk is part of the question: **1,429 questions per picker**.
- **"The schema".** Noun units are ranked against the 193 CLASSES, verb units against the 57 PREDICATES. The schema index (`SqliteSchemaVectorIndex`) covers classes and property definitions and embeds title and definition separately, scoring a candidate by the better of the two. I embedded the bundle directly with the same model (`all-MiniLM-L12-v2`) so I could try the alternatives.
- **Query = the unit's text** (Austin's form). The alternative, "unit. sentence" (what `_type_individuals_nlp_grounded` sends), was measured and is no better.
- **Schema side = "title: definition"**, chosen because it gave the best top-5 for nouns (table below).
- **Question.** For both pickers: `In this chunk, select the best match for "<unit>" from these candidates`, with the full chunk as context, each candidate as `Title (layer): full definition` (classes) or `title: definition` (predicates), and `none` offered. Clef gets the chunk as the shared state and a chunk's questions batched (up to 64 per request, within the context limit). Haiku makes one call per unit, with the instructions and the chunk in a cached system prompt and effort left at the default (medium), as the app's provider does.
- **Units to individuals.** Noun units given a class are grouped by the scorer's `name_key` across chunks. A name typed differently in different chunks takes the class picked most often. Its evidence is its first span, so a motivation-typed unit can pair with a gold statement by passage, as the scorer allows.
- **Verbs to relationships.** For each verb occurrence whose unit got a predicate, the dependency parse gives a subject (nsubj, the agent of a passive, or the noun a relative clause hangs on) and an object (dobj, attr, nsubjpass, or the first prepositional object). When both became individuals, that is a relationship.

### Why `gitlab_architecture`

It is the one the brief suggested and the fairest for this idea: it is mostly named technical things ("PostgreSQL", "GitLab Shell"), which is the case where a noun-phrase parse has the best chance of naming the gold individual. `edit_check` and `wikimedia_enterprise` lean more on statements and roles, which spaCy units name less often.

## Step 2 on its own (free, before any spend)

Gold individuals: 122. A noun unit carries a gold name for **83**; 35 more overlap a unit's name only partly (for example "GitLab agent for Kubernetes", "Outbound email (SMTP)", "Git over HTTP request"); 4 match nothing; none of the 8 motivation statements is named (they have no name). The 83 are named by 205 merged noun units.

An accepted class among the top k for those 205 units, `all-MiniLM-L12-v2`:

| query | schema side | @1 | @5 | @10 | @30 |
|---|---|---|---|---|---|
| unit | title | 0.07 | 0.23 | 0.30 | 0.48 |
| unit | definition | 0.07 | 0.21 | 0.33 | 0.54 |
| unit | title: definition | 0.16 | **0.28** | 0.34 | 0.46 |
| unit | max(title, definition) (the index's rule) | 0.09 | 0.23 | 0.31 | 0.51 |
| unit + sentence | max (nlp_grounded's form) | 0.08 | 0.22 | 0.30 | 0.53 |

With `all-mpnet-base-v2` the best figures are @5 0.26 and @30 0.56 (title: definition), about the same. Counted per distinct individual, an accepted class is in some unit's top 5 for **26 of the 83** (31%).

Predicates: of 83 gold relationships, **37 have no verb at all inside their evidence** (mermaid arrows, lists, nominal phrasing like "Lightweight connection pooler for PostgreSQL"). For the 46 that do, the gold predicate is in the top 5 of at least one of those verbs for 11 to 19 of them, depending on the variant (15 with the variant used). For comparison, simply always offering the five commonest gold predicates (serves, uses, depends-on, aggregates, provides) would cover 34 of the 46. Embedding the verb is worse than a constant list.

That was low enough to predict the outcome. Step 3 was still run, as asked, so the result is measured rather than assumed.

## Step 3 and the scored result

### Units

| | Clef | Haiku | both agree | oracle (top 5) |
|---|---|---|---|---|
| noun units given a class / none | 373 / 743 | 235 / 881 | 174 / 942 | 58 / 1,058 |
| of 205 gold-naming units: accepted class | 44 | 43 | 36 | 58 |
| ... wrong class (accepted class was in the list) | 41 (8) | 16 (3) | 7 (2) | 0 |
| ... none (accepted class was in the list) | 120 (6) | 146 (12) | 162 (20) | 147 |
| noun units given a class that name nothing in gold | 279 of 373 (75%) | 172 of 235 (73%) | 128 of 174 (74%) | 0 |
| verb units given a predicate / none | 149 / 164 | 134 / 179 | 88 / 225 | n/a |
| verb occurrences given a predicate: inside a gold relationship's evidence / with its predicate | 287: 42 / 4 | 253: 42 / 5 | 186: 28 / 4 | n/a |
| gold relationships (of 46 with a verb) whose verb got the gold predicate | 4 | 5 | 4 | 14 |

Most "none" answers on gold-naming units are correct given the list: the accepted class was not offered (for example "Redis" got `ux.uxapplication, ux.uxspec, ux.uxlibrary, data-store.namespace, api.responses`). Clef's confidences are low overall. It returns a full distribution: when it picks a class, that class's probability has a median of 0.44 and exceeds 0.5 in only 36% of picks (its own confidence figure has a median of 0.22). A threshold on it would trade recall for precision, but cannot recover the 57 individuals the shortlist already lost.

### Benchmark scorer, `gitlab_architecture`

| | found F1 | typed F1 | recall | core recall | precision | type accuracy | relationship recall | calls | cost |
|---|---|---|---|---|---|---|---|---|---|
| **find_then_type** (Haiku 5.5, replayed) | **0.635** | **0.541** | 0.607 | 0.889 | 0.667 | 0.851 | 0.265 | 229 | about $0.10 |
| parse + top 5 + Clef | 0.210 | 0.096 | 0.361 | 0.381 | 0.148 | 0.455 | 0.000 | 49 requests | $0.34 |
| parse + top 5 + Haiku | 0.209 | 0.133 | 0.271 | 0.254 | 0.170 | 0.636 | 0.000 | 1,429 | $0.38 |
| parse + top 5 + both agree | 0.181 | 0.136 | 0.197 | 0.222 | 0.168 | 0.750 | 0.000 | both | $0.72 |
| parse + top 5 + oracle pick (ceiling) | 0.351 | 0.351 | 0.213 | 0.206 | 1.000 | 1.000 | 0.000 | none | none |
| parse + top 30 (`all-mpnet-base-v2`, definitions cut to 400 chars) + Clef | 0.195 | 0.093 | 0.656 | 0.778 | 0.115 | 0.475 | 0.000 | 119 requests | $0.95 |
| parse + top 30 + Haiku | 0.270 | 0.183 | 0.484 | 0.492 | 0.187 | 0.678 | 0.000 | 1,429 | $0.73 |
| parse + top 30 + both agree | 0.266 | 0.193 | 0.385 | 0.413 | 0.203 | 0.723 | 0.000 | both | $1.67 |
| parse + top 30 + oracle pick (ceiling) | 0.573 | 0.573 | 0.402 | 0.381 | 1.000 | 1.000 | 0.000 | none | none |

The two oracle rows are ceilings with perfect precision, which no picker gets; they are not comparable with find_then_type's 0.541, which carries real precision.

**Top-30 variant (the weakest link, widened).** With 30 candidates an accepted class is offered for 114 of the 205 gold-naming units (49 of the 83 named individuals), against 58 units (26 individuals) with 5. Recall rises (Haiku 0.27 to 0.48, Clef 0.36 to 0.66, Clef core recall 0.78), but precision does not: Clef types 868 of 1,116 noun units (673 of them name nothing in gold) and Haiku types 396 (274 name nothing). Haiku's typed F1 goes from 0.133 to 0.183 (+0.05, under the noise line), Clef's stays at 0.09, and agreement reaches 0.193. Losses by stage (Haiku): parse 39, shortlist 34, pick 13, typed right 36. Clef: parse 39, shortlist 34, pick 18, typed right 31; with 30 options it also picks inconsistently across chunks (11 individuals right in one chunk, wrong in another). Relationship recall stays 0 for the reason given below. With 30 candidates the oracle predicate pick gets 30 of the 46 verb-bearing relationships, but neither picker gets more than 9.

Clef and Haiku differ by 0.04 typed F1 on this take: noise. Clef finds more (recall 0.36 vs 0.27) because it says "none" less often, and pays for it in wrong classes. The agreement filter raises type accuracy (0.75) without changing typed F1.

### Where it fails

Stage at which each of the 122 gold individuals is lost (main run):

| stage | Clef | Haiku |
|---|---|---|
| 1 parse: no noun unit carries a gold name | 39 | 39 |
| 2 shortlist: no unit's top 5 holds an accepted class | 57 | 57 |
| 3 pick: said none | 2 | 3 |
| 3 pick: wrong class (or wrong in one chunk) | 7 | 3 |
| typed right | 17 | 20 |

(The scorer's typed counts, 20 and 21, differ slightly because it takes each name's majority class and pairs statements by passage.)

- **Parse (39 lost).** Multi-word names that cross a preposition or parenthesis ("GitLab agent for Kubernetes", "Git over SSH request", "Outbound email (SMTP)"), names glued to neighbours in diagrams and lists ("EE GitLab", "Monitoring Process", "traffic ObjectStorage"), and every motivation statement. The parse also makes most of the noise: 926 distinct noun units for 122 gold individuals.
- **Shortlist (57 lost), the weakest link.** A bare product name has nothing for a sentence embedding to grip ("Redis", "Sidekiq", "Puma", "Praefect", "Apache" get API, UX and security classes), and "title: definition" texts that are about 1,000 characters long dilute the class's core meaning. This is the same failure the September and November probes found: embedding shortlists are the root problem.
- **Pick (5 to 10 lost).** Real but small: "AuthorizedKeysCommand" goes to `security.authenticationconfig` (Clef and Haiku both), "users" to `motivation.stakeholder`, "Gitaly storage nodes" to `technology.technologycollaboration`.
- **Precision.** About three of every four units given a class name nothing in gold: generic nouns ("interfaces", "paths", "example", "documentation"), diagram fragments ("SMTP Puma TCP"), and real but not gold-worthy things ("managed services", "Unix sockets"). Being given the whole chunk does not stop either picker typing a generic noun when a plausible class is on its list.
- **Relationships (0).** No gold relationship has a verb whose parsed subject and object are both its two gold ends: 37 have no verb, 34 have verbs whose arguments are other words, and 12 have one end parsed. So even perfect predicate picks could not build one correct relationship by this route on this document. The predicate picks are also mostly the verb's own word ("require" to `requires`, "accesses" to `accesses`), while gold states the architectural relation, often with a different verb ("Puma ... is used to run the core Rails Application" is `puma serves gitlab-rails`).

### Ten examples of each kind

From the main run, drawn at random (seed 7), with the unit's five candidates.

**Right**
1. "Prometheus" to `technology.systemsoftware` (Clef)
2. "git user" to `security.actor` (Clef, Haiku)
3. "Runway service" to `technology.technologyservice` (Clef)
4. "Unix domain socket" to `technology.technologyinterface` (gold `technology.path`, interface accepted; Clef, Haiku)
5. "PostgreSQL" to `data-store.database` (gold system software, database accepted; Clef, Haiku)
6. "GitLab API" to `api.openapidocument` (accepted; Clef)
7. "Kubernetes" to `technology.systemsoftware` (Haiku)
8. "SSHService" to `application.applicationservice` (accepted; Haiku)
9. "CI artifacts" to `technology.artifact` (accepted; Haiku)
10. "AI features" to `product.feature` (accepted; Haiku)

**Wrong class**
1. "Redis" to `data-store.namespace` (Clef; list had no accepted class)
2. "Gitaly" to `application.applicationinteraction` (Clef; list `ux.uxlibrary, ux.uxapplication, security.securitypolicy, security.separationofduty, application.applicationinteraction`)
3. "AuthorizedKeysCommand" to `security.authenticationconfig` (both; gold application component, not in list)
4. "Gitaly storage nodes" to `technology.technologycollaboration` (Clef; `technology.node` was first in the list)
5. "GitLab administrators" to `security.actor` (Clef; `business.businessrole` was in the list)
6. "Amazon S3" to `technology.systemsoftware` (Clef; gold technology service, not in list)
7. "GitLab Workhorse" to `technology.systemsoftware` (Haiku; gold application component, not in list)
8. "GitLab web app" to `ux.uxapplication` (Haiku)
9. "users" to `motivation.stakeholder` (Haiku; `security.actor` was in the list)
10. "postgresql exporter" to `apm.exporterconfig` (Haiku)

**Wrongly "none"**
1. "Sidekiq" (list: `api.response, ux.statetransition, security.countermeasure, api.openapidocument, data-store.accesspattern`)
2. "Praefect" (list: security, navigation and UX classes)
3. "Apache" (list: five API classes)
4. "EE" (list: five UX classes)
5. "Puma" (Haiku)
6. "Charts" (list: `ux.chartseries, ux.tablecolumn, apm.dashboard, ...`)
7. "Google Cloud Storage" / "Azure Blob Storage" (no technology service in the list)
8. "LFS objects" (Clef; `business.businessobject` WAS in the list: a real pick error)
9. "GitLab application" (Haiku; `application.applicationcollaboration` WAS in the list)
10. "Distribution team" (gold business actor; list had business role and security actor)

**Spurious** (a class for something gold does not hold)
1. "SMTP Puma TCP" to `technology.path` (mermaid fragment)
2. "Prometheus Prometheus Prometheus TCP" to `technology.path`
3. "communicates" to `technology.path` (a verb tagged as a noun)
4. "example" to `api.example`
5. "documentation" to `api.externaldocumentation`
6. "better user experience" to `ux.uxspec`
7. "interfaces" to `application.applicationinterface`
8. "managed services" to `technology.technologyservice`
9. "Unix sockets" / "SSH connections" to `technology.path`
10. "AI architecture A SaaS model gateway" to `technology.technologyservice` (a heading run into a name)

## Compared with `_type_individuals_nlp_grounded`

That path (spaCy noun chunks, query "label. sentence", schema index top 8 with threshold 0.2, an LLM confirming with the SENTENCE as context) was measured on the same document without spending: its noun chunks name **64** distinct gold individuals (labels keep determiners, so "the GitLab Runner" never matches) against this experiment's 83, and its retrieval puts an accepted class in the top 8 for **0.29** of the gold-naming chunks against 0.28 in this experiment's top 5. Its ceiling is therefore slightly lower than this one's. Austin's four changes (adjective+noun units, exactly five candidates, the full chunk, a decision model beside an LLM) improve the parse a little and leave the retrieval where it was, and the full chunk only helps the step that was already working (the pick). The September verdict on that path ("worse than LLM typing") is confirmed here on a bigger, harder document, for the same reason.

## Cost, size and latency

| | requests | tokens | dollars | wall time |
|---|---|---|---|---|
| Clef, top 5 | 49 requests (about 29 questions each) | about 1.4 M input (priced at $0.24/M) | $0.34 | 49 s at 4 requests in parallel (about 4.2 s per request) |
| Haiku, top 5 | 1,429 calls | 5.99 M input (4.03 M of it cache reads), 0.29 M output | $0.38 | 274 s at 8 in parallel (median 1.4 s per call) |
| find_then_type (Haiku) | 229 calls | not recomputed here | about $0.10 | not measured |
| Clef, top 30 | 119 requests (about 12 questions each) | about 3.9 M input | $0.95 | 129 s (4.3 s per request) |
| Haiku, top 30 | 1,429 calls | 9.10 M input (4.09 M cache reads), 0.37 M output | $0.73 | 329 s (median 1.7 s per call) |

Total spent in this experiment: $2.39 (main run $0.72, top-30 variant $1.67) (ceiling $5).

The parse is free and takes seconds, but it makes about 6 times as many questions as find_then_type makes calls, so this shape is 3 to 4 times dearer than find_then_type for a third of its typed F1.

## The single change that would most improve it

Replace the embedding shortlist. Of the 83 individuals the parse can name, the top 5 loses 57, and every downstream number is capped by that (the oracle ceiling is 0.35). Widening it to 30 candidates was measured: it lifts the ceiling to 0.57 and recall by 0.2 or more, but typed F1 only by 0.05 for Haiku (noise) and not at all for Clef, because the pickers then type far more of the parse's noise. So the honest answer is two changes in a row: a shortlist that holds the answer (an LLM ranking against the whole catalog did this in the November probes; an embedding of any width tried here did not), and a filter that drops the roughly 900 noise units before typing. Of those two, the shortlist is the larger single gain on paper (57 of 122 individuals lost there with five candidates), and the noise filter is what decides whether that gain shows up. Once the shortlist is replaced by an LLM ranking against the whole catalog, what is left is find_then_type with a spaCy mention finder in place of the LLM finder, and the parse is then the next cap (83 of 122 named, and about 900 noise units to filter).

## What I could not verify

- One take on one document; no repeat runs, so pick-to-pick variance is unknown. Clef versus Haiku (0.10 vs 0.13 typed F1) is within noise.
- The gold is model-made; "spurious" partly means "not in gold" (some of those units, such as "Unix sockets", are arguably real).
- find_then_type's latency was not measured (its replay is from a cassette), and its dollar figure is the one recorded earlier.
- Clef's token counts are not returned by the adapter; the 1.4 M figure is back-computed from its price.
- Relationships were tried only through the dependency parse of `en_core_web_sm`; a larger spaCy model (`en_core_web_lg`, not installed, a few hundred MB) or a coreference step was not tried. Given that 37 of 83 gold relationships have no verb at all, I do not expect it to change the conclusion.
- The top-30 variant's definitions were cut to 400 characters (to keep within budget and Clef's context), so it differs from the main run in two ways, not one.
