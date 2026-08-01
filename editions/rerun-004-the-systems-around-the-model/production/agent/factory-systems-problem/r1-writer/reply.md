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

<!-- SCRATCH: not part of the manuscript -->

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
