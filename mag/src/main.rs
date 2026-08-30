
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

    Plan {
        edition: String,
    },

    Capture {
        url: String,

        #[arg(long)]
        edition: Option<String>,

        #[arg(long)]
        tags: Option<String>,

        #[arg(long)]
        title: Option<String>,

        #[arg(long)]
        author: Option<String>,

        #[arg(long)]
        published: Option<String>,

        #[arg(long)]
        html: Option<PathBuf>,

        #[arg(long)]
        article: Option<String>,

        #[arg(long, default_value = "article")]
        mode: String,
        #[arg(long, default_value = "sonnet")]
        model: String,
    },

    Produce {
        plan: PathBuf,

        #[arg(long)]
        resume: Option<PathBuf>,

        #[arg(long)]
        only: Option<String>,
        #[arg(long = "writer-model", default_value = "opus")]
        writer_model: String,

        #[arg(long = "frontmatter-model", default_value = "haiku")]
        frontmatter_model: String,
    },

    Translate {
        run_dir: PathBuf,
        #[arg(long, default_value = "codex:gpt-5.6-luna")]
        model: String,
    },

    Art {
        edition: String,

        #[arg(long = "gen-cmd", default_value = art::DEFAULT_GEN_CMD)]
        gen_cmd: String,

        #[arg(long, default_value_t = 4)]
        candidates: u32,
        #[arg(long, default_value = "opus")]
        model: String,

        #[arg(long = "dry-run")]
        dry_run: bool,

        #[arg(long)]
        showcase: bool,

        #[arg(long)]
        only: Option<String>,

        #[arg(long)]
        note: Option<String>,

        #[arg(long)]
        articles: Option<String>,

        #[arg(long = "resume-round")]
        resume_round: Option<String>,
    },

    CastSheet {

        direction: PathBuf,

        #[arg(long = "gen-cmd", required_unless_present_any = ["dry_run", "showcase"])]
        gen_cmd: Option<String>,

        #[arg(long, default_value_t = 4)]
        candidates: u32,

        #[arg(long = "dry-run")]
        dry_run: bool,

        #[arg(long)]
        showcase: bool,

        #[arg(long)]
        note: Option<String>,
    },

    CastCheck {
        edition: String,

        #[arg(long)]
        round: Option<String>,

        #[arg(long)]
        direction: Option<PathBuf>,

        #[arg(long, default_value = "sonnet")]
        model: String,
    },

    Render {
        edition: String,

        #[arg(long, default_value = "render_edition")]
        operation: String,

        #[arg(long)]
        article: Option<String>,

        #[arg(long)]
        langs: Option<String>,

        #[arg(long)]
        run: Option<String>,

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
        Cmd::Art { edition, gen_cmd, candidates, model, dry_run, showcase, only, note, articles, resume_round } => {
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
                articles.as_deref(),
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
