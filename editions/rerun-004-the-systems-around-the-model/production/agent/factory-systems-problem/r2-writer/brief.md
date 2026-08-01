# Faithful-edit production prompt

You are a production editor preparing a source that already fits the magazine.
This mode stays close to the original text. You are not a summarizer and not a
rewriter: you clean the source for print and otherwise leave it alone.

## Inputs

The source extraction at `library/sources/<source-id>/extracted.md` (or several
extractions when the article combines short posts by one author), and the
article's row in the edition manifest.

## Procedure

1. Read the whole extraction.
2. Remove web chrome: navigation, advertising, subscription prompts, social
   furniture, duplicated boilerplate.
3. Normalize typography, whitespace, headings, lists, links, and footnotes for
   print, and repair obvious extraction or OCR errors.
4. Adapt figure captions without changing their meaning.
5. Add the frontmatter below and check the page budget. If the result exceeds
   seven A5 reader pages, stop: the piece converts to `faithful_synthesis`
   under `docs/EDITORIAL_POLICY.md`. Do not compress it here.

## Hard rules

- Keep the source's wording, sentence order, section order, qualifications,
  tone, and grammatical person. Do not paraphrase for smoothness.
- Keep the author's voice intact, including profanity, jokes, asides, insults,
  and sign-offs. "they are selling bullshit" and "Good luck." are the reason
  this mode exists.
- Write as little new prose as possible. Any addition must be rare, necessary,
  and visibly labeled to the reader as an "Editor's note".
- Never manufacture a quotation, a link, a number, or a claim, and never
  reorder the argument.
- When several short posts by one author are combined, keep each post's text
  intact and in a declared order. Do not write transitions in the author's
  voice between them.
- If the source is slides, preserve its sequence and wording while converting
  visual hierarchy into headings, captions, and lists. Do not infer missing
  prose.
- `docs/WRITING_RULES.md` governs only the text you write yourself, such as an
  editor's note or a caption; there the banned tics apply, including the
  antithesis close "It is not X. It is Y." Never apply the rules to the
  author's sentences, and never rewrite one because it uses a banned
  construction.

## Format

```
---
source_ids:
- <source-id>                     # one entry per source, always a list
content_mode: faithful_edit
label: FAITHFUL EDIT
---
```

The title, byline, and `source_body_sha256` pins live in the article's
`edition.yaml` row, not here. The body follows the closing `---` and must begin
with a paragraph, never a heading, so the illustrated opener can set it. Use
`##` for section headings; no H1.

## Working notes

End your reply with a line containing exactly:

    <!-- SCRATCH: not part of the manuscript -->

and put your working notes below it: what you kept, what chrome you removed, and every sentence you wrote yourself. Everything above that line is the
manuscript and is written to disk as it stands; everything below it is stripped
before the file is written and is never shown to a judge or to a reader.

Write the notes for the person who revises this piece next, which may be you in
another session. A review finding names the sentence where a defect *surfaces*;
your notes are usually the only record of where it was *made*, and a reviser
working from findings alone can patch a symptom without ever finding its cause.
Say what you decided, what you cut and why, and which choices the piece is
resting on.

## How this will be judged

- A fact-checker reads the manuscript against the extraction claim by claim:
  every manuscript claim must be present in the source, and every substantive
  source claim must be present in the manuscript or be removable chrome.
- A line editor checks typography, structure, labeling of any editor addition,
  and confirms the author's voice was not smoothed.

---

# The assignment

The prompt above governs. This section names the piece, supplies its complete inputs, and states the output contract.

- Edition: `rerun-004-the-systems-around-the-model` (The Systems Around the Model)
- Piece id: `factory-systems-problem`
- content_mode: `faithful_edit`
- Title: The Factory Is a Systems Problem
- Byline: Geoffrey Huntley
- Page budget: 7 rendered A5 reader page(s)

## Source extractions

3 extraction(s), each complete. You are drafting the whole piece in this one pass from all of it: nothing else will be sent, and no later call will stitch a second half on.

### Extraction `software-factories-are-super-real-but-the-factor-ab8ad3ab` (1 lines, complete)

