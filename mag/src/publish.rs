use crate::caller::write_atomic;
use crate::model::records::slug;
use crate::render::{publication_name, resolve_edition_dir};
use crate::site::{config, publish_record, Asset};
use anyhow::{ensure, Context, Result};
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

#[derive(clap::Args)]
pub struct PublishArgs {
    #[arg(help = "Edition id, e.g. 011")]
    pub edition: String,
    #[arg(
        long,
        help = "The approved PDF, uploaded to the issue's GitHub Release"
    )]
    pub pdf: PathBuf,
    #[arg(
        long,
        help = "The EPUB to upload with it; without it, publish builds one with `mag epub` (every issue ships both)"
    )]
    pub epub: Option<PathBuf>,
    #[arg(long, default_value = "en", help = "The language these files are")]
    pub lang: String,
    #[arg(
        long = "dry-run",
        help = "Print what would be uploaded instead of running gh (nothing is written)"
    )]
    pub dry_run: bool,
}

struct Staging(PathBuf);

impl Drop for Staging {
    fn drop(&mut self) {
        fs::remove_dir_all(&self.0).ok();
    }
}

struct Upload {
    kind: &'static str,
    source: PathBuf,
    name: String,
    asset: Asset,
}

pub fn run(args: &PublishArgs) -> Result<i32> {
    let root = std::env::current_dir()?;
    let site = config(&root)?;
    let dir = resolve_edition_dir(&args.edition)?;
    let edition = dir
        .file_name()
        .context("no edition dir name")?
        .to_string_lossy();
    ensure!(
        args.lang.len() == 2 && args.lang.bytes().all(|b| b.is_ascii_lowercase()),
        "--lang takes a two-letter code like en or es, not {}",
        args.lang
    );
    let tag = format!("issue-{edition}");
    let stem = format!(
        "{}-{edition}-{}",
        slug(&publication_name(&root)?),
        args.lang
    );
    let url = |name: &str| {
        format!(
            "https://github.com/{}/releases/download/{tag}/{name}",
            site.repo
        )
    };
    let pdf = upload(&args.pdf, "pdf", b"%PDF-", &stem, &url)?;
    let epub = match &args.epub {
        Some(epub) => epub.clone(),
        None => {
            crate::site::epub::run(&crate::site::epub::EpubArgs {
                edition: args.edition.clone(),
                lang: args.lang.clone(),
                cover: None,
            })?;
            dir.join("epub").join(format!("{stem}.epub"))
        }
    };
    let uploads = vec![pdf, upload(&epub, "epub", b"PK", &stem, &url)?];
    let path = dir.join("publish.yaml");
    if args.dry_run {
        for one in &uploads {
            println!(
                "dry run, not uploading: gh release upload {tag} {} as {} to {}",
                one.source.display(),
                one.name,
                site.repo
            );
        }
        println!("would write {}", path.display());
        return Ok(0);
    }
    let spec: serde_norway::Value =
        serde_norway::from_str(&fs::read_to_string(dir.join("edition.yaml"))?)?;
    let title = spec["title"]
        .as_str()
        .context("edition.yaml has no title")?;
    let current = current_digests(&site.repo, &tag, &format!("Issue {edition}: {title}"))?;
    let staging = std::env::temp_dir().join(format!("mag-publish-{}", std::process::id()));
    fs::create_dir_all(&staging)?;
    let _staging = Staging(staging.clone());
    let mut record = publish_record(&path)?;
    for one in uploads {
        match current.contains(&format!("{}:{}", one.name, one.asset.sha256)) {
            true => println!("unchanged on the release, skipped: {}", one.name),
            false => send(&site.repo, &tag, &staging, &one)?,
        }
        let assets = record.entry(args.lang.clone()).or_default();
        match one.kind {
            "pdf" => assets.pdf = Some(one.asset),
            _ => assets.epub = Some(one.asset),
        }
    }
    write_atomic(&path, serde_norway::to_string(&record)?)?;
    println!("wrote {}", path.display());
    println!(
        "\nnext: mag site, then wrangler deploy, then git add {0} && git commit -m 'edition {edition}: publish the {1} downloads' && git push",
        path.display(),
        args.lang
    );
    Ok(0)
}

fn upload(
    path: &Path,
    kind: &'static str,
    magic: &[u8],
    stem: &str,
    url: &dyn Fn(&str) -> String,
) -> Result<Upload> {
    let bytes = fs::read(path).with_context(|| format!("reading {}", path.display()))?;
    ensure!(
        bytes.starts_with(magic),
        "{} is not a {kind}",
        path.display()
    );
    let name = format!("{stem}.{kind}");
    Ok(Upload {
        kind,
        source: path.to_path_buf(),
        asset: Asset {
            url: url(&name),
            bytes: bytes.len() as u64,
            sha256: crate::util::sha256_hex(&bytes),
        },
        name,
    })
}

fn gh(args: &[&str]) -> Result<std::process::Output> {
    Command::new("gh")
        .args(args)
        .output()
        .context("running gh; is the GitHub CLI installed and logged in?")
}

fn current_digests(repo: &str, tag: &str, title: &str) -> Result<Vec<String>> {
    let found = gh(&["api", &format!("repos/{repo}/releases/tags/{tag}")])?;
    if !found.status.success() {
        let made = gh(&[
            "release",
            "create",
            tag,
            "--repo",
            repo,
            "--title",
            title,
            "--notes",
            "",
            "--latest=false",
        ])?;
        ensure!(
            made.status.success(),
            "gh could not create release {tag}: {}",
            String::from_utf8_lossy(&made.stderr)
        );
        return Ok(Vec::new());
    }
    let release: serde_json::Value = serde_json::from_slice(&found.stdout)?;
    Ok(release["assets"]
        .as_array()
        .into_iter()
        .flatten()
        .filter_map(|a| {
            let digest = a["digest"].as_str()?.strip_prefix("sha256:")?;
            Some(format!("{}:{digest}", a["name"].as_str()?))
        })
        .collect())
}

fn send(repo: &str, tag: &str, staging: &Path, one: &Upload) -> Result<()> {
    let staged = staging.join(&one.name);
    fs::copy(&one.source, &staged)?;
    let out = gh(&[
        "release",
        "upload",
        tag,
        &staged.to_string_lossy(),
        "--clobber",
        "--repo",
        repo,
    ])?;
    ensure!(
        out.status.success(),
        "the upload of {} failed; publish.yaml is unchanged: {}",
        one.name,
        String::from_utf8_lossy(&out.stderr)
    );
    println!("uploaded {}", one.name);
    Ok(())
}
