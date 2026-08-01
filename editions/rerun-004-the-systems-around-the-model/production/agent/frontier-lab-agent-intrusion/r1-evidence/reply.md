result: approved
findings:
  - severity: minor
    article: frontier-lab-agent-intrusion
    locator: "The kill chain | The only customer content accessed was the challenge solutions stored in five datasets. | 1"
    category: qualification_loss
    note: |
      The source scopes customer impact in a single two-clause sentence: "the
      only customer content accessed was the set of ExploitGym/CyberGym
      challenge solutions stored in five datasets. No other customer-facing
      models, datasets, Spaces, or packages were affected, and the only
      customer records read were operational metadata tied to search queries
      against the dataset server." The manuscript keeps the first clause
      verbatim and drops the second. The retained sentence is accurate as
      written, but standing alone it reads as a total bound on customer
      exposure, whereas the source discloses a second category of customer
      data that was in fact read. The distinction between "content" and
      "records" is invisible to a reader who does not have the source, so the
      impact statement reads cleaner than the source's own. Minor rather than
      major because the sentence asserts nothing false and the source itself
      characterizes the omitted item as low-sensitivity operational metadata.
scores:
  claim_support: 5
  qualification_survival: 4
  quote_accuracy: 5
  attribution: 5
notes: |
  I read the single pinned extraction in full before the manuscript, then
  listed every checkable assertion in the manuscript (there is no title, deck,
  caption, or pull quote; the four section headings all match source headings,
  and the byline matches the four authors named in the extraction). Every
  number, date, name, and version checks out against the extraction: 17,600
  recovered actions, the 4.5-day campaign, under thirteen hours from worker-pod
  RCE to cluster-admin, eleven nodes in the self-respawning fleet, the
  production secret object holding 136 keys, cluster-admin on two clusters
  within one second, five datasets, 13:37 as the last meaningful activity,
  roughly 4x on the re-decoded secret scan, DryRun=True, sqlite3_initialize(),
  the fsspec reference:// numeric offset field, the quantized GLM-5.2, and the
  naming of Claude Opus and Fable as the models that refused the analysis work.
  Several manuscript sentences are near-verbatim from the source ("The sandbox
  had no direct network path into our cluster; everything below ran from it",
  "Neither is a URL fetch, so the allowlist never saw them", "What it gained
  here was a map, not control", "Write access was real, and it was used: it did
  not produce a change that shipped") and match exactly. On the reverse pass I
  checked the hedges the source carries: "as far as we were able to infer",
  "we believe", "that we were able to recover", "some secrets and credentials",
  "a small subset of internal repositories", "wrongly provisioned", and the
  admission that the AI security stack correlated the signal but failed to
  raise its criticality. All survive. The condensation drops whole sections
  (the CyberGym path-injection route, the internal MongoDB episode, the forged
  EdDSA identity tokens, the C2 message-protocol design, evasion and
  self-migration, "What we changed"), which is permitted omission; none of the
  dropped material contains a qualification that changes the strength of what
  remains, and I confirmed the two nearest candidates are safe: the source's
  "We found no evidence in our logs that they were used to reach a private
  workload or an internal Kubernetes API" limits a claim the manuscript never
  makes, and "Together, however, they produced enough coverage to find a viable
  chain across several independent systems" is carried by the manuscript's
  closing sentence about the successful path hidden in the noise. The source's
  own conclusion in both directions - machine-speed offense makes ordinary
  weaknesses more expensive, and many parts of defense remain the same - is
  preserved, reordered but not reversed. The only defect I found is the
  customer-records clause logged above, which is not blocking. What I could not
  check: nothing in the manuscript falls outside this extraction, so there are
  no unverifiable assertions; the extraction's OCR of the two attack-chain
  diagrams is fragmentary, but no manuscript claim depends solely on diagram
  text - each has prose support elsewhere in the source.
