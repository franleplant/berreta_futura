use anyhow::{bail, Context, Result};
use std::fs;
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::process::{Command, ExitStatus, Stdio};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Condvar, Mutex};
use std::thread;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

pub const CALL_RETRIES: u32 = 2;
pub const CONCURRENCY: usize = 8;

pub fn call_timeout_secs_for(spec: Option<&ModelSpec>) -> u64 {
    if let Some(v) = std::env::var("MAG_CALL_TIMEOUT_SECS")
        .ok()
        .and_then(|v| v.parse().ok())
    {
        return v;
    }
    match spec.and_then(|s| s.effort.as_deref()) {
        Some("max" | "xhigh") => 2700,
        Some("high") => 1500,
        _ => 600,
    }
}

fn ollama_num_ctx() -> u64 {
    std::env::var("MAG_OLLAMA_NUM_CTX")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(49152)
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Backend {
    Claude,
    Ollama,
    Codex,
}

#[derive(Debug, Clone)]
pub struct ModelSpec {
    pub backend: Backend,
    pub model: String,

    pub effort: Option<String>,

    pub full: String,
}

impl ModelSpec {
    pub fn parse(spec: &str) -> Result<Self> {
        let (backend_str, model) = match spec.split_once(':') {
            Some((b, m)) => (b, m.to_string()),
            None => ("claude", spec.to_string()),
        };
        let backend = match backend_str {
            "claude" => Backend::Claude,
            "ollama" => Backend::Ollama,
            "codex" => Backend::Codex,
            other => bail!("unknown backend '{other}' in model spec '{spec}'"),
        };
        let (model, effort) = match model.split_once('@') {
            Some((m, e)) => (m.to_string(), Some(e.to_string())),
            None => (model, None),
        };
        if model.is_empty() {
            bail!("model spec '{spec}' has no model name");
        }
        if effort.is_some() && backend != Backend::Codex {
            bail!("reasoning effort is only supported on the codex backend: '{spec}'");
        }
        Ok(Self {
            backend,
            model,
            effort,
            full: spec.to_string(),
        })
    }
}

pub fn create_fresh_dir(path: &Path) -> Result<()> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::create_dir(path).with_context(|| {
        format!(
            "creating {} (a directory by that name may already exist; retry in a second)",
            path.display()
        )
    })
}

pub fn write_atomic(path: impl AsRef<Path>, bytes: impl AsRef<[u8]>) -> Result<()> {
    let path = path.as_ref();
    let name = path
        .file_name()
        .map_or_else(String::new, |n| n.to_string_lossy().into_owned());
    let tmp = path.with_file_name(format!(".{name}.{}.tmp", std::process::id()));
    fs::write(&tmp, bytes)
        .and_then(|()| fs::rename(&tmp, path))
        .inspect_err(|_| {
            let _ = fs::remove_file(&tmp);
        })
        .with_context(|| format!("writing {}", path.display()))
}

pub fn now_stamp() -> String {
    let secs = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("system clock before 1970")
        .as_secs();
    format_utc_stamp(secs)
}

fn format_utc_stamp(secs: u64) -> String {
    let days = (secs / 86400) as i64;
    let rem = secs % 86400;
    let (h, m, s) = (rem / 3600, (rem % 3600) / 60, rem % 60);
    let (y, mo, d) = civil_from_days(days);
    format!("{y:04}-{mo:02}-{d:02}T{h:02}-{m:02}-{s:02}")
}

fn civil_from_days(z: i64) -> (i64, u32, u32) {
    let z = z + 719468;
    let era = if z >= 0 { z } else { z - 146096 } / 146097;
    let doe = z - era * 146097;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = (doy - (153 * mp + 2) / 5 + 1) as u32;
    let m = if mp < 10 { mp + 3 } else { mp - 9 } as u32;
    let y = if m <= 2 { y + 1 } else { y };
    (y, m, d)
}

fn round1(x: f64) -> f64 {
    (x * 10.0).round() / 10.0
}

fn round4(x: f64) -> f64 {
    (x * 10000.0).round() / 10000.0
}

struct CodexScratch {
    dir: PathBuf,
    out: PathBuf,
}

impl CodexScratch {
    fn new() -> Result<Self, String> {
        static N: AtomicUsize = AtomicUsize::new(0);
        let n = N.fetch_add(1, Ordering::Relaxed);
        let dir = std::env::temp_dir().join(format!("mag-codex-{}-{n}", std::process::id()));
        std::fs::create_dir_all(&dir).map_err(|e| format!("creating codex scratch dir: {e}"))?;
        Ok(Self {
            out: dir.join("last-message.txt"),
            dir,
        })
    }
}

