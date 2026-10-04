use super::html::{art_paths, chapter, pieces, title_page};
use super::images::{flatten, Image};
use crate::model::manifest::Edition;
use anyhow::{Context, Result};
use image::imageops::FilterType;
use std::collections::BTreeMap;
use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};
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
pub(crate) struct EpubArgs {
    #[arg(help = "Edition id, e.g. 012")]
    pub edition: String,
    #[arg(long, default_value = "en", help = "Language edition to package")]
    pub lang: String,
    #[arg(
        long,
        help = "Cover image (PNG or JPEG) to use instead of the edition's cover art"
    )]
    pub cover: Option<PathBuf>,
    #[arg(
        long,
        default_value = "output/epub",
        help = "Directory to write the .epub into"
    )]
    pub out: PathBuf,
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
        escape(title)
    )
}

fn escape(value: &str) -> String {
    value
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
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
    let mut out = BTreeMap::new();
    for (index, path) in paths.into_iter().enumerate() {
        let (bytes, width, height) = jpeg(&path)?;
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
        escape(&edition.publication_name),
        escape(&edition.title),
        escape(&edition.publication_name),
        escape(&edition.publication_name),
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

pub fn run(args: &EpubArgs) -> Result<i32> {
    let root = std::env::current_dir()?.canonicalize()?;
    let site = super::config(&root)?;
    let issue = super::issue(&root, &args.edition)?;
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
    let cover = args
        .cover
        .clone()
        .or_else(|| edition.cover_art.clone())
        .context("no --cover and the edition has no cover art")?;
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
        escape(&edition.title)
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
                escape(&p.title)
            )
        })
        .collect();
    let nav = format!(
        "<nav epub:type=\"toc\" id=\"toc\"><h2>{}</h2><ol><li><a href=\"cover.xhtml\">{}</a></li>{contents}</ol></nav>\n<nav epub:type=\"landmarks\" hidden=\"hidden\"><ol><li><a epub:type=\"cover\" href=\"cover.xhtml\">Cover</a></li><li><a epub:type=\"bodymatter\" href=\"{}.xhtml\">Start</a></li></ol></nav>",
        escape(&crate::model::shared::ui(language, "contents")),
        escape(&edition.title),
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
    fs::create_dir_all(&args.out)?;
    let target = args.out.join(format!(
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
        "\nnext: AirDrop {} to an iPhone, or open it in Books on this Mac",
        target.display()
    );
    Ok(0)
}