```
[1] software factories are super real but we need to be realistic. the factory aspects haven’t been cracked yet, the [3] innovators are toying around with discovering practices and pieces. if someone is selling you a factory rn and they aren’t in the super small cohort (ie. they are likely startups created in last six months!) or circa <10 people in the who’s-who, who have been trying (and realistically failing) over the last two years. they are selling bullshit. it isn’t cracked but it’s a puzzle that’s being solved daily. the best practices right now are to build abstractions/pieces needed which entails solving [2] non-agent topics. [1] almost lights out. [2] sandboxing, monorepo, reproducible builds, ci/cd, identity/secret management, smashing corporate friction in the realm of devex for agents. [3] at home, in your homelab, you should be cracking on this problem space in your free time if you want a super fast promotion and red carpet service at your next interview. highest roi you can have right now is learning the entire damn stack, automating it and showing it at your next interview/doing a recorded talk at a meetup.
```

### Extraction `factories-are-not-a-token-or-llm-problem-ba5fabbf` (1 lines, complete)

```
i must stress that factories is not a token or llm problem. it’s a systems engineering and corporate culture problem. it won’t be solved through tokens or how you apply the tokens (but it is a piece of the puzzle) ugh. blog post time.
```

### Extraction `do-not-make-the-service-bus-non-deterministic-3a92442c` (1 lines, complete)

```
second hot take, as it seems the first hot take landed. n8n was a silly idea, which i’ve always suspected was developed by young folks in silicon valley who are all in on the LLM craze who have never worked in corporate in their life thus didn’t have the knowledge that service busses are a solved problem and there’s deep prior art in the spooky land of enterprise. look up anything in the @dotnet space such as mass transit, nservicebus, [1] wcf if you wanna steal ideas for prompting. if you want a modern plug and play choice, @temporalio exists. use it and have a job invoke an agent as a process. don’t make the entire service bus non-deterministic. [1] lots of bad memories here, not great tech impl but the theory / education is generally on point.
```

## Round 2: revise the draft below

A previous round of this piece was judged and did not pass. Your job is to produce the whole manuscript again, with every defect below gone. Rewrite as much as the repair needs; you are not patching sentences.

### Your predecessor's working notes

These are the notes from the draft below, not a judgment of it. A finding says where a defect *surfaces*; these notes are usually the only way to see where it was *made*. Read them before the findings.

