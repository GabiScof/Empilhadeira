#!/usr/bin/env python3
"""Sweep test cases with full pipeline (nav → PID → motor → world → vision).

FACE-RETREAT state machine: when the robot reaches ZREF with large D
(false equilibrium), it turns to face the tag, retreats straight,
then re-approaches with corrected heading.
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import config
from app.control.kinematics import twist_to_wheel_speeds
from app.control.navigation import NavigationController, _true_lateral
from app.sim.firmware_emulator import MotorModel, PidController
from app.sim.synthetic_vision import SyntheticVision
from app.sim.world import SimWorld

DT = 0.05
PID_DT = 1.0 / config.EMU_PID_HZ
PID_SUBSTEPS = int(DT / PID_DT)
STEPS = 10000


def run_one(robot_x, robot_y, robot_theta):
    world = SimWorld(robot_x=robot_x, robot_y=robot_y, robot_theta=robot_theta)
    vision = SyntheticVision(seed=42)
    nav = NavigationController()
    pid_e = PidController(config.EMU_PID_KP, config.EMU_PID_KI, config.EMU_PID_KD)
    pid_d = PidController(config.EMU_PID_KP, config.EMU_PID_KI, config.EMU_PID_KD)
    mot_e = MotorModel()
    mot_d = MotorModel()

    lost = 0
    converged_step = None
    faces = 0
    retreats = 0

    for i in range(STEPS):
        vs = vision.compute(
            world.robot_x, world.robot_y, world.robot_theta,
            world.tag_x, world.tag_y, world.tag_theta, world.tag_id,
        )
        if vs.detectado and vs.z_cm is not None:
            lost = 0
            old_phase = nav.phase
            v, omega = nav.compute(vs.z_cm, vs.x_cm or 0, vs.pitch_deg or 0)
            if nav.phase == "FACE" and old_phase != "FACE":
                faces += 1
            if nav.phase == "RETREAT" and old_phase != "RETREAT":
                retreats += 1
            w_esq, w_dir = twist_to_wheel_speeds(v, omega)
            pid_e.setpoint = w_esq
            pid_d.setpoint = w_dir

            if converged_step is None and v == 0.0 and omega == 0.0 and nav.phase == "APPROACH":
                converged_step = i
        else:
            lost += 1
            pid_e.setpoint = 0.0
            pid_d.setpoint = 0.0
            if lost > 200:
                break

        for _ in range(PID_SUBSTEPS):
            u_e = pid_e.update(mot_e.omega, PID_DT)
            u_d = pid_d.update(mot_d.omega, PID_DT)
            mot_e.step(u_e, PID_DT)
            mot_d.step(u_d, PID_DT)

        world.step(mot_e.omega, mot_d.omega, DT)

    dx = world.robot_x - world.tag_x
    dy = world.robot_y - world.tag_y
    return {
        "conv": converged_step,
        "dist": math.sqrt(dx * dx + dy * dy),
        "lost": lost > 200,
        "x_off": dx,
        "theta_err": math.degrees(world.robot_theta) + 90,
        "faces": faces,
        "retreats": retreats,
    }


cases = [
    ("centered", 100, 150, -math.pi / 2),
    ("offset10", 110, 150, -math.pi / 2),
    ("offset15", 115, 150, -math.pi / 2),
    ("offset18", 82, 116, -math.pi / 2),
    ("offset20", 120, 150, -math.pi / 2),
    ("heading17", 100, 150, -math.pi / 2 + 0.3),
    ("off15+h11", 115, 150, -math.pi / 2 + 0.2),
    ("off20+h17", 120, 150, -math.pi / 2 + 0.3),
    ("dump_mid", 94.04, 70.14, -1.5397),
]

hdr = (
    f"{'case':>10} | {'conv':>5} | {'dist':>6}"
    f" | {'lost':>5} | {'xOff':>6} | {'θerr':>6} | {'F':>2} {'R':>2}"
)
print(hdr)
print("-" * 62)

for label, rx, ry, rt in cases:
    r = run_one(rx, ry, rt)
    c = r["conv"] if r["conv"] is not None else "---"
    status = "LOST" if r["lost"] else "ok"
    print(
        f"{label:>10} | {c:>5} | {r['dist']:6.1f} | {status:>5} | "
        f"{r['x_off']:6.1f} | {r['theta_err']:6.1f} | {r['faces']:>2} {r['retreats']:>2}"
    )
