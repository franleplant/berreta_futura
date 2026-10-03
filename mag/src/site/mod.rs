mod html;
mod images;
mod logo;

use crate::model::manifest::{load_translation, Edition};
use crate::render::{request, resolve_edition_dir, RenderArgs};
use anyhow::{bail, Context, Result};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::{Path, PathBuf};

#[derive(clap::Args)]
pub(crate) struct SiteArgs {
    #[arg(
        long,
        default_value = "output/site",
        help = "Directory to write the static site into (replaced on every run)"
    )]
    pub out: PathBuf,
}

#[derive(Deserialize)]
struct Config {
    site: SiteConfig,
}

#[derive(Deserialize)]
pub struct SiteConfig {
    pub base_url: String,
    pub editions: Vec<String>,
    pub pdf_remote: String,
}

#[derive(Deserialize, Serialize, Clone, Debug, PartialEq)]
pub struct Pdf {
    pub url: String,
    pub bytes: u64,
    pub sha256: String,
}

#[derive(Deserialize, Serialize, Default)]
pub struct PublishRecord {
    #[serde(default)]
    pub pdfs: BTreeMap<String, Pdf>,
}

pub struct Issue {
    pub editions: Vec<Edition>,
    pub pdfs: BTreeMap<String, Pdf>,
}

const FONTS: [&str; 5] = [
    "source-serif-4/SourceSerif4SmText-Regular.ttf",
    "source-serif-4/SourceSerif4SmText-It.ttf",
    "source-serif-4/SourceSerif4SmText-Bold.ttf",
    "source-serif-4/SourceSerif4Display-Semibold.ttf",
    "source-serif-4/LICENSE.md",
];

pub fn config(root: &Path) -> Result<SiteConfig> {
    let text = fs::read_to_string(root.join("magazine.toml")).context("reading magazine.toml")?;
    let config: Config =
        toml::from_str(&text).context("magazine.toml needs a full [site] table")?;
    Ok(config.site)
}

pub fn publish_record(path: &Path) -> Result<PublishRecord> {
    match path.is_file() {
        true => serde_yaml::from_str(&fs::read_to_string(path)?)
            .with_context(|| format!("reading {}", path.display())),
        false => Ok(PublishRecord::default()),
    }
}

pub fn run(args: &SiteArgs) -> Result<i32> {
    let root = std::env::current_dir()?.canonicalize()?;
    let site = config(&root)?;
    let mut issues = site
        .editions
        .iter()
        .map(|id| issue(&root, id))
        .collect::<Result<Vec<_>>>()?;
    issues.sort_by(|a, b| b.editions[0].id.cmp(&a.editions[0].id));
    prepare(&args.out)?;
    let images = images::encode_all(html::image_paths(&issues), &args.out)?;
    let name = issues
        .first()
        .map_or("Magazine", |i| i.editions[0].publication_name.as_str())
        .to_string();
    let logo = logo::build(&name)?;
    let files = html::pages(&issues, &images, &site, &name, &logo.inline)?;
    for (path, body) in &files {
        let target = args.out.join(path);
        fs::create_dir_all(target.parent().context("a page has no parent")?)?;
        fs::write(&target, body)?;
    }
    fs::write(args.out.join("favicon.svg"), &logo.favicon)?;
    fs::write(args.out.join("apple-touch-icon.png"), &logo.touch)?;
    fs::write(args.out.join("og.png"), &logo.card)?;
    for font in FONTS {
        let target = args
            .out
            .join("fonts")
            .join(Path::new(font).file_name().unwrap());
        fs::create_dir_all(target.parent().unwrap())?;
        fs::copy(root.join("mag/assets/fonts").join(font), target)?;
    }
    println!(
        "site: {} pages, {} images, {} bytes in {}",
        files.len(),
        images.len(),
        tree_bytes(&args.out)?,
        args.out.display()
    );
    println!("\nnext: deploy {} as static assets", args.out.display());
    Ok(0)
}

fn tree_bytes(dir: &Path) -> Result<u64> {
    let mut total = 0;
    for entry in fs::read_dir(dir)? {
        let path = entry?.path();
        total += match path.is_dir() {
            true => tree_bytes(&path)?,
            false => fs::metadata(&path)?.len(),
        };
    }
    Ok(total)
}

fn prepare(out: &Path) -> Result<()> {
    if out.exists() {
        let ours = out.join("site.css").is_file() || fs::read_dir(out)?.next().is_none();
        if !ours {
            bail!(
                "{} exists and is not a site this command wrote; pick another --out",
                out.display()
            );
        }
        fs::remove_dir_all(out)?;
    }
    fs::create_dir_all(out)?;
    Ok(fs::write(
        out.join("site.css"),
        include_str!("../../assets/site.css"),
    )?)
}

