use crate::model::records::slug;
use crate::render::{publication_name, resolve_edition_dir};
use crate::site::{config, publish_record, Pdf};
use anyhow::{ensure, Context, Result};
use sha2::{Digest, Sha256};
use std::fs;
use std::io::Read;
use std::path::{Path, PathBuf};
use std::process::Command;

const WRANGLER_LIMIT: u64 = 315_000_000;

#[derive(clap::Args)]
pub(crate) struct PublishArgs {
    #[arg(help = "Edition id, e.g. 011")]
    pub edition: String,
    #[arg(long, help = "The approved PDF, uploaded to R2 unchanged")]
    pub pdf: PathBuf,
    #[arg(long, default_value = "en", help = "The language this PDF is")]
    pub lang: String,
    #[arg(
        long = "dry-run",
        help = "Print the upload command instead of running it (publish.yaml is still written)"
    )]
    pub dry_run: bool,
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
    let (bytes, sha256) = digest(&args.pdf)?;
    ensure!(
        bytes <= WRANGLER_LIMIT,
        "{} is {bytes} bytes; wrangler uploads at most 315 MB",
        args.pdf.display()
    );
    let key = key(
        &slug(&publication_name(&root)),
        &edition,
        &args.lang,
        &sha256,
    );
    let object = format!("{}/{key}", site.pdf_bucket);
    let file = args.pdf.to_string_lossy();
    let upload = [
        "wrangler",
        "r2",
        "object",
        "put",
        &object,
        "--file",
        &file,
        "--remote",
        "--content-type",
        "application/pdf",
    ];
    match args.dry_run {
        true => println!("dry run, not uploading: npx {}", upload.join(" ")),
        false => ensure!(
            Command::new("npx").args(upload).status()?.success(),
            "the R2 upload failed; publish.yaml is unchanged"
        ),
    }
    let url = format!("{}/{key}", site.pdf_base_url.trim_end_matches('/'));
    let path = dir.join("publish.yaml");
    let mut record = publish_record(&path)?;
    record.pdfs.insert(
        args.lang.clone(),
        Pdf {
            url: url.clone(),
            bytes,
            sha256,
        },
    );
    fs::write(&path, serde_yaml::to_string(&record)?)?;
    println!("link: {url}\nwrote {}", path.display());
    println!(
        "\nnext: git add {0} && git commit -m 'edition {edition}: publish the {1} PDF' && git push (the site deploy adds the link)",
        path.display(),
        args.lang
    );
    Ok(0)
}

fn key(name: &str, edition: &str, lang: &str, sha256: &str) -> String {
    format!(
        "{edition}/{lang}/{name}-{edition}-{lang}-{}.pdf",
        &sha256[..8]
    )
}

fn digest(path: &Path) -> Result<(u64, String)> {
    let mut file = fs::File::open(path).with_context(|| format!("opening {}", path.display()))?;
    let mut head = [0u8; 5];
    let pdf = file.read_exact(&mut head).is_ok() && &head == b"%PDF-";
    ensure!(pdf, "{} is not a PDF (no %PDF- header)", path.display());
    let mut hasher = Sha256::new();
    hasher.update(head);
    let bytes = 5 + std::io::copy(&mut file, &mut hasher)?;
    Ok((bytes, hex::encode(hasher.finalize())))
}
