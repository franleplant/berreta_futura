use crate::caller::{write_atomic, Caller, ModelSpec};
use crate::modelcard::{self, Card};
use crate::typeset::content::{string_literal, File, Tree};
use crate::typeset::cover::literal;
use crate::typeset::template::{self, BOOK_TEMPLATE_TYP};
use crate::typeset::world::Sources;
use crate::util::read;
use anyhow::{bail, ensure, Context, Result};
use std::path::{Path, PathBuf};

const CARDS_DIR: &str = "cards";
const CARD_SHEET_TYP: &str = include_str!("../assets/typeset/card-sheet.typ");
const ART_SIZE: &str = "1536x1024";

#[derive(clap::Args)]
pub struct CardsArgs {
    #[command(subcommand)]
    cmd: CardsCmd,
}

#[derive(clap::Subcommand)]
enum CardsCmd {
    #[command(
        about = "Write cards/<slug>/card.json from library sources through the gated card writer (the same call mag produce makes for a model_card row)"
    )]
    Write {
        slug: String,
        #[arg(
            long = "source",
            required = true,
            help = "Library source id; repeat for more sources"
        )]
        sources: Vec<String>,
        #[arg(long, default_value = "opus")]
        model: String,
    },
    #[command(
        about = "Generate card art candidates for cards/<slug> (one per brief) and a preview sheet of each one set in the card; --pick promotes one to cards/<slug>/art.jpg"
    )]
    Art {
        slug: String,
        #[arg(long = "gen-cmd", default_value = crate::art::DEFAULT_GEN_CMD)]
        gen_cmd: String,
        #[arg(long, default_value_t = 1, help = "Candidates per art brief")]
        variants: u32,
        #[arg(long, help = "Candidate to promote, e.g. 2-v1 for brief 2 variant 1")]
        pick: Option<String>,
        #[arg(
            long,
            help = "Rewrite only the art briefs from the card (gated call), leaving every other field alone, then generate"
        )]
        rebrief: bool,
        #[arg(long, default_value = "opus", help = "Model for --rebrief")]
        model: String,
    },
    #[command(
        about = "Lay out cards three to an A4 landscape sheet, each sheet followed by the all-over brand pattern for its back (print duplex, short edge; the back needs no alignment)"
    )]
    Sheet {
        #[arg(
            required = true,
            help = "<slug> or <card.json>, optionally :<art image> to override the art; a card may repeat"
        )]
        entries: Vec<String>,
        #[arg(
            long,
            help = "Output PDF (default: output/cards/<first slug>-sheet.pdf)"
        )]
        out: Option<PathBuf>,
        #[arg(
            long,
            help = "Print each card's art file name under it, to tell candidates apart"
        )]
        labels: bool,
    },
}

pub fn run(args: &CardsArgs) -> Result<i32> {
    match &args.cmd {
        CardsCmd::Write {
            slug,
            sources,
            model,
        } => write(slug, sources, model),
        CardsCmd::Art {
            slug,
            gen_cmd,
            variants,
            pick,
            rebrief,
            model,
        } => match pick {
            Some(name) => promote(slug, name),
            None => {
                if *rebrief {
                    rewrite_briefs(slug, model)?;
                }
                art(slug, gen_cmd, *variants)
            }
        },
        CardsCmd::Sheet {
            entries,
            out,
            labels,
        } => {
            let first = entries[0].split(':').next().unwrap_or("cards");
            let stem = Path::new(first)
                .file_stem()
                .map_or("cards".into(), |s| s.to_string_lossy());
            let out = out
                .clone()
                .unwrap_or_else(|| PathBuf::from(format!("output/cards/{stem}-sheet.pdf")));
            let cards = entries
                .iter()
                .map(|e| entry(e))
                .collect::<Result<Vec<_>>>()?;
            sheet(&cards, &out, &site()?, *labels)?;
            println!("sheet: {} ({} cards)", out.display(), cards.len());
            Ok(0)
        }
    }
}

fn card_dir(slug: &str) -> PathBuf {
    Path::new(CARDS_DIR).join(slug)
}

fn load(path: &Path) -> Result<Card> {
    serde_json::from_str(&read(path)?).with_context(|| format!("parsing {}", path.display()))
}