impl Drop for CodexScratch {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.dir);
    }
}

struct Semaphore {
    count: Mutex<usize>,
    cond: Condvar,
    max: usize,
}

struct Permit<'a>(&'a Semaphore);

impl Semaphore {
    fn new(max: usize) -> Self {
        Self {
            count: Mutex::new(0),
            cond: Condvar::new(),
            max,
        }
    }

    fn acquire(&self) -> Permit<'_> {
        let mut count = self.count.lock().unwrap();
        while *count >= self.max {
            count = self.cond.wait(count).unwrap();
        }
        *count += 1;
        Permit(self)
    }
}

impl Drop for Permit<'_> {
    fn drop(&mut self) {
        *self.0.count.lock().unwrap() -= 1;
        self.0.cond.notify_one();
    }
}

enum CallError {
    Transport(String),
    Timeout(String),
}

type Reply = (String, f64, f64);

pub struct Caller {
    sem: Semaphore,
    log_path: std::path::PathBuf,
    log_lock: Mutex<()>,
    root: std::path::PathBuf,
    total_cost: Mutex<f64>,
    calls: AtomicUsize,
    backoff: Duration,
}

impl Caller {
    pub fn new(run_dir: &std::path::Path) -> Self {
        Self {
            sem: Semaphore::new(CONCURRENCY),
            log_path: run_dir.join("log.jsonl"),
            log_lock: Mutex::new(()),
            root: std::env::current_dir().unwrap_or_else(|_| ".".into()),
            total_cost: Mutex::new(0.0),
            calls: AtomicUsize::new(0),
            backoff: Duration::from_secs(2),
        }
    }

    pub fn total_cost(&self) -> f64 {
        *self.total_cost.lock().unwrap()
    }

    pub fn calls(&self) -> usize {
        self.calls.load(Ordering::SeqCst)
    }

    pub fn call_with_parse<T>(
        &self,
        label: &str,
        spec: &ModelSpec,
        prompt: &str,
        parse: impl Fn(&str) -> Result<T>,
    ) -> Result<T> {
        self.call_with_parse_images(label, spec, prompt, &[], parse)
    }

    pub fn call_with_parse_images<T>(
        &self,
        label: &str,
        spec: &ModelSpec,
        prompt: &str,
        images: &[PathBuf],
        parse: impl Fn(&str) -> Result<T>,
    ) -> Result<T> {
        if !images.is_empty() && spec.backend == Backend::Ollama {
            bail!("{label}: the ollama backend is not wired for image input");
        }
        self.retry(label, spec, prompt, parse, |sent| {
            self.run_once(spec, sent, images)
        })
    }

    fn retry<T>(
        &self,
        label: &str,
        spec: &ModelSpec,
        prompt: &str,
        parse: impl Fn(&str) -> Result<T>,
        run: impl Fn(&str) -> Result<Reply, CallError>,
    ) -> Result<T> {
        let mut rejection: Option<String> = None;
        let mut transport: Option<String> = None;
        let mut last_reply: Option<String> = None;
        for attempt in 0..=CALL_RETRIES {
            let sent = match &rejection {
                None => prompt.to_string(),
                Some(e) => format!(
                    "{prompt}\n\nYour previous reply was rejected: {e}. Reply again \
                     following the required output format exactly."
                ),
            };
            let (result_text, cost, seconds) = match run(&sent) {
                Ok(v) => v,
                Err(CallError::Timeout(e)) => bail!("{label}: model call timed out: {e}"),
                Err(CallError::Transport(e)) => {
                    transport = Some(e);
                    if attempt < CALL_RETRIES {
                        thread::sleep(self.backoff * 2u32.pow(attempt));
                    }
                    continue;
                }
            };
            transport = None;
            *self.total_cost.lock().unwrap() += cost;
            self.calls.fetch_add(1, Ordering::SeqCst);
            match parse(&result_text) {
                Ok(parsed) => {
                    self.log_and_print(label, spec, seconds, cost, attempt)?;
                    return Ok(parsed);
                }
                Err(e) => {
                    rejection = Some(e.to_string());
                    last_reply = Some(result_text);
                }
            }
        }
        let saved = last_reply
            .as_ref()
            .and_then(|reply| self.save_failed_reply(label, spec, reply));
        bail!(
            "{label}: model call failed after retries: {}{}",
            transport
                .or(rejection)
                .unwrap_or_else(|| "unknown error".to_string()),
            match saved {
                Some(path) => format!(" (unparsed reply saved to {})", path.display()),
                None => String::new(),
            }
        )
    }

