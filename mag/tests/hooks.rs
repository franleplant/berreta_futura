use std::process::Command;

#[test]
fn git_hooks_are_installed() {
    let root = concat!(env!("CARGO_MANIFEST_DIR"), "/..");
    let out = Command::new("git")
        .args(["config", "core.hooksPath"])
        .current_dir(root)
        .output()
        .expect("git config");
    assert_eq!(
        String::from_utf8_lossy(&out.stdout).trim(),
        ".githooks",
        "run: git config core.hooksPath .githooks"
    );
}
