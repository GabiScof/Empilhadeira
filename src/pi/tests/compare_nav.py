#!/usr/bin/env python3
"""Side-by-side comparison: Reactive (APPROACH/FACE/RETREAT) vs Stanley controller.

Runs both controllers through the FULL pipeline (nav → kinematics → PID → motor
→ world → vision) on identical scenarios with deterministic seeding. Compares:
  - Convergence speed (steps / time)
  - Final accuracy (lateral offset, heading error)
  - Path smoothness (omega sign changes, RMS omega)
  - Whether FACE/RETREAT cycles were needed
"""

import math
import os
import sys
from dataclasses import dataclass, field

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import config
from app.control.kinematics import twist_to_wheel_speeds
from app.control.navigation import NavigationController, _true_lateral
from app.control.stanley_nav import StanleyNav
from app.sim.firmware_emulator import MotorModel, PidController
from app.sim.synthetic_vision import SyntheticVision
from app.sim.world import SimWorld

DT = 0.05
PID_DT = 1.0 / config.EMU_PID_HZ
PID_SUBSTEPS = int(DT / PID_DT)
MAX_STEPS = 6000


@dataclass
class RunResult:
    label: str
    controller: str
    converged_step: int | None = None
    final_dist: float = 0.0
    x_offset: float = 0.0
    theta_err: float = 0.0
    lost: bool = False
    faces: int = 0
    retreats: int = 0
    omega_sign_changes: int = 0
    omega_rms: float = 0.0
    path_length: float = 0.0
    omega_history: list[float] = field(default_factory=list)


def run_pipeline(label, controller, robot_x, robot_y, robot_theta, verbose=False):
    world = SimWorld(robot_x=robot_x, robot_y=robot_y, robot_theta=robot_theta)
    vision = SyntheticVision(seed=42)
    pid_e = PidController(config.EMU_PID_KP, config.EMU_PID_KI, config.EMU_PID_KD)
    pid_d = PidController(config.EMU_PID_KP, config.EMU_PID_KI, config.EMU_PID_KD)
    mot_e = MotorModel()
    mot_d = MotorModel()

    lost_count = 0
    result = RunResult(label=label, controller=type(controller).__name__)
    omegas = []
    prev_x, prev_y = robot_x, robot_y

    for i in range(MAX_STEPS):
        vs = vision.compute(
            world.robot_x, world.robot_y, world.robot_theta,
            world.tag_x, world.tag_y, world.tag_theta, world.tag_id,
        )

        if vs.detectado and vs.z_cm is not None:
            lost_count = 0
            z = vs.z_cm
            x = vs.x_cm or 0.0
            p = vs.pitch_deg or 0.0

            old_phase = controller.phase
            v, omega = controller.compute(z, x, p)
            new_phase = controller.phase

            if new_phase == "FACE" and old_phase != "FACE":
                result.faces += 1
            if new_phase == "RETREAT" and old_phase != "RETREAT":
                result.retreats += 1

            omegas.append(omega)

            w_esq, w_dir = twist_to_wheel_speeds(v, omega)
            pid_e.setpoint = w_esq
            pid_d.setpoint = w_dir

            converged = v == 0.0 and omega == 0.0
            if controller.phase not in ("APPROACH", "STANLEY"):
                converged = False

            if result.converged_step is None and converged:
                result.converged_step = i

            if verbose and i % 20 == 0:
                d_lat = _true_lateral(x, z, p)
                print(
                    f"  [{i:5d}] z={z:6.2f} x={x:6.2f} p={p:6.2f}° "
                    f"D={d_lat:6.2f} | v={v:6.2f} ω={omega:6.3f} "
                    f"phase={new_phase}"
                )
        else:
            lost_count += 1
            pid_e.setpoint = 0.0
            pid_d.setpoint = 0.0
            if lost_count > 300:
                result.lost = True
                break

        for _ in range(PID_SUBSTEPS):
            u_e = pid_e.update(mot_e.omega, PID_DT)
            u_d = pid_d.update(mot_d.omega, PID_DT)
            mot_e.step(u_e, PID_DT)
            mot_d.step(u_d, PID_DT)

        world.step(mot_e.omega, mot_d.omega, DT)

        dx = world.robot_x - prev_x
        dy = world.robot_y - prev_y
        result.path_length += math.sqrt(dx * dx + dy * dy)
        prev_x, prev_y = world.robot_x, world.robot_y

        if result.converged_step is not None and i > result.converged_step + 50:
            break

    dx = world.robot_x - world.tag_x
    dy = world.robot_y - world.tag_y
    result.final_dist = math.sqrt(dx * dx + dy * dy)
    result.x_offset = dx
    result.theta_err = math.degrees(world.robot_theta) + 90

    if omegas:
        result.omega_rms = math.sqrt(sum(o * o for o in omegas) / len(omegas))
        result.omega_sign_changes = sum(
            1 for i in range(1, len(omegas))
            if omegas[i] * omegas[i - 1] < 0
        )
    result.omega_history = omegas

    return result