    fn save_failed_reply(&self, label: &str, spec: &ModelSpec, reply: &str) -> Option<PathBuf> {
        let dir = self.log_path.parent()?.join("failed-replies");
        std::fs::create_dir_all(&dir).ok()?;
        let slug: String = label
            .chars()
            .map(|c| if c.is_ascii_alphanumeric() { c } else { '-' })
            .collect();
        let path = dir.join(format!("{slug}.txt"));
        let header = format!("# {label}\n# model: {}\n\n", spec.full);
        std::fs::write(&path, header + reply).ok()?;
        Some(path)
    }

    fn log_and_print(
        &self,
        label: &str,
        spec: &ModelSpec,
        seconds: f64,
        cost: f64,
        attempt: u32,
    ) -> Result<()> {
        let line = serde_json::json!({
            "label": label,
            "model": spec.full,
            "seconds": round1(seconds),
            "usd": round4(cost),
            "attempt": attempt,
        });
        {
            let _guard = self.log_lock.lock().unwrap();
            let mut f = std::fs::OpenOptions::new()
                .create(true)
                .append(true)
                .open(&self.log_path)
                .with_context(|| format!("opening {}", self.log_path.display()))?;
            writeln!(f, "{line}")?;
        }
        println!("    {label} [{}] {seconds:.0}s ${cost:.2}", spec.full);
        std::io::stdout().flush().ok();
        Ok(())
    }

    fn run_once(
        &self,
        spec: &ModelSpec,
        prompt: &str,
        images: &[PathBuf],
    ) -> Result<Reply, CallError> {
        let _permit = self.sem.acquire();
        let started = Instant::now();
        let scratch = match spec.backend {
            Backend::Codex => Some(CodexScratch::new().map_err(CallError::Transport)?),
            _ => None,
        };
        let cmd = self.backend_command(spec, images, scratch.as_ref());
        let timeout = Duration::from_secs(call_timeout_secs_for(Some(spec)));
        let (status, out, err) = run_child(cmd, stdin_payload(spec, prompt), timeout)?;
        let seconds = started.elapsed().as_secs_f64();
        let (result, cost) = match spec.backend {
            Backend::Claude => parse_claude(&out, &err, status),
            Backend::Codex => {
                parse_codex(&scratch.as_ref().expect("codex scratch").out, &err, status)
            }
            Backend::Ollama => parse_ollama(&out, &err, status),
        }
        .map_err(CallError::Transport)?;
        Ok((result, cost, seconds))
    }

    fn backend_command(
        &self,
        spec: &ModelSpec,
        images: &[PathBuf],
        scratch: Option<&CodexScratch>,
    ) -> Command {
        let mut cmd = match spec.backend {
            Backend::Claude => {
                let mut c = Command::new("claude");
                c.args([
                    "-p",
                    "--model",
                    &spec.model,
                    "--output-format",
                    "json",
                    "--no-session-persistence",
                ]);
                if images.is_empty() {
                    c.args(["--disallowedTools", "*"]);
                } else {
                    c.args(["--allowedTools", "Read"]);
                }
                c
            }
            Backend::Codex => {
                let mut c = Command::new("codex");
                c.args([
                    "exec",
                    "--model",
                    &spec.model,
                    "--sandbox",
                    "read-only",
                    "--skip-git-repo-check",
                    "--color",
                    "never",
                ]);
                if let Some(effort) = &spec.effort {
                    c.arg("-c")
                        .arg(format!("model_reasoning_effort=\"{effort}\""));
                }
                for img in images {
                    c.arg(format!("--image={}", img.display()));
                }
                c.arg("-o");
                c.arg(&scratch.expect("codex scratch").out);
                c.arg("-");
                c
            }
            Backend::Ollama => {
                let mut c = Command::new("curl");
                c.args([
                    "-s",
                    "--max-time",
                    &call_timeout_secs_for(Some(spec)).to_string(),
                    "-X",
                    "POST",
                    "http://localhost:11434/api/generate",
                    "-d",
                    "@-",
                ]);
                c
            }
        };
        cmd.current_dir(match scratch {
            Some(s) => s.dir.as_path(),
            None => self.root.as_path(),
        })
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
        cmd
    }
}

fn stdin_payload(spec: &ModelSpec, prompt: &str) -> String {
    match spec.backend {
        Backend::Claude | Backend::Codex => prompt.to_string(),
        Backend::Ollama => serde_json::json!({
            "model": spec.model,
            "prompt": prompt,
            "stream": false,
            "keep_alive": "2h",
            "options": {"num_ctx": ollama_num_ctx()},
        })
        .to_string(),
    }
}

