use crate::model::manifest::art_slots;
use crate::model::spec::EditionFile;
use anyhow::{ensure, Result};
use std::collections::BTreeSet;
use std::path::{Path, PathBuf};

const ROUNDS: &str = "art/rounds/";

pub fn round_paths(edition: &EditionFile) -> Vec<String> {
    art_slots(edition)
        .into_iter()
        .map(|(_, path)| path)
        .filter(|path| path.contains(ROUNDS))
        .collect()
}

pub fn pick_path(path: &str) -> String {
    let (head, rest) = path.split_once(ROUNDS).unwrap_or(("", path));
    let stem = Path::new(rest).file_stem().unwrap_or_default();
    format!("{head}art/picks/{}.jpg", stem.to_string_lossy())
}

fn resolve(raw: &str, edition_dir: &Path) -> PathBuf {
    match raw.starts_with("editions/") {
        true => PathBuf::from(raw),
        false => edition_dir.join(raw),
    }
}

pub fn promote(edition_dir: &Path) -> Result<Vec<(String, String)>> {
    let yaml_path = edition_dir.join("edition.yaml");
    let mut text = std::fs::read_to_string(&yaml_path)?;
    let rounds: BTreeSet<String> = round_paths(&serde_norway::from_str(&text)?)
        .into_iter()
        .collect();
    let moves: Vec<(String, String)> = rounds.into_iter().map(|p| (pick_path(&p), p)).collect();
    let picks: BTreeSet<&String> = moves.iter().map(|(pick, _)| pick).collect();
    ensure!(
        picks.len() == moves.len(),
        "two picked candidates share a file name; rename one before promoting"
    );
    for (pick, round) in &moves {
        crate::typeset::art::write_jpeg(&resolve(round, edition_dir), &resolve(pick, edition_dir))?;
        text = text.replace(round.as_str(), pick);
    }
    if !moves.is_empty() {
        std::fs::write(&yaml_path, text)?;
    }
    Ok(moves)
}

pub fn picked_from(pick: &str, candidate: &Path) -> bool {
    std::fs::read(pick).is_ok_and(|bytes| {
        crate::typeset::art::jpeg_bytes(candidate).is_ok_and(|fresh| fresh == bytes)
    })
}

pub fn refuse_rounds(edition_yaml: &EditionFile, edition: &str) -> Result<()> {
    let rounds = round_paths(edition_yaml);
    ensure!(
        rounds.is_empty(),
        "edition.yaml names {} candidate(s) under art/rounds/, which stay out of git (first: {}); run: mag art {edition} --promote",
        rounds.len(),
        rounds.first().map_or("", String::as_str)
    );
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    const YAML: &str = "# keep me\nid: '099'\ncover:\n  art_path: art/rounds/r1/cover-x-v2.png # pick\narticles:\n- id: a\n  opener_art:\n    path: art/rounds/r1/opener-a-v1.png\n  tail_art_path: art/picks/tail-a-v3.jpg\nclosing_plates:\n- title: Night\n  art_path: art/rounds/r2/closing-night-v4.png\n";

    const PROMOTED: &str = "# keep me\nid: '099'\ncover:\n  art_path: art/picks/cover-x-v2.jpg # pick\narticles:\n- id: a\n  opener_art:\n    path: art/picks/opener-a-v1.jpg\n  tail_art_path: art/picks/tail-a-v3.jpg\nclosing_plates:\n- title: Night\n  art_path: art/picks/closing-night-v4.jpg\n";

    fn edition() -> PathBuf {
        let dir = std::env::temp_dir().join(format!("mag-picks-{}", std::process::id()));
        for (name, size) in [
            ("r1/cover-x-v2", 640),
            ("r1/opener-a-v1", 320),
            ("r2/closing-night-v4", 200),
        ] {
            let path = dir.join(format!("art/rounds/{name}.png"));
            std::fs::create_dir_all(path.parent().unwrap()).unwrap();
            image::RgbaImage::from_fn(size, size / 2, |x, y| {
                image::Rgba([(x % 256) as u8, (y % 256) as u8, ((x ^ y) % 256) as u8, 255])
            })
            .save(path)
            .unwrap();
        }
        std::fs::write(dir.join("edition.yaml"), YAML).unwrap();
        dir
    }

    #[test]
    fn promotion_rewrites_only_round_paths_and_runs_once() {
        let dir = edition();
        assert_eq!(promote(&dir).unwrap().len(), 3);
        let text = std::fs::read_to_string(dir.join("edition.yaml")).unwrap();
        assert_eq!(text, PROMOTED);
        let cover = dir.join("art/picks/cover-x-v2.jpg");
        let source = dir.join("art/rounds/r1/cover-x-v2.png");
        let staged = dir.join("staged");
        crate::typeset::art::write_jpeg(&source, &staged).unwrap();
        assert_eq!(
            std::fs::read(&cover).unwrap(),
            std::fs::read(&staged).unwrap()
        );
        assert!(
            std::fs::metadata(&cover).unwrap().len() < std::fs::metadata(&source).unwrap().len()
        );
        assert_eq!(
            image::open(&cover).unwrap().to_rgb8().dimensions(),
            (640, 320)
        );
        let cover_pick = cover.to_string_lossy();
        assert!(picked_from(&cover_pick, &source));
        assert!(!picked_from(
            &cover_pick,
            &dir.join("art/rounds/r1/opener-a-v1.png")
        ));
        assert!(promote(&dir).unwrap().is_empty());
        assert_eq!(
            std::fs::read_to_string(dir.join("edition.yaml")).unwrap(),
            text
        );
        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn render_refuses_round_paths_with_the_promote_command() {
        let yaml = serde_norway::from_str(YAML).unwrap();
        let error = refuse_rounds(&yaml, "099").unwrap_err().to_string();
        assert!(error.contains("names 3 candidate(s)"), "{error}");
        assert!(error.ends_with("run: mag art 099 --promote"), "{error}");
        assert!(refuse_rounds(&serde_norway::from_str(PROMOTED).unwrap(), "099").is_ok());
    }

    #[test]
    fn a_pick_keeps_the_candidate_stem_and_edition_prefix() {
        assert_eq!(
            pick_path("editions/012/art/rounds/2026-10-01T14-56-14/tail-tla-v2.png"),
            "editions/012/art/picks/tail-tla-v2.jpg"
        );
    }
}