scenarios = [
    ("straight_100cm", 100, 150, -math.pi / 2),
    ("offset_10cm_R", 110, 150, -math.pi / 2),
    ("offset_15cm_R", 115, 150, -math.pi / 2),
    ("offset_20cm_R", 120, 150, -math.pi / 2),
    ("offset_10cm_L", 90, 150, -math.pi / 2),
    ("heading_+17deg", 100, 150, -math.pi / 2 + 0.3),
    ("heading_-17deg", 100, 150, -math.pi / 2 - 0.3),
    ("off15_h+11deg", 115, 150, -math.pi / 2 + 0.2),
    ("off20_h+17deg", 120, 150, -math.pi / 2 + 0.3),
    ("close_off6cm", 100, 80, -math.pi / 2),
    ("close_o10_h5", 110, 80, -math.pi / 2 + 0.1),
    ("far_off25cm", 125, 180, -math.pi / 2),
    ("far_o25_h20", 125, 180, -math.pi / 2 + 0.35),
]


def run_comparison(verbose_scenario=None):
    reactive_results = []
    stanley_results = []

    for label, rx, ry, rt in scenarios:
        verbose = label == verbose_scenario

        if verbose:
            print(f"\n{'='*80}")
            print(f"  DETAILED TRACE: {label}")
            print(f"  Start: ({rx}, {ry}), θ={math.degrees(rt):.1f}°")
            print(f"{'='*80}")

        nav_reactive = NavigationController()
        if verbose:
            print(f"\n  --- Reactive (APPROACH/FACE/RETREAT) ---")
        r_reactive = run_pipeline(label, nav_reactive, rx, ry, rt, verbose=verbose)
        reactive_results.append(r_reactive)

        nav_stanley = StanleyNav()
        if verbose:
            print(f"\n  --- Stanley Path-Following ---")
        r_stanley = run_pipeline(label, nav_stanley, rx, ry, rt, verbose=verbose)
        stanley_results.append(r_stanley)

    return reactive_results, stanley_results


def print_comparison(reactive_results, stanley_results):
    print(f"\n\n{'='*120}")
    print("  COMPARISON: Reactive vs Stanley")
    print(f"{'='*120}")

    hdr = (
        f"{'scenario':>16} │ {'conv_R':>6} {'conv_S':>6} │ "
        f"{'dist_R':>6} {'dist_S':>6} │ "
        f"{'xOff_R':>6} {'xOff_S':>6} │ "
        f"{'θerr_R':>6} {'θerr_S':>6} │ "
        f"{'ωRMS_R':>6} {'ωRMS_S':>6} │ "
        f"{'ωFlip_R':>4} {'ωFlip_S':>4} │ "
        f"{'path_R':>6} {'path_S':>6} │ "
        f"{'F/R':>4}"
    )
    print(hdr)
    print("─" * 120)

    wins_reactive = 0
    wins_stanley = 0
    ties = 0

    for r, s in zip(reactive_results, stanley_results):
        c_r = str(r.converged_step) if r.converged_step is not None else "---"
        c_s = str(s.converged_step) if s.converged_step is not None else "---"

        fr_label = f"{r.faces}/{r.retreats}" if r.faces > 0 else "-"

        faster = ""
        if r.converged_step is not None and s.converged_step is not None:
            if s.converged_step < r.converged_step * 0.9:
                faster = " ◄S"
                wins_stanley += 1
            elif r.converged_step < s.converged_step * 0.9:
                faster = " ◄R"
                wins_reactive += 1
            else:
                faster = " ≈"
                ties += 1
        elif s.converged_step is not None and r.converged_step is None:
            faster = " ◄S"
            wins_stanley += 1
        elif r.converged_step is not None and s.converged_step is None:
            faster = " ◄R"
            wins_reactive += 1

        print(
            f"{r.label:>16} │ {c_r:>6} {c_s:>6} │ "
            f"{r.final_dist:6.1f} {s.final_dist:6.1f} │ "
            f"{r.x_offset:6.2f} {s.x_offset:6.2f} │ "
            f"{r.theta_err:6.2f} {s.theta_err:6.2f} │ "
            f"{r.omega_rms:6.3f} {s.omega_rms:6.3f} │ "
            f"{r.omega_sign_changes:4d} {s.omega_sign_changes:4d} │ "
            f"{r.path_length:6.1f} {s.path_length:6.1f} │ "
            f"{fr_label:>4}{faster}"
        )

    print(f"\n  Summary: Stanley wins {wins_stanley}, "
          f"Reactive wins {wins_reactive}, Ties {ties}")


if __name__ == "__main__":
    verbose = None
    if len(sys.argv) > 1:
        verbose = sys.argv[1]
    r_results, s_results = run_comparison(verbose_scenario=verbose)
    print_comparison(r_results, s_results)