fn tracked_files(root: &Path, dir: &str) -> Result<BTreeSet<String>> {
    let output = std::process::Command::new("git")
        .args(["ls-files", "-z", "--", dir])
        .current_dir(root)
        .output()
        .context("running git ls-files")?;
    anyhow::ensure!(output.status.success(), "git ls-files failed for {dir}");
    Ok(String::from_utf8(output.stdout)?
        .split('\0')
        .filter(|path| !path.is_empty())
        .map(str::to_string)
        .collect())
}

pub fn newest_tracked_run(
    tracked: &BTreeSet<String>,
    dir: &str,
    articles: &[String],
    editorial: bool,
) -> Option<String> {
    let prefix = format!("{dir}/");
    let runs: BTreeSet<&str> = tracked
        .iter()
        .filter_map(|path| path.strip_prefix(&prefix)?.split_once('/'))
        .map(|(run, _)| run)
        .filter(|run| run.starts_with("run-"))
        .collect();
    let has = |run: &str, file: String| tracked.contains(&format!("{prefix}{run}/{file}"));
    runs.into_iter()
        .rev()
        .find(|run| {
            (!editorial || has(run, "editorial/final.md".into()))
                && articles
                    .iter()
                    .all(|id| has(run, format!("articles/{id}/final.md")))
        })
        .map(str::to_string)
}

fn issue(root: &Path, id: &str) -> Result<Issue> {
    let dir = resolve_edition_dir(id)?;
    let rel = dir.to_string_lossy().replace('\\', "/");
    let yaml: serde_yaml::Value =
        serde_yaml::from_str(&fs::read_to_string(dir.join("edition.yaml"))?)?;
    let articles: Vec<String> = yaml["articles"]
        .as_sequence()
        .into_iter()
        .flatten()
        .filter_map(|article| article["id"].as_str().map(str::to_string))
        .collect();
    let run = newest_tracked_run(
        &tracked_files(root, &rel)?,
        &rel,
        &articles,
        yaml.get("editorial").is_some(),
    )
    .with_context(|| format!("{rel} has no git-tracked complete run"))?;
    let scratch = root.join(".magazine/site").join(id);
    if scratch.exists() {
        fs::remove_dir_all(&scratch)?;
    }
    let args = RenderArgs {
        edition: id.to_string(),
        operation: "render_edition".to_string(),
        article: None,
        langs: None,
        run: Some(format!("{rel}/{run}")),
        anchor_model: "haiku".to_string(),
        no_model: true,
    };
    let request = request(&args, root, &scratch)?;
    let staged = scratch.join("staged");
    for row in &request.inputs {
        let target = staged.join(&row.target_path);
        fs::create_dir_all(target.parent().context("a staged file has no parent")?)?;
        fs::copy(&row.source_path, &target)?;
    }
    let base =
        crate::typeset::layout::edition(&staged, &request.edition_id, &request.publication_name)?;
    let editions = request
        .languages
        .iter()
        .map(|language| {
            let edition = match *language == request.primary_language {
                true => base.clone(),
                false => load_translation(&staged, &base, language)?,
            };
            crate::typeset::tone::print_figures(edition, &staged)
        })
        .collect::<Result<Vec<_>>>()?;
    let pdfs = publish_record(&dir.join("publish.yaml"))?.pdfs;
    Ok(Issue { editions, pdfs })
}

#[cfg(test)]
mod tests {
    use super::newest_tracked_run;
    use std::collections::BTreeSet;

    fn set(paths: &[&str]) -> BTreeSet<String> {
        paths.iter().map(|p| p.to_string()).collect()
    }

    #[test]
    fn the_newest_complete_tracked_run_wins_and_incomplete_ones_are_skipped() {
        let ids = vec!["a".to_string(), "b".to_string()];
        let tracked = set(&[
            "editions/011/run-1/articles/a/final.md",
            "editions/011/run-1/articles/b/final.md",
            "editions/011/run-2/articles/a/final.md",
            "editions/011/run-2/articles/b/final.md",
            "editions/011/run-3/articles/a/final.md",
            "editions/011/run-3/articles/b/draft.md",
            "editions/0110/run-9/articles/a/final.md",
        ]);
        assert_eq!(
            newest_tracked_run(&tracked, "editions/011", &ids, false),
            Some("run-2".to_string())
        );
        assert_eq!(
            newest_tracked_run(&tracked, "editions/011", &ids, true),
            None
        );
        assert_eq!(
            newest_tracked_run(&set(&[]), "editions/011", &ids, false),
            None
        );
    }
}
