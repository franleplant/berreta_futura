use crate::typeset::content::{File, Tree};
use anyhow::{Context, Result};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use typst::diag::{FileError, FileResult};
use typst::foundations::{Bytes, Datetime, Duration};
use typst::text::{Font, FontBook};
use typst::utils::LazyHash;
use typst::{Library, LibraryExt, World};
use typst_syntax::{FileId, RootedPath, Source, VirtualPath, VirtualRoot};

pub const ROOT: &str = "/root.typ";
pub const TEMPLATE: &str = "/template.typ";
pub const PRELUDE: &str = "#import \"/template.typ\": *\n";

pub struct Sources {
    library: LazyHash<Library>,
    book: LazyHash<FontBook>,
    fonts: Vec<Font>,
    main: FileId,
    texts: HashMap<FileId, Source>,
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

impl Sources {
    pub fn new(tree: &Tree, template: &str, root: &str, font_dir: &Path) -> Result<Self> {
        let fonts = faces(font_dir)?;
        let mut texts = HashMap::new();
        for File { path, source } in &tree.files {
            let file = id(&format!("/{path}"))?;
            texts.insert(file, Source::new(file, format!("{PRELUDE}{source}")));
        }
        for (path, text) in [(TEMPLATE, template), (ROOT, root)] {
            let file = id(path)?;
            texts.insert(file, Source::new(file, text.to_string()));
        }
        Ok(Self {
            library: LazyHash::new(Library::default()),
            book: LazyHash::new(FontBook::from_fonts(&fonts)),
            fonts,
            main: id(ROOT)?,
            texts,
        })
    }
}

impl World for Sources {
    fn library(&self) -> &LazyHash<Library> {
        &self.library
    }

    fn book(&self) -> &LazyHash<FontBook> {
        &self.book
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
        self.source(file)
            .map(|source| Bytes::from_string(source.text().to_string()))
    }

    fn font(&self, index: usize) -> Option<Font> {
        self.fonts.get(index).cloned()
    }

    fn today(&self, _offset: Option<Duration>) -> Option<Datetime> {
        None
    }
}
