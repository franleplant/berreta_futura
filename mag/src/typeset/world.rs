use crate::typeset::content::Tree;
use crate::typeset::decisions::{render_tree, Mark};
use anyhow::{Context, Result};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::{Mutex, OnceLock};
use typst::diag::{FileError, FileResult};
use typst::foundations::{Bytes, Datetime, Duration};
use typst::text::{Font, FontBook};
use typst::utils::LazyHash;
use typst::{Library, LibraryExt, World};
use typst_syntax::{FileId, RootedPath, Source, VirtualPath, VirtualRoot};

pub const ROOT: &str = "/root.typ";
pub const TEMPLATE: &str = "/template.typ";
const PRELUDE: &str = "#import \"/template.typ\": *\n";
const RASTERS: [&str; 3] = [".png", ".jpg", ".jpeg"];

struct Shared {
    library: LazyHash<Library>,
    book: LazyHash<FontBook>,
    fonts: Vec<Font>,
    rasters: Mutex<HashMap<FileId, FileResult<Bytes>>>,
}

static SHARED: OnceLock<Shared> = OnceLock::new();

pub struct Sources {
    shared: &'static Shared,
    main: FileId,
    texts: HashMap<FileId, Source>,
    marks: HashMap<FileId, Vec<Mark>>,
}

pub fn id(path: &str) -> Result<FileId> {
    let vpath = VirtualPath::new(path).map_err(|e| anyhow::anyhow!("{path}: {e}"))?;
    Ok(RootedPath::new(VirtualRoot::Project, vpath).intern())
}

fn ttfs(dir: &Path) -> Result<Vec<PathBuf>> {
    let mut out = Vec::new();
    for entry in std::fs::read_dir(dir).with_context(|| format!("reading {}", dir.display()))? {
        let path = entry?.path();
        if path.is_dir() {
            out.extend(ttfs(&path)?);
        } else if path.extension().is_some_and(|e| e == "ttf" || e == "otf") {
            out.push(path);
        }
    }
    out.sort();
    Ok(out)
}

fn faces(dir: &Path) -> Result<Vec<Font>> {
    let mut fonts = Vec::new();
    for file in ttfs(dir)? {
        let bytes =
            Bytes::new(std::fs::read(&file).with_context(|| format!("{}", file.display()))?);
        fonts.extend(Font::iter(bytes));
    }
    anyhow::ensure!(!fonts.is_empty(), "no fonts found under {}", dir.display());
    Ok(fonts)
}

pub fn font_dir() -> &'static Path {
    Path::new(concat!(env!("CARGO_MANIFEST_DIR"), "/assets/fonts"))
}

fn shared() -> Result<&'static Shared> {
    if let Some(loaded) = SHARED.get() {
        return Ok(loaded);
    }
    let fonts = faces(font_dir())?;
    Ok(SHARED.get_or_init(|| Shared {
        library: LazyHash::new(Library::default()),
        book: LazyHash::new(FontBook::from_fonts(&fonts)),
        fonts,
        rasters: Mutex::default(),
    }))
}

impl Sources {
    pub fn new(tree: &Tree, template: &str, root: &str) -> Result<Self> {
        let mut texts = HashMap::new();
        let mut marks = HashMap::new();
        for (path, rendered) in render_tree(tree, PRELUDE)? {
            let file = id(&format!("/{path}"))?;
            texts.insert(file, Source::new(file, rendered.text));
            marks.insert(file, rendered.marks);
        }
        for (path, text) in [(TEMPLATE, template), (ROOT, root)] {
            let file = id(path)?;
            texts.insert(file, Source::new(file, text.to_string()));
        }
        Ok(Self {
            shared: shared()?,
            main: id(ROOT)?,
            texts,
            marks,
        })
    }

    pub fn marks(&self, file: FileId) -> &[Mark] {
        self.marks.get(&file).map_or(&[], Vec::as_slice)
    }
}

impl World for Sources {
    fn library(&self) -> &LazyHash<Library> {
        &self.shared.library
    }

    fn book(&self) -> &LazyHash<FontBook> {
        &self.shared.book
    }

    fn main(&self) -> FileId {
        self.main
    }

    fn source(&self, file: FileId) -> FileResult<Source> {
        self.texts
            .get(&file)
            .cloned()
            .ok_or_else(|| FileError::NotFound(PathBuf::from(format!("{:?}", file.vpath()))))
    }

    fn file(&self, file: FileId) -> FileResult<Bytes> {
        let path = file.vpath().get_with_slash();
        if RASTERS
            .iter()
            .any(|kind| path.to_lowercase().ends_with(kind))
        {
            return self
                .shared
                .rasters
                .lock()
                .expect("the raster cache is not poisoned")
                .entry(file)
                .or_insert_with(|| {
                    std::fs::read(path)
                        .map(Bytes::new)
                        .map_err(|error| FileError::from_io(error, Path::new(path)))
                })
                .clone();
        }
        self.source(file)
            .map(|source| Bytes::from_string(source.text().to_string()))
    }

    fn font(&self, index: usize) -> Option<Font> {
        self.shared.fonts.get(index).cloned()
    }

    fn today(&self, _offset: Option<Duration>) -> Option<Datetime> {
        None
    }
}