```
## The headline finding: the mode does not fit the assignment

The three extractions contain about 340 words of author text in total (roughly
190 + 45 + 105). `faithful_edit` forbids paraphrase, forbids invented
transitions, and says "write as little new prose as possible." So the ceiling
for this piece in this mode is about 340 words of Huntley plus a labeled note
or two. The brief's ~1,100-word budget cannot be reached without writing 750
words that no source supports. I did not write them. The manuscript is ~460
words.

This is the honest answer to the "three into one" problem: **the shipped 305
words was not thin because the editor was lazy. It was thin because the mode
caps it there.** The previous version's real defects were structural (five
headings over 340 words, an orphan referent, a two-sentence section, a
conclusion promised by a heading and then dropped), and those are fixable
inside the mode. Length is not.

If the edition needs a developed 1,100-word article on this subject, the
options are:

1. `faithful_synthesis` or `selected_extracts` with more Huntley sources.
   These three posts are stubs; post 2 literally ends "blog post time,"
   meaning the argument was going to be written somewhere else. Find that blog
   post and the "first hot take" post, capture them, and the piece becomes a
   real feature in a faithful mode.
2. An `original_editorial` or magazine-voiced piece that uses these three as
   quoted material and does the developing itself. That is the only route to
   1,100 words that does not require inventing Huntley's sentences.
3. Ship it at ~460 words as a short faithful edit and give the page budget to
   something else.

My recommendation is (1) if capture is possible, (3) if it is not. Do not ask
`faithful_edit` to fill a page it has no text for.

## Root cause of the shipped version, read only after drafting

I opened `editions/004-the-systems-around-the-model/articles/factory-systems-problem.md`
after the draft above was finished. Every defect in the brief is there, and
there is a larger one underneath them that the brief does not name: **the
shipped piece is not a faithful edit at all. It is a paraphrase wearing the
`FAITHFUL EDIT` label.** Almost no sentence survives intact. "software
factories are super real" became "Software factories are real". "circa <10
people in the who's-who" became "the roughly ten people". "sandboxing,
monorepo" became "sandboxes, monorepos". "ugh. blog post time." is gone
entirely, and so is the "(but it is a piece of the puzzle)" qualification.
Two handles were turned into invented `x.com` links.

Most tellingly, "WCF gives me bad memories" is a *manufactured author-voiced
sentence*. The source says "lots of bad memories here" inside an annotation.
That line was praised as proof the edit kept Huntley's voice. Huntley never
wrote it. An editor wrote it in his person, which is the exact thing the mode
forbids, and it passed review because it sounded right.

That reframes the other findings. The dropped conclusion under the heading
"Keep the service bus deterministic" was not an oversight: the heading also
*inverts* the author's imperative from "don't make it non-deterministic" into
a positive instruction, which is a rewrite, and once you are rewriting, the
sentence the heading was named after stops feeling load-bearing. The orphaned
"Second hot take." survived for the mirror-image reason: it was the one place
the paraphrase stayed literal.

So the lesson for the next reviser is narrower than "develop it more." It is:
in this mode, if you find yourself with room to spare, the temptation is to
paraphrase into fluency and add connective sentences in the author's person.
Both are how this piece failed. The remedy is fewer editor words, not better
ones.

## The three-source seam

Reading order chosen: post 2 ("factories are not a token or llm problem"),
then post 1 ("software factories are super real"), then post 3 ("do not make
the service bus non-deterministic"). Frontmatter `source_ids` is left in the
placeholder's order and untouched, per the brief.

Why that order, and no author-voiced transitions anywhere:

- Post 2 is 44 words, which is the only block in the whole corpus that lands
  inside the 40-60 word opener window at a real sentence boundary. Post 1's
  sentence boundaries give 28 words or 76 words and nothing between, so post 1
  cannot open the piece without either a mid-sentence break (not allowed) or a
  failed opener page. This constraint, not taste, picked the order.
- The order also happens to read as thesis then evidence then instance: post 2
  states the claim (systems engineering and corporate culture, not tokens),
  post 1 gives the market and the non-agent stack, post 3 is one concrete
  system the claim applies to. Nothing was added to make that happen; the
  seam is carried entirely by sequence and by two labeled notes.
- Post 2 gets no heading. It is the opener paragraph, so it cannot be a
  heading, and giving a 44-word post its own `##` section is exactly the
  "two-sentence section" defect from last time. Two headings total, both of
  them the author's own words.

Risk this rests on: reordering. `faithful-edit.md` says "never reorder the
argument" (within a source, which I did not do) and separately says combined
posts run "in a declared order," which only means anything if the editor picks
one. I picked one and declared it in the first editor's note. If a reviewer
reads the reorder rule as covering across-post order too, the fallback is
order 1-2-3, and then the opener constraint breaks and someone has to choose
which hard rule loses. Flagging it rather than hiding it.

## Orphan referents found, and what I did with each

1. **"second hot take, as it seems the first hot take landed"** (post 3, first
   sentence). The first hot take is not in any of the three extractions. This
   is the one the last version stranded. I kept Huntley's sentence intact and
   supplied the antecedent with a labeled editor's note placed *before* the
   sentence, so the reader has it before they hit the dangling reference. I
   did not cut the marker, because cutting it would delete the author's words,
   and I did not guess that post 1 is the first hot take, because nothing in
   the captures says so. It is plausible and unverifiable, so it stays out.
2. **"ugh. blog post time."** (post 2, last sentence). Forward-looking, so not
   an orphan on its own. But putting post 2 first creates the implicature that
   the two sections that follow *are* the promised blog post. My reorder made
   this problem, so the first editor's note closes it: "The longer post
   promised above is not one of the three."
