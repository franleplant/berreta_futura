use std::process::Command;

#[test]
fn no_comments_in_codebase() {
    let root = concat!(env!("CARGO_MANIFEST_DIR"), "/..");
    let out = Command::new("python3")
        .arg("tools/nocomments.py")
        .current_dir(root)
        .output()
        .expect("python3 tools/nocomments.py");
    assert!(
        out.status.success(),
        "{}",
        String::from_utf8_lossy(&out.stdout)
    );
}
