#!/usr/bin/env python3
"""Standalone simulation trace — runs full nav loop and prints state.

Usage: cd src && python -m pi.tests.sim_trace
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import config
from app.control.kinematics import twist_to_wheel_speeds
from app.control.navigation import NavigationController
from app.sim.synthetic_vision import SyntheticVision
from app.sim.world import SimWorld

DT = 0.05  # 20 Hz
STEPS = 4000  # 200s of sim time


def run(robot_x=100.0, robot_y=150.0, robot_theta=-math.pi / 2, label="default"):
    world = SimWorld(robot_x=robot_x, robot_y=robot_y, robot_theta=robot_theta)
    vision = SyntheticVision(seed=42)
    nav = NavigationController()

    print(f"\n{'=' * 80}")
    print(f"RUN: {label}")
    print(f"Start: ({robot_x}, {robot_y}, {math.degrees(robot_theta):.1f}°)")
    print(f"Tag:   ({world.tag_x}, {world.tag_y}, {math.degrees(world.tag_theta):.1f}°)")
    print(f"ZREF={config.ZREF_CM}, KZ={config.NAV_KZ}, KP={config.NAV_KP_PITCH}")
    print(f"{'=' * 80}")
    print(
        f"{'step':>5} | {'x':>7} {'y':>7} {'θ°':>7} | "
        f"{'z_cm':>6} {'x_cm':>6} {'pitch':>6} | "
        f"{'v':>6} {'ω':>6} | {'w_e':>6} {'w_d':>6} | fb"
    )
    print("-" * 95)

    tag_lost_count = 0
    best_dist = 999
    converged_step = None

    for i in range(STEPS):
        vs = vision.compute(
            world.robot_x,
            world.robot_y,
            world.robot_theta,
            world.tag_x,
            world.tag_y,
            world.tag_theta,
            world.tag_id,
        )

        if vs.detectado and vs.z_cm is not None:
            tag_lost_count = 0
            v, omega = nav.compute(vs.z_cm, vs.x_cm or 0, vs.pitch_deg or 0)
            w_esq, w_dir = twist_to_wheel_speeds(v, omega)

            dist = math.sqrt(
                (world.robot_x - world.tag_x) ** 2 + (world.robot_y - world.tag_y) ** 2
            )
            if dist < best_dist:
                best_dist = dist

            if i < 50 or i % 100 == 0 or abs(vs.z_cm - config.ZREF_CM) < 3:
                fb = "FB" if nav.using_fallback else "  "
                print(
                    f"{i:5d} | {world.robot_x:7.1f} {world.robot_y:7.1f} "
                    f"{math.degrees(world.robot_theta):7.1f} | "
                    f"{vs.z_cm:6.1f} {vs.x_cm:6.1f} {vs.pitch_deg:6.1f} | "
                    f"{v:6.2f} {omega:6.3f} | {w_esq:6.2f} {w_dir:6.2f} | {fb}"
                )

            if (
                converged_step is None
                and abs(vs.z_cm - config.ZREF_CM) < 2
                and abs(vs.pitch_deg) < 5
                and abs(vs.x_cm) < 3
            ):
                converged_step = i
        else:
            tag_lost_count += 1
            w_esq, w_dir = 0.0, 0.0

            if tag_lost_count <= 5 or tag_lost_count % 50 == 0:
                print(
                    f"{i:5d} | {world.robot_x:7.1f} {world.robot_y:7.1f} "
                    f"{math.degrees(world.robot_theta):7.1f} | "
                    f"  LOST (count={tag_lost_count})"
                )

            if tag_lost_count > 200:
                print("  >>> TAG LOST FOR 200+ STEPS, ABORTING")
                break

        world.step(w_esq, w_dir, DT)

    dx = world.robot_x - world.tag_x
    dy = world.robot_y - world.tag_y
    final_dist = math.sqrt(dx * dx + dy * dy)
    final_theta = math.degrees(world.robot_theta)

    print("\n--- RESULT ---")
    print(f"Final pos: ({world.robot_x:.1f}, {world.robot_y:.1f}, {final_theta:.1f}°)")
    print(f"Final dist to tag: {final_dist:.1f} cm (best: {best_dist:.1f})")
    print(f"Converged at step: {converged_step}")
    print(f"Tag lost total: {tag_lost_count}")

    return converged_step is not None


if __name__ == "__main__":
    ok1 = run(100, 150, -math.pi / 2, "centered start")
    ok2 = run(120, 150, -math.pi / 2, "offset 20cm right")
    ok3 = run(100, 150, -math.pi / 2 + 0.3, "heading +17° off")

    print(f"\n{'=' * 80}")
    print(f"centered:  {'PASS' if ok1 else 'FAIL'}")
    print(f"offset:    {'PASS' if ok2 else 'FAIL'}")
    print(f"heading:   {'PASS' if ok3 else 'FAIL'}")
