# Reader persona review prompt

Three readers test whether the edition's teaching material works. Run all three
passes in order, keeping them separate (what a later persona learns never
travels back), and report one verdict.
You judge the EDITOR-AUTHORED FURNITURE and the explainer (the article whose
`content_mode` is `in_a_nutshell`), not the article bodies, whose truth the
fact-checker already owns. Furniture means the standfirst or deck, the key ideas
box (90 words or fewer), the glossary, the "try it in fifteen minutes" exercise,
the cheat sheet, and the editors' diagram captions. Judge only the furniture
that exists. Absent furniture is ONE `missing_furniture` finding per article
listing everything missing, never one per item, and none at all where the
edition declares it absent.

## Nadia, first encounter

Reads the explainer and its furniture. No other article, no prior knowledge of
the subject. She sees the pinned source extraction in step 1 only, and must not
reopen it afterwards.

1. From the SOURCE EXTRACTION, not the manuscript, write six comprehension
   questions a reader of this explainer should be able to answer: the central
   claim, two mechanisms, one number or stated limit, one term the explainer
   ought to define, and one that tests whether the mental model is USABLE
   ("given <a situation the source covers>, which part handles it?"), not
   merely present. Do not screen for answerability: "the piece never answers
   this" is the finding you are hunting. Write yours before reading the writer's
   own six where those were supplied; theirs never replace yours, but one of
   theirs the piece cannot answer is a `comprehension_gap` all the same.
2. Answer them closed-book from the explainer and its furniture alone. Every
   answer cites the paragraph supporting it by its first six words. No cite,
   no answer: the question is failed, `answer: null`, `correct: false`. An
   answer you know from the source but the piece does not carry is failed too.
3. Score correct out of six. Each failed question is one `comprehension_gap`
   finding naming what the piece never says, or says too late to use:
   `major` alone, `blocking` once two or more fail.

Nadia alone is re-run on the Spanish edition, against the Spanish explainer and
furniture with the questions rewritten in Spanish: comprehension is the thing
translation breaks.

## Marcus, the eight-minute manager

Marcus is TWO separate runs, not two steps of one. Run A is written down before
run B starts and is never revised afterwards; the harness enforces the boundary
by giving run A less context.

Run A. Input: the FURNITURE ONLY (standfirst, key ideas, captions, glossary,
cheat sheet). The body is withheld. Emit the `manager_takeaways` block and
nothing else: the one decision he would make and the three claims he would
repeat to his team, each a sentence he would say aloud.

Run B. Input: that block verbatim, plus the body. Adjudicate all four items
`supported`, `unsupported`, or `contradicted`, quoting the body passage that
settles each. Unsupported is `major`, contradicted `blocking`, category
`unsupported_inference`, quoting the furniture that produced it.

## Priya, skeptical staff engineer

Reads the furniture against the pinned source extraction. She is the only
persona who sees the source throughout.

1. Hunt simplifications that crossed into falsehood, and caveats the source
   states that the furniture drops. Check the cheat sheet and glossary line by
   line against the source.
2. Follow the "try it in fifteen minutes" exercise exactly as written and
   confirm every step is executable: no missing prerequisite, no command, flag,
   or API the source does not show, no unstated account, key, or model, and it
   fits fifteen minutes. A step that cannot be followed is `blocking`.

## Categories

`comprehension_gap`, `missing_furniture`, `unsupported_inference`,
`oversimplification`, `dropped_caveat`, `glossary_error`, `cheat_sheet_error`,
`exercise_not_executable`.

Severity: `blocking` when the teaching material fails its reader: two or more
comprehension questions unanswerable, furniture the body contradicts, a
simplification that is now false, an exercise step that cannot be followed.
`major` for one failed question, an unsupported manager inference, a dropped
caveat, a glossary or cheat-sheet error. `minor` for absent furniture and
wording that costs a reader a second pass. Any `blocking` finding forces
`result: changes_required`.

## Output

Return one YAML document and nothing else. The operator records it with
`mag review record <edition-id> --kind learning`.

```yaml
result: changes_required        # approved | changes_required
findings:
  - severity: blocking
    article: mcp-in-a-nutshell  # article id, or `edition` for edition-wide furniture
    locator: "Key ideas | Servers are stateless by default | 1"
    repair_from: "Key ideas | Each server exposes a bounded set | 1"
    category: unsupported_inference
    persona: marcus
    note: |
      Run A claim 2 was "we can skip session handling". The body says the
      opposite for Streamable HTTP.
manager_takeaways:
  - article: mcp-in-a-nutshell
    decision: Pilot one MCP server behind the existing gateway this quarter.
    claims:                     # exactly three, written in run A
      - Each server exposes a bounded set of actions.
      - Servers are stateless, so we can skip session handling.
      - One host can use several servers without merging them.
    adjudication:               # run B: four verdicts, decision then claims 1-3
      - item: decision
        verdict: supported
        cite: "The host owns intelligence and orchestration"
      - item: claim-2
        verdict: contradicted
        cite: "Remote servers use Streamable HTTP"
comprehension:
  - persona: nadia
    language: en                # en | es
    correct: 5
    of: 6
    questions:
      - question: What boundary does the protocol define?
        answer: Between the AI application and external programs.
        cite: "The Model Context Protocol defines how"
        correct: true
scores:
  comprehension: 4
  standalone_sufficiency: 3
  technical_honesty: 4
notes: One paragraph on what each of the three readers came away with.
```

- `locator` is one string, `"<section or furniture heading> | <exact quote> |
  <1-based occurrence index>"`. Normalize curly quotes and apostrophes (U+2018,
  U+2019, U+201C, U+201D) to straight ones on both sides before matching. Omit
  it only for a finding whose scope is the whole edition.
- Where the defect is STRUCTURAL, meaning its cause sits earlier than the
  sentence it shows in, add `repair_from`: a second locator on the earliest
  sentence at which it could be repaired. A comprehension gap is repaired where
  the piece first had room to answer, not where the answer never arrives.
- `note` is always a YAML block scalar (`note: |`), since it quotes sentences.
- Use `findings: []` when nothing is wrong; `changes_required` needs at least
  one finding. `persona` is required on every finding.
- `manager_takeaways` holds one entry per article Marcus read, `adjudication`
  resolving all four items; `comprehension` one entry per Nadia run, all six
  questions each. Both gate through findings, never through a score.
- Scores are integers 1-5 and ADVISORY. They never gate a release, and no
  finding is ever softened or dropped to protect one.
