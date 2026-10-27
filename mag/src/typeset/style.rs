use std::sync::atomic::{AtomicBool, Ordering};

static BOOK: AtomicBool = AtomicBool::new(false);

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Style {
    Classic,
    Book,
}

impl Style {
    pub fn of(typesetting: Option<&str>) -> Self {
        match typesetting.map(str::trim) {
            Some("book") => Self::Book,
            _ => Self::Classic,
        }
    }
}

pub fn set(style: Style) {
    BOOK.store(style == Style::Book, Ordering::SeqCst);
}

pub fn current() -> Style {
    match BOOK.load(Ordering::SeqCst) {
        true => Style::Book,
        false => Style::Classic,
    }
}
