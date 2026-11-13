# Edit check

Offer people actionable feedback about Wikipedia policies while they are editing.

| Group: | Editing |
|---|---|
| Start: | 2022-10-01 |
| Backlog: | #EditCheck |

The Editing Team is working on a set of improvements for the visual editor to help new volunteers understand and follow some of the policies and guidelines necessary to make constructive changes to Wikipedia projects.

Below, you can find information about the goals of this project, the history that has informed it, and why the Wikimedia Foundation's Product Department is prioritizing this work.

Watch Editing team/Community Conversations for scheduled meetings about this project.

## Features

Several features are available within Edit Check:

- **Reference check**
- **Link check and Reference reliability**
- **Paste Check**

The Editing team works on new Checks:

- **Tone check**

The Editing team works on the related features:

- **Suggestion Mode**
- **TextMatch**

See also:

- Glossary of the terms we use
- Checks' configuration

## Objectives

1. Newcomers and Junior Contributors from Sub-Saharan Africa will feel safe and confident enough while editing to publish changes they are proud of and that experienced volunteers consider useful.
2. Moderators at the English and French Wikipedias will notice improvements in the quality of edits newcomers are making and be motivated to configure how Edit Check presents policies to them.

## Status

Updates for 2026 are listed below.

### 19 June 2026

The team is continuing to work on Suggestion Mode and other aspects of Edit Checks. The A/B experiment was launched on 15 wikis and is collecting data.

The documentation page for TextMatch has been updated and made ready for translation. Communities are encouraged to try out this feature, and let us know what you do and don't like about it, and about any bugs you find or feature-requests you have. There are some inspiring examples of how communities are currently using it listed in the Help:Suggestion mode page.

A new experimental suggestion type, "Add an image", has been created using the same functionality as the Growth team's version. Work is also ongoing on improving the functionality of the "Add a link" suggestion type, so that it can become a default global suggestion type in the future.

There is ongoing investigation into whether an LLM trained on English Wikipedia's Manual of Style can generate reliable types of suggestions.

Some research was completed to learn if LLMs could be helpful in detecting hallucinated references. This research confirmed that in English LLMs are effective at evaluating whether web-based sources corroborate claims on Wikipedia. Next, the team will investigate how effective this method is in other languages.

The team is building a way for Suggestions to be stored more efficiently, so that in the future the suggestions can be used by, or shown within, other software features, as well as showing the existence & count to editors in an article's "Read" mode.

### 10 April 2026

*Suggestion Mode*

The team is continuing to work on Suggestion Mode. The feature has been available as a Beta Feature globally since early March and at English Wikipedia since early February. Improvements to the tool since then include: Better detection of quotations for the `ignoreQuotedContent` setting; Better detection of existing references for the `addReference` suggestions; Addition of a toggle-button to hide suggestions temporarily - this will soon also save the 'hidden' state across future edit-sessions; Clearer and more accurate details in `Special:EditChecks` which shows the local configuration; Two new edit-tags added to published edits; A variety of bug-fixes and performance-improvements.

Some communities have started to use the textMatch feature to create custom local types of Suggestion.

We are now preparing for an A/B experiment with newcomers at ~20 Wikipedias, to measure what kind of impact the tool has on the percentage of constructive (un-reverted) edits by newcomers, as well as editor-retention and any changes in revert-rates and block rates.

