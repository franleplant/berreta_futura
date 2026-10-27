---
source_ids:
- llms-are-making-formal-software-verification-fea-f6a30134
content_mode: article
label: ARTICLE
---

Most software is riddled with bugs, and AI can now easily find and exploit them. Formal verification could prove code free of bugs, but it has historically required years of expert effort. Working with Theorem, we used Claude to prove that 239 fuzz-test entry points across 123 open-source libraries never crash on any input under 64 MB, at the level of compiled RISC-V code. To our knowledge, this is the first large-scale effort to use AI to formally verify production software at the assembly level. Along the way, Claude found bugs that had eluded detection for years despite trillions of test runs. The proofs hold only under stated assumptions, and "formally verified" does not mean "bug-free." As model capabilities continue to improve, we expect formal verification to become an essential part of secure software development.

## Why proofs, and why now

Even heavily tested code has bugs. The Linux kernel, one of the most well-tested pieces of software today, recently had over 1,000 vulnerabilities disclosed. Formal verification translates code into a mathematical model and proves it always follows a defined set of rules. A failed proof points to a possible bug; remove the cause, try again, and you end with a proof.

The cost has kept it niche. seL4 took two person-years to build and 20 to verify. Frontier models can now produce correctness proofs for real-world software fully autonomously.

## Turning tests into proofs

The hard part is the spec. What would it mean for a text editor to be "correct"? We sidestepped this by converting existing fuzz tests into specs. A fuzzer throws semirandom inputs at an entry point, hoping one causes a crash, with no guarantee of exercising every path. Our spec says the test won't crash for *any* input under 64 MB. If Claude proves it, fuzzing that entry point on RISC-V will never find a bug.

We did this on Google's OSS-Fuzz, which instruments C and C++ programs with AddressSanitizer (ASan) so that improper memory access crashes. Over a few weeks, Claude patched the bugs it found and proved there are no crashes for 239 entry points across 123 libraries. The proofs total about 180 million lines of Rocq. A typical proof runs about 600,000 lines, covering a binary with a median of 18,000 RISC-V instructions. The proofs assume a single-threaded static binary with a fixed memory budget on a RISC-V CPU running Linux.

Virtually none of this needs manual review. The Rocq proof checker ensures the proof satisfies the spec. A developer needs to trust only:

- the formal models of RISC-V and of Linux processes;
- the exact theorem statements;
- the Rocq proof checker itself.

**This doesn't mean these libraries contain no bugs.** Remaining bugs either lie in those components or fall outside the proof's scope. Hardening the trusted components is not insignificant, but it is far more tractable than debugging every line the proofs cover, and the approach can secure any number of projects without enlarging them. We're publishing the trusted components not already public, the complete proofs for fuzz tests that needed no patching, and the specs we couldn't prove.

## Bugs found along the way

Attempting the proofs found hundreds of bugs. Claude patched each one, the spec was regenerated, and Claude proved the new spec. Patching opens the door to reward hacking: Claude could rewrite a program into one that trivially never crashes. To discourage this, we penalized any patch, offered extra credit for proving how few inputs it changed, and audited the patches.

Many of these bugs are ones a fuzzer, typically capped at 1 MB inputs, would be unlikely to ever find:

- an out-of-bounds write in a decompressor, triggered only by inputs of around 20 MB with one rare layout;
- an out-of-bounds read in an image decoder that needed a 64 MB input and over 2 GB of memory;
- a rediscovery of CVE-2026-56132 in libexpat, which needed deeply nested input.

Claude also found logic bugs that never crash, such as a file-loading restriction that isn't always enforced.

Proving "no crash" can prove more than memory safety. An LZO fuzz test crashes if decompressing a compressed input doesn't return the original, so proving it never crashes proves the roundtrip. For cpp-httplib, Claude had to prove, on machine code, that libc++'s red-black tree keeps its depth logarithmically bounded.

## Other experiments

Claude wrote a formal spec of RFC 1950, the zlib format, and proved that the Linux kernel's zlib implements it, working on the x86 binary with x86 semantics Claude generated and heavily tested. We repeated this for half a dozen other widely used libraries and found some minor, unexploitable corner-case bugs. We conclude that these codebases are already almost fully correct, and that end-to-end correctness proofs about real existing code are possible.

Claude also wrote a Rust interpreter for a large subset of Python and proved with Verus that it follows CPython semantics from an academic paper. Across 1.7 million random programs, it matched CPython in 99.95% of tests; the rest were known corner cases. Elsewhere, we found a logic bug latent for more than a decade, and in one week on a PDF reader, as many security bugs as are typically reported in a year.

## Cost

Proofs can take hundreds of millions of tokens. There are compelling reasons to expect this to improve. On 36 small tasks built from real OSS-Fuzz code, Opus 5.5 proves half of them with about 40% fewer tokens than Opus 5, and we expect the trend to continue as models are trained on long verification tasks.

Proofs are also reusable. Agents sharing a workspace needed 17% fewer tokens than agents working alone, and some succeeded after failing solo. At scale, most of a proof covers code every program contains, such as C runtime and ASan initialization, so teams copied finished proofs and adapted them. Dependencies follow a power law: proving a small set of shared libraries makes a huge swath of software feasible to prove.

## Limitations

**"Formally verified" does not mean "bug-free."** A proof checker can't tell you whether your spec matches reality. Our proofs cover single-threaded static RISC-V binaries linked against musl libc; most people run these libraries on x86 or ARM against glibc. ASan doesn't detect all memory-safety bugs, we didn't verify every entry point, and callers can still misuse a library. This also means we know where to look for remaining bugs. We expect these limitations to become tractable as we learn more and as models continue to improve.

## Conclusion

Formal verification, once practical only for the most safety-critical code, will soon be as practical as fuzzing is today for almost all production software. As LLMs find more and more vulnerabilities, we must use processes that can guarantee security properties. We encourage all developers to try formal verification with LLMs, especially those who tried it with less capable models and found it didn't work.