fn drain<R: Read + Send + 'static>(mut pipe: R) -> thread::JoinHandle<Vec<u8>> {
    thread::spawn(move || {
        let mut buf = Vec::new();
        let _ = pipe.read_to_end(&mut buf);
        buf
    })
}

fn descendants(pid: u32) -> Vec<u32> {
    let out = Command::new("pgrep")
        .args(["-P", &pid.to_string()])
        .stderr(Stdio::null())
        .output()
        .map(|o| o.stdout)
        .unwrap_or_default();
    let kids: Vec<u32> = String::from_utf8_lossy(&out)
        .split_whitespace()
        .filter_map(|p| p.parse().ok())
        .collect();
    kids.iter()
        .flat_map(|&kid| descendants(kid).into_iter().chain([kid]))
        .collect()
}

fn kill_descendants(pid: u32) {
    for victim in descendants(pid) {
        let _ = Command::new("kill")
            .args(["-KILL", &victim.to_string()])
            .stderr(Stdio::null())
            .status();
    }
}

fn run_child(
    mut cmd: Command,
    payload: String,
    timeout: Duration,
) -> Result<(ExitStatus, Vec<u8>, Vec<u8>), CallError> {
    let transport = |what: &str, e: std::io::Error| CallError::Transport(format!("{what}: {e}"));
    let mut child = cmd.spawn().map_err(|e| transport("failed to spawn", e))?;
    let mut stdin = child.stdin.take().expect("piped stdin");
    let writer = thread::spawn(move || {
        let _ = stdin.write_all(payload.as_bytes());
    });
    let stdout_reader = drain(child.stdout.take().expect("piped stdout"));
    let stderr_reader = drain(child.stderr.take().expect("piped stderr"));
    let started = Instant::now();
    let status = loop {
        match child.try_wait() {
            Ok(Some(status)) => break Some(status),
            Ok(None) if started.elapsed() > timeout => {
                kill_descendants(child.id());
                let _ = child.kill();
                let _ = child.wait();
                break None;
            }
            Ok(None) => thread::sleep(Duration::from_millis(50)),
            Err(e) => return Err(transport("wait failed", e)),
        }
    };
    let _ = writer.join();
    let out = stdout_reader.join().unwrap_or_default();
    let err = stderr_reader.join().unwrap_or_default();
    status
        .map(|s| (s, out, err))
        .ok_or_else(|| CallError::Timeout(format!("after {}s", timeout.as_secs())))
}

fn truncated(bytes: &[u8]) -> String {
    String::from_utf8_lossy(bytes).chars().take(300).collect()
}

fn parse_claude(out: &[u8], err: &[u8], status: ExitStatus) -> Result<(String, f64), String> {
    let data: serde_json::Value = serde_json::from_slice(out).map_err(|_| {
        format!(
            "non-JSON output (exit {}): {}",
            status.code().unwrap_or(-1),
            truncated(err)
        )
    })?;
    let is_error = data
        .get("is_error")
        .and_then(serde_json::Value::as_bool)
        .unwrap_or(false);
    let subtype = data.get("subtype").and_then(|v| v.as_str()).unwrap_or("");
    if is_error || subtype != "success" {
        let dumped: String = data.to_string().chars().take(300).collect();
        return Err(format!("call failed: {dumped}"));
    }
    let cost = data
        .get("total_cost_usd")
        .and_then(serde_json::Value::as_f64)
        .unwrap_or(0.0);
    let result = data
        .get("result")
        .and_then(|v| v.as_str())
        .ok_or_else(|| "call succeeded but had no 'result' field".to_string())?
        .to_string();
    Ok((result, cost))
}

fn parse_codex(
    out_path: &PathBuf,
    err: &[u8],
    status: ExitStatus,
) -> Result<(String, f64), String> {
    if !status.success() {
        return Err(format!("codex exited with {status}: {}", truncated(err)));
    }
    let reply = std::fs::read_to_string(out_path)
        .map_err(|e| format!("codex wrote no final message ({e})"))?;
    if reply.trim().is_empty() {
        return Err("codex final message was empty".to_string());
    }
    Ok((reply, 0.0))
}