3. **"i must stress that..."** (post 2, first words). Soft referent: he is
   stressing against something said earlier, off-capture. It reads as plain
   emphasis without an antecedent, so I left it alone. Noting it so the next
   reviser does not think it was missed.
4. **The bracketed numerals** `[1] [2] [3]` in post 1 and `[1]` in post 3 are
   not orphans, they are the author's own annotation markers with their text
   trailing at the end of each capture. Handled as footnotes, below.

## Footnotes: a real bug fixed from the placeholder

The placeholder at
`editions/rerun-004-the-systems-around-the-model/articles/factory-systems-problem.md`
renders post 1's note [1] **twice**: once as body text ("almost lights
out.[^1]" glued to the end of the last sentence) and once as the footnote
definition. In the capture, `[1]` is a marker sitting immediately before
"software factories" in the very first words, and "almost lights out." is its
note text. I moved the marker onto `software factories[^1]` and left the text
only in the definition. Same for `innovators[^3]` and `non-agent topics.[^2]`,
whose placement the placeholder already had right.

Numbering: I kept Huntley's own numbers rather than renumbering to order of
appearance (which would be 1, 3, 2). Post 3's note is `[1]` in its own
capture; it becomes `[^4]` here only because footnote labels are
document-scoped and `[^1]` was taken. That renumber is the single unavoidable
change to a source numeral in the piece.

## Each source's own conclusion, confirmed present

- Post 1: "the best practices right now are to build abstractions/pieces
  needed which entails solving non-agent topics." Present, closing its
  section. Its stronger exhortation, "highest roi you can have right now is
  learning the entire damn stack, automating it and showing it at your next
  interview/doing a recorded talk at a meetup," lives in note [3] in the
  capture and therefore lives in footnote [^3] here. It is verbatim and
  complete, but it *is* in a footnote. If a reviewer wants it in the body,
  that is a defensible promotion, but it would be the editor deciding the
  author's structure. I left it where he put it.
- Post 2: "it's a systems engineering and corporate culture problem." Present,
  in the opener paragraph, along with the qualification "(but it is a piece of
  the puzzle)" which is easy to drop and which I kept.
- Post 3: "don't make the entire service bus non-deterministic." Present, as
  the last sentence of the article, matching the heading named after it. This
  is the exact fact-checker finding from last time and it is now the line the
  piece ends on.

Nothing was cut from any of the three captures. There was no web chrome to
remove: all three extractions are clean DOM transcriptions of the post text
with no nav, no subscribe prompts, no social furniture.

## Voice decisions

- **Lowercase kept throughout the author's text.** All three posts are
  all-lowercase. Sentence-casing them is defensible as "normalize typography
  for print," but it would smooth the most visible feature of the voice across
  every line, and the placeholder in the repo keeps lowercase too. My own
  headings and notes use sentence case, which has the useful side effect of
  making editorial apparatus visually distinct from author text at a glance.
  If house style later demands sentence case in print, change it in one pass
  and say so.
- Kept: "they are selling bullshit", "the spooky land of enterprise", "ugh.
  blog post time.", "the entire damn stack", "rn", "ie.", "wanna", "<10",
  "who's-who", the `!` in "(ie. they are likely startups created in last six
  months!)", and the ungrammatical dangling `if` clause before "they are
  selling bullshit." That last one is a run-on the author left in; it is not
  an extraction error and I did not repair it.
- Kept `@dotnet` and `@temporalio` as handles. They are the author's chosen
  way of naming .NET and Temporal, and turning them into product names would
  be rewriting. Arguably they are "social furniture" and a line editor may
  disagree; if so, `.NET` and `Temporal` are the swap, and it changes wording.
- The only sentences I wrote are the two editor's notes (~75 words total).
  Both are labeled in bold. Neither uses a banned tic; I checked them against
  `docs/WRITING_RULES.md`, which per the mode governs only these two notes and
  the two headings, never Huntley's lines.

## Layout compliance

- Opening paragraph: 44 words, inside the 40-60 window. It is post 2 whole, so
  it cannot drift if someone re-edits around it.
- First body block is a paragraph. No H1. Two `##` headings. No figures
  anchored, so heading wording was free and I used the author's own.
