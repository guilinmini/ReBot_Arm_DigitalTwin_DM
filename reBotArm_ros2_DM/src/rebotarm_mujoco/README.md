# reBotArm MuJoCo real2sim

This package mirrors `/rebotarm/joint_states` into a MuJoCo model. The first
version is read-only from the robot side: it does not command real hardware.

## Full simulation with RViz

From the repository root:

```bash
cd reBotArm_ros2_DM
source scripts/source_rebotarm_env.sh
colcon build --symlink-install --packages-select rebotarm_bringup rebotarm_mujoco
source install/setup.bash
ros2 launch rebotarm_mujoco simulation.launch.py
```

This starts the fake driver, MuJoCo physics, task server, overhead camera,
RViz, and a joint control window. Drag the separate joint
sliders to move the arm; RViz follows the physical simulation's feedback and
shows the raw overhead RGB image. No web connection is required. Stop any older
simulation first, and use `Ctrl+C` to stop all nodes launched here.

Color detection is off by default, and camera rendering excludes the IK target
marker overlay. Raw sensor output is published as `sensor_msgs/Image` (`rgb8`)
on `/rebotarm/mujoco/overhead_rgb/image_raw` and `sensor_msgs/CameraInfo` on
`/rebotarm/mujoco/overhead_rgb/camera_info`.

Available launch arguments:

| Argument | Default | Purpose |
| --- | --- | --- |
| `use_rviz` | `true` | Open RViz with the robot and RGB image |
| `use_joint_gui` | `true` | Open the joint command sliders |
| `open_viewer` | `true` | Open the MuJoCo viewer |
| `use_camera` | `true` | Publish raw RGB images and camera calibration |
| `use_color_detector` | `false` | Optionally run color detection when the camera is enabled |
| `model_path` | colored B601 MJCF | Use the same model for physics, IK, and rendering |
| `joint_map_file` | `joint_map_kinematic.yaml` | Map ROS joints to the model |
| `rviz_config` | `rviz/simulation.rviz` | Select an RViz layout |

For a run without GUI windows:

```bash
ros2 launch rebotarm_mujoco simulation.launch.py use_rviz:=false open_viewer:=false use_joint_gui:=false
```

In the unified launch, the sliders use `publish_mode:=commands` and publish
`JointMotorCmd` messages through the fake driver. Only the fake driver publishes
`/rebotarm/joint_states`; MuJoCo publishes the physical feedback on
`/rebotarm/mujoco/physics_joint_states`, which feeds the robot TF publisher and
camera. Slider changes send only the changed joint, and continuous command
publishing is off by default to allow task and web commands to run.
Gripper sliders use single-finger travel (0–0.05 m), converted to total opening
(0–0.10 m) for the driver. Standalone `joint_slider_gui.launch.py` keeps its
original `publish_mode:=joint_states` default for direct real2sim use.

## Run

```bash
cd ~/reBotArm_ros2_DM
source scripts/source_rebotarm_env.sh
colcon build --symlink-install --packages-select rebotarm_mujoco
source install/setup.bash
./scripts/start_real2sim.sh
```

The Seeed-style black, silver, and yellow model is the default. It keeps the
same MuJoCo joints, inertials, and collision geometry as the legacy STL model.
To open the legacy single-material model explicitly:

```bash
REAL2SIM_MODEL=legacy ./scripts/start_real2sim.sh
```

`start_real2sim.sh` opens the MuJoCo viewer and mirrors `/rebotarm/joint_states`.
Run `start_joint_slider_gui.sh`, fake bringup, or a real controller in another
terminal to publish that topic.

The slider GUI also exposes controller gravity compensation controls. They call:

```bash
ros2 service call /rebotarm/gravity_compensation/start std_srvs/srv/Trigger
ros2 service call /rebotarm/gravity_compensation/stop std_srvs/srv/Trigger
ros2 service call /rebotarm/gravity_compensation/status std_srvs/srv/Trigger
```

The main GUI entry uses the colored STL visual model. Rebuild the package first
so the split STL files from `rebotarm_bringup/description/meshes` are installed
into the MuJoCo package share directory:

```bash
colcon build --symlink-install --packages-select rebotarm_mujoco
source install/setup.bash
./scripts/start_real2sim.sh
```

The STL model uses `joint_map_kinematic.yaml`, where the single ROS `finger_left`
joint drives both MuJoCo gripper slide joints:

```yaml
finger_left:
  targets:
    - mujoco: finger_left
      scale: 1.0
    - mujoco: finger_right
      scale: -1.0
```

For the STL gripper, `finger_left` is a prismatic joint in meters. Use values in
the `0.0` to `0.05` range; larger values are clamped by the sync node to the
MJCF joint limits.

## MuJoCo tau_g compare and torque loop

Run the MuJoCo torque node:

```bash
./scripts/start_mujoco_torque_control.sh
```

By default it:

- uses the colored STL model.
- follows `/rebotarm/joint_states` as the MuJoCo torque-loop target.
- computes MuJoCo gravity torques.
- loads `reBotArm_control_py` when available and compares SDK `tau_g`.
- publishes:
  - `/rebotarm/mujoco/tau_g`
  - `/rebotarm/mujoco/sdk_tau_g`
  - `/rebotarm/mujoco/tau_g_diff`
- runs a MuJoCo-only torque loop using `tau_g + PD` and publishes
  `/rebotarm/mujoco/joint_states`.

Send a pure MuJoCo target without touching hardware:

```bash
MUJOCO_TORQUE_TARGET_TOPIC=/rebotarm/mujoco/target_joint_states ./scripts/start_mujoco_torque_control.sh

ros2 topic pub --once /rebotarm/mujoco/target_joint_states sensor_msgs/msg/JointState \
"{name: [joint1, joint2, joint3, joint4, joint5, joint6], position: [0.0, -0.7, -0.8, 0.0, 0.5, 0.0]}"
```

Watch the comparison:

```bash
ros2 topic echo /rebotarm/mujoco/tau_g --once
ros2 topic echo /rebotarm/mujoco/sdk_tau_g --once
ros2 topic echo /rebotarm/mujoco/tau_g_diff --once
```

Useful environment variables:

```bash
MUJOCO_TORQUE_MODEL=colored
MUJOCO_TORQUE_OPEN_VIEWER=false
MUJOCO_TORQUE_COMPARE_TOPIC=/rebotarm/joint_states
MUJOCO_TORQUE_TARGET_TOPIC=/rebotarm/joint_states
MUJOCO_TORQUE_LIMIT=18.0
```

## Parameters

- `model_path`: MuJoCo MJCF model path.
- `joint_map_file`: YAML mapping from ROS joint names to MuJoCo joint names.
- `joint_state_topic`: defaults to `/rebotarm/joint_states`.
- `open_viewer`: open an interactive MuJoCo viewer, defaults to `true`.
- `sync_hz`: render/sync loop frequency, defaults to `60.0`.
- `smoothing_alpha`: `1.0` means direct tracking; lower values smooth motion.
- `stale_timeout`: stop applying stale joint states after this many seconds.
- `mujoco_torque_control` adds torque-loop parameters:
  - `target_joint_state_topic`
  - `compare_joint_state_topic`
  - `sim_joint_state_topic`
  - `mujoco_tau_g_topic`
  - `sdk_tau_g_topic`
  - `tau_g_diff_topic`
  - `control_hz`
  - `publish_hz`
  - `compare_log_hz`
  - `sdk_compare_enabled`
  - `torque_limit`
  - `kp`
  - `kd`
