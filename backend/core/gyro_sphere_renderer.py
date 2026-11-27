"""
Gyroscopic Core Sphere Renderer - Design A (High-Craft Floating AI HUD)

Renders a true 32-bit per-pixel RGBA floating 3D Gyroscopic Core (`PIL.Image`):
- 3 interlocking 3D-tilted brushed titanium orbital rings with back/front depth sorting
- Shaded obsidian metallic core housing a recessed glowing neural aperture
- Reactive spring-physics "Jarvis pop" tied to live speech energy when responding
- Crisp emerald state when Mic is armed & sapphire progress arc for background tasks
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple

import numpy as np
from PIL import Image, ImageDraw


# Palette constants aligned with Unleash-Agent dark studio aesthetic
PALETTE = {
    "idle_core": (180, 192, 204),       # Cool titanium/zinc standby aperture
    "mic_core": (16, 185, 129),         # #10b981 Emerald active listening
    "thinking_core": (96, 165, 250),    # #60a5fa Sapphire processing / task
    "speaking_core": (110, 247, 198),   # Luminous emerald-white Jarvis pop
    "progress_arc": (96, 165, 250),     # #60a5fa Task progress arc
}


@dataclass
class SphereVisualState:
    """Normalized state input driving one frame of the Gyroscopic Core renderer."""
    mode: str = "IDLE"              # "IDLE" | "LISTENING" | "THINKING" | "SPEAKING"
    mic_active: bool = False        # User toggle: True keeps ring/core emerald
    speech_energy: float = 0.0      # [0.0 .. 1.0] speaker amplitude during reply
    task_progress: float = 0.0      # [0.0 .. 100.0] active background task %
    active_tasks_count: int = 0
    hovered: bool = False


class GyroSphereRenderer:
    """
    2x supersampled + numpy-shaded per-pixel alpha renderer for the Gyroscopic Core.
    Optimized for <3 ms frame generation at 104x104 output resolution.
    """

    def __init__(self, size: int = 104):
        self.size = int(size)
        self.ss = 2  # 2x supersampling for crisp anti-aliased rings & arcs
        self.hi = self.size * self.ss

        # Coordinate grids for fast vectorized core sphere & aura shading (at output size)
        c = (self.size - 1) / 2.0
        y, x = np.mgrid[0:self.size, 0:self.size].astype(np.float32)
        self._dx = x - c
        self._dy = y - c
        self._dist = np.sqrt(self._dx * self._dx + self._dy * self._dy)

        # Spring & motion state
        self._phase = 0.0
        self._pop = 0.0
        self._pop_vel = 0.0
        self._click_pop = 0.0
        self._glow_smooth = 0.0
        self._ripple = 0.0
        self._ripple_alpha = 0.0
        self._last_peak = 0.0

        # Precompute 3D ring parameter grid
        self._num_pts = 72
        self._u = np.linspace(0.0, 2.0 * math.pi, self._num_pts, endpoint=False, dtype=np.float32)
        self._cos_u = np.cos(self._u)
        self._sin_u = np.sin(self._u)

    def trigger_click_impulse(self):
        """Injects a snappy tactile pop when user clicks the sphere."""
        self._click_pop = 1.0
        self._pop_vel += 5.5

    def _step_physics(self, state: SphereVisualState, dt: float):
        dt = max(0.004, min(0.05, float(dt)))

        # Angular speed ramps smoothly by cognitive state
        if state.mode == "SPEAKING":
            speed = 2.6 + 1.8 * state.speech_energy
        elif state.mode == "THINKING":
            speed = 2.35
        elif state.mic_active or state.mode == "LISTENING":
            speed = 1.55
        else:
            speed = 0.62

        self._phase += dt * speed

        # Spring-damper for Jarvis speech "pop" + tactile click feedback
        if state.mode == "SPEAKING":
            energy = max(0.0, min(1.0, float(state.speech_energy)))
            # Punchy attack curve makes syllables pop distinctly
            target_pop = (energy ** 0.72) * 0.92 + 0.14
            if energy - self._last_peak > 0.22 and energy > 0.52:
                self._ripple = 0.0
                self._ripple_alpha = min(0.95, 0.45 + energy * 0.5)
            self._last_peak = energy * 0.85
        else:
            self._last_peak *= 0.85
            target_pop = 0.08 if state.hovered else 0.0
            if state.mic_active:
                # Subtle organic breathing while listening
                target_pop += 0.05 * (0.5 + 0.5 * math.sin(self._phase * 2.1))

        if self._click_pop > 0.001:
            target_pop = max(target_pop, self._click_pop * 0.7)
            self._click_pop *= math.exp(-dt * 9.0)

        # Critically-underdamped spring -> crisp expansion with tiny organic settle
        stiffness = 195.0
        damping = 17.5
        accel = stiffness * (target_pop - self._pop) - damping * self._pop_vel
        self._pop_vel += accel * dt
        self._pop = max(-0.08, min(1.35, self._pop + self._pop_vel * dt))

        # Smooth glow intensity & expanding harmonic ripple
        target_glow = 1.0 if state.mode == "SPEAKING" else (0.72 if state.mic_active else (0.65 if state.active_tasks_count > 0 else 0.18))
        self._glow_smooth += (target_glow - self._glow_smooth) * min(1.0, dt * 8.0)

        if self._ripple_alpha > 0.01:
            self._ripple += dt * 1.9
            self._ripple_alpha *= math.exp(-dt * 4.2)
            if self._ripple > 1.0:
                self._ripple_alpha = 0.0

    def _resolve_accent_rgb(self, state: SphereVisualState) -> Tuple[int, int, int]:
        if state.mode == "SPEAKING":
            return PALETTE["speaking_core"]
        if state.mic_active or state.mode == "LISTENING":
            return PALETTE["mic_core"]
        if state.mode == "THINKING" or state.active_tasks_count > 0:
            return PALETTE["thinking_core"]
        return PALETTE["idle_core"]

    @staticmethod
    def _rot_matrix(rx: float, ry: float, rz: float) -> np.ndarray:
        cx, sx = math.cos(rx), math.sin(rx)
        cy, sy = math.cos(ry), math.sin(ry)
        cz, sz = math.cos(rz), math.sin(rz)
        mx = np.array([[1.0, 0.0, 0.0], [0.0, cx, -sx], [0.0, sx, cx]], dtype=np.float32)
        my = np.array([[cy, 0.0, sy], [0.0, 1.0, 0.0], [-sy, 0.0, cy]], dtype=np.float32)
        mz = np.array([[cz, -sz, 0.0], [sz, cz, 0.0], [0.0, 0.0, 1.0]], dtype=np.float32)
        return mz @ my @ mx

    def _render_core_and_aura(self, state: SphereVisualState, accent: Tuple[int, int, int]) -> np.ndarray:
        """Vectorized dark metallic titanium core sphere + glowing neural aperture + outer aura."""
        buf = np.zeros((self.size, self.size, 4), dtype=np.float32)
        pop = max(0.0, self._pop)

        # Core sphere scales radially with pop impulse
        core_r = 18.0 + pop * 4.2
        dist = self._dist
        dx = self._dx
        dy = self._dy

        ar, ag, ab = [float(v) for v in accent]

        # 1. Soft atmospheric dark drop shadow + state aura behind gyroscope
        aura_r = 48.0 + pop * 5.0
        aura_t = np.clip(1.0 - dist / aura_r, 0.0, 1.0)
        aura_glow = (aura_t ** 2.3) * (0.30 + 0.44 * self._glow_smooth + pop * 0.28)
        buf[:, :, 0] += ar * 0.55 * aura_glow
        buf[:, :, 1] += ag * 0.55 * aura_glow
        buf[:, :, 2] += ab * 0.55 * aura_glow
        buf[:, :, 3] += aura_glow * 155.0

        # Subtle harmonic ripple wave during Jarvis speech peaks
        if self._ripple_alpha > 0.02:
            rip_r = core_r + 11.0 + self._ripple * 20.0
            rip_band = np.exp(-((dist - rip_r) ** 2) / 2.2) * self._ripple_alpha
            buf[:, :, 0] += ar * rip_band * 0.95
            buf[:, :, 1] += ag * rip_band * 0.95
            buf[:, :, 2] += ab * rip_band * 0.95
            buf[:, :, 3] += rip_band * 185.0

        # 2. Central 3D Obsidian Metallic Sphere
        # Anti-aliased edge mask within 1px border
        sphere_alpha = np.clip(core_r + 0.7 - dist, 0.0, 1.0)
        inside = sphere_alpha > 0.001

        nx = np.zeros_like(dist)
        ny = np.zeros_like(dist)
        nz = np.zeros_like(dist)
        r_norm = np.minimum(dist / max(core_r, 1e-3), 0.999)
        nx[inside] = dx[inside] / core_r
        ny[inside] = dy[inside] / core_r
        nz[inside] = np.sqrt(np.maximum(0.0, 1.0 - r_norm[inside] ** 2))

        # Top-left studio key light (-0.48, -0.58, 0.66)
        ndotl = np.clip(-0.48 * nx - 0.58 * ny + 0.66 * nz, 0.0, 1.0)
        spec = (ndotl ** 14.0) * 0.62
        fresnel = (1.0 - nz) ** 2.5

        # Dark brushed titanium surface base
        base_v = 14.0 + 42.0 * (ndotl ** 1.3) + spec * 165.0
        sph_r = base_v + fresnel * (26.0 + ar * 0.16)
        sph_g = base_v + fresnel * (28.0 + ag * 0.16) + 2.0
        sph_b = base_v + fresnel * (34.0 + ab * 0.16) + 6.0

        # Recessed machined aperture housing ring around inner lens
        bezel_ring = np.exp(-((dist - (core_r * 0.58)) ** 2) / 0.9) * 0.35
        sph_r += 95.0 * bezel_ring
        sph_g += 102.0 * bezel_ring
        sph_b += 112.0 * bezel_ring

        # Subtle glowing inner neural lens ("the eye") centered inside obsidian shell
        lens_r = 6.8 + pop * 3.1
        lens_d = dist / lens_r
        lens_core = np.exp(-(lens_d ** 2) * 1.45)
        lens_hot = np.exp(-(lens_d ** 2) * 5.0)

        core_power = (
            0.34 if (not state.mic_active and state.mode == "IDLE")
            else (0.88 + 0.24 * math.sin(self._phase * 2.2) if state.mode != "SPEAKING" else 1.08 + pop * 0.45)
        )
        core_power = max(0.2, min(1.5, core_power))

        sph_r = np.where(inside, sph_r * (1.0 - lens_core * 0.68) + (ar * lens_core + 255.0 * lens_hot * 0.88) * core_power, 0.0)
        sph_g = np.where(inside, sph_g * (1.0 - lens_core * 0.68) + (ag * lens_core + 255.0 * lens_hot * 0.90) * core_power, 0.0)
        sph_b = np.where(inside, sph_b * (1.0 - lens_core * 0.68) + (ab * lens_core + 255.0 * lens_hot * 0.88) * core_power, 0.0)

        # Crisp 1px bright specular rim along sphere equator
        rim_ring = np.exp(-((dist - (core_r - 0.6)) ** 2) / 0.7) * (0.48 + 0.38 * fresnel)
        sph_r += (215.0 + ar * 0.2) * rim_ring
        sph_g += (222.0 + ag * 0.2) * rim_ring
        sph_b += (232.0 + ab * 0.2) * rim_ring

        # Alpha-blend sphere cleanly onto aura buffer
        sa = sphere_alpha
        buf[:, :, 0] = buf[:, :, 0] * (1.0 - sa) + np.clip(sph_r, 0.0, 255.0) * sa
        buf[:, :, 1] = buf[:, :, 1] * (1.0 - sa) + np.clip(sph_g, 0.0, 255.0) * sa
        buf[:, :, 2] = buf[:, :, 2] * (1.0 - sa) + np.clip(sph_b, 0.0, 255.0) * sa
        buf[:, :, 3] = np.clip(buf[:, :, 3] * (1.0 - sa) + 255.0 * sa, 0.0, 255.0)

        return np.clip(buf, 0.0, 255.0).astype(np.uint8)

    def _draw_gyro_rings(
        self,
        state: SphereVisualState,
        accent: Tuple[int, int, int],
    ) -> Tuple[Image.Image, Image.Image]:
        """Draws back (z < 0) and front (z >= 0) halves of 3 interlocking 3D titanium orbital rings cleanly."""
        back_img = Image.new("RGBA", (self.hi, self.hi), (0, 0, 0, 0))
        front_img = Image.new("RGBA", (self.hi, self.hi), (0, 0, 0, 0))
        d_back = ImageDraw.Draw(back_img)
        d_front = ImageDraw.Draw(front_img)

        pop = max(0.0, self._pop)
        center = (self.hi - 1) / 2.0
        p = self._phase

        # Three orthogonal-ish gimbal rings with distinct precession rates & pop expansion
        ring_specs = [
            (26.5 + pop * 5.0, 0.62, 0.35 + p * 0.92, p * 0.41, 0.45 + p * 0.55, 2.7 * self.ss),
            (30.2 + pop * 5.8, -0.58, 1.15 - p * 0.78, -0.45 + p * 0.52, -0.82 - p * 0.38, 2.4 * self.ss),
            (33.5 + pop * 6.5, 1.18 + math.sin(p * 0.35) * 0.14, -0.45 + p * 0.64, 0.75 + p * 0.48, 0.2 + p * 0.7, 2.1 * self.ss),
        ]

        circle_pts = np.stack([self._cos_u, self._sin_u, np.zeros_like(self._cos_u)], axis=0)
        ar, ag, ab = accent
        accent_mix = 0.65 if state.mode == "SPEAKING" else (0.45 if state.mic_active else (0.36 if state.active_tasks_count > 0 else 0.12))

        n = self._num_pts

        def _mix_rgb(lum: float, mix: float) -> Tuple[int, int, int]:
            return (
                int(min(255.0, lum * (1.0 - mix * 0.58) + ar * mix)),
                int(min(255.0, lum * (1.0 - mix * 0.58) + ag * mix)),
                int(min(255.0, lum * (1.0 - mix * 0.58) + ab * mix)),
            )

        for radius_out, rx, ry, rz, sheen_phase, stroke_w in ring_specs:
            r_hi = radius_out * self.ss
            rot = self._rot_matrix(rx, ry, rz)
            pts = rot @ (circle_pts * r_hi)

            xs = center + pts[0]
            ys = center + pts[1]
            zs = pts[2]

            w_base = max(2, int(round(stroke_w)))
            w_edge = w_base + 2
            w_hi = max(1, w_base // 2)

            # Group consecutive samples into unbroken back (z < 0) and front (z >= 0) runs
            runs: list[Tuple[bool, list[Tuple[float, float]]]] = []
            for i in range(n + 1):
                idx = i % n
                front = bool(zs[idx] >= 0.0)
                pt = (float(xs[idx]), float(ys[idx]))
                if not runs:
                    runs.append((front, [pt]))
                elif runs[-1][0] == front:
                    runs[-1][1].append(pt)
                else:
                    # Include crossing boundary point cleanly in both halves so zero gap appears
                    runs[-1][1].append(pt)
                    runs.append((front, [pt]))

            # Merge wrap-around if first and last runs share same visibility
            if len(runs) >= 2 and runs[0][0] == runs[-1][0]:
                merged_pts = runs[-1][1][:-1] + runs[0][1]
                runs[0] = (runs[0][0], merged_pts)
                runs.pop()

            back_color = (*_mix_rgb(108.0, accent_mix * 0.85), 145)
            front_color = (*_mix_rgb(176.0, accent_mix), 240)
            hi_color = (*_mix_rgb(236.0, accent_mix * 0.55), 215)

            for is_front, poly in runs:
                if len(poly) < 2:
                    continue
                target_draw = d_front if is_front else d_back
                bevel_alpha = 195 if is_front else 115
                target_draw.line(poly, fill=(14, 16, 22, bevel_alpha), width=w_edge, joint="curve")
                target_draw.line(poly, fill=front_color if is_front else back_color, width=w_base, joint="curve")
                if is_front and len(poly) >= 6:
                    # Smooth central metallic highlight along middle half of front arc
                    q0 = len(poly) // 4
                    q1 = max(q0 + 2, (len(poly) * 3) // 4)
                    # Shift highlight subtly with sheen_phase
                    shift = int((math.sin(sheen_phase) * 0.15) * len(poly))
                    s0 = max(0, min(len(poly) - 2, q0 + shift))
                    s1 = max(s0 + 2, min(len(poly), q1 + shift))
                    target_draw.line(poly[s0:s1], fill=hi_color, width=w_hi, joint="curve")

        # Optional outer task progress arc (sweeps clockwise from top 12 o'clock)
        if state.active_tasks_count > 0 or state.task_progress > 0.5:
            pct = max(2.0, min(100.0, float(state.task_progress)))
            pad = 7.0 * self.ss
            bbox = [pad, pad, self.hi - pad, self.hi - pad]
            pr, pg, pb = PALETTE["progress_arc"]
            d_front.arc(bbox, start=-90, end=-90 + pct * 3.6, fill=(pr, pg, pb, 240), width=max(2, int(2.3 * self.ss)))

        resample = getattr(Image, "Resampling", Image).LANCZOS
        return back_img.resize((self.size, self.size), resample), front_img.resize((self.size, self.size), resample)

    def render_frame(self, state: SphereVisualState, dt: float = 1 / 30.0) -> Image.Image:
        """Advances spring physics by `dt` and composites one crisp per-pixel RGBA frame."""
        self._step_physics(state, dt)
        accent = self._resolve_accent_rgb(state)

        core_rgba = self._render_core_and_aura(state, accent)
        back_rings, front_rings = self._draw_gyro_rings(state, accent)

        # True 3D depth composite: back rings -> core sphere + aura -> front rings
        canvas = back_rings
        core_img = Image.fromarray(core_rgba, mode="RGBA")
        canvas = Image.alpha_composite(canvas, core_img)
        canvas = Image.alpha_composite(canvas, front_rings)
        return canvas
