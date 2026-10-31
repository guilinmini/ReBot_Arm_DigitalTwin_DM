from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import yaml
from rclpy.action import GoalResponse

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from rebotarmcontroller.ros_actions import ArmActions  # noqa: E402


class MoveItGripperTests(unittest.TestCase):
    def make_action(self, position, *, reached=True, canceled=False):
        feedback = []
        action = ArmActions.__new__(ArmActions)
        action._hardware = SimpleNamespace(
            set_gripper_target=Mock(),
            gripper_position_m=lambda: position,
            get_gripper_state=lambda: (0.0, 0.0, 0.2, 1),
            gripper_reached_target=lambda: reached,
        )
        goal = Mock()
        goal.request = SimpleNamespace(
            command=SimpleNamespace(position=position, max_effort=0.3)
        )
        goal.is_cancel_requested = canceled
        goal.publish_feedback.side_effect = lambda value: feedback.append(copy.deepcopy(value))
        return action, goal, feedback

    def test_moveit_open_close_and_partial_open_use_total_width(self):
        for single_finger in [0.0, 0.0125, 0.05]:
            with self.subTest(single_finger=single_finger):
                width = single_finger * 2.0
                action, goal, feedback = self.make_action(width)
                goal.request.command.position = single_finger
                result = action.execute_moveit_gripper_command(goal)
                action._hardware.set_gripper_target.assert_called_once_with(width, 0.3)
                self.assertAlmostEqual(result.position, single_finger)
                self.assertAlmostEqual(feedback[-1].position, single_finger)
                self.assertTrue(result.reached_goal)
                goal.succeed.assert_called_once()
                goal.abort.assert_not_called()

    def test_existing_action_keeps_total_opening_units(self):
        action, goal, feedback = self.make_action(0.08)
        result = action.execute_gripper_command(goal)
        action._hardware.set_gripper_target.assert_called_once_with(0.08, 0.3)
        self.assertAlmostEqual(result.position, 0.08)
        self.assertAlmostEqual(feedback[-1].position, 0.08)

    def test_canceled_moveit_result_uses_single_finger_units(self):
        action, goal, _ = self.make_action(0.06, canceled=True)
        goal.request.command.position = 0.05
        result = action.execute_moveit_gripper_command(goal)
        self.assertAlmostEqual(result.position, 0.03)
        self.assertFalse(result.reached_goal)
        goal.canceled.assert_called_once()
        goal.succeed.assert_not_called()

    def test_unreached_goal_is_not_reported_as_success(self):
        action, goal, _ = self.make_action(0.02, reached=False)
        goal.request.command.position = 0.05
        with patch("rebotarmcontroller.ros_actions.time.monotonic", side_effect=[0.0, 6.0]):
            result = action.execute_moveit_gripper_command(goal)
        self.assertFalse(result.reached_goal)
        self.assertAlmostEqual(result.position, 0.01)
        goal.abort.assert_called_once()
        goal.succeed.assert_not_called()

    def test_moveit_goal_limits(self):
        action, goal, _ = self.make_action(0.0)
        for position in [0.0, 0.025, 0.05]:
            goal.request.command.position = position
            self.assertEqual(action.moveit_gripper_goal_callback(goal.request), GoalResponse.ACCEPT)
        for position in [-0.001, 0.051, float("nan"), float("inf")]:
            goal.request.command.position = position
            self.assertEqual(action.moveit_gripper_goal_callback(goal.request), GoalResponse.REJECT)
        goal.request.command.position = 0.025
        for effort in [-1.0, float("nan"), float("inf")]:
            goal.request.command.max_effort = effort
            self.assertEqual(action.moveit_gripper_goal_callback(goal.request), GoalResponse.REJECT)

    def test_moveit_config_routes_finger_left_to_adapter(self):
        config_path = PACKAGE_ROOT.parent / "rebotarm_moveit_config/config/moveit_hardware_controllers.yaml"
        config = yaml.safe_load(config_path.read_text())["moveit_simple_controller_manager"]
        grippers = [name for name in config["controller_names"] if config[name]["type"] == "GripperCommand"]
        self.assertEqual(len(grippers), 1)
        name = grippers[0]
        self.assertEqual(config[name]["joints"], ["finger_left"])
        self.assertEqual(config[name]["command_joint"], "finger_left")
        endpoint = "/" + name + "/" + config[name]["action_ns"]
        with patch("rebotarmcontroller.ros_actions.ActionServer") as server:
            action = ArmActions(Mock(), Mock(), "rebotarm")
        matching = [call for call in server.call_args_list if call.args[2] == endpoint]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0].kwargs["execute_callback"], action.execute_moveit_gripper_command)


if __name__ == "__main__":
    unittest.main()