**Seeking feedback and assistance**: Administrators at all Wikipedias can help to configure this tool so that it can recognize local standard heading-names, and so that it links to relevant local documentation pages from each type of suggestion (see Help:Suggestion mode#For administrators). All editors are strongly encouraged to share ideas and feedback on how the tool could be further improved.

### 4 February 2026

*Suggestion Mode*

The Team is working on Suggestion Mode. The focus right now is clarifying what actions and instructions Suggestion Mode will present to experienced editors who use the Beta Feature for Suggestion Mode.

**Seeking feedback:** we are particularly interested in learning what kinds of additional Suggestions you want to create (whether you can locally create them with textmatch, or if you need developer-assistance for more complicated types of Suggestion), plus any adjustments you think would be needed in the text of the existing cards, plus what are the most suitable global links for each type of Suggestion (or local links if there is nothing globally suitable). *Please let us know on the talk page.*

## Strategy and Approach

To equip newcomers and Junior Contributors from Sub-Saharan Africa with the know-how and tools to publish changes they are proud of and that experienced volunteers consider useful, the Editing Team will be introducing new functionality within the visual editor (desktop and mobile) that will check the changes people are attempting to make and present them with actions they can take to improve these changes in ways that will align with established Wikipedia policies and guidelines.

The first "check" the Editing Team will be introducing is one that will detect when people are attempting to add *new* content to an existing article *without* a corresponding reference and prompt them to do so. The functionality will be accompanied by a complimentary set of features that will enable moderators to configure the user experience newcomers and Junior Contributors will see to ensure the software is guiding them to take actions that align with project policies and conventions.

## Challenges

The visual editor's growing popularity among people who are new to editing Wikipedia leads us to think that the editing experience has been reasonably successful at helping inexperienced volunteers learn the *technical skills* necessary to publish changes to Wikipedia.

The trouble is that the visual editor and other editing interfaces do not make people aware of the Wikipedia policies and guidelines they are expected to follow.

As a result, the changes inexperienced volunteers publish often break established best practices and lead to undesirable outcomes for inexperienced volunteers, experienced volunteers, and Wikipedia projects as a whole:

1. **Inexperienced volunteers** – become disappointed and frustrated when the good-faith change(s) they arrived to the wiki seeking to make are undone (read: reverted), deleted, and/or scrutinized in inequitable ways. These poor interactions are demotivating and drive these could-be volunteers and community members, and the knowledge that are uniquely positioned to offer, away.
2. **Experienced volunteers/moderators** – need to do more work reverting low-quality edits and posting messages on inexperienced volunteers' talk pages to make them aware of the policies and/or guidelines they are likely to have unknowingly broken. Continually needing to educate inexperienced volunteers and undo their changes can lead to experienced volunteers becoming skeptical of inexperienced volunteers and impatient with them.
3. **Wikipedia projects** – struggle to grow and diversify their volunteer populations and shrink the knowledge gaps present within Wikimedia wikis.

This project seeks to address the challenges above by:

1. Offering inexperienced volunteers relevant and actionable feedback about Wikipedia policies in the precious moments when they are in the midst of making a change using the visual editor.
2. Equipping moderators with a new ability to specify the feedback inexperienced volunteers are presented with while they are editing

## Theory of change

This project is built on the belief that by surfacing relevant guidance in the precious moments when inexperienced volunteers are in the midst of making a change to Wikipedia and equipping them with the know-how and tools necessary to apply this guidance, they will make changes they are proud of and that experienced volunteers value.

In the longer term, the Editing Team thinks that people who are new, particularly people who have historically been excluded from and harmed by established power structures, will feel safe and motivated making changes to Wikipedia if they can accurately predict whether the changes they are attempting to make are aligned with existing Wikipedia policies, guidelines, and/or cultural conventions.

More broadly, the Editing Team thinks that to evolve towards a future where wikis' policies and cultural norms – and ultimately, content – reflect the diverse experiences of the people these projects are intended to serve, we first need to make the norms and standards that are currently in place legible and actionable to people while they are editing. This way, volunteers can develop shared awareness of cases where these norms and standards are not having the impacts they were intended to have and decide what – if any – changes they think are worth making to them in response.

## Primary audiences

The Editing Team is centering the needs of people in this work who are:

1. Experience: **Learning the basics of contributing to Wikipedia**
  - *In the context of this project, we are considering people who are still "learning the basics" to be people who have published <100 cumulative edits to a single, or multiple, Wikipedias. This includes people who are editing Wikipedia for the first time.*
2. Location: **Living in Sub-Saharan Africa**
3. Projects: **Contributing to the English and French Wikipedias**
4. Motivation: **Seeking to fill gaps they notice within Wikipedia**

The four focus criteria listed above are outgrowths of:

- Newcomers are two times more likely to live in Africa or Asia.
- The movement struggles to retain editors who live outside Europe and North America.
- People from Sub-Saharan Africa are underrepresented within the movement: people from Sub-Saharan Africa represent only 1% of active unique editors, despite representing 15% of the global population and 7% of the global internet population.
- 80% of registered editors in Sub-Saharan Africa contribute to English or French Wikipedia.


## Design

### Reference Detection

To start, the Editing Team is pursuing an approach with Edit Check that minimizes the likelihood of false positives and is implemented in ways that empower volunteers, on a per-project basis, to evolve the heuristic to become more robust over time.

This strategy amounts to the initial reference Edit Check becoming activated if/when all of the following conditions are met:

1. A minimum of one new paragraph of text is added to the article someone is editing
2. The "new paragraph(s) of text" someone has added does NOT include a reference
3. The changes described in "1." and "2." are happening on a page within the main namespace (NS:0)

The conditions above are implemented and maintained in code here: editcheck/init.js

The Editing Team arrived at the decision to *start* with a relatively limited and straightforward set of rules in order to:

1. Increase the likelihood that newcomers and Junior Contributors find the guidance Edit Check is presenting them with, and the editing experience more broadly, to be intuitive and straightforward so that they feel encourage to return to edit again
2. Decrease the likelihood that Edit Check is creating more work for experienced volunteers by prompting newcomers and Junior Contributors to add sources when they are not needed

*You can learn more about the assumptions that informed the thinking above in phab:T329988#8654867.*

### Other applications


### Configurability

The Editing Team thinks it is crucial that moderators be empowered to configure when, and for whom, Edit Check becomes activated. This way, they can be confident the software is promoting behavior they deem to be productive and modify the software when it is not.

In line with the above, and drawing inspiration from how the Edit filter and Growth Team Community configuration systems afford volunteers the ability to audit and configure how they function on-wiki, Edit Check will enable volunteers, on a per project basis to:

- **Audit** and **edit** the logic that determines when the reference Edit Check becomes activated and
- **Review** the edits people who are shown Edit Check are making

Work to implement the above is ongoing in phab:T327959.

### User Experience

#### Mobile

The first version of Edit Check will introduce a new step within the *mobile* visual editor's publishing workflow that people will see if/when they add new content *without* a reference.

#### Desktop

Edit checks are shown at the side on Desktop.

## Experiments

### Multi-Check (References) A/B Test

To learn whether the Multi-Check was effective at causing, newcomers to publish new content edits that include references while lowering the likelihood those edits would be reverted, we ran an A/B test with 12 Wikipedias.

Below you can read more about what this experiment demonstrated, what the Editing Team is planning in response, and more details about the test's design.

#### Conclusion and next steps

Multi-Check caused statistically significant increases in the proportion of edits that include a reference and are not reverted within 48 hours without causing undesirable changes in edit completion or other forms of disruption (e.g. blocks).

In response, Multi-Check was deployed to all wikis where Reference Check is currently available on June 25, 2025.

#### Findings

- *Proportion of new content edits with a reference*
  - Users are more likely to include at least one reference with their new content edits when multi-check (references) is available.
    - Edits that were shown multiple Reference Checks in a session are **1.3 times** more likely to include at least one new reference in the final published edit compared to sessions shown a single Reference Check.
- *Revert Rate*
  - Overall, we did not identify any significant changes in new content edit revert rate between the control and test group.
  - However, there was a **-34.7% decrease** in revert rate when directly comparing edits presented multiple checks compared to edits presented a single reference check
- *Proportion of users that publish at least one new content edit with a reference*
  - Overall, there was a **5.5% increase** in the proportion of distinct users who published a new content edit with a reference when multi-check was available.
- *Guardrails*
  - There were **no decreases** in edit completion rate for up to 5 reference checks being presented in a single session (which accounts for the majority of multi-check edits).
  - We also did not identify any increases in revert rate at any number of reference checks presented.

#### Leading Indicators (T388731)

- *New(er) volunteers are encountering Multi-Check*
  - In the test group, multiple reference checks were shown within a single editing session at **19% of all published new content VE edits (549 edits)** by unregistered users and users with 100 or fewer edits.
  - For edits shown multiple checks, the majority of edits (73%) were shown between **2 to 5 Reference Checks**.
- *People shown multiple Reference Checks w/in an edit go on to publish at a relatively high rate*
  - The edit completion rate for sessions that were shown multiple checks within a session was **76.1% compared to 75%** for sessions shown only one check, indicating that multiple checks are not causing significant disruption or confusion to the editors.
- *Likelihood to include a reference*
  - Sessions shown multiple checks are **more likely to include at least one new reference** in the final published edit compared to sessions shown just a single check.
  - In the test group, **52.5%** of all published edits shown multiple Reference checks included at least one new reference compared to **39.7%** of edits that were shown a single check.
- *Disruption (revert and block rates)*
  - In the test group, the revert rate of new content edits shown multiple Reference Checks (**17%**) is currently lower compared to sessions shown a single Reference Check (**26%**).
  - **No significant changes** in the proportion of users blocked after being shown multiple Reference Checks compared to a single Reference Check.

### Multi-Check Phase 1 Impact Analysis

In December 2024, we released a new design for the Edit Check desktop experience. This change shifted Edit Checks from appearing *within* articles to appearing *alongside* them, in a new "siderail."

To decide how – if at all – this change impacted volunteer disruption and edit quality, we compared analyzed several key metrics shifted before and after this change.

**Findings**

- The revert rate of new content edits where Reference Check was activated decreased by **15.7%**.
  - 20.4% (pre) → 17.2% (post).
- The proportion of new content edits that included a reference following the change increased **8%**.
  - 34.8% (pre) → 37.9% (post)
- Excluding reverted edits, there was **3.2%** increase [2 percentage points] in edit completion rate.
  - **68%** of edits where Reference Check was presented were successfully saved and not reverted following the change in the Edit Check UX.
- The rate at which people *declined* to add a reference when Edit Check prompted them decreased **4.7%.**

**Conclusion(s)**

The findings above suggest this design change has been net positive. As a result, we will continue depending on this new design paradigm as we introduce new types of Edit Checks and moments within the editing workflow when they are presented.

### Reference Check A/B Test

To learn whether the Reference Edit Check is effective at causing **newcomers to make edits they intended and experienced volunteers value**, we conducted an A/B test with 15 Wikipedias.

Below you can read more about what this experiment demonstrated, what the Editing Team is planning in response, and more details about the test's design.

**Conclusion and next step(s)**

Reference Check caused an **increase in the quality of edits** newcomers publish and **did not cause any significant disruption**.

This combination is leading the Editing team to be confident that offering Reference Check as a default-on feature would have a net positive impact on all wikis and the people who contribute to them.

*You can read the full A/B test report here.*

#### Findings

**New content edits *with* a reference**

People shown the Reference Check are **2.2 times more likely** to publish a new content edit that includes a reference and is constructive (not reverted within 48 hours).

- Increases were observed across *all reviewed user types*, wikis, and platforms.

- The highest observed increase was on mobile where contributors are **4.2 times more likely** to publish a constructive new content edit with a reference when Reference Check was shown to eligible edits.

**Revert rate**

- New content edit revert rate **decreased by 8.6%** if Reference Check was available.
  - New content edits by contributors from Sub-Saharan Africa are **53% less likely** to be reverted when Reference Check is shown to eligible edits.

While some non-constructive new content edits with a reference were introduced by this feature (5 percentage point increase), there was a higher proportion of constructive new content edits with a reference added (23.4 percentage point increase). As a result, we observed an overall increase in the quality of new content edits.

**Constructive Retention Rate**

- Contributors that are shown Reference Check and successfully save a non-reverted edit are **16 percent more likely** to return to make a non-reverted edit in their second month (31-60 days after).
  - This increase was primarily observed for desktop edits. There was a non-statistically significant difference observed on mobile.

#### Guardrails

**Edit Completion Rate**

- We observed **no drastic decreases** in edit completion rate from intent to save (where Reference Check is shown) to save success overall or by wiki.
- Overall, there was a **10% decrease** in edit completion rate for edits where Reference Check was shown.
  - There was a higher observed decrease in edit completion rate on mobile compared to desktop. On mobile, edit completion rate decreased by -24.3% while on desktop it decreased by -3.1%.

**Block Rate**

- There were **decreases or no changes** in the rate of users blocked after after being shown Reference Check and publishing an edit compared to users in the control group.

**False Negative Rate**

- There was a low false negative rate. Only **1.8%** of all published new content edits in the test group did not include a new reference and were not shown Reference Check.

**False Positive Rate**

- **6.6%** of contributors dismissed adding a citation because they indicated the new content being added does not need a reference. This was the least selected decline option overall.

#### Test design

11 Wikipedias participated in the test. At each wiki, 50% of users were randomly assigned to a `test` group and 50% were assigned to a `control` group.

Users in the `test` group were shown the Reference Check notice prompting them to decide whether the new content they were adding need a reference (if they had not already added one themselves).

User in the `control` group were shown the default editing experience, even if they did not accompany the new content they were adding with a reference.

#### Timing

This analysis was completed on 16 April 2024 and analyzed engagement data at the 11 participating wikis from 18 February 2024 through 4 April 2024.

## Evaluating impact

The viability of the features introduced as part of the Edit Check project depends on the impacts it causes and averts.

This section describes the:

1. **Impacts** the features introduced as part of the Edit Check are intended to cause and avert
2. **Data** we will use to *help* determine the extent to which a feature has/has not *caused* a particular impact
3. **Evaluation methods** we will use to gather the data necessary to determine the impact of a given feature

| ID | Outcome | Data | Evaluation Method(s) |
|---|---|---|---|
| 1. | Increase the quality of edits newcomers and Junior Contributors editing from within Sub-Saharan Africa publish in the main namespace | *Decrease* in the proportion of published edits that add new content and are reverted within 48 hours or have a *high* revision risk score Comments/reports from experienced volunteers about the quality of edits Edit Check is activated within | A/B test, qualitative feedback (e.g. talk page discussions, false positive reporting) |
| 2. | Increase the likelihood that newcomers and Junior Contributors editing from within Sub-Saharan Africa will accompany the new content they are adding with a reference | Increase in the percentage of published edits that add new content *and* include a reference Increase in the percent of newcomers or Junior Contributors from SSA that publish at least one new content edit that includes a reference Increase in the likelihood that someone includes a reference the next time they contribute new content. | A/B test |
| 3. | Newcomers and Junior Contributors editing from within Sub-Saharan Africa will report feeling safe and confident making changes to Wikipedia | Newcomers and Junior Contributors find the feedback and calls to action Edit Check presents them with to be: Helpful Supportive Motivating | Qualitative feedback via channels like:Community Calls, talk pages, event organizers, etc. |
| 4. | Experienced volunteers will independently audit and iterate upon Edit Check's default configurations to ensure Edit Check is causing newcomers and Junior Contributors to make productive edits. |  |  |
| 5. | Newcomers and Junior Contributors will be more aware of the need to add a reference when contributing new content because the visual editor will prompt them to do so in cases where they have not done so themselves. | Increase in the percent of newcomers or Junior Contributors from SSA that publish at least one new content edit that includes a reference. | A/B test |

| ID | Outcome | Data | Evaluation Method(s) |
|---|---|---|---|
| 1. | Edit quality decreases | *Increase* in the proportion of published edits that add new content and are reverted within 48 hours *or* have a *high* revision risk score Comments/reports from experienced volunteers about the quality of edits Edit Check is activated within | A/B test, qualitative review and feedback |
| 2. | Edits become more difficult to patrol because unreliable citations are difficult to detect | Significant increase in the percentage of new content edits new and developing volunteers make that include a reference Comments/reports from experienced volunteers about the quality of edits Edit Check is activated within | A/B test, qualitative review and feedback |
| 3. | Edit completion rate drastically decreases | Proportion of edits that are started (`event.action` = `init`) that are successfully published (`event.action` = `saveSuccess`). | A/B test |
| 4. | Edit abandonment rate drastically increases | Proportion of contributors that are presented Edit Check feedback and abandon their edits (indicated by `event.action` = `abort` and `event.abort_type` = `abandon`) | A/B test |
| 5. | Blocks increase | Proportion of contributors blocked after publishing an edit where Edit Check was shown is significantly higher than edits in which Edit Check was *not* shown | A/B test |
| 6. | High false positive or false negative rates | Proportion of new content edits published without a reference and without being shown Edit Check (indicator of false negative) Proportion of contributors that dismiss adding a citation and select *"I didn't add new information"* or other indicator that the change they are making doesn't require a citation | A/B test, qualitative feedback received from volunteers about the accuracy and usefulness of Edit Check's current configuration |
| 7. | Edit Check is too resource intensive to scale | Efficiencies do *not* emerge over time making each new Edit Check as "expensive" to implement as the first one | Qualitative assessment by the Edting team |

## Deployment process

*Please see Deployment status#Deployment process .*

## Background

Volunteers throughout the movement have a long history of working to:

- **Proactively** educate and guide newcomers to make changes they feel proud of and changes that improve Wikipedia
- **Prevent** people from publishing destructive changes, *and*
- **React** to and moderate changes to Wikipedia articles.

The Editing Team and this project have been inspired by these efforts, some of which are listed below. If there is a project or resource you think we should be aware of, please add it here!

| Initiative | Description | Initiator(s) |
|---|---|---|
| WikiNPOV Drift Detector: ML tool for detecting neutrality drift in Wikipedia articles over time | A machine learning tool that monitors Wikipedia articles continuously and flags when measurable signals collectively indicate NPOV drift, before any human editor would notice it. | User:AgarwalMahima |
| Wikipedia:WikiProject_AI_Tools | Constructive uses of LLMs and AI to support editors. | User:Chaotic_Enby |
| https://www.wikidata.org/wiki/Wikidata:ProVe | A tool that provides information about the quality of the references of Wikidata items, based on techniques such as large language models, triple verbalisation, and semantic similairty |  |
| User:SodiumJS/copying-check.js | Client-side copying detector | User:Sohom Datta |
| Wish: Apply AI to article improvement suggestions on the homepage | "A much better AI system than the previous one that recommends articles for improvement would help editors going through this, including new and veteran users." | User:Leonard609 |
| Wikimedia-l: Mopping with the tap open | A discussion wherein Romaine describes a pattern of people who are new adding information to Wikipedia without citing source(s). | nl:Gebruiker:Romaine |
| Model: meta:Eno-Prompt | A project to train a fine-tuned open-source LLM (large language model) that will detect disinformation based on linguistic analysis. |  |
| Paper: Counter-Misinformation Dynamics: The Case of Wikipedia Editing Communities during the 2024 US Presidential Elections | Recommendations to make Wikipedia more resilient to misinformation. Includes recommendations relevant to Edit Check. |  |
| Wish: Make editnotices display as pop-ups | Make people aware when they are at risk of changing an article volunteers consider to be about a contentious topic | User:Theleekycauldron |
| Corrector ortográfico, Helferlein/Rechtschreibprüfung, ויקיפדיה:סקריפטים/בודק איות, Revisor_ortográfico | A tool that checks pages loaded in the browser against a list of common spelling errors. | Poco_a_poco, Benutzer:APPER, :משתמש:ערן, Elisardojm |
| Error Finder | A tool to find common errors in Persian texts | Reza1615 |
| Wish: Warn when large amount of content has been copy-pasted | A wish to warn people who are pasting text into Wikipedia and to annotate edits in which this occurs so that patroller can consider this as they are reviewing edits/looking for edits to review. | Matěj_Suchánek |
| fr:Projet:Articles sans sources ( along with 3 other wikiprojects) | A WikiProject intended to add sources to articles that need them |  |
| CopyPatrol | Tool that allows you to see recent Wikipedia edits that are flagged as possible copyright violations | Community Tech Team |
| paper: Automatically Neutralizing Subjective Bias in Text | Method for automatically bringing inappropriately subjective text into a neutral point of view ("neutralizing" biased text). | Reid Pryzant, Richard Diehl Martinez, Nathan Dass, Sadao Kurohashi, Dan Jurafsky, Diyi Yang |
| Wikipedia:Citation watchlist | User script that adds visual indicators to watchlist and recent changes entries when unreliable sources are added to articles. | Harej, Ocaasi |
| Internet Archive Reference Explorer | Explore references included in Wikipedia articles via a range of criteria |  |
| WikiScore | A tool created to validate edits and count scores of participants in wikicontests. |  |
| Earwig's **Copyvio Detector** | This tool attempts to detect copyright violations in articles. | The Earwig |
| CiteUnseen | A user script that adds categorical icons to Wikipedia citations, providing readers and editors a quick initial evaluation of citations at a glance. | SuperHamster |
| Credibility bot | Monitors and collects data on source usage within Wikipedia articles | Harej |
| Salebot ( French Wikipedia) | A counter-vandalism bot that uses regex to identify issues. |  |
| Edit intros ( English Wikipedia) | A message is shown automatically when editing a page categorized as either Category:Living people or Category:Possibly living people. |  |
| Make edit notices more visible in Visual Editor | How might we make it so people who are in the midst of an edit are likely to see and "internalize" the information that is currently presented within Edit Notices? | User:Stjn |
| Internet Archive Reference Explorer | Automatically detect source quality | Ocaasi |
| Wish: Reference requirement for new article creation | Require new article to include references | User:Mega809 |
| Edit Notices | Enables individual volunteers and projects to display a custom notice above the edit form, depending on the page, namespace, or other circumstances. |  |
| Page notices |  |  |
| Maintenance templates |  |  |
| Extension:AbuseFilter | Enables privileged users to set specific actions to be taken when actions by users, such as edits, match certain criteria. |  |
| Extension:Disambiguator | Displays a notification in the 2006/2010 *wikitext* editor whenever one adds a link to a disambiguation page. | Community Tech |
| ORES |  | Halfak (WMF) |
| Suggested Edits |  |  |
| CiteHighlighter | Highlights 1800 sources green, yellow, or red depending on their reliability. | Novem Linguae |
| Checkwiki | Helps clean up syntax and other errors in the source code of Wikipedia | Stefan Kühn, Bgwhite |
| Edit Diff Tagging | Showcases all the different tags that can be automatically determined (generally via basic heuristics) for a given Wikipedia edit diff. | Isaac (WMF) |
| CivilityCheck | A project to evaluate the civility in the comments of Wikipedia discussions in order to address the problem of abuse that leads to declining editorship within the Wiki community. | Deus Nsenga, Baelul Haile, David Ihim, and Elan Houticolo-Retzler |
| BOTutor | A bot that sends a message to people who attempt to publish an edit that triggers an existing set of rules | ValeJappo |
| Gadget-autocomplete.js |  | ערן |
| Text reactions | A *proposal* that would make it possible for the editing interface to *react* to what the people enter in the editing area | SD0001 |
| Editwizard | A step-by-step process for guiding newcomers to source the content they are attempting to add to Wikipedia articles | Ankit18gupta, Enterprisey, Firefly, and SD0001 |
| Headbomb/unreliable | " The script breaks down links to various sources in different 'severities' of unreliability. In general, the script is kept in sync with WP:RSPSOURCES, {{Predatory open access source list}}, WP:NPPSG, WP:SPSLIST (not fully implemented yet) and WP:CITEWATCH, with some minor differences." | Headbomb, SD0001 |
| The Wikipedia Adventure | Game based on the tech of Extension:GuidedTour that teaches basic wikitext markup and the rules about reliable sources and neutral point of view. Research into its effectiveness is described at m:Research:Impact of The Wikipedia Adventure on new editor retention. | Ocaasi |
| w:Help:Introduction | The primary tutorial for new editors at English Wikipedia, covering both policies and technical how-to for VisualEditor and wiki markup. Most recently overhauled in late 2020 and more actively maintained than TWA. | Sdkb, Evolution and evolvability, and others |
| User:Phlsph7/ HighlightUnreferencedPassages | A user script to highlight passages that lack references with a red background. Its main purpose is to help users quickly identify unreferenced passages, paragraphs, and sections in mainspace articles and drafts | Phlsph7 |
| Wish: Add notice to the visual editor that unsourced edits may be reverted | A notice in the "Publish changes" dialogue of the visual editor that states that unsourced edits will be reverted | User:Lectrician1 |
| Wish: Warn when adding a url reference that matches the SpamBlacklist | Warn when the url added as reference is registered in the SpamBlacklist, and thus prevent the warning from appearing when saving the page. | User:DSan |
| Edit FIler #686 | Edit Filter that is triggered when a new user possibly adding unreferenced material to BLP | User:Rich Farmbrough |
| WikiLearn | Platform for training |  |
| DannyS712/copyvio-check.js | Automatically checks the copyvio percentage of new pages in the background and displays this info with a link to the report in the 'info' panel of the Page curation toolbar. | DannyS712 |
| XLinkBot | A bot that warns people who have added an external link that is inappropriate in some way. | Versageek, Beetstra |
