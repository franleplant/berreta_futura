use sha2::{Digest, Sha256};
use std::path::PathBuf;
use std::sync::OnceLock;

#[derive(Clone, Copy, PartialEq)]
pub enum Mode {
    Committed,
    Live,
    Write,
}

pub fn mode() -> Mode {
    static MODE: OnceLock<Mode> = OnceLock::new();
    *MODE.get_or_init(|| {
        let mode = match std::env::var("MAG_ORACLE").as_deref() {
            Err(_) => Mode::Committed,
            Ok("live") => Mode::Live,
            Ok("write") => Mode::Write,
            Ok(other) => panic!("MAG_ORACLE={other}: use live or write"),
        };
        let name = [
            "committed expectation",
            "live python",
            "live python, rewriting",
        ];
        eprintln!("ORACLE MODE: {}", name[mode as usize]);
        mode
    })
}

pub fn live() -> bool {
    mode() != Mode::Committed
}

pub fn sha256(bytes: &[u8]) -> String {
    hex::encode(Sha256::digest(bytes))
}

pub fn expectation(name: &str, oracle: impl FnOnce() -> String) -> String {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("tests")
        .join(name);
    let committed = || std::fs::read_to_string(&path).unwrap_or_default();
    match mode() {
        Mode::Committed => {
            let text = committed();
            assert!(!text.is_empty(), "{name} is missing: run MAG_ORACLE=write");
            text
        }
        Mode::Live => {
            let fresh = oracle();
            assert!(
                fresh == committed(),
                "{name} no longer equals the live oracle: run MAG_ORACLE=write"
            );
            eprintln!("ORACLE CHECK: {name} equals the live oracle");
            fresh
        }
        Mode::Write => {
            let fresh = oracle();
            std::fs::write(&path, &fresh).expect("the expectation is writable");
            eprintln!("ORACLE WRITE: {name}");
            fresh
        }
    }
}

pub fn snapshot() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/repo_snapshot")
}

const PINS: &str = include_str!("../pinned_inputs.sha256");

pub fn pinned_paths() -> impl Iterator<Item = &'static str> {
    PINS.lines()
        .filter_map(|line| line.split_once("  ").map(|(_, path)| path))
}

pub fn pinned(test: &str, path: &str) -> PathBuf {
    let pin = PINS
        .lines()
        .find_map(|line| line.split_once("  ").filter(|(_, pinned)| *pinned == path))
        .unwrap_or_else(|| panic!("{test}: {path} is not in mag/tests/pinned_inputs.sha256"));
    let live = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join(path);
    let found = std::fs::read(&live).map_or_else(|error| error.to_string(), |bytes| sha256(&bytes));
    assert!(
        found == pin.0,
        "{test}: pinned input {path} changed (found {found}, pinned {}); its committed expectation was recorded from the pinned bytes",
        pin.0
    );
    live
}