fn write(slug: &str, sources: &[String], model: &str) -> Result<i32> {
    let dir = card_dir(slug);
    std::fs::create_dir_all(&dir)?;
    let text = sources
        .iter()
        .map(|id| read(&Path::new("library/sources").join(id).join("article.md")))
        .collect::<Result<Vec<_>>>()?
        .join("\n\n");
    let caller = Caller::new(&dir);
    let card = modelcard::write_card(
        &caller,
        &format!("{slug} card"),
        &ModelSpec::parse(model)?,
        &text,
    )?;
    let path = dir.join("card.json");
    write_atomic(&path, serde_json::to_string_pretty(&card)? + "\n")?;
    let gaps = modelcard::missing(&card);
    println!("card: {}", path.display());
    if !gaps.is_empty() {
        println!(
            "  still missing {}; capture a lab page that states it with `mag capture <url> --library-only` and pass it as another --source",
            gaps.join(", ")
        );
    }
    println!("next: mag cards art {slug}");
    Ok(0)
}

fn rewrite_briefs(slug: &str, model: &str) -> Result<()> {
    let dir = card_dir(slug);
    let path = dir.join("card.json");
    let mut card = load(&path)?;
    card.art_briefs = modelcard::write_briefs(
        &Caller::new(&dir),
        &format!("{slug} art"),
        &ModelSpec::parse(model)?,
        &card,
    )?;
    write_atomic(&path, serde_json::to_string_pretty(&card)? + "\n")?;
    for (n, brief) in card.art_briefs.iter().enumerate() {
        println!("  brief {}: {brief}", n + 1);
    }
    Ok(())
}

fn shelve(candidates: &Path) -> Result<()> {
    let old: Vec<PathBuf> = std::fs::read_dir(candidates)?
        .filter_map(|e| e.ok().map(|e| e.path()))
        .filter(|p| p.is_file())
        .collect();
    if old.is_empty() {
        return Ok(());
    }
    let stamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)?
        .as_secs();
    let shelf = candidates.join(format!("earlier-{stamp}"));
    std::fs::create_dir_all(&shelf)?;
    for path in old {
        if let Some(name) = path.file_name() {
            std::fs::rename(&path, shelf.join(name))?;
        }
    }
    println!("earlier candidates: {}", shelf.display());
    Ok(())
}

fn art(slug: &str, gen_cmd: &str, variants: u32) -> Result<i32> {
    let dir = card_dir(slug);
    let card = load(&dir.join("card.json"))?;
    let candidates = dir.join("candidates");
    std::fs::create_dir_all(&candidates)?;
    shelve(&candidates)?;
    let cmd = crate::art::expand_placeholders(gen_cmd)?;
    let jobs: Vec<(String, PathBuf, String)> = card
        .art_briefs
        .iter()
        .enumerate()
        .flat_map(|(n, brief)| {
            let candidates = &candidates;
            (1..=variants).map(move |v| {
                let name = format!("{}-v{v}", n + 1);
                let prompt = modelcard::art_prompt(brief);
                (name.clone(), candidates.join(format!("{name}.png")), prompt)
            })
        })
        .collect();
    let results: Vec<(String, Result<(), String>)> = std::thread::scope(|scope| {
        let handles: Vec<_> = jobs
            .iter()
            .map(|(name, out, prompt)| {
                let env = [
                    ("MAG_PROMPT", prompt.clone()),
                    ("MAG_OUT", out.to_string_lossy().into_owned()),
                    ("MAG_REF", String::new()),
                    ("MAG_SIZE", ART_SIZE.to_string()),
                ];
                let cmd = &cmd;
                scope.spawn(move || (name.clone(), crate::art::run_gen_command(cmd, &env, out)))
            })
            .collect();
        handles
            .into_iter()
            .map(|h| h.join().expect("a generator thread panicked"))
            .collect()
    });
    for (name, result) in &results {
        println!(
            "  {name}: {}",
            result.as_ref().map_or_else(Clone::clone, |()| "ok".into())
        );
    }
    let made: Vec<String> = results
        .iter()
        .filter(|(_, r)| r.is_ok())
        .map(|(name, _)| {
            format!(
                "{}:{}",
                dir.join("card.json").display(),
                candidates.join(format!("{name}.png")).display()
            )
        })
        .collect();
    ensure!(!made.is_empty(), "no candidate was generated");
    let preview = candidates.join("preview.pdf");
    sheet(
        &made.iter().map(|e| entry(e)).collect::<Result<Vec<_>>>()?,
        &preview,
        &site()?,
        true,
    )?;
    println!(
        "preview: {} (candidates in order: {})",
        preview.display(),
        results
            .iter()
            .filter(|(_, r)| r.is_ok())
            .map(|(n, _)| n.as_str())
            .collect::<Vec<_>>()
            .join(", ")
    );
    println!("next: mag cards art {slug} --pick <candidate>, or --rebrief for new ideas");
    Ok(0)
}

fn promote(slug: &str, name: &str) -> Result<i32> {
    let dir = card_dir(slug);
    let candidate = dir.join("candidates").join(format!("{name}.png"));
    ensure!(candidate.exists(), "no candidate {}", candidate.display());
    let art = dir.join("art.jpg");
    crate::typeset::art::write_jpeg(&candidate, &art)?;
    println!("art: {}", art.display());
    println!("next: mag cards sheet {slug}");
    Ok(0)
}