- Note that the opener QR resolves to the *first* `source_ids` entry, which is
  post 1, while the opener paragraph is post 2. Frontmatter order is frozen by
  the brief, so I left it, but a reader scanning the QR lands on a different
  post than the one printed above it. Someone should decide whether that is
  acceptable or whether `source_ids` should be reordered to match the reading
  order.

## Unclear prompt instructions

1. `faithful-edit.md` says "never reorder the argument" and "keep each post's
   text intact and in a declared order" in the same rule list. Across multiple
   posts these pull in opposite directions and the prompt does not say which
   wins. Suggest it state explicitly that across-post order is the editor's to
   choose and declare, while within-post order is frozen.
2. The prompt's only length guard is a *ceiling* (seven A5 pages, convert to
   synthesis above it). There is no floor and no guidance for the case here,
   where the sources are far too short for the slot. That gap is what produced
   the 305-word failure. Suggest a matching rule: if the combined captures
   cannot fill the assigned budget, the piece is under-sourced, and the fix is
   more sources or a different mode, never padding.
3. The opener's 40-60 word requirement is not in `faithful-edit.md`,
   `docs/WRITING_RULES.md`, or `docs/DESIGN_SYSTEM.md`. `DESIGN_SYSTEM.md`
   only says the opener ends after the introductory paragraph. In a mode that
   cannot rewrite the author's first paragraph, a hard word window on it is a
   constraint the writer often cannot satisfy at all. It should be written
   down somewhere, with a stated remedy for when no source paragraph fits.
```

### The draft under revision

```
---
source_ids:
- software-factories-are-super-real-but-the-factor-ab8ad3ab
- factories-are-not-a-token-or-llm-problem-ba5fabbf
- do-not-make-the-service-bus-non-deterministic-3a92442c
content_mode: faithful_edit
label: FAITHFUL EDIT
---

i must stress that factories is not a token or llm problem. it's a systems engineering and corporate culture problem. it won't be solved through tokens or how you apply the tokens (but it is a piece of the puzzle) ugh. blog post time.

**Editor's note.** Three short posts by one author, published separately. The reading order is this magazine's and not a sequence Huntley wrote: the paragraph above, then the two sections below. The captures carry no dates, so the order they were written in cannot be recovered here. The longer post promised above is not one of the three.

## Software factories are super real

software factories[^1] are super real but we need to be realistic. the factory aspects haven't been cracked yet, the innovators[^3] are toying around with discovering practices and pieces. if someone is selling you a factory rn and they aren't in the super small cohort (ie. they are likely startups created in last six months!) or circa <10 people in the who's-who, who have been trying (and realistically failing) over the last two years. they are selling bullshit.

it isn't cracked but it's a puzzle that's being solved daily. the best practices right now are to build abstractions/pieces needed which entails solving non-agent topics.[^2]

[^1]: almost lights out.

[^2]: sandboxing, monorepo, reproducible builds, ci/cd, identity/secret management, smashing corporate friction in the realm of devex for agents.

[^3]: at home, in your homelab, you should be cracking on this problem space in your free time if you want a super fast promotion and red carpet service at your next interview. highest roi you can have right now is learning the entire damn stack, automating it and showing it at your next interview/doing a recorded talk at a meetup.

## Don't make the service bus non-deterministic

**Editor's note.** The first hot take is a separate post and is not one of the three collected here.

second hot take, as it seems the first hot take landed. n8n was a silly idea, which i've always suspected was developed by young folks in silicon valley who are all in on the LLM craze who have never worked in corporate in their life thus didn't have the knowledge that service busses are a solved problem and there's deep prior art in the spooky land of enterprise.

look up anything in the @dotnet space such as mass transit, nservicebus, wcf[^4] if you wanna steal ideas for prompting. if you want a modern plug and play choice, @temporalio exists. use it and have a job invoke an agent as a process. don't make the entire service bus non-deterministic.

