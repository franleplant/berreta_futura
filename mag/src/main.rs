// mag — sources in, edition content out:
// no database, no run state, fail loud, plain output files.

mod art;
mod caller;
mod capture;
mod plan_cmd;
mod produce;
mod render;
mod translate;

use anyhow::Result;
use clap::{Parser, Subcommand};
use std::collections::HashSet;
use std::path::{Path, PathBuf};

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
    Plan {
        edition: String,
    },
    /// Capture a source: fetch the page, transcribe it verbatim through one
    /// fidelity-gated model call, download media, queue it, update sources.md,
    /// and record it in the edition's plan.yaml (own row, or --article to join one)
    Capture {
        url: String,
        /// Collecting edition to queue into (default: the intake edition;
        /// created, and made the intake edition, if it does not exist)
        #[arg(long)]
        edition: Option<String>,
        /// Comma-separated tags for record.yaml
        #[arg(long)]
        tags: Option<String>,
        /// Override the extracted title
        #[arg(long)]
        title: Option<String>,
        /// Override the extracted author
        #[arg(long)]
        author: Option<String>,
        /// Override the extracted publish date (YYYY-MM-DD)
        #[arg(long)]
        published: Option<String>,
        /// Saved HTML to capture from instead of fetching the URL (for pages
        /// curl cannot reach: login walls, JS-rendered apps). The URL is
        /// still recorded and still derives the source id.
        #[arg(long)]
        html: Option<PathBuf>,
        /// Join this existing article row in the edition's plan.yaml instead
        /// of getting a row of its own
        #[arg(long)]
        article: Option<String>,
        /// Content mode for the new plan row: article or in_a_nutshell
        #[arg(long, default_value = "article")]
        mode: String,
        #[arg(long, default_value = "sonnet")]
        model: String,
    },
    /// Produce an edition from a plan.yaml
    Produce {
        plan: PathBuf,
        /// Existing run dir; pieces with final.md are skipped
        #[arg(long)]
        resume: Option<PathBuf>,
        /// Comma-separated article ids
        #[arg(long)]
        only: Option<String>,
        #[arg(long = "writer-model", default_value = "opus")]
        writer_model: String,
        /// Cheap model that derives frontmatter (editorial title) from finished manuscripts
        #[arg(long = "frontmatter-model", default_value = "haiku")]
        frontmatter_model: String,
    },
    /// Translate a run's accepted pieces to Spanish
    Translate {
        run_dir: PathBuf,
        #[arg(long, default_value = "codex:gpt-5.6-luna")]
        model: String,
    },
    /// Generate art candidate rounds for an edition (human selects)
    Art {
        edition: String,
        /// Shell command template for one image; {prompt}, {out}, and {ref} are substituted
        #[arg(long = "gen-cmd", default_value = art::DEFAULT_GEN_CMD)]
        gen_cmd: String,
        /// How many candidates per art brief
        #[arg(long, default_value_t = 4)]
        candidates: u32,
        #[arg(long, default_value = "opus")]
        model: String,
        /// Propose briefs and write generate.sh, but spend no image credits
        #[arg(long = "dry-run")]
        dry_run: bool,
        /// Only rebuild art/showcase.html from the rounds on disk (no model call, no generation)
        #[arg(long)]
        showcase: bool,
        /// Scope this round to some purposes (comma-separated: cover,opener,tail,closing);
        /// earlier briefs for them are treated as rejected and fed back as what not to repeat
        #[arg(long)]
        only: Option<String>,
        /// Editor's note appended to the brief prompt (why the last round was rejected, direction for this one)
        #[arg(long)]
        note: Option<String>,
        /// Complete an interrupted round dir: reuse its briefs.yaml, keep candidates
        /// already on disk, generate only the missing ones, then finish the round
        #[arg(long = "resume-round")]
        resume_round: Option<String>,
    },
    /// Generate cast model-sheet candidates for an art direction (no brief-writer call;
    /// human approves by pointing the cast's `reference:` at the chosen variant)
    CastSheet {
        /// The art direction file whose direction.cast to sheet
        direction: PathBuf,
        /// Shell command template for one image; {prompt}, {out}, and {ref} are substituted
        #[arg(long = "gen-cmd", required_unless_present_any = ["dry_run", "showcase"])]
        gen_cmd: Option<String>,
        /// How many sheet candidates to render
        #[arg(long, default_value_t = 4)]
        candidates: u32,
        /// Write the prompt and generate.sh, but spend no image credits
        #[arg(long = "dry-run")]
        dry_run: bool,
        /// Only rebuild the direction's cast showcase.html from the rounds on disk
        #[arg(long)]
        showcase: bool,
        /// Editor's note appended to the sheet prompt
        #[arg(long)]
        note: Option<String>,
    },
    /// Judge an edition's generated candidates against the cast canon (advisory:
    /// writes cast-check.yaml into the round, badges off-model images in the showcase)
    CastCheck {
        edition: String,
        /// Round stamp to check, or 'all' (default: the newest round)
        #[arg(long)]
        round: Option<String>,
        /// Art direction file to take the cast from (default: the edition's art_direction_path)
        #[arg(long)]
        direction: Option<PathBuf>,
        /// Vision-capable judge model
        #[arg(long, default_value = "sonnet")]
        model: String,
    },
    /// Render an edition via the Python renderer seam (mag-render-adapter)
    Render {
        edition: String,
        /// measure_article, measure_edition, or render_edition
        #[arg(long, default_value = "render_edition")]
        operation: String,
        /// Article id, required for measure_article
        #[arg(long)]
        article: Option<String>,
        /// Comma-separated languages to render (default: en + es if translations exist)
        #[arg(long)]
        langs: Option<String>,
        /// Run dir whose finals to render (default: newest complete run, else committed files)
        #[arg(long)]
        run: Option<String>,
        /// Cheap model that re-anchors figures to this run's headings
        #[arg(long = "anchor-model", default_value = "haiku")]
        anchor_model: String,
    },
}

