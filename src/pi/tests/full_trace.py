#!/usr/bin/env python3
"""Full-pipeline trace with EVERY detail logged for debugging.

Logs: step, robot pose, vision output, nav decision, wheel speeds,
motor states, phase transitions, convergence checks.
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import config
from app.control.kinematics import twist_to_wheel_speeds
from app.control.navigation import (
    NavigationController,
    _true_lateral,
    _compute_twist,
    _CENTER_THRESH,
    _CONVERGE_Z_TOL,
    _CONVERGE_D_TOL,
    _CONVERGE_P_TOL,
    _FACE_TRIGGER_D,
    _FACE_TRIGGER_TICKS,
    _FACE_MIN_TICKS,
    _FACE_X_ALIGNED,
    _FACE_PITCH_TOL,
    _RETREAT_TARGET_Z,
)
from app.sim.firmware_emulator import MotorModel, PidController
from app.sim.synthetic_vision import SyntheticVision
from app.sim.world import SimWorld

DT = 0.05
PID_DT = 1.0 / config.EMU_PID_HZ
PID_SUBSTEPS = int(DT / PID_DT)
MAX_STEPS = 6000


def run_trace(label, robot_x, robot_y, robot_theta, verbose_every=10, max_steps=MAX_STEPS):
    print(f"\n{'='*90}")
    print(f"  SCENARIO: {label}")
    print(f"  Start: x={robot_x}, y={robot_y}, θ={math.degrees(robot_theta):.1f}°")
    print(f"  Tag: x={100}, y={50}, θ={90}°")
    print(f"  Config: KZ={config.NAV_KZ} KX={config.NAV_KX} KP_PITCH={config.NAV_KP_PITCH}"
          f" ZREF={config.ZREF_CM} MAX_V={config.NAV_MAX_APPROACH_SPEED}")
    print(f"{'='*90}")

    world = SimWorld(robot_x=robot_x, robot_y=robot_y, robot_theta=robot_theta)
    vision = SyntheticVision(seed=99)
    nav = NavigationController()
    pid_e = PidController(config.EMU_PID_KP, config.EMU_PID_KI, config.EMU_PID_KD)
    pid_d = PidController(config.EMU_PID_KP, config.EMU_PID_KI, config.EMU_PID_KD)
    mot_e = MotorModel()
    mot_d = MotorModel()

    lost_count = 0
    converged_step = None
    phase_log = []
    prev_phase = None

    for i in range(max_steps):
        vs = vision.compute(
            world.robot_x, world.robot_y, world.robot_theta,
            world.tag_x, world.tag_y, world.tag_theta, world.tag_id,
        )

        if vs.detectado and vs.z_cm is not None:
            lost_count = 0
            z = vs.z_cm
            x = vs.x_cm or 0.0
            p = vs.pitch_deg or 0.0
            d_lat = _true_lateral(x, z, p)
            z_err = z - config.ZREF_CM

            old_phase = nav.phase
            v, omega = nav.compute(z, x, p)
            new_phase = nav.phase

            if new_phase != prev_phase:
                phase_log.append((i, new_phase))
                prev_phase = new_phase

            w_esq, w_dir = twist_to_wheel_speeds(v, omega)
            pid_e.setpoint = w_esq
            pid_d.setpoint = w_dir

            actually_converged = (
                v == 0.0 and omega == 0.0 and new_phase == "APPROACH"
            )
            if converged_step is None and actually_converged:
                converged_step = i

            converge_check = (
                abs(z_err) < _CONVERGE_Z_TOL
                and abs(d_lat) < _CONVERGE_D_TOL
                and abs(p) < _CONVERGE_P_TOL
            )

            if i % verbose_every == 0 or new_phase != old_phase or (converged_step == i):
                tag = ""
                if new_phase != old_phase:
                    tag = f" ** PHASE: {old_phase}->{new_phase} **"
                if converged_step == i:
                    tag += " ** CONVERGED **"

                print(
                    f"[{i:5d}] "
                    f"robot=({world.robot_x:7.2f},{world.robot_y:7.2f},θ={math.degrees(world.robot_theta):7.2f}°) "
                    f"| vis: z={z:6.2f} x={x:6.2f} p={p:6.2f}° "
                    f"| D={d_lat:6.2f} zErr={z_err:6.2f} "
                    f"| nav: v={v:6.2f} ω={omega:6.3f} phase={new_phase:8s} "
                    f"| w=({w_esq:6.2f},{w_dir:6.2f}) "
                    f"| mot=({mot_e.omega:5.2f},{mot_d.omega:5.2f}) "
                    f"| conv={converge_check}"
                    f"{tag}"
                )

            if converged_step is not None and i > converged_step + 50:
                break
        else:
            lost_count += 1
            pid_e.setpoint = 0.0
            pid_d.setpoint = 0.0
            if i % verbose_every == 0 or lost_count == 1:
                print(
                    f"[{i:5d}] "
                    f"robot=({world.robot_x:7.2f},{world.robot_y:7.2f},θ={math.degrees(world.robot_theta):7.2f}°) "
                    f"| TAG LOST (count={lost_count})"
                )
            if lost_count > 300:
                print(f"  >> TAG PERMANENTLY LOST after {i} steps")
                break

        for _ in range(PID_SUBSTEPS):
            u_e = pid_e.update(mot_e.omega, PID_DT)
            u_d = pid_d.update(mot_d.omega, PID_DT)
            mot_e.step(u_e, PID_DT)
            mot_d.step(u_d, PID_DT)

        world.step(mot_e.omega, mot_d.omega, DT)

    # Final report
    dx = world.robot_x - world.tag_x
    dy = world.robot_y - world.tag_y
    final_dist = math.sqrt(dx * dx + dy * dy)
    theta_err = math.degrees(world.robot_theta) + 90

    print(f"\n  RESULT for '{label}':")
    print(f"    Final pos: ({world.robot_x:.2f}, {world.robot_y:.2f}), θ={math.degrees(world.robot_theta):.2f}°")
    print(f"    Distance to tag: {final_dist:.2f} cm")
    print(f"    Lateral offset (x): {dx:.2f} cm")
    print(f"    Heading error: {theta_err:.2f}°")
    print(f"    Converged at step: {converged_step}")
    print(f"    Phase transitions: {phase_log}")
    print(f"    Tag lost at end: {lost_count > 300}")
    print(f"    Status: {'CONVERGED' if converged_step else 'LOST' if lost_count > 300 else 'TIMEOUT'}")

    return {
        "label": label,
        "conv": converged_step,
        "dist": final_dist,
        "x_off": dx,
        "theta_err": theta_err,
        "lost": lost_count > 300,
        "phases": phase_log,
    }


scenarios = [
    ("straight_100cm", 100, 150, -math.pi / 2),
    ("offset_10cm_right", 110, 150, -math.pi / 2),
    ("offset_15cm_right", 115, 150, -math.pi / 2),
    ("offset_20cm_right", 120, 150, -math.pi / 2),
    ("offset_10cm_left", 90, 150, -math.pi / 2),
    ("heading_+17deg", 100, 150, -math.pi / 2 + 0.3),
    ("heading_-17deg", 100, 150, -math.pi / 2 - 0.3),
    ("off15_heading11", 115, 150, -math.pi / 2 + 0.2),
    ("off20_heading17", 120, 150, -math.pi / 2 + 0.3),
    ("close_offset6", 100, 80, -math.pi / 2),
    ("close_off10_h5", 110, 80, -math.pi / 2 + 0.1),
    ("far_off25", 125, 180, -math.pi / 2),
    ("far_off25_h20", 125, 180, -math.pi / 2 + 0.35),
]


if __name__ == "__main__":
    results = []
    for label, rx, ry, rt in scenarios:
        r = run_trace(label, rx, ry, rt, verbose_every=20)
        results.append(r)

    print(f"\n\n{'='*90}")
    print("  SUMMARY")
    print(f"{'='*90}")
    hdr = f"{'scenario':>20} | {'conv':>5} | {'dist':>6} | {'xOff':>6} | {'θerr':>6} | {'status':>8} | phases"
    print(hdr)
    print("-" * 90)
    for r in results:
        c = r["conv"] if r["conv"] is not None else "---"
        st = "CONV" if r["conv"] else ("LOST" if r["lost"] else "TIMEOUT")
        phases = ",".join(f"{s}@{t}" for t, s in r["phases"])
        print(
            f"{r['label']:>20} | {c:>5} | {r['dist']:6.1f} | "
            f"{r['x_off']:6.1f} | {r['theta_err']:6.1f} | {st:>8} | {phases}"
        )

    all_ok = all(r["conv"] is not None for r in results)
    print(f"\nAll converged: {all_ok}")
    if not all_ok:
        failed = [r["label"] for r in results if r["conv"] is None]
        print(f"FAILED: {failed}")
