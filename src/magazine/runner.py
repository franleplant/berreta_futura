"""The one seam through which the pipeline may execute a model.

Historically nothing under ``src/`` invoked a model: prose and art came from an
operating agent following ``prompts/``, and ``mag`` only validated and packaged.
This module is where that changes, and it is deliberately the *only* place it
changes.  It resolves a configured coding-agent CLI into a callable runner and
executes it.  It does not decide what to ask for, does not read editions, and
writes nothing but the transient capture file described below -- composing
prompts and placing results stay with the produce phase that calls it.

Two backends, asymmetric on purpose.

**Text** runs through ``codex exec`` by default and may be switched to
``claude -p`` with ``[runner] text_backend`` in ``magazine.toml``, or for a
single invocation with :meth:`RunnerConfig.with_text_backend`, which is what
``mag produce --backend`` calls.

A third text backend, ``agent``, is named by the same key and resolved nowhere:
it executes no process, so :func:`resolve_text_runner` refuses it by name and
points at the cooperative driver in :mod:`magazine.produce_agent` instead.  It
is listed in :data:`TEXT_BACKENDS` so that ``text_backend = "agent"`` and
``--backend agent`` are validated exactly like the two that do shell out.

**Image** runs through ``codex exec`` and nothing else.  ``[runner]
image_backend`` exists only so a configuration that tries to name another
backend is *refused* rather than silently ignored; there is no value of it that
routes illustration work to ``claude``, and no override -- neither the config
key nor the produce flag -- reaches it.

Both are hard dependencies.  :func:`resolve_text_runner` and
:func:`resolve_image_runner` look the selected binary up with ``shutil.which``
and raise :class:`RunnerError` naming the binary and the key that chose it.
There is no fallback backend and no degraded mode: a produce run either has the
tool it was configured with or it does not start.

The invocation contract, read off ``codex exec --help`` and ``claude --help``
for the versions installed on the author's machine (``codex-cli 0.142.5``,
``claude 2.1.220``) rather than assumed:

* ``codex exec [--sandbox MODE] [--model M] --skip-git-repo-check --color never
  --output-last-message FILE -`` -- a bare ``-`` in the prompt position makes
  Codex read the instructions from stdin, which is how a prompt larger than the
  platform's argv limit gets in.  ``codex exec`` streams a session transcript to
  stdout, so the model's answer is taken from the ``--output-last-message``
  file rather than parsed back out of the stream.
* ``claude -p --output-format text [--model M]`` -- ``-p``/``--print`` is the
  non-interactive mode and reads the prompt from stdin when no prompt argument
  is given.  Its stdout *is* the final message, so no capture file is used.
  (Note that ``-p`` means ``--profile`` under ``codex exec`` and ``--print``
  under ``claude``; the two argv shapes share nothing and are built separately.)

Execution itself goes through the :class:`CommandRunner` protocol so tests
exercise the argv and stdin contract without a model or a network: the suite
injects a fake and never runs the real binaries.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Protocol

from .errors import MagazineError


class RunnerError(MagazineError):
    """Raised when a configured model backend is unusable or fails a run."""


DEFAULT_TEXT_BACKEND = "codex"
"""The text backend.  ``[runner] text_backend`` absent means this."""

AGENT_BACKEND = "agent"
"""The cooperative backend: the pipeline emits briefs and ingests answers.

