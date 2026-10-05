use super::html::{art_paths, chapter, pieces, title_page};
use super::images::{flatten, Image};
use crate::model::manifest::Edition;
use crate::util::{escape_html, parallel};
use anyhow::{Context, Result};
use image::imageops::FilterType;
use std::collections::BTreeMap;
use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::thread;
use zip::write::SimpleFileOptions;
use zip::CompressionMethod;

const MAX_WIDTH: u32 = 1600;
const FONTS: [&str; 4] = [
    "SourceSerif4SmText-Regular.ttf",
    "SourceSerif4SmText-It.ttf",
    "SourceSerif4SmText-Bold.ttf",
    "SourceSerif4Display-Semibold.ttf",
];

#[derive(clap::Args)]
pub struct EpubArgs {
    #[arg(help = "Edition id, e.g. 012")]
    pub edition: String,
    #[arg(long, default_value = "en", help = "Language edition to package")]
    pub lang: String,
    #[arg(
        long,
        help = "Cover image (PNG or JPEG) to use instead of the newest render's cover.png"
    )]
    pub cover: Option<PathBuf>,
}

fn rendered_cover(dir: &Path, language: &str) -> Option<PathBuf> {
    let mut renders: Vec<PathBuf> = fs::read_dir(dir)
        .ok()?
        .filter_map(|entry| Some(entry.ok()?.path()))
        .filter(|path| {
            path.file_name()
                .is_some_and(|n| n.to_string_lossy().starts_with("render-"))
        })
        .collect();
    renders.sort();
    renders
        .into_iter()
        .rev()
        .map(|render| render.join(language).join("cover.png"))
        .find(|cover| cover.is_file())
}

fn jpeg(path: &Path) -> Result<(Vec<u8>, u32, u32)> {
    let mut rgb = flatten(path)?;
    if rgb.width() > MAX_WIDTH {
        let height = rgb.height() * MAX_WIDTH / rgb.width();
        rgb = image::imageops::resize(&rgb, MAX_WIDTH, height, FilterType::Lanczos3);
    }
    let mut bytes = Vec::new();
    image::codecs::jpeg::JpegEncoder::new_with_quality(&mut bytes, 82).encode_image(&rgb)?;
    Ok((bytes, rgb.width(), rgb.height()))
}

fn xhtml(language: &str, title: &str, body: &str) -> String {
    format!(
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n<!DOCTYPE html>\n<html xmlns=\"http://www.w3.org/1999/xhtml\" xmlns:epub=\"http://www.idpf.org/2007/ops\" lang=\"{language}\" xml:lang=\"{language}\">\n<head>\n<meta charset=\"utf-8\"/>\n<title>{}</title>\n<link rel=\"stylesheet\" href=\"style.css\"/>\n</head>\n<body>\n{body}\n</body>\n</html>\n",
        escape_html(title)
    )
}

fn slug(name: &str) -> String {
    name.to_lowercase()
        .split(|c: char| !c.is_alphanumeric())
        .filter(|s| !s.is_empty())
        .collect::<Vec<_>>()
        .join("-")
}

struct Book {
    files: Vec<(String, Vec<u8>)>,
    manifest: Vec<String>,
}

impl Book {
    fn add(&mut self, name: &str, media: &str, properties: &str, bytes: Vec<u8>) {
        let id = format!("f{}", self.manifest.len());
        let properties = match properties {
            "" => String::new(),
            p => format!(" properties=\"{p}\""),
        };
        self.manifest.push(format!(
            "<item id=\"{id}\" href=\"{name}\" media-type=\"{media}\"{properties}/>"
        ));
        self.files.push((format!("OEBPS/{name}"), bytes));
    }
}

fn images(edition: &Edition, book: &mut Book) -> Result<BTreeMap<PathBuf, Image>> {
    let mut paths = art_paths(edition);
    paths.sort();
    paths.dedup();
    let lanes = thread::available_parallelism().map_or(4, usize::from);
    let encoded = paths
        .chunks(lanes)
        .flat_map(|chunk| parallel(chunk, |path| jpeg(path)))
        .collect::<Result<Vec<_>>>()?;
    let mut out = BTreeMap::new();
    for (index, (path, (bytes, width, height))) in paths.into_iter().zip(encoded).enumerate() {
        let name = format!("images/{index:03}.jpg");
        book.add(&name, "image/jpeg", "", bytes);
        let image = Image {
            variants: vec![(name, width)],
            width,
            height,
        };
        out.insert(path, image);
    }
    Ok(out)
}

fn package(edition: &Edition, book: &Book, spine: &[String], base_url: &str) -> String {
    let language = &edition.language;
    let itemrefs: String = spine
        .iter()
        .map(|id| format!("<itemref idref=\"{id}\"/>"))
        .collect();
    format!(
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n<package xmlns=\"http://www.idpf.org/2007/opf\" version=\"3.0\" unique-identifier=\"uid\" xml:lang=\"{language}\">\n<metadata xmlns:dc=\"http://purl.org/dc/elements/1.1/\">\n<dc:identifier id=\"uid\">{}/{}/{language}</dc:identifier>\n<dc:title>{}: {}</dc:title>\n<dc:creator>{}</dc:creator>\n<dc:publisher>{}</dc:publisher>\n<dc:language>{language}</dc:language>\n<dc:date>{}</dc:date>\n<meta property=\"dcterms:modified\">{}T00:00:00Z</meta>\n<meta name=\"cover\" content=\"f0\"/>\n</metadata>\n<manifest>\n{}\n</manifest>\n<spine>{itemrefs}</spine>\n</package>\n",
        base_url.trim_end_matches('/'),
        edition.id,
        escape_html(&edition.publication_name),
        escape_html(&edition.title),
        escape_html(&edition.publication_name),
        escape_html(&edition.publication_name),
        edition.publication_date,
        edition.publication_date,
        book.manifest.join("\n"),
    )
}

