use mag::critic::inspect;
use mag::critic::metrics;
use sha2::{Digest, Sha256};
use std::path::{Path, PathBuf};

fn manifest() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).to_path_buf()
}

fn fixtures() -> PathBuf {
    manifest().join("tests/critic_inspect_fixtures")
}

fn digest(data: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(data);
    hex::encode(hasher.finalize())
}

fn scratch(tag: &str) -> PathBuf {
    let stamp = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .expect("a clock after 1970")
        .as_nanos();
    let path = std::env::temp_dir().join(format!("wp53bii-{tag}-{stamp}"));
    std::fs::create_dir_all(&path).expect("the scratch directory is writable");
    path
}

fn rendered_digests(directory: &Path) -> Vec<(String, String)> {
    let mut entries: Vec<PathBuf> = std::fs::read_dir(directory)
        .expect("the render directory is readable")
        .map(|entry| entry.expect("an entry").path())
        .collect();
    entries.sort();
    entries
        .iter()
        .map(|path| {
            (
                path.file_name()
                    .and_then(|name| name.to_str())
                    .expect("a utf-8 name")
                    .to_string(),
                digest(&std::fs::read(path).expect("the raster is readable")),
            )
        })
        .collect()
}

#[test]
fn render_pages_output_does_not_depend_on_the_shard_count() {
    let pdf = fixtures().join("pages12.pdf");
    let mut seen = vec![];
    for shards in [Some(1), Some(3), Some(5), Some(12), None] {
        let directory = scratch(&format!("shards-{shards:?}"));
        inspect::render_pages(&pdf, &directory, shards).expect("rasterization succeeds");
        seen.push(rendered_digests(&directory));
    }
    for (index, run) in seen.iter().enumerate().skip(1) {
        assert_eq!(
            run, &seen[0],
            "shard configuration {index} changed the output"
        );
    }
    assert_eq!(seen[0].len(), 12, "the fixture rasterizes twelve pages");
}

#[test]
fn render_pages_reports_a_rasterization_failure() {
    let directory = scratch("failure");
    let broken = directory.join("not-a.pdf");
    std::fs::write(&broken, b"this is not a pdf").expect("the decoy is writable");
    let error = inspect::render_pages(&broken, &directory.join("out"), None)
        .expect_err("poppler must reject the decoy");
    assert!(
        error
            .to_string()
            .starts_with("Could not rasterize reader PDF for criticism: "),
        "unexpected message: {error}"
    );
}

#[test]
fn differencing_pages_of_different_sizes_fails_rather_than_truncating() {
    let square = metrics::decode_rgb(&fixtures().join("luma_pins.png")).expect("decodes");
    let strip = metrics::decode_rgb(&fixtures().join("threshold_bands.png")).expect("decodes");
    assert!(inspect::difference(&square, &strip).is_err());
}
