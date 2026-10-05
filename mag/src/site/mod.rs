use crate::model::kinds::RenderOperation;
pub mod epub;
mod html;
mod images;
mod logo;

use crate::model::manifest::{load_translation, Edition};
use crate::model::shared::parse_yaml;
use crate::model::spec::EditionFile;
use crate::render::{request, resolve_edition_dir, RenderArgs};
use anyhow::{bail, ensure, Context, Result};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::{Path, PathBuf};

#[derive(clap::Args)]
pub struct SiteArgs {
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
    pub repo: String,
}

#[derive(Deserialize, Serialize, Clone, Debug, PartialEq)]
pub struct Asset {
    pub url: String,
    pub bytes: u64,
    pub sha256: String,
}

#[derive(Deserialize, Serialize, Default, Debug)]
#[serde(deny_unknown_fields)]
pub struct Assets {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub pdf: Option<Asset>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub epub: Option<Asset>,
}

pub type PublishRecord = BTreeMap<String, Assets>;

pub struct Issue {
    pub editions: Vec<Edition>,
    pub assets: PublishRecord,
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

pub fn parse_publish_record(text: &str, path: &str) -> Result<PublishRecord> {
    let record: PublishRecord = serde_norway::from_str(text).with_context(|| {
        let old = text.lines().any(|line| line.starts_with("pdfs:"));
        match old {
            true => format!("{path} is the old Drive format; re-run `mag publish NNN --pdf <file> [--epub <file>]` and commit it"),
            false => format!("reading {path}"),
        }
    })?;
    for asset in record.values().flat_map(|a| [&a.pdf, &a.epub]).flatten() {
        ensure!(
            asset.sha256.len() == 64
                && asset
                    .sha256
                    .bytes()
                    .all(|b| matches!(b, b'0'..=b'9' | b'a'..=b'f')),
            "{path}: sha256 must be 64 lowercase hex characters, got {}",
            asset.sha256
        );
    }
    Ok(record)
}

pub fn publish_record(path: &Path) -> Result<PublishRecord> {
    match path.is_file() {
        true => parse_publish_record(&fs::read_to_string(path)?, &path.display().to_string()),
        false => Ok(PublishRecord::new()),
    }
}

struct Scratch;

impl Drop for Scratch {
    fn drop(&mut self) {
        fs::remove_dir_all(scratch_root()).ok();
    }
}

pub fn run(args: &SiteArgs) -> Result<i32> {
    let _scratch = Scratch;
    let root = std::env::current_dir()?.canonicalize()?;
    let site = config(&root)?;
    let mut issues = crate::util::parallel(&site.editions, |id| issue(&root, id))
        .into_iter()
        .collect::<Result<Vec<_>>>()?;
    issues.sort_by(|a, b| b.editions[0].id.cmp(&a.editions[0].id));
    prepare(&args.out)?;
    let images = images::encode_all(
        &html::image_paths(&issues),
        &args.out,
        &root.join(".magazine/site-cache"),
    )?;
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

fn committed_text(root: &Path, path: &str) -> Result<String> {
    let output = std::process::Command::new("git")
        .args(["show", &format!("HEAD:{path}")])
        .current_dir(root)
        .output()
        .context("running git show")?;
    anyhow::ensure!(
        output.status.success(),
        "{path} is not committed at HEAD; mag site publishes committed files only"
    );
    Ok(String::from_utf8(output.stdout)?)
}

fn git_lines(root: &Path, args: &[&str], paths: &[&str]) -> Result<BTreeSet<String>> {
    let output = std::process::Command::new("git")
        .args(args)
        .arg("--")
        .args(paths)
        .current_dir(root)
        .output()
        .context("running git")?;
    anyhow::ensure!(output.status.success(), "git {} failed", args.join(" "));
    Ok(String::from_utf8(output.stdout)?
        .split('\0')
        .filter(|path| !path.is_empty())
        .map(str::to_string)
        .collect())
}

fn require_committed(root: &Path, inputs: &[String]) -> Result<()> {
    let paths: Vec<&str> = inputs.iter().map(String::as_str).collect();
    let tracked = git_lines(root, &["ls-files", "-z"], &paths)?;
    let dirty = git_lines(root, &["diff", "--name-only", "-z", "HEAD"], &paths)?;
    let bad: Vec<&String> = inputs
        .iter()
        .filter(|path| !tracked.contains(*path) || dirty.contains(*path))
        .collect();
    anyhow::ensure!(
        bad.is_empty(),
        "mag site publishes committed inputs only; untracked or modified: {}",
        bad.iter()
            .map(|p| p.as_str())
            .collect::<Vec<_>>()
            .join(", ")
    );
    Ok(())
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

fn scratch_root() -> PathBuf {
    std::env::temp_dir().join(format!("mag-site-{}", std::process::id()))
}

pub fn issue(root: &Path, id: &str) -> Result<Issue> {
    let dir = resolve_edition_dir(id)?;
    let rel = dir.to_string_lossy().replace('\\', "/");
    let yaml: EditionFile = parse_yaml(&committed_text(root, &format!("{rel}/edition.yaml"))?)?;
    let articles: Vec<String> = yaml
        .articles
        .into_iter()
        .map(|article| article.id)
        .filter(|id| !id.is_empty())
        .collect();
    let tracked = tracked_files(root, &rel)?;
    let run = newest_tracked_run(&tracked, &rel, &articles, yaml.editorial.is_some())
        .with_context(|| format!("{rel} has no git-tracked complete run"))?;
    let scratch = scratch_root().join(id);
    if scratch.exists() {
        fs::remove_dir_all(&scratch)?;
    }
    let args = RenderArgs {
        edition: id.to_string(),
        operation: RenderOperation::RenderEdition,
        article: None,
        langs: None,
        run: Some(format!("{rel}/{run}")),
        no_legibility: true,
    };
    let request = request(&args, root)?;
    let inputs: Vec<String> = request
        .inputs
        .iter()
        .map(|row| match Path::new(&row.source_path).strip_prefix(root) {
            Ok(rel) if !rel.starts_with(".magazine") => rel.to_string_lossy().replace('\\', "/"),
            _ => row.target_path.clone(),
        })
        .collect();
    require_committed(root, &inputs)?;
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
    let publish_path = format!("{rel}/publish.yaml");
    let assets = match tracked.contains(&publish_path) {
        true => parse_publish_record(&committed_text(root, &publish_path)?, &publish_path)?,
        false => PublishRecord::new(),
    };
    Ok(Issue { editions, assets })
}

#[cfg(test)]
mod tests {
    use super::{newest_tracked_run, require_committed};
    use std::collections::BTreeSet;

    fn set(paths: &[&str]) -> BTreeSet<String> {
        paths.iter().map(std::string::ToString::to_string).collect()
    }

    #[test]
    fn require_committed_names_untracked_and_modified_inputs() {
        let dir = std::env::temp_dir().join(format!("mag-site-git-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        let git = |args: &[&str]| {
            let status = std::process::Command::new("git")
                .args(["-c", "user.name=t", "-c", "user.email=t@t"])
                .args(args)
                .current_dir(&dir)
                .status()
                .unwrap();
            assert!(status.success());
        };
        git(&["init", "-q"]);
        std::fs::write(dir.join("a.md"), "a").unwrap();
        git(&["add", "a.md"]);
        git(&["commit", "-qm", "a"]);
        std::fs::write(dir.join("é b.png"), "e").unwrap();
        git(&["add", "é b.png"]);
        git(&["commit", "-qm", "e"]);
        let both = vec!["a.md".to_string(), "b.md".to_string()];
        let unicode = vec!["é b.png".to_string()];
        assert!(require_committed(&dir, &unicode).is_ok());
        std::fs::write(dir.join("b.md"), "b").unwrap();
        let err = require_committed(&dir, &both).unwrap_err().to_string();
        assert!(err.ends_with(": b.md"), "{err}");
        assert!(require_committed(&dir, &both[..1]).is_ok());
        std::fs::write(dir.join("a.md"), "changed").unwrap();
        let err = require_committed(&dir, &both[..1]).unwrap_err().to_string();
        assert!(err.ends_with(": a.md"), "{err}");
        std::fs::remove_dir_all(&dir).unwrap();
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
