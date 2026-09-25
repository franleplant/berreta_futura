use sha2::{Digest, Sha256};
use std::path::PathBuf;

pub fn sha256(bytes: &[u8]) -> String {
    hex::encode(Sha256::digest(bytes))
}

pub fn expectation(name: &str) -> String {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("tests")
        .join(name);
    let text = std::fs::read_to_string(&path).unwrap_or_default();
    assert!(!text.is_empty(), "{name} is missing");
    text
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
