"""The model-execution seam: selection, refusal, and the argv/stdin contract.

Nothing here runs ``codex`` or ``claude``.  Binary presence is faked by
pointing ``[runner] codex_binary`` / ``claude_binary`` at an executable every
POSIX box has, and execution goes through an injected :class:`FakeCommand`, so
the suite proves the contract the real CLIs are called with without a model,
a network, or an API key.
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from magazine.runner import (
    AGENT_BACKEND,
    CODEX_SANDBOX_MODES,
    DEFAULT_TEXT_BACKEND,
    DEFAULT_TIMEOUT_SECONDS,
    IMAGE_BACKEND,
    TEXT_BACKENDS,
    CommandInvocation,
    CommandResult,
    RunnerConfig,
    RunnerError,
    SubprocessCommandRunner,
    resolve_image_runner,
    resolve_text_runner,
)

# An executable that certainly exists, standing in for an installed backend.
INSTALLED = "/bin/echo"
MISSING = "definitely-not-an-installed-agent-cli"


class FakeCommand:
    """Record invocations and replay a scripted result.

    When the argv carries ``--output-last-message`` the fake writes ``stdout``
    to that path, the way ``codex exec`` does, so the capture-file path is
    exercised rather than stubbed around.
    """

    def __init__(
        self, *, returncode: int = 0, stdout: str = "drafted copy\n", stderr: str = ""
    ) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.calls: list[CommandInvocation] = []
        self.write_final_message = True

    def run(self, invocation: CommandInvocation) -> CommandResult:
        self.calls.append(invocation)
        argv = list(invocation.argv)
        if "--output-last-message" in argv and self.write_final_message:
            target = Path(argv[argv.index("--output-last-message") + 1])
            target.write_text(self.stdout, encoding="utf-8")
            return CommandResult(self.returncode, "", self.stderr)
        return CommandResult(self.returncode, self.stdout, self.stderr)

    @property
    def argv(self) -> list[str]:
        return list(self.calls[-1].argv)


def codex_config(**overrides) -> RunnerConfig:
    return RunnerConfig(codex_binary=INSTALLED, claude_binary=INSTALLED, **overrides)


class ConfigLoadingTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def write(self, table: str = "") -> Path:
        path = self.root / "magazine.toml"
        path.write_text('[publication]\nname = "Test Review"\n' + table, encoding="utf-8")
        return path

    def test_absent_table_yields_the_codex_defaults(self):
        self.write()

        config = RunnerConfig.load(self.root)

        self.assertEqual(config.text_backend, DEFAULT_TEXT_BACKEND)
        self.assertEqual(config.text_backend, "codex")
        self.assertEqual(config.image_backend, IMAGE_BACKEND)
        self.assertEqual(config.timeout_seconds, DEFAULT_TIMEOUT_SECONDS)

    def test_absent_config_file_yields_the_defaults(self):
        self.assertEqual(RunnerConfig.load(self.root), RunnerConfig())

    def test_the_table_is_read(self):
        self.write(
            "\n[runner]\n"
            'text_backend = "claude"\n'
            "timeout_seconds = 60\n"
            'codex_sandbox = "read-only"\n'
            'text_model = "gpt-5"\n'
        )

        config = RunnerConfig.load(self.root)

        self.assertEqual(config.text_backend, "claude")
        self.assertEqual(config.timeout_seconds, 60.0)
        self.assertEqual(config.codex_sandbox, "read-only")
        self.assertEqual(config.text_model, "gpt-5")

    def test_unknown_text_backend_fails_at_load_rather_than_falling_back(self):
        self.write('\n[runner]\ntext_backend = "gemini"\n')

        with self.assertRaises(RunnerError) as caught:
            RunnerConfig.load(self.root)
        message = str(caught.exception)
        self.assertIn("gemini", message)
        for known in TEXT_BACKENDS:
            self.assertIn(repr(known), message)

    def test_claude_cannot_be_selected_for_images_in_config(self):
        self.write('\n[runner]\nimage_backend = "claude"\n')

        with self.assertRaises(RunnerError) as caught:
            RunnerConfig.load(self.root)
        self.assertIn("not a configurable backend", str(caught.exception))

    def test_a_misspelled_key_is_refused_rather_than_ignored(self):
        self.write('\n[runner]\ntext_backends = "claude"\n')

        with self.assertRaises(RunnerError) as caught:
            RunnerConfig.load(self.root)
        self.assertIn("text_backends", str(caught.exception))

    def test_non_positive_timeout_is_refused(self):
        for value in ("0", "-5", '"soon"'):
            with self.subTest(value=value):
                self.write(f"\n[runner]\ntimeout_seconds = {value}\n")
                with self.assertRaises(RunnerError):
                    RunnerConfig.load(self.root)

    def test_unknown_sandbox_mode_is_refused(self):
        self.write('\n[runner]\ncodex_sandbox = "yolo"\n')

        with self.assertRaises(RunnerError) as caught:
            RunnerConfig.load(self.root)
        for known in CODEX_SANDBOX_MODES:
            self.assertIn(repr(known), str(caught.exception))

    def test_the_shipped_config_declares_a_usable_runner_table(self):
        # The repo's own magazine.toml must stay loadable by this module.
        config = RunnerConfig.load(Path(__file__).resolve().parents[1])

        self.assertEqual(config.text_backend, "codex")
        self.assertEqual(config.image_backend, IMAGE_BACKEND)


class TextBackendOverrideTests(unittest.TestCase):
    """``mag produce --backend``: one run's text backend, and nothing else.

    The override exists so an operator out of credits on the configured
    backend does not have to edit ``magazine.toml`` and remember to revert it.
    What it must never become is a second, quieter way to name an image
    backend, so the image assertions below are the point of this class as much
    as the text ones.
    """

    def test_absent_override_leaves_the_configuration_alone(self):
        config = codex_config(text_model="gpt-5")

        self.assertIs(config.with_text_backend(None), config)

    def test_the_override_moves_the_text_backend_and_nothing_else(self):
        config = codex_config(text_model="gpt-5", image_model="gpt-image")

        overridden = config.with_text_backend("claude")

        self.assertEqual(overridden.text_backend, "claude")
        self.assertEqual(config.text_backend, "codex")
        for name in RunnerConfig.__dataclass_fields__:
            if name == "text_backend":
                continue
            with self.subTest(field=name):
                self.assertEqual(getattr(overridden, name), getattr(config, name))

    def test_an_unknown_override_is_refused_the_way_the_config_key_is(self):
        with self.assertRaises(RunnerError) as caught:
            codex_config().with_text_backend("gemini")
        message = str(caught.exception)
        self.assertIn("gemini", message)
        for known in TEXT_BACKENDS:
            self.assertIn(repr(known), message)

    def test_every_named_backend_survives_the_round_trip(self):
        for backend in TEXT_BACKENDS:
            with self.subTest(backend=backend):
                config = codex_config().with_text_backend(backend)
                self.assertEqual(config.text_backend, backend)
                if backend == AGENT_BACKEND:
                    # Named like the others and resolved like none of them: the
                    # cooperative backend runs no process, so there is nothing
                    # here to hand a binary back.
                    continue
                self.assertEqual(
                    resolve_text_runner(config, command=FakeCommand()).backend, backend
                )

    def test_the_agent_backend_is_selectable_but_resolves_no_process(self):
        config = codex_config().with_text_backend(AGENT_BACKEND)

        with self.assertRaises(RunnerError) as caught:
            resolve_text_runner(config, command=FakeCommand())

        self.assertIn("runs no process", str(caught.exception))
        self.assertIn("--backend agent", str(caught.exception))

    def test_the_override_reaches_the_text_argv(self):
        command = FakeCommand()
        config = codex_config().with_text_backend("claude")

        resolve_text_runner(config, command=command).generate("Draft it.")

        argv = command.argv
        self.assertEqual(argv[1], "-p")
        self.assertNotIn("exec", argv)

    def test_an_overridden_config_still_resolves_codex_for_images(self):
        command = FakeCommand()
        config = codex_config(image_model="gpt-image").with_text_backend("claude")

        runner = resolve_image_runner(config, command=command)
        runner.generate("Illustrate the opener.")

        self.assertEqual(config.image_backend, IMAGE_BACKEND)
        self.assertEqual(runner.backend, IMAGE_BACKEND)
        argv = command.argv
        self.assertEqual(argv[1], "exec")
        self.assertNotIn("-p", argv)

    def test_the_override_cannot_name_the_image_backend_at_all(self):
        # There is no keyword for it: the signature takes one text backend.
        with self.assertRaises(TypeError):
            codex_config().with_text_backend(image_backend="claude")


class BinaryPresenceTests(unittest.TestCase):
    def test_a_missing_text_binary_fails_fast_naming_the_key(self):
        config = RunnerConfig(codex_binary=MISSING)

        with self.assertRaises(RunnerError) as caught:
            resolve_text_runner(config, command=FakeCommand())
        message = str(caught.exception)
        self.assertIn(MISSING, message)
        self.assertIn("[runner] text_backend", message)
        self.assertIn("no fallback", message)

    def test_a_missing_claude_binary_fails_fast(self):
        config = RunnerConfig(text_backend="claude", claude_binary=MISSING)

        with self.assertRaises(RunnerError) as caught:
            resolve_text_runner(config, command=FakeCommand())
        self.assertIn(MISSING, str(caught.exception))

    def test_a_missing_image_binary_fails_fast_naming_the_image_key(self):
        config = RunnerConfig(codex_binary=MISSING)

        with self.assertRaises(RunnerError) as caught:
            resolve_image_runner(config, command=FakeCommand())
        self.assertIn("[runner] image_backend", str(caught.exception))

    def test_resolution_pins_the_absolute_path_it_checked(self):
        runner = resolve_text_runner(codex_config(), command=FakeCommand())

        self.assertEqual(runner.binary, INSTALLED)
        self.assertTrue(Path(runner.binary).is_absolute())


class TextRunnerContractTests(unittest.TestCase):
    def test_codex_is_invoked_as_exec_reading_the_prompt_from_stdin(self):
        command = FakeCommand()
        runner = resolve_text_runner(codex_config(), command=command)

        result = runner.generate("Write the opener for edition 5.")

        self.assertEqual(result.backend, "codex")
        self.assertEqual(result.text, "drafted copy\n")
        argv = command.argv
        self.assertEqual(argv[0], INSTALLED)
        self.assertEqual(argv[1], "exec")
        self.assertEqual(argv[-1], "-")
        self.assertIn("--skip-git-repo-check", argv)
        self.assertEqual(command.calls[-1].stdin, "Write the opener for edition 5.")

    def test_the_prompt_never_travels_on_argv(self):
        command = FakeCommand()
        runner = resolve_text_runner(codex_config(), command=command)
        prompt = "SENTINEL " * 5000

        runner.generate(prompt)

        self.assertNotIn("SENTINEL", " ".join(command.argv))
        self.assertEqual(command.calls[-1].stdin, prompt)

    def test_claude_is_invoked_in_print_mode_with_no_prompt_argument(self):
        command = FakeCommand()
        runner = resolve_text_runner(
            codex_config(text_backend="claude"), command=command
        )

        result = runner.generate("Copy-edit this paragraph.")

        self.assertEqual(result.backend, "claude")
        self.assertEqual(command.argv, [INSTALLED, "-p", "--output-format", "text"])
        # No trailing "-" placeholder: claude reads stdin when no prompt follows.
        self.assertNotIn("-", command.argv)
        self.assertEqual(command.calls[-1].stdin, "Copy-edit this paragraph.")

    def test_codex_answer_comes_from_the_final_message_file_not_the_transcript(self):
        # ``codex exec`` streams a session log on stdout; the fake returns an
        # empty stdout and writes the answer where the flag points.
        command = FakeCommand(stdout="the finished draft")
        runner = resolve_text_runner(codex_config(), command=command)

        result = runner.generate("Draft it.")

        self.assertIn("--output-last-message", command.argv)
        self.assertEqual(result.text, "the finished draft")

    def test_claude_answer_comes_straight_from_stdout(self):
        command = FakeCommand(stdout="the finished draft")
        runner = resolve_text_runner(
            codex_config(text_backend="claude"), command=command
        )

        self.assertEqual(runner.generate("Draft it.").text, "the finished draft")
        self.assertNotIn("--output-last-message", command.argv)

    def test_the_configured_model_and_sandbox_reach_the_argv(self):
        command = FakeCommand()
        runner = resolve_text_runner(
            codex_config(text_model="gpt-5-codex", codex_sandbox="read-only"),
            command=command,
        )

        runner.generate("Draft it.")

        argv = command.argv
        self.assertEqual(argv[argv.index("--model") + 1], "gpt-5-codex")
        self.assertEqual(argv[argv.index("--sandbox") + 1], "read-only")

    def test_the_configured_timeout_reaches_the_command(self):
        command = FakeCommand()
        runner = resolve_text_runner(codex_config(timeout_seconds=42), command=command)

        runner.generate("Draft it.")
        self.assertEqual(command.calls[-1].timeout_seconds, 42.0)

        runner.generate("Draft it.", timeout_seconds=7)
        self.assertEqual(command.calls[-1].timeout_seconds, 7.0)


class FailureSurfacingTests(unittest.TestCase):
    def test_a_non_zero_exit_raises_with_the_backend_stderr(self):
        command = FakeCommand(returncode=3, stderr="model refused the task")
        runner = resolve_text_runner(codex_config(), command=command)

        with self.assertRaises(RunnerError) as caught:
            runner.generate("Draft it.")
        message = str(caught.exception)
        self.assertIn("exited 3", message)
        self.assertIn("model refused the task", message)

    def test_a_clean_exit_with_no_output_is_a_failure_not_an_empty_draft(self):
        command = FakeCommand(stdout="   \n")
        runner = resolve_text_runner(codex_config(), command=command)

        with self.assertRaises(RunnerError) as caught:
            runner.generate("Draft it.")
        self.assertIn("no text", str(caught.exception))

    def test_a_missing_capture_file_after_a_clean_exit_is_a_failure(self):
        command = FakeCommand()
        command.write_final_message = False
        runner = resolve_text_runner(codex_config(), command=command)

        with self.assertRaises(RunnerError) as caught:
            runner.generate("Draft it.")
        self.assertIn("wrote no final message", str(caught.exception))

    def test_an_empty_prompt_never_reaches_a_backend(self):
        command = FakeCommand()
        runner = resolve_text_runner(codex_config(), command=command)

        with self.assertRaises(RunnerError):
            runner.generate("   \n")
        self.assertEqual(command.calls, [])

    def test_the_capture_file_does_not_outlive_the_run(self):
        command = FakeCommand()
        runner = resolve_text_runner(codex_config(), command=command)

        runner.generate("Draft it.")

        argv = command.argv
        capture = Path(argv[argv.index("--output-last-message") + 1])
        self.assertFalse(capture.exists())
        self.assertFalse(capture.parent.exists())

    def test_a_timeout_is_reported_as_a_runner_error(self):
        # The one place a real process runs, and it is `sleep`, not a model.
        with self.assertRaises(RunnerError) as caught:
            SubprocessCommandRunner().run(
                CommandInvocation(
                    argv=("/bin/sleep", "5"), stdin="", timeout_seconds=0.05
                )
            )
        self.assertIn("did not finish within", str(caught.exception))

    def test_an_unexecutable_binary_is_reported_as_a_runner_error(self):
        with self.assertRaises(RunnerError) as caught:
            SubprocessCommandRunner().run(
                CommandInvocation(
                    argv=("/nonexistent/agent",), stdin="", timeout_seconds=5
                )
            )
        self.assertIn("Cannot execute", str(caught.exception))


class ImageRunnerTests(unittest.TestCase):
    def test_the_image_runner_is_codex_exec(self):
        command = FakeCommand()
        runner = resolve_image_runner(codex_config(), command=command)

        self.assertEqual(runner.backend, IMAGE_BACKEND)
        self.assertEqual(runner.kind, "image")
        runner.generate("Illustrate the opener.")
        self.assertEqual(command.argv[1], "exec")

    def test_a_claude_image_backend_is_refused_at_resolve_time_too(self):
        # from_mapping already refuses this, so only code can build it; the
        # guarantee is that no path out of resolve_image_runner returns claude.
        config = RunnerConfig(image_backend="claude", codex_binary=INSTALLED)

        with self.assertRaises(RunnerError) as caught:
            resolve_image_runner(config, command=FakeCommand())
        message = str(caught.exception)
        self.assertIn("'codex' only", message)
        self.assertIn("claude", message)

    def test_the_text_backend_never_leaks_into_image_generation(self):
        command = FakeCommand()
        config = codex_config(text_backend="claude", text_model="opus")

        runner = resolve_image_runner(config, command=command)
        runner.generate("Illustrate the opener.")

        self.assertEqual(runner.backend, "codex")
        argv = command.argv
        self.assertEqual(argv[1], "exec")
        self.assertNotIn("opus", argv)
        self.assertNotIn("-p", argv)

    def test_the_image_model_is_the_image_runners_own(self):
        command = FakeCommand()
        config = codex_config(text_model="text-model", image_model="image-model")

        resolve_image_runner(config, command=command).generate("Illustrate it.")

        argv = command.argv
        self.assertEqual(argv[argv.index("--model") + 1], "image-model")


if __name__ == "__main__":
    unittest.main()
