"""Exercise the environment helper in real Bash and Zsh subprocesses."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ENV_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "source_rebotarm_env.sh"
SHELLS = [name for name in ("bash", "zsh") if shutil.which(name)]


class SourceEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="rebotarm env test ")
        self.addCleanup(self.directory.cleanup)
        self.workspace = Path(self.directory.name) / "workspace with spaces"
        self.script = self.workspace / "scripts" / ENV_SCRIPT.name
        self.script.parent.mkdir(parents=True)
        shutil.copyfile(ENV_SCRIPT, self.script)
        self.venv = self.workspace / ".venv"
        self.site_packages = self.venv / "lib" / "python3.10" / "site-packages"
        self.site_packages.mkdir(parents=True)
        (self.venv / "bin").mkdir()
        (self.venv / "bin" / "activate").write_text('export VIRTUAL_ENV="$REBOTARM_VENV"\n')
        (self.workspace / "install").mkdir()
        ros_root = self.workspace / "ros"
        (ros_root / "bin").mkdir(parents=True)
        ros2 = ros_root / "bin" / "ros2"
        ros2.write_text("#!/bin/sh\nexit 0\n")
        ros2.chmod(0o755)
        for shell in SHELLS:
            (ros_root / f"setup.{shell}").write_text(
                f'export PATH="$REBOTARM_ENV_TEST_ROS_BIN:$PATH"\n'
                f'export ROS_DISTRO=test\nexport REBOTARM_ENV_TEST_ROS_SHELL={shell}\n'
                # ROS hooks may refer to optional unset variables.
                'if [ -n "$REBOTARM_ENV_TEST_UNSET" ]; then :; fi\n'
            )
            (self.workspace / "install" / f"setup.{shell}").write_text(
                'export AMENT_PREFIX_PATH="$REBOTARM_ROS2_WORKSPACE/install"\n'
                f'export REBOTARM_ENV_TEST_WORKSPACE_SHELL={shell}\n'
            )
        self.environment = os.environ.copy()
        for key in list(self.environment):
            if key.startswith(("ROS_", "REBOTARM_", "_REBOTARM_", "AMENT_", "COLCON_")) or key in (
                "VIRTUAL_ENV", "PYTHONPATH", "LD_LIBRARY_PATH"
            ):
                self.environment.pop(key)
        self.environment.update(
            ROS_SETUP=str(ros_root / "setup.bash"),
            REBOTARM_ENV_TEST_ROS_BIN=str(ros_root / "bin"),
            REBOTARM_ENV_TEST_SOURCE=str(self.script),
        )

    def run_shell(self, shell, code):
        options = ["-f", "-c"] if shell == "zsh" else ["--noprofile", "--norc", "-c"]
        result = subprocess.run(
            [shell, *options, code], cwd="/", env=self.environment,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def test_workspace_paths_and_matching_shell_setup(self):
        for shell in SHELLS:
            with self.subTest(shell=shell):
                result = self.run_shell(shell, '''
                    source "$REBOTARM_ENV_TEST_SOURCE" || exit 1
                    printf 'workspace=%s\nvenv=%s\nros=%s\nsetup=%s\n' \
                        "$REBOTARM_ROS2_WORKSPACE" "$VIRTUAL_ENV" \
                        "$REBOTARM_ENV_TEST_ROS_SHELL" "$REBOTARM_ENV_TEST_WORKSPACE_SHELL"
                    command -v dirname
                    command -v ros2
                ''')
                self.assertIn(f"workspace={self.workspace}\n", result.stdout)
                self.assertIn(f"venv={self.venv}\n", result.stdout)
                self.assertIn(f"ros={shell}\nsetup={shell}\n", result.stdout)
                self.assertNotIn("environment ready for child commands", result.stdout)

    def test_optional_cmeel_and_missing_venv_do_not_abort_sourcing(self):
        shutil.rmtree(self.venv)
        for shell in SHELLS:
            with self.subTest(shell=shell):
                result = self.run_shell(shell, '''
                    source "$REBOTARM_ENV_TEST_SOURCE" || exit 1
                    printf 'workspace=%s\n' "$AMENT_PREFIX_PATH"
                ''')
                self.assertIn(f"workspace={self.workspace}/install\n", result.stdout)
                self.assertNotIn("no matches found", result.stderr)

    def test_repeated_sourcing_preserves_options_and_deduplicates_pythonpath(self):
        for shell in SHELLS:
            with self.subTest(shell=shell):
                result = self.run_shell(shell, '''
                    source "$REBOTARM_ENV_TEST_SOURCE" || exit 1
                    source "$REBOTARM_ENV_TEST_SOURCE" || exit 1
                    printf 'pythonpath=%s\n' "$PYTHONPATH"
                    if [ -n "${ZSH_VERSION:-}" ]; then
                        [[ -o nomatch ]] || exit 2
                    fi
                ''')
                pythonpath = next(line for line in result.stdout.splitlines() if line.startswith("pythonpath="))
                self.assertEqual(pythonpath.removeprefix("pythonpath=").split(":"), [str(self.site_packages)])

    def test_strict_shell_options_are_preserved(self):
        for shell in SHELLS:
            with self.subTest(shell=shell):
                self.run_shell(shell, '''
                    set -eu
                    source "$REBOTARM_ENV_TEST_SOURCE"
                    [[ "$-" == *e* && "$-" == *u* ]] || exit 2
                ''')

    def test_failed_setup_returns_without_exiting_the_calling_shell(self):
        for shell in SHELLS:
            with self.subTest(shell=shell):
                (self.workspace / "ros" / f"setup.{shell}").write_text("return 7\n")
                result = self.run_shell(shell, '''
                    if source "$REBOTARM_ENV_TEST_SOURCE"; then exit 2; fi
                    printf 'caller survived\n'
                ''')
                self.assertIn("caller survived", result.stdout)

    def test_direct_execution_locates_the_workspace(self):
        for shell in SHELLS:
            with self.subTest(shell=shell):
                result = subprocess.run(
                    [shell, str(self.script)], cwd="/", env=self.environment,
                    text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("environment ready for child commands", result.stdout)


if __name__ == "__main__":
    unittest.main()