fn write(target: &Path, opf: String, files: Vec<(String, Vec<u8>)>) -> Result<()> {
    let mut zip = zip::ZipWriter::new(fs::File::create(target)?);
    let stored = SimpleFileOptions::default().compression_method(CompressionMethod::Stored);
    let deflated = SimpleFileOptions::default().compression_method(CompressionMethod::Deflated);
    zip.start_file("mimetype", stored)?;
    zip.write_all(b"application/epub+zip")?;
    let meta = [
        (
            "META-INF/container.xml",
            include_str!("../../assets/epub/container.xml")
                .as_bytes()
                .to_vec(),
        ),
        (
            "META-INF/com.apple.ibooks.display-options.xml",
            include_str!("../../assets/epub/display-options.xml")
                .as_bytes()
                .to_vec(),
        ),
        ("OEBPS/content.opf", opf.into_bytes()),
    ];
    let all = meta
        .into_iter()
        .map(|(name, bytes)| (name.to_string(), bytes))
        .chain(files);
    for (name, bytes) in all {
        zip.start_file(name, deflated)?;
        zip.write_all(&bytes)?;
    }
    zip.finish()?;
    Ok(())
}

fn cover(args: &EpubArgs, dir: &Path, language: &str) -> Result<PathBuf> {
    args.cover
        .clone()
        .or_else(|| rendered_cover(dir, language))
        .with_context(|| {
            format!(
                "no rendered {language} cover in {}: run `mag render {}` first, or pass --cover",
                dir.display(),
                args.edition
            )
        })
}

pub fn run(args: &EpubArgs) -> Result<i32> {
    let root = std::env::current_dir()?.canonicalize()?;
    let site = super::config(&root)?;
    let issue = super::issue(&root, &args.edition, false)?;
    let edition = issue
        .editions
        .iter()
        .find(|e| e.language == args.lang)
        .with_context(|| format!("edition {} has no {} language", args.edition, args.lang))?;
    let language = edition.language.as_str();
    let mut book = Book {
        files: Vec::new(),
        manifest: Vec::new(),
    };
    let dir = crate::render::resolve_edition_dir(&args.edition)?;
    let cover = cover(args, &dir, language)?;
    let (bytes, _, _) = jpeg(&cover)?;
    book.add("images/cover.jpg", "image/jpeg", "cover-image", bytes);
    let images = images(edition, &mut book)?;
    book.add(
        "style.css",
        "text/css",
        "",
        include_bytes!("../../assets/epub.css").to_vec(),
    );
    for font in FONTS {
        let bytes = fs::read(root.join("mag/assets/fonts/source-serif-4").join(font))?;
        book.add(&format!("fonts/{font}"), "font/ttf", "", bytes);
    }
    let mut spine = Vec::new();
    let mut add_page = |book: &mut Book, name: &str, title: &str, body: &str, nav: bool| {
        spine.push(format!("f{}", book.manifest.len()));
        let properties = if nav { "nav" } else { "" };
        let page = xhtml(language, title, body);
        book.add(name, "application/xhtml+xml", properties, page.into_bytes());
    };
    let cover_body = format!(
        "<section class=\"cover-page\" epub:type=\"cover\"><img src=\"images/cover.jpg\" alt=\"{}\"/></section>",
        escape_html(&edition.title)
    );
    add_page(&mut book, "cover.xhtml", &edition.title, &cover_body, false);
    add_page(
        &mut book,
        "title.xhtml",
        &edition.title,
        &title_page(edition),
        false,
    );
    let pieces = pieces(edition)?;
    let contents: String = pieces
        .iter()
        .map(|p| {
            format!(
                "<li><a href=\"{}.xhtml\">{}</a></li>",
                p.slug,
                escape_html(&p.title)
            )
        })
        .collect();
    let nav = format!(
        "<nav epub:type=\"toc\" id=\"toc\"><h2>{}</h2><ol><li><a href=\"cover.xhtml\">{}</a></li>{contents}</ol></nav>\n<nav epub:type=\"landmarks\" hidden=\"hidden\"><ol><li><a epub:type=\"cover\" href=\"cover.xhtml\">Cover</a></li><li><a epub:type=\"bodymatter\" href=\"{}.xhtml\">Start</a></li></ol></nav>",
        escape_html(&crate::model::shared::ui(language, "contents")),
        escape_html(&edition.title),
        pieces.first().map_or("title", |p| p.slug.as_str())
    );
    add_page(&mut book, "nav.xhtml", &edition.title, &nav, true);
    for piece in &pieces {
        let body = chapter(edition, piece, &images)?;
        add_page(
            &mut book,
            &format!("{}.xhtml", piece.slug),
            &piece.title,
            &body,
            false,
        );
    }
    let opf = package(edition, &book, &spine, &site.base_url);
    fs::create_dir_all(dir.join("epub"))?;
    let target = dir.join("epub").join(format!(
        "{}-{}-{language}.epub",
        slug(&edition.publication_name),
        edition.id
    ));
    write(&target, opf, book.files)?;
    println!(
        "epub: {} chapters, {} images, {} bytes in {}",
        pieces.len(),
        images.len() + 1,
        fs::metadata(&target)?.len(),
        target.display()
    );
    println!(
        "\nnext: open {} in Books to check it, then commit it; `mag site` links a committed EPUB on the issue page",
        target.display()
    );
    Ok(0)
}
