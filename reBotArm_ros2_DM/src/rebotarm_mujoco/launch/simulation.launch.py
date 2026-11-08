"""Start the MuJoCo desktop simulation, joint controls, camera, and RViz."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def _include(package, filename, arguments, *, condition=None):
    # Child launches reuse names such as joint_state_topic and publish_hz.
    # Keep their configurations (and the camera's EGL environment) local.
    return GroupAction(
        condition=condition,
        actions=[
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    PathJoinSubstitution([FindPackageShare(package), "launch", filename])
                ),
                launch_arguments=arguments.items(),
            )
        ],
    )


def generate_launch_description():
    mujoco_share = FindPackageShare("rebotarm_mujoco")
    model_path = LaunchConfiguration("model_path")
    joint_map_file = LaunchConfiguration("joint_map_file")
    joint_states = "/rebotarm/joint_states"
    physics_joint_states = "/rebotarm/mujoco/physics_joint_states"
    object_states = "/rebotarm/mujoco/object_states"

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "use_rviz", default_value="true", description="Open RViz with robot and RGB views."
            ),
            DeclareLaunchArgument(
                "use_joint_gui", default_value="true", description="Open the joint command sliders."
            ),
            DeclareLaunchArgument(
                "open_viewer", default_value="true", description="Open the MuJoCo viewer."
            ),
            DeclareLaunchArgument(
                "use_camera", default_value="true", description="Publish the overhead RGB camera."
            ),
            DeclareLaunchArgument(
                "use_color_detector",
                default_value="false",
                description="Optionally detect colored objects; disabled for raw camera output.",
            ),
            DeclareLaunchArgument(
                "model_path",
                default_value=PathJoinSubstitution(
                    [mujoco_share, "models", "rebotarm_b601_colored.xml"]
                ),
            ),
            DeclareLaunchArgument(
                "joint_map_file",
                default_value=PathJoinSubstitution(
                    [mujoco_share, "config", "joint_map_kinematic.yaml"]
                ),
            ),
            DeclareLaunchArgument(
                "rviz_config",
                default_value=PathJoinSubstitution(
                    [mujoco_share, "rviz", "simulation.rviz"]
                ),
            ),
            _include(
                "rebotarm_bringup",
                "fake_bringup.launch.py",
                {
                    "use_rviz": LaunchConfiguration("use_rviz"),
                    "rviz_config": LaunchConfiguration("rviz_config"),
                    "robot_joint_state_topic": physics_joint_states,
                },
            ),
            _include(
                "rebotarm_mujoco",
                "mujoco_physics_grasp.launch.py",
                {
                    "model_path": model_path,
                    "joint_map_file": joint_map_file,
                    "target_joint_state_topic": joint_states,
                    "sim_joint_state_topic": physics_joint_states,
                    "object_states_topic": object_states,
                    "open_viewer": LaunchConfiguration("open_viewer"),
                },
            ),
            _include(
                "rebotarm_mujoco",
                "sim_task_server.launch.py",
                {
                    "model_path": model_path,
                    "joint_map_file": joint_map_file,
                    "joint_state_topic": joint_states,
                },
            ),
            GroupAction(
                condition=IfCondition(LaunchConfiguration("use_camera")),
                actions=[
                    _include(
                        "rebotarm_mujoco",
                        "sim_rgb_camera.launch.py",
                        {
                            "model_path": model_path,
                            "joint_map_file": joint_map_file,
                            "joint_state_topic": physics_joint_states,
                            "object_states_topic": object_states,
                            "virtual_grasp_enabled": "false",
                            "render_target_marker": "false",
                        },
                    ),
                    _include(
                        "rebotarm_mujoco",
                        "sim_color_detector.launch.py",
                        {},
                        condition=IfCondition(LaunchConfiguration("use_color_detector")),
                    ),
                ],
            ),
            _include(
                "rebotarm_mujoco",
                "joint_slider_gui.launch.py",
                {"publish_mode": "commands"},
                condition=IfCondition(LaunchConfiguration("use_joint_gui")),
            ),
        ]
    )
