use anyhow::{bail, Context, Result};
use std::io::{Read, Write};
use std::path::PathBuf;
use std::process::{Command, Stdio};
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
        Some("max") | Some("xhigh") => 2700,
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

impl Semaphore {
    fn new(max: usize) -> Self {
        Self {
            count: Mutex::new(0),
            cond: Condvar::new(),
            max,
        }
    }

    fn acquire(&self) {
        let mut count = self.count.lock().unwrap();
        while *count >= self.max {
            count = self.cond.wait(count).unwrap();
        }
        *count += 1;
    }

    fn release(&self) {
        let mut count = self.count.lock().unwrap();
        *count -= 1;
        self.cond.notify_one();
    }
}

struct SemaphoreGuard<'a>(&'a Semaphore);

impl<'a> SemaphoreGuard<'a> {
    fn acquire(sem: &'a Semaphore) -> Self {
        sem.acquire();
        Self(sem)
    }
}

impl Drop for SemaphoreGuard<'_> {
    fn drop(&mut self) {
        self.0.release();
    }
}

pub struct Caller {
    sem: Semaphore,
    log_path: std::path::PathBuf,
    log_lock: Mutex<()>,
    root: std::path::PathBuf,
    total_cost: Mutex<f64>,
    calls: AtomicUsize,
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
        let mut last_error: Option<String> = None;
        let mut last_reply: Option<String> = None;
        for attempt in 0..=CALL_RETRIES {
            let sent = match &last_error {
                None => prompt.to_string(),
                Some(e) => format!(
                    "{prompt}\n\nYour previous reply was rejected: {e}. Reply again \
                     following the required output format exactly."
                ),
            };

            let (result_text, cost, seconds) = match self.run_once(spec, &sent, images) {
                Ok(v) => v,
                Err(e) => {
                    last_error = Some(e);
                    continue;
                }
            };

            *self.total_cost.lock().unwrap() += cost;
            self.calls.fetch_add(1, Ordering::SeqCst);

            match parse(&result_text) {
                Ok(parsed) => {
                    self.log_and_print(label, spec, seconds, cost, attempt)?;
                    return Ok(parsed);
                }
                Err(e) => {
                    last_error = Some(e.to_string());
                    last_reply = Some(result_text);
                    continue;
                }
            }
        }

        let saved = match &last_reply {
            Some(reply) => self.save_failed_reply(label, spec, reply),
            None => None,
        };
        bail!(
            "{label}: model call failed after retries — {}{}",
            last_error.unwrap_or_else(|| "unknown error".to_string()),
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
    ) -> Result<(String, f64, f64), String> {
        let _permit = SemaphoreGuard::acquire(&self.sem);
        let started = Instant::now();
        let scratch = match spec.backend {
            Backend::Codex => Some(CodexScratch::new()?),
            _ => None,
        };

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
                c.arg(&scratch.as_ref().expect("codex scratch").out);
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
        cmd.current_dir(match &scratch {
            Some(s) => s.dir.as_path(),
            None => self.root.as_path(),
        })
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());

        let mut child = cmd
            .spawn()
            .map_err(|e| format!("failed to spawn {:?}: {e}", spec.backend))?;

        let stdin_payload = match spec.backend {
            Backend::Claude | Backend::Codex => prompt.to_string(),
            Backend::Ollama => serde_json::json!({
                "model": spec.model,
                "prompt": prompt,
                "stream": false,
                "keep_alive": "2h",
                "options": {"num_ctx": ollama_num_ctx()},
            })
            .to_string(),
        };
        let mut stdin = child.stdin.take().expect("piped stdin");
        let writer = thread::spawn(move || {
            let _ = stdin.write_all(stdin_payload.as_bytes());
        });

        let mut stdout = child.stdout.take().expect("piped stdout");
        let stdout_reader = thread::spawn(move || {
            let mut buf = Vec::new();
            let _ = stdout.read_to_end(&mut buf);
            buf
        });

        let mut stderr = child.stderr.take().expect("piped stderr");
        let stderr_reader = thread::spawn(move || {
            let mut buf = Vec::new();
            let _ = stderr.read_to_end(&mut buf);
            buf
        });

        let timeout = Duration::from_secs(call_timeout_secs_for(Some(spec)));
        let status = loop {
            match child.try_wait() {
                Ok(Some(status)) => break Some(status),
                Ok(None) => {
                    if started.elapsed() > timeout {
                        let _ = child.kill();
                        let _ = child.wait();
                        break None;
                    }
                    thread::sleep(Duration::from_millis(50));
                }
                Err(e) => return Err(format!("wait failed: {e}")),
            }
        };

        let _ = writer.join();
        let out = stdout_reader.join().unwrap_or_default();
        let err = stderr_reader.join().unwrap_or_default();
        let seconds = started.elapsed().as_secs_f64();

        let status = match status {
            Some(s) => s,
            None => {
                return Err(format!(
                    "timeout after {}s",
                    call_timeout_secs_for(Some(spec))
                ))
            }
        };

        match spec.backend {
            Backend::Claude => {
                let data: serde_json::Value = serde_json::from_slice(&out).map_err(|_| {
                    let err_text = String::from_utf8_lossy(&err);
                    let truncated: String = err_text.chars().take(300).collect();
                    format!(
                        "non-JSON output (exit {}): {truncated}",
                        status.code().unwrap_or(-1)
                    )
                })?;
                let is_error = data
                    .get("is_error")
                    .and_then(|v| v.as_bool())
                    .unwrap_or(false);
                let subtype = data.get("subtype").and_then(|v| v.as_str()).unwrap_or("");
                if is_error || subtype != "success" {
                    let dumped = data.to_string();
                    let truncated: String = dumped.chars().take(300).collect();
                    return Err(format!("call failed: {truncated}"));
                }
                let cost = data
                    .get("total_cost_usd")
                    .and_then(|v| v.as_f64())
                    .unwrap_or(0.0);
                let result = data
                    .get("result")
                    .and_then(|v| v.as_str())
                    .ok_or_else(|| "call succeeded but had no 'result' field".to_string())?
                    .to_string();
                Ok((result, cost, seconds))
            }
            Backend::Codex => {
                let out_path = &scratch.as_ref().expect("codex scratch").out;
                if !status.success() {
                    let err_text = String::from_utf8_lossy(&err);
                    let truncated: String = err_text.chars().take(300).collect();
                    return Err(format!("codex exited with {status}: {truncated}"));
                }
                let reply = std::fs::read_to_string(out_path)
                    .map_err(|e| format!("codex wrote no final message ({e})"))?;
                if reply.trim().is_empty() {
                    return Err("codex final message was empty".to_string());
                }

                Ok((reply, 0.0, seconds))
            }
            Backend::Ollama => {
                if !status.success() {
                    let err_text = String::from_utf8_lossy(&err);
                    let truncated: String = err_text.chars().take(300).collect();
                    return Err(format!("ollama call exited with {status}: {truncated}"));
                }
                let data: serde_json::Value = serde_json::from_slice(&out).map_err(|_| {
                    let text = String::from_utf8_lossy(&out);
                    let truncated: String = text.chars().take(300).collect();
                    format!("non-JSON ollama response: {truncated}")
                })?;
                if let Some(e) = data.get("error").and_then(|v| v.as_str()) {
                    return Err(format!("ollama error: {e}"));
                }
                let result = data
                    .get("response")
                    .and_then(|v| v.as_str())
                    .ok_or_else(|| "ollama reply had no 'response' field".to_string())?
                    .to_string();
                Ok((result, 0.0, seconds))
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

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
}
