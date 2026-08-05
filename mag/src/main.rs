// mag — sources in, edition content out. Port of tools/produce.py's shape:
// no database, no run state, fail loud, plain output files.

mod art;
mod caller;
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
    /// Propose a plan.yaml for an edition (one model call; human edits it)
    Plan {
        edition: String,
        #[arg(long, default_value = "codex:gpt-5.6-luna@max")]
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
        #[arg(long = "writer-model", default_value = "codex:gpt-5.6-luna@max")]
        writer_model: String,
        #[arg(long = "judge-model", default_value = "codex:gpt-5.6-luna@max")]
        judge_model: String,
        /// Extra style doc appended to the writing pack (e.g. docs/styles/x.md)
        #[arg(long)]
        style: Option<PathBuf>,
    },
    /// Translate a run's accepted pieces to Spanish
    Translate {
        run_dir: PathBuf,
        #[arg(long, default_value = "codex:gpt-5.6-luna@max")]
        model: String,
    },
    /// Generate art candidate rounds for an edition (human selects)
    Art {
        edition: String,
        /// Shell command template for one image; {prompt} and {out} are substituted
        #[arg(long = "gen-cmd")]
        gen_cmd: String,
        /// How many candidates per art brief
        #[arg(long, default_value_t = 4)]
        candidates: u32,
        #[arg(long, default_value = "opus")]
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
        Cmd::Plan { edition, model } => {
            let spec = caller::ModelSpec::parse(&model)?;
            plan_cmd::propose_plan(&edition, &spec)
        }
        Cmd::Produce { plan, resume, only, writer_model, judge_model, style } => {
            let writer = caller::ModelSpec::parse(&writer_model)?;
            let judge = caller::ModelSpec::parse(&judge_model)?;
            let only_set: Option<HashSet<String>> =
                only.map(|s| s.split(',').map(|x| x.trim().to_string()).collect());
            produce::run_edition(&plan, resume, only_set, &writer, &judge, style)
        }
        Cmd::Translate { run_dir, model } => {
            let spec = caller::ModelSpec::parse(&model)?;
            translate::run(&run_dir, &spec)
        }
        Cmd::Art { edition, gen_cmd, candidates, model } => {
            let spec = caller::ModelSpec::parse(&model)?;
            art::run(&edition, &gen_cmd, candidates, &spec)
        }
        Cmd::Render { edition, operation, article, langs, run } => {
            render::run(&edition, &operation, article.as_deref(), langs.as_deref(), run.as_deref())
        }
    }
}