fn main() {
    let cli = Cli::parse();
    match run(cli) {
        Ok(code) => std::process::exit(code),
        Err(e) => {
            eprintln!("error: {e:#}");
            std::process::exit(1);
        }
    }
}

fn run(cli: Cli) -> Result<i32> {
    if !Path::new("prompts").is_dir() {
        anyhow::bail!("must run from the repo root: no ./prompts directory found in the current directory");
    }

    match cli.cmd {
        Cmd::Plan { edition } => plan_cmd::propose_plan(&edition),
        Cmd::Capture { url, edition, tags, title, author, published, html, article, mode, model } => {
            let spec = caller::ModelSpec::parse(&model)?;
            capture::run(
                &url,
                edition.as_deref(),
                tags.as_deref(),
                title.as_deref(),
                author.as_deref(),
                published.as_deref(),
                html.as_deref(),
                article.as_deref(),
                &mode,
                &spec,
            )
        }
        Cmd::Produce { plan, resume, only, writer_model, frontmatter_model } => {
            let writer = caller::ModelSpec::parse(&writer_model)?;
            let frontmatter = caller::ModelSpec::parse(&frontmatter_model)?;
            let only_set: Option<HashSet<String>> =
                only.map(|s| s.split(',').map(|x| x.trim().to_string()).collect());
            produce::run_edition(&plan, resume, only_set, &writer, &frontmatter)
        }
        Cmd::Translate { run_dir, model } => {
            let spec = caller::ModelSpec::parse(&model)?;
            translate::run(&run_dir, &spec)
        }
        Cmd::Art { edition, gen_cmd, candidates, model, dry_run, showcase, only, note, resume_round } => {
            let spec = caller::ModelSpec::parse(&model)?;
            art::run(
                &edition,
                Some(gen_cmd.as_str()),
                candidates,
                &spec,
                dry_run,
                showcase,
                only.as_deref(),
                note.as_deref(),
                resume_round.as_deref(),
            )
        }
        Cmd::CastSheet { direction, gen_cmd, candidates, dry_run, showcase, note } => {
            art::cast_sheet_run(&direction, gen_cmd.as_deref(), candidates, dry_run, showcase, note.as_deref())
        }
        Cmd::CastCheck { edition, round, direction, model } => {
            let spec = caller::ModelSpec::parse(&model)?;
            art::cast_check_run(&edition, round.as_deref(), direction.as_deref(), &spec)
        }
        Cmd::Render { edition, operation, article, langs, run, anchor_model } => {
            let anchor = caller::ModelSpec::parse(&anchor_model)?;
            render::run(&edition, &operation, article.as_deref(), langs.as_deref(), run.as_deref(), &anchor)
        }
    }
}
