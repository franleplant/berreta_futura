use anyhow::Result;
use clap::{Parser, Subcommand};
use mag::{
    art, capture, plan_cmd, print_cmd, produce, publish, render, site, sourcecodes, translate,
};
use std::path::Path;

#[derive(Parser)]
#[command(name = "mag", about = "sources in, edition content out")]
struct Cli {
    #[command(subcommand)]
    cmd: Cmd,
}

#[derive(Subcommand)]
enum Cmd {
    /// Write plan.yaml from the edition's queued library sources (no model call; human edits it).
    /// Re-running appends rows for queued sources the plan does not reference yet; existing rows stay untouched.
    Plan(plan_cmd::PlanArgs),
    /// Capture a source: fetch the page, transcribe it verbatim through one
    /// fidelity-gated model call, download media, queue it, update sources.md,
    /// and record it in the edition's plan.yaml (own row, or --article to join one)
    Capture(capture::CaptureArgs),
    /// Produce a printable, self-contained HTML version of a blog post: keep
    /// the page's own style, content, and images; strip site chrome, scripts,
    /// players, and other unprintable parts (no model call)
    Print(print_cmd::PrintArgs),
    /// Produce an edition from a plan.yaml
    Produce(produce::ProduceArgs),
    /// Translate a run's accepted pieces to Spanish
    Translate(translate::TranslateArgs),
    /// Generate art candidate rounds for an edition (human selects)
    Art(art::ArtArgs),
    /// Generate cast model-sheet candidates for an art direction (no brief-writer call;
    /// human approves by pointing the cast's `reference:` at the chosen variant)
    CastSheet(art::CastSheetArgs),
    /// Judge an edition's generated candidates against the cast canon (advisory:
    /// writes cast-check.yaml into the round, badges off-model images in the showcase)
    CastCheck(art::CastCheckArgs),
    /// Write editions/<edition>/source-codes: one QR SVG per source for the web
    /// edition and codes.json with the print fit (run after picking opener art, before render)
    SourceCodes(sourcecodes::SourceCodesArgs),
    /// Render an edition through Typst
    Render(render::RenderArgs),
    /// Build the public static website from the editions listed in magazine.toml [site]
    Site(site::SiteArgs),
    /// Package one language of an edition as an EPUB 3 for Apple Books and other e-readers
    Epub(site::epub::EpubArgs),
    /// Upload an approved edition PDF to Google Drive and record its link in editions/<edition>/publish.yaml
    Publish(publish::PublishArgs),
}

fn main() {
    match run(Cli::parse()) {
        Ok(code) => std::process::exit(code),
        Err(e) => {
            eprintln!("error: {e:#}");
            std::process::exit(1);
        }
    }
}

fn run(cli: Cli) -> Result<i32> {
    if !Path::new("prompts").is_dir() {
        anyhow::bail!(
            "must run from the repo root: no ./prompts directory found in the current directory"
        );
    }
    match cli.cmd {
        Cmd::Plan(args) => plan_cmd::run(&args),
        Cmd::Capture(args) => capture::run(&args),
        Cmd::Print(args) => print_cmd::run(&args),
        Cmd::Produce(args) => produce::run(&args),
        Cmd::Translate(args) => translate::run(&args),
        Cmd::Art(args) => art::run(&args),
        Cmd::CastSheet(args) => art::cast_sheet_run(&args),
        Cmd::CastCheck(args) => art::cast_check_run(&args),
        Cmd::SourceCodes(args) => sourcecodes::run(&args),
        Cmd::Render(args) => render::run(&args),
        Cmd::Site(args) => site::run(&args),
        Cmd::Epub(args) => site::epub::run(&args),
        Cmd::Publish(args) => publish::run(&args),
    }
}
