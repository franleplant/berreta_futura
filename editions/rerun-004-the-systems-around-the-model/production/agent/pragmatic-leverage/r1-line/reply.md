result: changes_required
findings:
  - severity: major
    article: pragmatic-leverage
    locator: "- | This one is a bit of an addendum / side-quest to the recent series. | 1"
    repair_from: "Seeking leverage | Even before AI, only 25–50% of the time to ship a feature was writing the code itself. | 1"
    category: opening
    note: |
      The first thing a magazine reader meets is publishing logistics for a blog
      they are not reading, and all three of its referents are missing from the
      page. "This one is a bit of an addendum / side-quest to the recent series.
      It didn't fit cleanly into the main post so I'm publishing it standalone.
      It is referenced briefly in *Why Software Factories Fail part 2: Turning
      the lights back on*." There is no recent series in this edition, no main
      post, and no part 1. The paragraph also de-sells the piece before it
      starts: it says the material did not fit anywhere else. What follows is
      strong and self-contained, and "Even before AI, only 25-50% of the time to
      ship a feature was writing the code itself" is a real opening line that
      needs no runway. Retention and placement are the edition's call, not the
      author's wording, so this is repairable as a cut plus a labeled editor
      standfirst.
    suggestion: "**Editor's note.** Published standalone as an addendum to the author's Why Software Factories Fail series, and referenced in part 2, Turning the lights back on."
  - severity: major
    article: pragmatic-leverage
    locator: "The 80/20 rule in AI coding leverage | **note** For this example I'm gonna blur | 1"
    category: house_style
    note: |
      Two problems at one site. First, "**note**" is unlabeled editorial
      apparatus: a bold lowercase marker that a reader cannot attribute. If it
      is the author's aside it should read as one in his voice; if it is an
      editor addition, house style requires it visibly labeled. As it stands the
      reader guesses. Second, the sentence it introduces is broken in half by a
      display quote: "For this example I'm gonna blur" / blockquote / "into a
      single percentage number but obviously they're two separate variables."
      On a rendered A5 page the reader hits a pulled-out block mid-clause and
      has to reassemble the sentence across it. The block quote is also doing
      two different jobs in six lines, once as an interrupted definition and
      once as the "expected pain" formula, so the formula loses the emphasis it
      has earned. Formatting is editor-owned, and the repair below preserves the
      author's wording exactly.
    suggestion: "For this example I'm gonna blur \"chance you'll have to change something\" weighted by \"how painful the change will be\" into a single percentage number, but obviously they're two separate variables."
  - severity: minor
    article: pragmatic-leverage
    locator: "Seeking leverage | If you're only using AI to write the code, then you're taking the 2–4 hours of coding time down to 10–20 minutes | 1"
    category: repeated_cadence
    note: |
      The piece runs on one sentence shape, "If you X, (then) Y", six times in
      495 words. "If you're only using AI to write the code, then you're taking
      the 2-4 hours of coding time down to 10-20 minutes". "But if you use AI to
      help you plan and align, then you actually get closer to 2-3x faster." "If
      the model is 50% likely to get a button style wrong, but the fix is one
      cheap prompt, then our combined "expected pain" is low." "If you draw this
      out, there's an inverse relationship between effort invested up front and
      expected pain." "if you've done some work at the "Product" level and have
      not answered all the open questions yet, it's possible you may need to end
      it where you are". "If you're doing multiple phases of planning, zooming
      in from 50kft view all the way to the 10kft view, you want to do a little
      bit of steering at each phase". Every step of the argument is a
      conditional addressed to "you", so the escalation from yolo prompt to
      hand-written spec to writing every line lands with the same weight each
      time. Capped at minor: the repair requires rewording the author's own
      sentences.
  - severity: minor
    article: pragmatic-leverage
    locator: "The 80/20 rule in AI coding leverage | Good luck. | 1"
    repair_from: "The 80/20 rule in AI coding leverage | This is what we mean by leverage, and it requires being pragmatic. | 1"
    category: ending
    note: |
      The piece stops on a blog sign-off. The paragraph before it does the
      closing work ("This is what we mean by leverage, and it requires being
      pragmatic... you want to do a little bit of steering at each phase to
      ensure you are eliminating as much expected pain as possible"), and then
      "Good luck." adds a beat that belongs to a comment thread rather than to a
      printed page, where it reads as the author walking away from the argument
      he has just made. Capped at minor and no replacement offered: the line is
      the author's.
  - severity: minor
    article: pragmatic-leverage
    locator: "The 80/20 rule in AI coding leverage | if you yolo a two-sentence prompt into your factory | 1"
    category: jargon
    note: |
      "your factory" is the load-bearing noun of the whole example and is never
      defined here. It is series vocabulary arriving without the series, and the
      opening paragraph is the only place the word "factory" is otherwise
      visible, inside a post title. The same holds for the planning vocabulary
      later: "some work at the "Product" level", "zoom down a level to the
      technical details", "zooming in from 50kft view all the way to the 10kft
      view". A reader who has not read the series can follow the probability
      argument but cannot picture the thing being planned. The repair is an
      editor gloss on first use rather than a change to the author's sentences.
  - severity: minor
    article: pragmatic-leverage
    locator: "The 80/20 rule in AI coding leverage | your chance of getting a fully-mergeable result is ~50%, the chance you have to rework it is 50% | 1"
    category: dead_words
    note: |
      The second clause is the arithmetic complement of the first and adds
      nothing: if the chance of a mergeable result is 50%, the chance of rework
      is 50% by definition. The two are also joined by a comma splice, which
      makes the restatement look like a second, separate figure and stalls the
      reader on the sentence that sets up the entire model.
  - severity: minor
    article: pragmatic-leverage
    locator: "The 80/20 rule in AI coding leverage | This is what we mean by leverage | 1"
    category: orphan_referent
    note: |
      The byline is one author and the piece opens in the first person singular:
      "so I'm publishing it standalone", "For this example I'm gonna blur". Then
      a "we" appears twice with no antecedent, "our combined "expected pain" is
      low" and "This is what we mean by leverage". Nothing in the piece
      introduces a company or a team, so the reader cannot tell whether the
      pronoun widened to include them or to include colleagues they have not met.
scores:
  structure: 3
  flow: 3
  sentence_craft: 3
  house_style: 2
  voice_consistency: 3
notes: |
  The core of this is genuinely good and takes about two minutes to read: the
  cost breakdown, the three-point escalation from yolo prompt to hand-written
  spec to writing every line, the expected-pain formula, and the warning against
  spending six hours to remove pain you could have removed in ten. Those steps
  are restatable in order from one read, and the formula earns its display. What
  surrounds them is blog furniture that has not been converted for a printed
  page. It opens on which post this did not fit into, it closes on "Good luck.",
  it asks the reader to "draw this out" and to picture "the far end" of an axis
  the page never shows, and it leans on vocabulary the series carried but this
  extract does not: your factory, the "Product" level, 50kft. The bold "note"
  marker and the sentence severed by a block quote are the most visible
  production defects and the cheapest to fix. Underneath, six "If you X, then Y"
  sentences give the argument one dynamic where it wants three. Against a
  seven-page budget this runs 495 words, so there is room for a labeled editor
  standfirst to supply the missing context without crowding anything out.