fn parse_ollama(out: &[u8], err: &[u8], status: ExitStatus) -> Result<(String, f64), String> {
    if !status.success() {
        return Err(format!(
            "ollama call exited with {status}: {}",
            truncated(err)
        ));
    }
    let data: serde_json::Value = serde_json::from_slice(out)
        .map_err(|_| format!("non-JSON ollama response: {}", truncated(out)))?;
    if let Some(e) = data.get("error").and_then(|v| v.as_str()) {
        return Err(format!("ollama error: {e}"));
    }
    let result = data
        .get("response")
        .and_then(|v| v.as_str())
        .ok_or_else(|| "ollama reply had no 'response' field".to_string())?
        .to_string();
    Ok((result, 0.0))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn create_fresh_dir_fails_when_the_directory_exists() {
        let dir = std::env::temp_dir().join(format!("mag-fresh-{}", std::process::id()));
        let _ = fs::remove_dir_all(&dir);
        assert!(create_fresh_dir(&dir).is_ok());
        assert!(create_fresh_dir(&dir).is_err());
        fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn write_atomic_replaces_whole_files_and_leaves_no_partial() {
        let dir = scratch("atomic");
        let file = dir.join("a.yaml");
        write_atomic(&file, "one").unwrap();
        write_atomic(&file, "two").unwrap();
        assert_eq!(fs::read_to_string(&file).unwrap(), "two");
        let target = dir.join("taken");
        fs::create_dir(&target).unwrap();
        assert!(write_atomic(&target, "x").is_err());
        let mut names: Vec<_> = fs::read_dir(&dir)
            .unwrap()
            .map(|e| e.unwrap().file_name().into_string().unwrap())
            .collect();
        names.sort();
        assert_eq!(names, ["a.yaml", "taken"]);
    }

    #[test]
    fn model_spec_defaults_to_claude() {
        let s = ModelSpec::parse("opus").unwrap();
        assert_eq!(s.backend, Backend::Claude);
        assert_eq!(s.model, "opus");
        assert_eq!(s.full, "opus");
    }

    #[test]
    fn model_spec_splits_on_first_colon_only() {
        let s = ModelSpec::parse("ollama:gemma4:e4b").unwrap();
        assert_eq!(s.backend, Backend::Ollama);
        assert_eq!(s.model, "gemma4:e4b");
    }

    #[test]
    fn timestamp_matches_known_unix_time() {
        assert_eq!(format_utc_stamp(1700000000), "2023-11-14T22-13-20");
    }

    fn scratch(name: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!("mag-{name}-{}", std::process::id()));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();
        dir
    }

    fn quick_caller(name: &str) -> Caller {
        let mut caller = Caller::new(&scratch(name));
        caller.backoff = Duration::from_millis(1);
        caller
    }

    #[test]
    fn timeout_returns_even_when_a_grandchild_holds_stdout() {
        let mut cmd = Command::new("sh");
        cmd.args(["-c", "sleep 30 & sleep 30"])
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        let started = Instant::now();
        let result = run_child(cmd, String::new(), Duration::from_millis(300));
        assert!(matches!(result, Err(CallError::Timeout(_))));
        assert!(started.elapsed() < Duration::from_secs(10));
    }

    #[test]
    fn transport_errors_retry_with_the_original_prompt_and_timeouts_do_not() {
        let caller = quick_caller("retry");
        let spec = ModelSpec::parse("opus").unwrap();
        let prompts = Mutex::new(Vec::new());
        let flaky = |sent: &str| {
            let mut seen = prompts.lock().unwrap();
            seen.push(sent.to_string());
            if seen.len() < 3 {
                Err(CallError::Transport("429".into()))
            } else {
                Ok(("ok".to_string(), 0.0, 0.0))
            }
        };
        let got = caller.retry("t", &spec, "PROMPT", |r| Ok(r.to_string()), flaky);
        assert_eq!(got.unwrap(), "ok");
        assert!(prompts.lock().unwrap().iter().all(|p| p == "PROMPT"));
        let calls = Mutex::new(0);
        let slow = |_: &str| {
            *calls.lock().unwrap() += 1;
            Err(CallError::Timeout("1s".into()))
        };
        let got = caller.retry("t", &spec, "PROMPT", |r| Ok(r.to_string()), slow);
        assert!(got.is_err());
        assert_eq!(*calls.lock().unwrap(), 1);
    }

    #[test]
    fn parse_rejections_are_fed_back_to_the_model() {
        let caller = quick_caller("reject");
        let spec = ModelSpec::parse("opus").unwrap();
        let prompts = Mutex::new(Vec::new());
        let run = |sent: &str| {
            prompts.lock().unwrap().push(sent.to_string());
            Ok(("reply".to_string(), 0.0, 0.0))
        };
        let parse = |_: &str| -> Result<()> { bail!("bad shape") };
        assert!(caller.retry("t", &spec, "PROMPT", parse, run).is_err());
        let seen = prompts.lock().unwrap();
        assert_eq!(seen.len(), 3);
        assert_eq!(seen[0], "PROMPT");
        assert!(seen[1].contains("rejected: bad shape"));
    }
}
