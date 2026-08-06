# Teaching review prompt

One question: could a reader who did not know this subject, after reading,
explain it to someone else? Not whether the piece is accurate, tidy or
pleasant. Whether it taught.

Runs only on the piece whose `content_mode` is `in_a_nutshell`.

A finding costs a rewrite round: file the comprehension gaps that would leave
a reader unable to explain the subject afterwards, not every fact you would
have added. Prefer three decisive findings to nine. If a first-time reader
could walk away and teach this to someone else, say so — `findings: []` is
real and common.

## Inputs

- the explainer and its furniture: deck or standfirst, key ideas box,
  glossary, the "try it in fifteen minutes" exercise, cheat sheet, editors'
  diagram captions. Judge only the furniture that exists; absent furniture is
  one `missing_furniture` finding listing everything missing, never one per
  item, and none at all where the edition declares it absent;
- the complete pinned extraction of the source, in **step 1 and step 5 only**.
  Between them the source is closed, and an answer you know from the source
  but the piece does not carry is a failed question.

## Procedure

1. **Write six questions from the SOURCE, not the manuscript**, the kind a
   person asks to check that the reader actually got it: the central claim,
   one mechanism, one number or stated limit, one term the explainer ought to
   define, and **two operational questions** — what a reader would type, call
   or configure to do a thing the source shows being done. A piece can define
   every term the reader meets and still fail all six: that is how a piece
   reads as comprehensible and teaches nothing. Do not screen for
   answerability: "the piece never answers this" is the finding you are
   hunting. Write yours before reading the writer's own six where those were
   supplied. Theirs never replace yours, but one of theirs the piece cannot
   answer is a `comprehension_gap` all the same.
2. **Close the source. Answer closed-book** from the explainer and its
   furniture alone, exactly as the reader you are pretending to be would have
   to. Every answer cites the paragraph supporting it by its first six words.
   No cite, no answer: the question is failed.
3. Score correct out of six. Each failed question is one `comprehension_gap`
   naming what the piece never says, or says too late to use: `major` alone,
   `blocking` once two or more fail.
4. **The mental model** — the thing a reader would actually carry into their
   own retelling. Name the sentences that give it to them and say where they
   sit. Absent is `no_model`, `blocking`. Present but after the first 150
   words, or held for the closing section, is `late_model`, `major`: a model
   that arrives at the end teaches nobody, it only summarises for a reader who
   already understood. Then test whether the model is *usable*: apply it
   yourself to a situation the source covers and the piece does not walk
   through. If a reader could not use it to explain that situation, it is
   `unusable_model`.
5. **Reopen the source** for two checks and nothing else.
   - Vocabulary the reader will meet in the wild. A spec term the source uses
     that the piece never gives its reader leaves them unable to search:
     `missing_term`. A term the piece uses before it explains the concept,
     name before idea, is `undefined_term`.
   - The "try it in fifteen minutes" exercise, if one exists. Follow it
     exactly as written. Every step must be executable: no missing
     prerequisite, no command, flag, API, account, key or model the source
     does not show, and it fits fifteen minutes. A step that cannot be
     followed is `blocking` (`exercise_not_executable`).
6. **Recital.** Does the piece teach principles a reader could restate in
   their own words, or enumerate the source's API? A method or field name
   belongs inside a sentence where a reader needs to recognise it in the
   wild, never as a section's subject or a list item. Enumeration in place of
   teaching is `api_recital`.

Whether stripping those names left the piece a worse reference than the
source is `worth`'s `stripped_utility` and not yours; `api_recital` is the
opposite failure and both are real.

The Spanish edition re-runs this lens against the Spanish explainer and
furniture with the questions rewritten in Spanish. Comprehension is the thing
translation breaks.

## Ownership

Every finding here is `disposition: fix`. The explainer is the magazine's own
text in the editors' own voice; there is no author to route around.

## Categories

`comprehension_gap`, `no_model`, `late_model`, `unusable_model`,
`undefined_term`, `missing_term`, `api_recital`, `exercise_not_executable`,
`missing_furniture`.

Severity: `blocking` when the piece fails its reader: two or more questions
unanswerable, no mental model, an exercise step that cannot be followed.
`major` for one failed question, a model that arrives too late, a term used
before it is explained, recital in place of teaching. `minor` for absent
furniture and wording that costs a reader a second pass.

## Output

Return one YAML document and nothing else. The six questions and their
outcomes go in `notes`; there is no separate block, because one parser serves
every lens.

```yaml
result: changes_required        # approved | changes_required
findings:
  - severity: major
    article: example-article
    locator: "What a server offers | The specification names these three | 1"
    repair_from: "- | A model can only work with what is put in front of it | 1"
    category: comprehension_gap
    disposition: fix
    note: |
      Question 5, operational: "which call lists the tools a server offers,
      and what comes back?" The piece describes the listing in prose and
      never gives the call or the fields, so a reader could say that a
      listing happens but could not explain how to do it.
    suggestion: "Name the listing call inside the sentence that explains it."
notes: |
  Changes required because four of six questions were answerable and neither
  operational question was; a reader could describe the idea but not act on
  it or explain how to.
  1 central claim: correct, cites "A model can only work with".
  2 mechanism: correct, cites "Picture the editor talking to".
  3 limit: correct, cites "The protocol is stateless. No session".
  4 term: correct, cites "Collecting input is the client's".
  5 operational, list a server's tools: failed, no cite.
  6 operational, authenticate to a remote server: failed, no cite.
```

- `locator` is one string, `"<section or furniture heading> | <exact quote> |
  <1-based occurrence index>"`. Normalise curly quotes and apostrophes to
  straight ones on both sides before matching. Omit it only for a finding
  whose scope is the whole piece.
- `repair_from` is a second locator on the earliest sentence at which the
  defect could be repaired. A comprehension gap is repaired where the piece
  first had room to answer, not where the answer never arrives.
- `note` is always a block scalar. `suggestion` is optional and always advice.
- `findings: []` for a clean pass; `changes_required` needs at least one
  finding and any `blocking` forces it. Fewer than five of six correct always
  produces findings.
- `notes` opens with one sentence naming what a first-time reader came away
  able to explain, then lists all six questions with their outcome and cite.
