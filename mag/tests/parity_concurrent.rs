mod parity_fixture;

use parity_fixture::{leg, root};
use std::path::Path;
use std::process::{Child, Command};

fn spawn(label: &str, out: &Path, a: &Path, b: &Path) -> Child {
    Command::new(env!("CARGO_BIN_EXE_mag"))
        .current_dir(root())
        .env("MAG_PARITY_OUT_DIR", out)
        .args(["parity", label, "--pre-rendered"])
        .args([a, b])
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped())
        .spawn()
        .expect("mag parity")
}

fn finish(child: Child) -> (bool, String) {
    let out = child.wait_with_output().expect("wait");
    (
        out.status.success(),
        String::from_utf8_lossy(&out.stderr).into_owned(),
    )
}

fn verdict(out: &Path) -> String {
    std::fs::read_to_string(out.join("verdict.json")).expect("verdict.json")
}

fn tier_e(raw: &str) -> String {
    let doc: serde_json::Value = serde_json::from_str(raw).expect("verdict json");
    doc["tier_e"]["display_list"]["status"]
        .as_str()
        .expect("display list status")
        .to_string()
}

#[test]
fn concurrent_runs_in_their_own_out_dirs_do_not_corrupt_each_others_verdicts() {
    let dir = root().join("output/parity-concurrent");
    let (equal, differing) = (leg(&dir, "equal", 0.0), leg(&dir, "differing", 4.0));
    let (out_same, out_diff) = (dir.join("out-same"), dir.join("out-diff"));

    let serial_same = {
        let (ok, err) = finish(spawn("conc", &out_same, &equal, &equal));
        assert!(ok, "equal pair must pass: {err}");
        verdict(&out_same)
    };
    let serial_diff = {
        let (ok, _) = finish(spawn("conc", &out_diff, &equal, &differing));
        assert!(!ok, "differing pair must exit nonzero");
        verdict(&out_diff)
    };
    assert_eq!(tier_e(&serial_same), "pass");
    assert_eq!(tier_e(&serial_diff), "fail");

    let (x, y) = (
        spawn("conc", &out_same, &equal, &equal),
        spawn("conc", &out_diff, &equal, &differing),
    );
    let (ok_x, err_x) = finish(x);
    let (ok_y, _) = finish(y);
    assert!(
        ok_x,
        "equal pair must still pass under concurrency: {err_x}"
    );
    assert!(!ok_y, "differing pair must still fail under concurrency");
    assert_eq!(
        verdict(&out_same),
        serial_same,
        "concurrent run wrote another run's verdict into out-same"
    );
    assert_eq!(
        verdict(&out_diff),
        serial_diff,
        "concurrent run wrote another run's verdict into out-diff"
    );
}

#[test]
fn two_runs_sharing_one_out_dir_refuse_rather_than_overwrite() {
    let dir = root().join("output/parity-shared");
    let (equal, differing) = (leg(&dir, "equal", 0.0), leg(&dir, "differing", 4.0));
    let shared = dir.join("out");

    let (x, y) = (
        spawn("shared", &shared, &equal, &equal),
        spawn("shared", &shared, &equal, &differing),
    );
    let results = [finish(x), finish(y)];
    let refused: Vec<&String> = results
        .iter()
        .map(|(_, err)| err)
        .filter(|err| err.contains("another mag parity run holds"))
        .collect();
    assert_eq!(
        refused.len(),
        1,
        "exactly one of two runs sharing an out dir must be refused: {results:?}"
    );
    assert!(
        refused[0].contains("MAG_PARITY_OUT_DIR"),
        "the refusal must name the override: {}",
        refused[0]
    );
    assert!(
        !shared.join("run.lock").exists(),
        "the lock must be released when the run ends"
    );
}