struct Entry {
    card: Card,
    art: PathBuf,
}

fn entry(spec: &str) -> Result<Entry> {
    let (card_part, art) = match spec.split_once(':') {
        Some((card, art)) => (card, Some(PathBuf::from(art))),
        None => (spec, None),
    };
    let (json, default_art) = if card_part.ends_with(".json") {
        (PathBuf::from(card_part), None)
    } else {
        let dir = card_dir(card_part);
        (dir.join("card.json"), Some(dir.join("art.jpg")))
    };
    let art = art
        .or(default_art)
        .with_context(|| format!("{spec}: a card.json path needs :<art image>"))?;
    if !art.exists() {
        bail!(
            "{spec}: no art at {}; pick one with mag cards art",
            art.display()
        );
    }
    Ok(Entry {
        card: load(&json)?,
        art: std::path::absolute(&art)?,
    })
}

fn site() -> Result<String> {
    Ok(crate::render::magazine_toml(Path::new("."))?
        .get("site")
        .and_then(|s| s.get("base_url"))
        .and_then(toml::Value::as_str)
        .unwrap_or_default()
        .trim_start_matches("https://")
        .trim_end_matches('/')
        .to_string())
}

fn sheet(entries: &[Entry], out: &Path, site: &str, labels: bool) -> Result<()> {
    let labs = Path::new(env!("CARGO_MANIFEST_DIR")).join("assets/labs");
    let items = entries
        .iter()
        .map(|e| {
            let label = e
                .art
                .file_stem()
                .filter(|_| labels)
                .map_or("none".into(), |s| string_literal(&s.to_string_lossy()));
            Ok(format!(
                "(card: {}, art: {}, date: none, label: {label})",
                literal(&serde_json::to_value(&e.card)?),
                string_literal(&e.art.to_string_lossy())
            ))
        })
        .collect::<Result<Vec<_>>>()?;
    let source = format!(
        "{CARD_SHEET_TYP}\n#card-sheet(({},), labs: {}, site: {})\n",
        items.join(", "),
        string_literal(&labs.to_string_lossy()),
        string_literal(site)
    );
    let tree = Tree {
        files: vec![File {
            path: "main.typ".to_string(),
            source,
        }],
        ..Tree::default()
    };
    let roots: Vec<PathBuf> = entries
        .iter()
        .filter_map(|e| e.art.parent().map(Path::to_path_buf))
        .collect();
    let world =
        Sources::new(&tree, BOOK_TEMPLATE_TYP, "#include \"/main.typ\"\n")?.allowing(&roots)?;
    let document = template::document(&world)?;
    if let Some(parent) = out.parent() {
        std::fs::create_dir_all(parent)?;
    }
    std::fs::write(out, template::pdf(&document)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn four_cards_print_as_two_sheets_each_followed_by_its_pattern_back() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR"));
        let card: Card = serde_json::from_str(r#"{"name": "Example 2", "model_id": "example-2", "lab": "Anthropic", "cost": [{"label": "in", "value": "$4"}], "type_line": {"kind": "Frontier Model", "roles": ["Coder"]}, "traits": ["Asks before acting."], "effort": null, "advice": [], "strength": null, "weakness": null, "resistance": null, "benchmark": null, "flavor": null, "released": "2026-10-12", "art_briefs": []}"#).unwrap();
        let art = root.join("tests/typeset_fixtures/media/landscape.png");
        let entries: Vec<Entry> = (0..4)
            .map(|_| Entry {
                card: card.clone(),
                art: art.clone(),
            })
            .collect();
        let out = std::env::temp_dir().join(format!("mag-card-sheet-{}.pdf", std::process::id()));
        sheet(&entries, &out, "example.org", true).unwrap();
        let pdf = lopdf::Document::load(&out).unwrap();
        let sizes: Vec<(i64, i64)> = pdf
            .get_pages()
            .values()
            .map(|id| {
                let page = pdf.get_dictionary(*id).unwrap();
                let media = page.get(b"MediaBox").unwrap().as_array().unwrap();
                let pt = |o: &lopdf::Object| {
                    o.as_float()
                        .map(f64::from)
                        .or_else(|_| o.as_i64().map(|i| i as f64))
                        .unwrap()
                        .round() as i64
                };
                (pt(&media[2]), pt(&media[3]))
            })
            .collect();
        assert_eq!(
            sizes,
            vec![(842, 595); 4],
            "front, back, front, back, all A4 landscape"
        );
        std::fs::remove_file(&out).unwrap();
    }
}
