use anyhow::{anyhow, bail, Context, Result};
use sha2::{Digest, Sha256};
use std::fs;
use std::path::{Path, PathBuf};
use std::thread;

pub(crate) fn read(path: &Path) -> Result<String> {
    fs::read_to_string(path).with_context(|| format!("reading {}", path.display()))
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct EditionId(String);

pub fn edition_names(root: &Path) -> Result<Vec<String>> {
    let editions = root.join("editions");
    let mut names = Vec::new();
    if editions.is_dir() {
        for entry in
            fs::read_dir(&editions).with_context(|| format!("reading {}", editions.display()))?
        {
            let entry = entry?;
            if entry.path().is_dir() {
                names.push(entry.file_name().to_string_lossy().to_string());
            }
        }
    }
    names.sort();
    Ok(names)
}

impl EditionId {
    pub fn pick(given: &str, names: impl IntoIterator<Item = String>) -> Result<Self> {
        let mut names: Vec<String> = names.into_iter().collect();
        names.sort();
        names.dedup();
        if names.iter().any(|n| n == given) {
            return Ok(Self(given.to_string()));
        }
        let mut hits: Vec<String> = names.into_iter().filter(|n| n.starts_with(given)).collect();
        match hits.len() {
            0 => bail!("no edition '{given}': no id or unambiguous prefix of one"),
            1 => Ok(Self(hits.remove(0))),
            _ => bail!("ambiguous edition '{given}': matches {}", hits.join(", ")),
        }
    }

    pub fn resolve(root: &Path, given: &str) -> Result<Self> {
        Self::pick(given, edition_names(root)?)
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }
}

pub(crate) fn prompts_path(file: &str) -> PathBuf {
    PathBuf::from("prompts").join(file)
}

pub(crate) fn escape_html(value: &str) -> String {
    value
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
}

pub(crate) fn sha256_hex(bytes: impl AsRef<[u8]>) -> String {
    hex::encode(Sha256::digest(bytes))
}

pub(crate) fn parallel<T: Sync, R: Send>(
    items: &[T],
    job: impl Fn(&T) -> Result<R> + Sync,
) -> Vec<Result<R>> {
    let job = &job;
    thread::scope(|scope| {
        let handles: Vec<_> = items
            .iter()
            .map(|item| scope.spawn(move || job(item)))
            .collect();
        handles
            .into_iter()
            .map(|handle| {
                handle
                    .join()
                    .unwrap_or_else(|_| Err(anyhow!("worker thread panicked")))
            })
            .collect()
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn root_with(names: &[&str]) -> PathBuf {
        let root = std::env::temp_dir().join(format!(
            "mag-edid-{}-{}",
            std::process::id(),
            names.join("-")
        ));
        for n in names {
            fs::create_dir_all(root.join("editions").join(n)).unwrap();
        }
        root
    }

    #[test]
    fn exact_id_wins_over_longer_ids() {
        let root = root_with(&["012", "0120"]);
        assert_eq!(EditionId::resolve(&root, "012").unwrap().as_str(), "012");
    }

    #[test]
    fn ambiguous_prefix_is_refused_with_candidates() {
        let root = root_with(&["010", "011", "012"]);
        let err = EditionId::resolve(&root, "01").unwrap_err().to_string();
        assert!(
            err.contains("ambiguous") && err.contains("010, 011, 012"),
            "{err}"
        );
        assert_eq!(EditionId::resolve(&root, "011").unwrap().as_str(), "011");
    }

    #[test]
    fn unique_prefix_resolves_and_unknown_id_is_refused() {
        let root = root_with(&["010", "011"]);
        assert_eq!(EditionId::resolve(&root, "010").unwrap().as_str(), "010");
        let err = EditionId::resolve(&root, "099").unwrap_err().to_string();
        assert!(err.contains("no edition '099'"), "{err}");
    }
}