It is a text backend in every sense that matters to ``mag produce`` -- it is
named by the same key, it answers the same calls, and the pipeline that uses it
is the same pipeline -- but it executes nothing, so it resolves to no binary and
never reaches this module's process plumbing.  A Python process cannot spawn a
Claude Code subagent, and a fleet driver cannot be shelled out to; inverting the
call is the only way that case is coverable at all.  See
:mod:`magazine.produce_agent`.
"""

TEXT_BACKENDS: tuple[str, ...] = (AGENT_BACKEND, "claude", "codex")
"""Every backend ``[runner] text_backend`` may name."""

IMAGE_BACKEND = "codex"
"""The only backend that may generate illustrations.  Not configurable."""

DEFAULT_TIMEOUT_SECONDS = 900.0
"""Wall-clock ceiling for one invocation when the config does not set one."""

CODEX_SANDBOX_MODES: tuple[str, ...] = (
    "danger-full-access",
    "read-only",
    "workspace-write",
)
"""``codex exec --sandbox`` values, as that CLI documents them."""

DEFAULT_CODEX_SANDBOX = "workspace-write"
"""Produce work writes drafts and art into the workspace, so this is the default."""


# ---------------------------------------------------------------------------
# Configuration.


@dataclass(frozen=True)
class RunnerConfig:
    """The ``[runner]`` table, parsed and validated.

    Every field has a default, so an absent table is a legal configuration
    meaning "Codex for both, fifteen minutes, workspace-write".  Validation
    happens here rather than at resolve time so a typo in ``magazine.toml``
    cannot survive as far as a subprocess.
    """

    text_backend: str = DEFAULT_TEXT_BACKEND
    image_backend: str = IMAGE_BACKEND
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    codex_sandbox: str = DEFAULT_CODEX_SANDBOX
    codex_binary: str = "codex"
    claude_binary: str = "claude"
    text_model: str | None = None
    image_model: str | None = None

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> RunnerConfig:
        """Build a config from a parsed ``[runner]`` table (``None`` for absent)."""

        table = dict(data or {})
        unknown = sorted(set(table) - set(cls.__dataclass_fields__))
        if unknown:
            raise RunnerError(
                "Unknown [runner] key(s) in magazine.toml: "
                + ", ".join(repr(key) for key in unknown)
                + "; expected "
                + ", ".join(sorted(cls.__dataclass_fields__))
            )
        return cls(
            text_backend=_text_backend_name(table.get("text_backend")),
            image_backend=_image_backend_name(table.get("image_backend")),
            timeout_seconds=_timeout_seconds(table.get("timeout_seconds")),
            codex_sandbox=_codex_sandbox(table.get("codex_sandbox")),
            codex_binary=_binary_name(table.get("codex_binary"), "codex", "codex_binary"),
            claude_binary=_binary_name(table.get("claude_binary"), "claude", "claude_binary"),
            text_model=_optional_text(table.get("text_model"), "text_model"),
            image_model=_optional_text(table.get("image_model"), "image_model"),
        )

    def with_text_backend(self, backend: str | None) -> RunnerConfig:
        """Return this config with the *text* backend swapped for one run.

        The produce phase exposes this as ``mag produce --backend``, for the
        ordinary case of an operator who is out of credits on the configured
        backend and does not want to edit -- and then remember to revert --
        ``magazine.toml``.  ``None`` means "no override", so a caller can pass
        an absent flag straight through.

        It is deliberately narrower than the config it copies: only
        ``text_backend`` moves, and the value goes through the same validator
        the file does, so ``--backend gemini`` is refused exactly as
        ``text_backend = "gemini"`` is.  ``image_backend`` is not reachable
        from here and cannot be -- illustration is not a backend choice, and a
        flag that could redirect it would be a way around that rule.
        """

        if backend is None:
            return self
        return replace(self, text_backend=_text_backend_name(backend))

    @classmethod
    def load(cls, root: Path) -> RunnerConfig:
        """Read ``<root>/magazine.toml`` and parse its ``[runner]`` table."""

        path = root / "magazine.toml"
        if not path.is_file():
            return cls()
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as error:
            raise RunnerError(f"Cannot read {path}: {error}") from error
        table = data.get("runner")
        if table is not None and not isinstance(table, Mapping):
            raise RunnerError(f"[runner] in {path} must be a table")
        return cls.from_mapping(table)


def _text_backend_name(configured: object | None) -> str:
    if configured is None:
        return DEFAULT_TEXT_BACKEND
    name = str(configured).strip()
    if name not in TEXT_BACKENDS:
        raise RunnerError(
            f"Unknown [runner] text_backend {name!r}; expected one of "
            + ", ".join(repr(known) for known in TEXT_BACKENDS)
            + f" (omit the key for the default {DEFAULT_TEXT_BACKEND!r})"
        )
    return name


def _image_backend_name(configured: object | None) -> str:
    """Accept only Codex.

    Illustration work is not a backend choice.  The key is parsed at all so
    that writing ``image_backend = "claude"`` is a loud refusal instead of a
    line the compiler quietly ignores while running Codex anyway.
    """

    if configured is None:
        return IMAGE_BACKEND
    name = str(configured).strip()
    if name != IMAGE_BACKEND:
        raise RunnerError(
            f"[runner] image_backend must be {IMAGE_BACKEND!r}, not {name!r}; "
            "image and illustration generation is not a configurable backend"
        )
    return name


def _timeout_seconds(configured: object | None) -> float:
    if configured is None:
        return DEFAULT_TIMEOUT_SECONDS
    if isinstance(configured, bool) or not isinstance(configured, (int, float)):
        raise RunnerError("[runner] timeout_seconds must be a positive number")
    value = float(configured)
    if value <= 0:
        raise RunnerError("[runner] timeout_seconds must be a positive number")
    return value


def _codex_sandbox(configured: object | None) -> str:
    if configured is None:
        return DEFAULT_CODEX_SANDBOX
    name = str(configured).strip()
    if name not in CODEX_SANDBOX_MODES:
        raise RunnerError(
            f"Unknown [runner] codex_sandbox {name!r}; expected one of "
            + ", ".join(repr(known) for known in CODEX_SANDBOX_MODES)
        )
    return name


def _binary_name(configured: object | None, default: str, key: str) -> str:
    """A binary name or path override.

    An override changes *which executable* runs, never which backend it is:
    ``codex_binary`` still builds the ``codex exec`` argv.  It exists for
    installs that are not on a service's ``PATH``.
    """

    if configured is None:
        return default
    name = str(configured).strip()
    if not name:
        raise RunnerError(f"[runner] {key} must be a non-empty binary name or path")
    return name


def _optional_text(configured: object | None, key: str) -> str | None:
    if configured is None:
        return None
    value = str(configured).strip()
    if not value:
        raise RunnerError(f"[runner] {key} must be a non-empty string when present")
    return value


# ---------------------------------------------------------------------------
# Execution.


@dataclass(frozen=True)
class CommandInvocation:
    """One process to run: its argv, what to feed its stdin, and how long to wait."""

    argv: tuple[str, ...]
    stdin: str
    timeout_seconds: float
    cwd: Path | None = None


@dataclass(frozen=True)
class CommandResult:
    """What one process printed and how it exited."""

    returncode: int
    stdout: str
    stderr: str


class CommandRunner(Protocol):
    """Run one invocation to completion and report what it printed."""

    def run(self, invocation: CommandInvocation) -> CommandResult:
        ...


class SubprocessCommandRunner:
    """The production :class:`CommandRunner`: an actual child process.

    The prompt always goes in over stdin, never argv, so a full manuscript
    brief cannot hit the platform's argument-length limit.  A timeout kills the
    child and is reported as a :class:`RunnerError` rather than escaping as a
    ``subprocess`` exception.
    """

    def run(self, invocation: CommandInvocation) -> CommandResult:
        try:
            completed = subprocess.run(
                list(invocation.argv),
                input=invocation.stdin,
                capture_output=True,
                text=True,
                timeout=invocation.timeout_seconds,
                cwd=str(invocation.cwd) if invocation.cwd is not None else None,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise RunnerError(
                f"{invocation.argv[0]} did not finish within "
                f"{invocation.timeout_seconds:g}s; raise [runner] timeout_seconds "
                "or narrow the request"
            ) from error
        except OSError as error:
            raise RunnerError(
                f"Cannot execute {invocation.argv[0]}: {error}"
            ) from error
        return CommandResult(
            returncode=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
        )


# ---------------------------------------------------------------------------
# Resolved backends.


@dataclass(frozen=True)
class GenerationResult:
    """One completed model run: its output and the provenance of the run.

    ``argv`` and ``duration_seconds`` are carried because the architecture
    requires an AI execution record to name the model configuration and timing
    it used; the produce phase writes them, this module only reports them.
    """

    text: str
    backend: str
    argv: tuple[str, ...]
    stderr: str
    duration_seconds: float


@dataclass(frozen=True)
class ModelRunner:
    """A resolved backend: which binary runs, how it is called, and by what.

    Constructed only by :func:`resolve_text_runner` and
    :func:`resolve_image_runner`, both of which have already proved the binary
    exists.  ``binary`` is the absolute path ``shutil.which`` returned, so the
    ``PATH`` the check ran against is the one the run uses.
    """

    kind: str
    """``"text"`` or ``"image"`` -- what this runner was resolved for."""

    backend: str
    """``"codex"`` or ``"claude"``."""

    binary: str
    """Absolute path to the executable, as resolved at selection time."""

    config_key: str
    """The ``magazine.toml`` key that selected this backend, for error copy."""

    argv_tail: tuple[str, ...]
    """Everything after the binary, before any per-call arguments."""

    final_message_flag: str | None
    """Flag that writes the model's last message to a file, if the CLI has one.

    ``codex exec`` streams a whole session to stdout, so its answer is read
    back from ``--output-last-message``.  ``claude -p`` prints only the answer,
    so this is ``None`` and stdout is taken directly.
    """

    timeout_seconds: float
    command: CommandRunner

    def generate(
        self,
        prompt: str,
        *,
        cwd: Path | None = None,
        timeout_seconds: float | None = None,
        extra_args: Sequence[str] = (),
    ) -> GenerationResult:
        """Run the backend over ``prompt`` and return the model's answer.

        The prompt is written to the child's stdin.  A non-zero exit, an empty
        answer, or a timeout raises :class:`RunnerError` quoting the backend's
        own stderr -- nothing here retries, substitutes another backend, or
        returns a partial result.
        """

        if not prompt.strip():
            raise RunnerError(f"Refusing to run {self.backend} with an empty prompt")
        limit = self.timeout_seconds if timeout_seconds is None else timeout_seconds
        with tempfile.TemporaryDirectory(prefix="mag-runner-") as workspace:
            capture: Path | None = None
            capture_argv: tuple[str, ...] = ()
            if self.final_message_flag is not None:
                capture = Path(workspace) / "final-message.txt"
                capture_argv = (self.final_message_flag, str(capture))
            argv = (
                self.binary,
                *self.argv_tail,
                *capture_argv,
                *(str(item) for item in extra_args),
                *self._prompt_argv(),
            )
            started = time.monotonic()
            result = self.command.run(
                CommandInvocation(
                    argv=argv, stdin=prompt, timeout_seconds=limit, cwd=cwd
                )
            )
            elapsed = time.monotonic() - started
            if result.returncode != 0:
                raise RunnerError(
                    f"{self.backend} exited {result.returncode} running "
                    f"{' '.join(argv)}\n{(result.stderr or result.stdout).strip()}"
                )
            if capture is not None:
                if not capture.is_file():
                    raise RunnerError(
                        f"{self.backend} exited 0 but wrote no final message to "
                        f"{self.final_message_flag}; the run produced nothing usable"
                    )
                text = capture.read_text(encoding="utf-8")
            else:
                text = result.stdout
        if not text.strip():
            raise RunnerError(f"{self.backend} exited 0 but returned no text")
        return GenerationResult(
            text=text,
            backend=self.backend,
            argv=argv,
            stderr=result.stderr,
            duration_seconds=elapsed,
        )

    def _prompt_argv(self) -> tuple[str, ...]:
        """Trailing argv that tells the CLI to take the prompt from stdin."""

        # Codex needs the explicit ``-`` placeholder; ``claude -p`` reads stdin
        # whenever no prompt argument follows, so it needs nothing.
        return ("-",) if self.backend == "codex" else ()


def _codex_argv_tail(config: RunnerConfig, *, model: str | None) -> tuple[str, ...]:
    tail = ["exec", "--sandbox", config.codex_sandbox]
    if model:
        tail += ["--model", model]
    # ``--skip-git-repo-check`` keeps the runner usable from a sandbox copy of
    # the tree; ``--color never`` keeps ANSI escapes out of captured output.
    tail += ["--skip-git-repo-check", "--color", "never"]
    return tuple(tail)


def _claude_argv_tail(config: RunnerConfig, *, model: str | None) -> tuple[str, ...]:
    tail = ["-p", "--output-format", "text"]
    if model:
        tail += ["--model", model]
    return tuple(tail)


def _require_binary(name: str, *, backend: str, config_key: str) -> str:
    """Resolve ``name`` on ``PATH`` or refuse the run outright."""

    found = shutil.which(name)
    if found is None:
        raise RunnerError(
            f"The {backend} backend needs the {name!r} executable and it is not "
            f"on PATH (selected by {config_key} in magazine.toml). Install it or "
            "point [runner] at an installed backend; there is no fallback."
        )
    return found


def resolve_text_runner(
    config: RunnerConfig, *, command: CommandRunner | None = None
) -> ModelRunner:
    """Select and prove the text backend named by ``config``.

    Raises :class:`RunnerError` before any work is attempted if the selected
    binary is not installed.
    """

    backend = config.text_backend
    if backend == AGENT_BACKEND:
        # Reached only by a caller that resolved a runner without checking the
        # backend first.  ``Magazine.produce`` branches before here, because
        # there is no process to resolve: the agent backend's "binary" is
        # whoever is reading the emitted briefs.
        raise RunnerError(
            f"The {AGENT_BACKEND!r} text backend runs no process: it emits briefs "
            "and ingests answers. Drive it with `mag produce <edition-id> "
            "--backend agent`, which needs no executable on PATH."
        )
    if backend == "codex":
        binary_name, argv_tail, final_flag = (
            config.codex_binary,
            _codex_argv_tail(config, model=config.text_model),
            "--output-last-message",
        )
    else:
        binary_name, argv_tail, final_flag = (
            config.claude_binary,
            _claude_argv_tail(config, model=config.text_model),
            None,
        )
    config_key = "[runner] text_backend"
    return ModelRunner(
        kind="text",
        backend=backend,
        binary=_require_binary(binary_name, backend=backend, config_key=config_key),
        config_key=config_key,
        argv_tail=argv_tail,
        final_message_flag=final_flag,
        timeout_seconds=config.timeout_seconds,
        command=command or SubprocessCommandRunner(),
    )


def resolve_image_runner(
    config: RunnerConfig, *, command: CommandRunner | None = None
) -> ModelRunner:
    """Select and prove the image backend, which is always Codex.

    :meth:`RunnerConfig.from_mapping` already refuses a non-Codex
    ``image_backend``, so reaching this check means the config object was built
    in code.  It is enforced again here because this is the function every
    illustration caller goes through, and the guarantee is that no path out of
    it can return a ``claude`` runner.
    """

    config_key = "[runner] image_backend"
    if config.image_backend != IMAGE_BACKEND:
        raise RunnerError(
            f"Image generation runs through {IMAGE_BACKEND!r} only; "
            f"{config_key} names {config.image_backend!r}"
        )
    return ModelRunner(
        kind="image",
        backend=IMAGE_BACKEND,
        binary=_require_binary(
            config.codex_binary, backend=IMAGE_BACKEND, config_key=config_key
        ),
        config_key=config_key,
        argv_tail=_codex_argv_tail(config, model=config.image_model),
        final_message_flag="--output-last-message",
        timeout_seconds=config.timeout_seconds,
        command=command or SubprocessCommandRunner(),
    )
