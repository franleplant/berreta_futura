// The model caller: parametric over backends, faithful to produce.py's Caller.
//
// A model spec string is `<backend>:<model>`, backend defaulting to `claude`
// when there is no colon at all (so `opus` == `claude:opus`). When a colon is
// present the spec splits on the FIRST colon only, so `ollama:gemma4:e4b`
// yields backend `ollama`, model `gemma4:e4b`.

use anyhow::{bail, Context, Result};
use std::io::{Read, Write};
use std::process::{Command, Stdio};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Condvar, Mutex};
use std::thread;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

pub const CALL_TIMEOUT_SECS: u64 = 600;
pub const CALL_RETRIES: u32 = 2;
pub const CONCURRENCY: usize = 8;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Backend {
    Claude,
    Ollama,
}

#[derive(Debug, Clone)]
pub struct ModelSpec {
    pub backend: Backend,
    pub model: String,
    /// The original spec string, exactly as given — logged as the "model"
    /// field so the run log always shows what was actually asked for.
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
            other => bail!("unknown backend '{other}' in model spec '{spec}'"),
        };
        if model.is_empty() {
            bail!("model spec '{spec}' has no model name");
        }
        Ok(Self {
            backend,
            model,
            full: spec.to_string(),
        })
    }
}

/// UTC timestamp in produce.py's `%Y-%m-%dT%H-%M-%S` shape, computed from
/// SystemTime with no chrono dependency.
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

/// Howard Hinnant's days-since-epoch -> (year, month, day) algorithm.
fn civil_from_days(z: i64) -> (i64, u32, u32) {
    let z = z + 719468;
    let era = if z >= 0 { z } else { z - 146096 } / 146097;
    let doe = z - era * 146097; // [0, 146096]
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365; // [0, 399]
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100); // [0, 365]
    let mp = (5 * doy + 2) / 153; // [0, 11]
    let d = (doy - (153 * mp + 2) / 5 + 1) as u32; // [1, 31]
    let m = if mp < 10 { mp + 3 } else { mp - 9 } as u32; // [1, 12]
    let y = if m <= 2 { y + 1 } else { y };
    (y, m, d)
}

fn round1(x: f64) -> f64 {
    (x * 10.0).round() / 10.0
}

fn round4(x: f64) -> f64 {
    (x * 10000.0).round() / 10000.0
}

/// A simple counting semaphore capping in-flight subprocesses, acquired
/// around the subprocess run only (never around the whole retry loop).
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

    /// Plain call: no parsing, returns the raw reply text.
    pub fn llm(&self, label: &str, spec: &ModelSpec, prompt: &str) -> Result<String> {
        self.call_with_parse(label, spec, prompt, |s: &str| Ok(s.to_string()))
    }

    /// Run one headless call with retry; `parse` failures count as retryable
    /// failures, with the parse error fed back into the retry prompt, exactly
    /// like produce.py's Caller.llm.
    pub fn call_with_parse<T>(
        &self,
        label: &str,
        spec: &ModelSpec,
        prompt: &str,
        parse: impl Fn(&str) -> Result<T>,
    ) -> Result<T> {
        let mut last_error: Option<String> = None;
        for attempt in 0..=CALL_RETRIES {
            let sent = match &last_error {
                None => prompt.to_string(),
                Some(e) => format!(
                    "{prompt}\n\nYour previous reply was rejected: {e}. Reply again \
                     following the required output format exactly."
                ),
            };

            let (result_text, cost, seconds) = match self.run_once(spec, &sent) {
                Ok(v) => v,
                Err(e) => {
                    last_error = Some(e);
                    continue;
                }
            };

            // produce.py tracks cost/calls as soon as the subprocess call
            // itself succeeds, before the parse step — so a parse failure on
            // a later retry still leaves the earlier successful call's cost
            // counted. Ported faithfully.
            *self.total_cost.lock().unwrap() += cost;
            self.calls.fetch_add(1, Ordering::SeqCst);

            match parse(&result_text) {
                Ok(parsed) => {
                    self.log_and_print(label, spec, seconds, cost, attempt)?;
                    return Ok(parsed);
                }
                Err(e) => {
                    last_error = Some(e.to_string());
                    continue;
                }
            }
        }
        bail!(
            "{label}: model call failed after retries — {}",
            last_error.unwrap_or_else(|| "unknown error".to_string())
        )
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

    /// One subprocess attempt. Returns (reply text, cost usd, elapsed secs) on
    /// success, or a retryable error message.
    fn run_once(&self, spec: &ModelSpec, prompt: &str) -> Result<(String, f64, f64), String> {
        let _permit = SemaphoreGuard::acquire(&self.sem);
        let started = Instant::now();

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
                    "--disallowedTools",
                    "*",
                ]);
                c
            }
            Backend::Ollama => {
                let mut c = Command::new("ollama");
                c.args(["run", &spec.model]);
                c
            }
        };
        cmd.current_dir(&self.root)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());

        let mut child = cmd
            .spawn()
            .map_err(|e| format!("failed to spawn {:?}: {e}", spec.backend))?;

        let mut stdin = child.stdin.take().expect("piped stdin");
        let prompt_owned = prompt.to_string();
        let writer = thread::spawn(move || {
            let _ = stdin.write_all(prompt_owned.as_bytes());
            // drop stdin here to close it, signaling EOF to the child
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

        let timeout = Duration::from_secs(CALL_TIMEOUT_SECS);
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
            None => return Err(format!("timeout after {CALL_TIMEOUT_SECS}s")),
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
                let is_error = data.get("is_error").and_then(|v| v.as_bool()).unwrap_or(false);
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
            Backend::Ollama => {
                if !status.success() {
                    let err_text = String::from_utf8_lossy(&err);
                    let truncated: String = err_text.chars().take(300).collect();
                    return Err(format!("ollama exited with {status}: {truncated}"));
                }
                let result = String::from_utf8_lossy(&out).to_string();
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
        // `date -u -r 1700000000 +"%Y-%m-%dT%H-%M-%S"` => 2023-11-14T22-13-20
        assert_eq!(format_utc_stamp(1700000000), "2023-11-14T22-13-20");
    }
}
