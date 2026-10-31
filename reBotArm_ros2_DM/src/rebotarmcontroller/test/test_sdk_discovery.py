from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from rebotarmcontroller import hardware_manager  # noqa: E402
from rebotarmcontroller.hardware_manager import HardwareManager  # noqa: E402


class SdkDiscoveryTests(unittest.TestCase):
    def test_explicit_workspace_takes_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"REBOTARM_ROS2_WORKSPACE": directory}):
                self.assertEqual(HardwareManager._workspace_root(), Path(directory).resolve())

    def test_source_and_copied_install_find_workspace_sdk(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory).resolve()
            helper = workspace / "scripts" / "source_rebotarm_env.sh"
            helper.parent.mkdir()
            helper.touch()
            sdk = workspace / "third_party" / "reBotArm_control_py"
            (sdk / "reBotArm_control_py").mkdir(parents=True)
            module_paths = [
                "src/rebotarmcontroller/rebotarmcontroller/hardware_manager.py",
                "build/rebotarmcontroller/rebotarmcontroller/hardware_manager.py",
                "install/rebotarmcontroller/lib/python3.10/site-packages/"
                "rebotarmcontroller/hardware_manager.py",
                "install/lib/python3.12/site-packages/rebotarmcontroller/hardware_manager.py",
            ]
            for relative_path in module_paths:
                with self.subTest(module_path=relative_path):
                    with (
                        patch.dict(os.environ, {"REBOTARM_ROS2_WORKSPACE": ""}),
                        patch.object(hardware_manager, "__file__", str(workspace / relative_path)),
                        patch.object(sys, "path", list(sys.path)),
                    ):
                        self.assertEqual(HardwareManager._workspace_root(), workspace)
                        self.assertEqual(HardwareManager._ensure_rebot_sdk_in_syspath(), sdk)
                        self.assertIn(str(sdk), sys.path)


if __name__ == "__main__":
    unittest.main()