[^4]: lots of bad memories here, not great tech impl but the theory / education is generally on point.
```

### Findings you must clear

Every finding is an obligation: the defect it names must be gone from your draft. A `suggestion` is advisory. You are judged on whether the defect survived, never on whether you took the suggested line, so solve it however the piece is best served.

1. [major] invented_claim (from the evidence)
   - where it shows: Don't make the service bus non-deterministic | The first hot take is a separate post and is not one of the three collected here. | 1
   - earliest repair point: - | The captures carry no dates, so the order they were written in cannot be recovered here. | 1
   - note:
     The extraction supports only that a first hot take exists and had landed:
     "second hot take, as it seems the first hot take landed." Nothing in any of
     the three extractions identifies that first hot take or rules out the two
     other collected posts as candidates for it. Neither collected post is
     dated, neither self-identifies, and both are short opinion posts of the
     kind the phrase describes. The editor's note nonetheless asserts a
     definite negative - that it "is not one of the three collected here" -
     which the pinned sources cannot establish. It also contradicts the
     article's own earlier disclosure that "the order they were written in
     cannot be recovered here": a magazine that cannot recover the order cannot
     know that an earlier collected post was not the first hot take. The defect
     is structural, since the certainty it borrows is set up in the first
     editor's note, which is where a hedge belongs.
2. [minor] invented_claim (from the evidence)
   - where it shows: - | The longer post promised above is not one of the three. | 1
   - note:
     The source's only relevant words are "ugh. blog post time." The
     extractions carry no date, no title, and no link for the promised post, so
     whether it is among the three captures cannot be checked. The claim is not
     baseless - all three captures are short, and "blog post time" reads as
     prospective - but the software-factories post is on exactly the promised
     subject ("the best practices right now are to build abstractions/pieces
     needed which entails solving non-agent topics"), is the longest of the
     three, and carries footnotes. On the pinned evidence it cannot be excluded,
     and the note excludes it flatly.
3. [minor] overstated_furniture (from the evidence)
   - where it shows: Don't make the service bus non-deterministic | Don't make the service bus non-deterministic | 1
   - note:
     The source's imperative is "don't make the entire service bus
     non-deterministic." The magazine-supplied heading drops "entire", and the
     word is load-bearing: the sentence before it in the same source tells the
     reader to "have a job invoke an agent as a process", that is, to keep the
     non-deterministic agent inside an otherwise deterministic bus. Read alone,
     the heading is a blanket prohibition on non-determinism in the bus, which
     is stronger advice than the source gives. Mitigated by the full sentence
     appearing verbatim at the end of the same section.
4. [major] missing_transition (from the line)
   - where it shows: Don't make the service bus non-deterministic | second hot take, as it seems the first hot take landed | 1
   - earliest repair point: Software factories are super real | the best practices right now are to build abstractions/pieces needed which entails solving non-agent topics. | 1
   - note:
     The two sections are welded, not joined. Section one ends on "the best
     practices right now are to build abstractions/pieces needed which entails
     solving non-agent topics." Section two opens on "second hot take, as it
     seems the first hot take landed. n8n was a silly idea". Nothing in the
     seam tells the reader why an orchestration tool has suddenly arrived, and
     the only thing standing in the gap is the editor's note about a first hot
     take that is not here, which draws attention to an absence instead of
     building a bridge. The connection is available and unstated: a
     non-deterministic service bus is exactly one of the "non-agent topics"
     section one says has to be solved properly, so the second section is the
     first section's argument applied to one piece of plumbing. Placement is a
     second problem: the note pre-empts a confusion the reader has not had
     yet, so it reads as an apology before the reader knows what is being
     apologised for. Both the note and the seam are editor-owned, so this is
     fixable without touching a word of Huntley's.
   - suggestion (advisory): Replace the editor's note with one that bridges: **Editor's note.** The next post applies the same argument to one piece of that plumbing. Its numbering refers to an earlier post not collected here.
5. [minor] opening (from the line)
   - where it shows: - | ugh. blog post time. | 1
   - earliest repair point: - | i must stress that factories is not a token or llm problem | 1
   - note:
     The piece opens by announcing that the real writing is still to come.
     "i must stress that factories is not a token or llm problem" is a good
     cold thesis and both sections serve it, but the paragraph ends on "ugh.
     blog post time.", and the editor's note then confirms "The longer post
     promised above is not one of the three." So the reader's first thirty
     seconds are spent being promised an article and then told it is not in
     the magazine. The disclosure is honest and correctly labelled, which is
     why this is minor rather than major, but disclosure is not repair: the
     opening still spends its energy on something absent. Capped at minor and
     the suggestion left as advice, since the sentence is the author's own and
     the fix is a placement decision rather than a rewrite.
   - suggestion (advisory): End the opening paragraph at "it won't be solved through tokens or how you apply the tokens (but it is a piece of the puzzle)" and move "ugh. blog post time." into the editor's note as the reason the promised post is absent.
6. [minor] argument_order (from the line)
   - where it shows: Software factories are super real | sandboxing, monorepo, reproducible builds, ci/cd, identity/secret management | 1
   - earliest repair point: Software factories are super real | the best practices right now are to build abstractions/pieces needed which entails solving non-agent topics. | 1
   - note:
     The only concrete content in section one sits in a footnote. The body
     says factories are real, not cracked, being worked on daily, and that the
     answer is "abstractions/pieces needed which entails solving non-agent
     topics". Every noun a reader can act on, "sandboxing, monorepo,
     reproducible builds, ci/cd, identity/secret management, smashing
     corporate friction in the realm of devex for agents", is in footnote 2.
     In A5 print that list lands at the bottom of the page, after the reader
     has already decided the section was abstract. Two of the three footnotes
     carry more weight than the paragraphs they hang off. Minor because the
     text is the author's and lifting it changes his shape, but the footnote
     versus body split is the magazine's typesetting call.
   - suggestion (advisory): Set footnote 2 as a run-in list inside the sentence it annotates rather than at the foot of the page.
7. [minor] jargon (from the line)
   - where it shows: Don't make the service bus non-deterministic | n8n was a silly idea | 1
   - note:
     n8n is the subject of the second section's opening judgement and the
     piece never says what it is. A backend engineer who has not touched
     workflow automation gets "n8n was a silly idea" and has nothing to attach
     the judgement to; the sentence that follows explains who built it and
     what they did not know, but not what it does. The same paragraph then
     leans on "mass transit, nservicebus, wcf" and "@temporalio" as the
     contrast, and those at least come pre-labelled as service buses. The
     handles are a second small wart in print: "@dotnet" and "@temporalio"
     read as platform residue on the page. Author's own sentence, so capped at
     minor; a four-word editor gloss on first use would clear it without
     touching the line.
   - suggestion (advisory): Gloss on first use: n8n (a visual workflow-automation tool).
8. [minor] dead_words (from the line)
   - where it shows: Software factories are super real | if someone is selling you a factory rn and they aren't in the super small cohort | 1
   - note:
     This is where my attention dropped and I went back. The conditional
     collapses: "if someone is selling you a factory rn and they aren't in the
     super small cohort (ie. they are likely startups created in last six
     months!) or circa <10 people in the who's-who, who have been trying (and
     realistically failing) over the last two years. they are selling
     bullshit." The parenthetical appears to gloss the cohort the sellers are
     NOT in, which inverts what it seems to mean; "or circa <10 people in the
     who's-who" hangs off nothing; and the full stop before "they are selling
     bullshit" severs the apodosis from its protasis, so the payoff line
     arrives as an unattached fragment. Author's own sentence in a faithful
     edit, so this caps at minor and I am not proposing wording. Worth a
     query to Huntley rather than a silent repair, since the sentence carries
     the section's only test a reader can apply.

## Output contract

Return the complete manuscript first: the frontmatter the prompt specifies, then the body, and nothing before it. Then a line containing exactly:

    <!-- SCRATCH: not part of the manuscript -->

Then your working notes for that draft: the concept graph or claim ladder you built the piece from, what you cut and why, and anything a later reviser would otherwise have to reconstruct. Everything below the marker is stripped before the manuscript is written and is never shown to a judge, so write it for the next writer, not for a reader. Return no other commentary, and do not wrap the manuscript in a code fence.
