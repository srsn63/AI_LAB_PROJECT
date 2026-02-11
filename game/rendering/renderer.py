import pygame
import math
import traceback
import sys
from game.core.config import GameConfig


# ── Helper utilities ──────────────────────────────────────────────────

def _lerp_color(c1, c2, t):
    """Linearly interpolate between two RGB colors."""
    t = max(0.0, min(1.0, t))
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )


def _hash_xy(x, y, seed=0):
    """Cheap deterministic hash for tile variation."""
    n = x * 374761393 + y * 668265263 + seed
    n = (n ^ (n >> 13)) * 1274126177
    return n & 0xFFFFFFFF


def _health_bar_color(pct):
    """Return an RGB color for a health percentage (1.0 = green, 0.0 = red)."""
    if pct > 0.55:
        return _lerp_color((255, 220, 30), (40, 220, 75), (pct - 0.55) / 0.45)
    return _lerp_color((220, 40, 30), (255, 220, 30), pct / 0.55)


# ══════════════════════════════════════════════════════════════════════
#  RENDERER
# ══════════════════════════════════════════════════════════════════════

class GameRenderer:
    """
    Handles all rendering using Pygame.
    Decoupled from core logic – receives state to draw.

    Layout:  [ 800 px game world | 260 px info panel ]
    """

    # ── Side-panel geometry ───────────────────────────────────────────
    PANEL_W = 260                          # right-side info panel width
    PANEL_BG = (14, 14, 20)
    PANEL_BORDER = (40, 110, 200)

    # ── Colour palettes ──────────────────────────────────────────────
    TERRAIN_BASE = {
        "floor":  (58, 56, 62),
        "water":  (22, 50, 100),
        "wall":   (16, 16, 20),
        "mud":    (88, 62, 36),
        "grass":  (34, 78, 34),
        "rock":   (90, 90, 102),
    }
    TERRAIN_ALT = {
        "floor":  (50, 48, 53),
        "water":  (18, 42, 82),
        "wall":   (12, 12, 16),
        "mud":    (74, 52, 30),
        "grass":  (28, 66, 28),
        "rock":   (80, 80, 90),
    }
    TERRAIN_HIGHLIGHT = {
        "floor":  (68, 66, 72),
        "water":  (42, 78, 135),
        "wall":   (26, 26, 34),
        "mud":    (102, 80, 50),
        "grass":  (52, 108, 52),
        "rock":   (115, 115, 130),
    }
    TERRAIN_LABELS = {
        "floor": "Concrete",
        "water": "Water",
        "wall":  "Wall",
        "mud":   "Mud",
        "grass": "Grass",
        "rock":  "Rock",
    }

    AGENT_COLORS = {
        1: {
            "body":   (40, 200, 85),
            "accent": (110, 255, 155),
            "dark":   (18, 95, 38),
            "glow":   (60, 255, 120),
            "tag":    "Agent 1",
            "banner": (30, 140, 60),
        },
        2: {
            "body":   (210, 55, 55),
            "accent": (255, 140, 110),
            "dark":   (115, 22, 22),
            "glow":   (255, 80, 60),
            "tag":    "Agent 2",
            "banner": (140, 35, 35),
        },
    }

    RES_PALETTE = {
        "food":  {"fill": (230, 75, 65),  "rim": (255, 165, 145), "label": "Food"},
        "ammo":  {"fill": (45, 175, 220), "rim": (125, 225, 255), "label": "Ammo"},
        "scrap": {"fill": (165, 165, 178), "rim": (218, 218, 230), "label": "Scrap"},
    }

    STATE_INFO = {
        "FIGHT":    {"color": (255, 70, 70),   "icon": "[!]", "desc": "Engaging in combat"},
        "FLEE":     {"color": (255, 200, 50),  "icon": ">>>", "desc": "Retreating to safety"},
        "SCAVENGE": {"color": (80, 200, 255),  "icon": "[?]", "desc": "Searching for resources"},
        "EAT":      {"color": (100, 255, 100), "icon": "[+]", "desc": "Consuming food to heal"},
        "UPGRADE":  {"color": (200, 140, 255), "icon": "[^]", "desc": "Spending scrap on upgrades"},
    }

    # ── Initialisation ────────────────────────────────────────────────

    def __init__(self):
        self.config = GameConfig()
        pygame.init()

        # Total window = game area + side panel
        self.map_w = self.config.SCREEN_WIDTH   # 800
        self.map_h = self.config.SCREEN_HEIGHT   # 600
        self.win_w = self.map_w + self.PANEL_W   # 1060
        self.win_h = self.map_h                   # 600

        self.screen = pygame.display.set_mode((self.win_w, self.win_h))
        pygame.display.set_caption(self.config.TITLE)
        self.clock = pygame.time.Clock()

        # Fonts
        self.font_lg   = pygame.font.SysFont("Consolas", 22, bold=True)
        self.font_md   = pygame.font.SysFont("Consolas", 15)
        self.font_md_b = pygame.font.SysFont("Consolas", 15, bold=True)
        self.font_sm   = pygame.font.SysFont("Consolas", 12)
        self.font_sm_b = pygame.font.SysFont("Consolas", 12, bold=True)
        self.font_xs   = pygame.font.SysFont("Consolas", 10)
        self.font_tag  = pygame.font.SysFont("Consolas", 11, bold=True)
        self.font_state = pygame.font.SysFont("Consolas", 13, bold=True)
        self.font_state_map = pygame.font.SysFont("Consolas", 11, bold=True)

        # Caches
        self._tile_cache: dict = {}
        self._fog_cache: pygame.Surface | None = None
        self._fog_hero_pos: tuple | None = None
        self._grid_overlay: pygame.Surface | None = None

        # Animation
        self._anim_tick = 0

    # ── Public API ────────────────────────────────────────────────────

    def get_events(self):
        events = []
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                class QuitEvent:
                    type = "QUIT"
                events.append(QuitEvent())
        return events

    def render(self, game_state, local_agent_id=1):
        try:
            self._anim_tick += 1
            self.screen.fill((10, 10, 14))

            has_world = (
                getattr(game_state, "world", None) is not None
                and game_state.world.grid
            )
            has_agents = getattr(game_state, "agents", None) is not None

            if has_world:
                self._render_world(game_state)
                self._render_grid_overlay(game_state)
                self._render_resources(game_state)

            if has_world and has_agents:
                self._render_fog_of_war(game_state, local_agent_id)

            if has_agents:
                self._render_agents(game_state, local_agent_id)

            # Right-side info panel (always drawn)
            self._render_panel(game_state, local_agent_id)

            # Game over overlay
            if getattr(game_state, "game_over", False):
                self._render_game_over(game_state, local_agent_id)

            pygame.display.flip()
        except Exception as e:
            print(f"Renderer Error: {e}")
            traceback.print_exc()

    def tick(self, fps: int):
        self.clock.tick(fps)

    def quit(self):
        pygame.quit()

    # ══════════════════════════════════════════════════════════════════
    #  GAME  OVER  OVERLAY
    # ══════════════════════════════════════════════════════════════════

    def _render_game_over(self, game_state, local_agent_id) -> None:
        """Full-screen game-over overlay."""
        winner = getattr(game_state, "winner", None)
        is_winner = (winner == local_agent_id)

        # Dim the whole screen
        dim = pygame.Surface((self.win_w, self.win_h), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 160))
        self.screen.blit(dim, (0, 0))

        # Center of game area
        cx = self.map_w // 2
        cy = self.map_h // 2

        # Animated pulse
        pulse = 0.5 + 0.5 * math.sin(self._anim_tick * 0.04)

        # Banner box
        bw, bh = 420, 180
        bx = cx - bw // 2
        by = cy - bh // 2

        if is_winner:
            border_col = (60, 220, 100)
            title_text = "VICTORY!"
            title_col  = (80, 255, 120)
            sub_text   = f"Agent {local_agent_id} wins the match!"
            glow_col   = (40, 200, 80)
        else:
            border_col = (220, 60, 60)
            title_text = "DEFEATED"
            title_col  = (255, 80, 80)
            sub_text   = f"Agent {winner} wins the match!"
            glow_col   = (200, 40, 40)

        # Glow behind box
        glow_r = int(240 + 20 * pulse)
        glow_s = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
        pygame.draw.circle(glow_s, (*glow_col, int(25 + 15 * pulse)), (glow_r, glow_r), glow_r)
        self.screen.blit(glow_s, (cx - glow_r, cy - glow_r))

        # Box
        box = pygame.Surface((bw, bh), pygame.SRCALPHA)
        pygame.draw.rect(box, (10, 10, 18, 230), (0, 0, bw, bh), border_radius=10)
        pygame.draw.rect(box, (*border_col, 200), (0, 0, bw, bh), 3, border_radius=10)
        self.screen.blit(box, (bx, by))

        # Title
        title = self.font_lg.render(title_text, True, title_col)
        self.screen.blit(title, (cx - title.get_width() // 2, by + 30))

        # Subtitle line
        sub = self.font_md_b.render(sub_text, True, (200, 205, 220))
        self.screen.blit(sub, (cx - sub.get_width() // 2, by + 70))

        # Divider
        pygame.draw.line(self.screen, (60, 65, 85), (bx + 30, by + 105), (bx + bw - 30, by + 105), 1)

        # "GAME OVER" label
        go = self.font_sm.render("GAME  OVER", True, (140, 145, 170))
        self.screen.blit(go, (cx - go.get_width() // 2, by + 115))

        # Tick info
        tick_text = f"Final tick: {getattr(game_state, 'ticks', 0)}"
        tt = self.font_xs.render(tick_text, True, (100, 105, 125))
        self.screen.blit(tt, (cx - tt.get_width() // 2, by + 140))

    # ══════════════════════════════════════════════════════════════════
    #  WORLD  TILES
    # ══════════════════════════════════════════════════════════════════

    def _get_tile_surface(self, terrain_value: str, variant: int) -> pygame.Surface:
        key = (terrain_value, variant)
        if key in self._tile_cache:
            return self._tile_cache[key]

        ts = self.config.TILE_SIZE
        surf = pygame.Surface((ts, ts))

        base = self.TERRAIN_BASE.get(terrain_value, (255, 0, 255))
        alt  = self.TERRAIN_ALT.get(terrain_value, base)
        hi   = self.TERRAIN_HIGHLIGHT.get(terrain_value, base)

        blend = (variant % 100) / 100.0 * 0.4
        bg = _lerp_color(base, alt, blend)
        surf.fill(bg)

        # ── per-terrain procedural texture ──
        if terrain_value == "grass":
            for i in range(10):
                bx = ((variant * (i + 1) * 7) % (ts - 4)) + 2
                by = ((variant * (i + 1) * 13) % (ts - 4)) + 2
                bh = 3 + (variant * (i + 1)) % 5
                shade = _lerp_color(hi, (60, 140, 60), (i % 3) / 3.0)
                pygame.draw.line(surf, shade, (bx, by), (bx + (i % 3) - 1, by - bh), 1)
            # Scatter a few lighter dots
            for i in range(4):
                dx = ((variant * (i + 7) * 19) % (ts - 6)) + 3
                dy = ((variant * (i + 7) * 23) % (ts - 6)) + 3
                surf.set_at((dx, dy), hi)
        elif terrain_value == "water":
            phase = (variant % 7)
            for wy in range(3 + phase, ts, 7):
                amp = 1 + (variant + wy) % 3
                for wx in range(0, ts, 2):
                    offset = int(amp * math.sin((wx + phase) * 0.5))
                    py = min(ts - 1, max(0, wy + offset))
                    c = _lerp_color(hi, (55, 100, 170), (wx % 6) / 6.0)
                    surf.set_at((wx, py), c)
        elif terrain_value == "rock":
            for i in range(3):
                cx = 3 + ((variant * (i + 2) * 11) % (ts - 6))
                cy = 3 + ((variant * (i + 2) * 17) % (ts - 6))
                length = 4 + (variant * (i + 1)) % 6
                angle = (variant * (i + 1) * 3) % 360
                ex = cx + int(length * math.cos(math.radians(angle)))
                ey = cy + int(length * math.sin(math.radians(angle)))
                pygame.draw.line(surf, alt, (cx, cy), (ex, ey), 1)
            # Tiny specular dots
            for i in range(3):
                sx = ((variant * (i + 5) * 13) % (ts - 4)) + 2
                sy = ((variant * (i + 5) * 29) % (ts - 4)) + 2
                surf.set_at((sx, sy), hi)
        elif terrain_value == "mud":
            for i in range(6):
                sx = ((variant * (i + 3) * 11) % (ts - 8)) + 4
                sy = ((variant * (i + 3) * 17) % (ts - 8)) + 4
                r = 2 + (variant * (i + 1)) % 3
                pygame.draw.circle(surf, alt, (sx, sy), r)
            # Dark streaks
            for i in range(2):
                x1 = ((variant * (i + 1) * 31) % ts)
                pygame.draw.line(surf, _lerp_color(base, (50, 35, 18), 0.5),
                                 (x1, 0), (x1 + 4, ts), 1)
        elif terrain_value == "wall":
            # Brick pattern with mortar
            mortar = _lerp_color(base, (8, 8, 10), 0.5)
            for by_pos in range(0, ts, 8):
                offset = 0 if (by_pos // 8) % 2 == 0 else 8
                for bx_pos in range(offset, ts + 8, 16):
                    # Brick fill slight variation
                    bv = (bx_pos * 13 + by_pos * 7 + variant) % 100
                    bc = _lerp_color(base, hi, bv / 200.0)
                    pygame.draw.rect(surf, bc, (bx_pos + 1, by_pos + 1, 14, 6))
                    pygame.draw.rect(surf, mortar, (bx_pos, by_pos, 16, 8), 1)
            # Dark inner shadow at top-left of each brick
            for by_pos in range(0, ts, 8):
                offset = 0 if (by_pos // 8) % 2 == 0 else 8
                for bx_pos in range(offset, ts + 8, 16):
                    pygame.draw.line(surf, mortar, (bx_pos + 1, by_pos + 1), (bx_pos + 13, by_pos + 1), 1)
        elif terrain_value == "floor":
            # Concrete: subtle noise + hairline cracks
            for i in range(5):
                px = ((variant * (i + 1) * 31) % (ts - 2)) + 1
                py = ((variant * (i + 1) * 37) % (ts - 2)) + 1
                surf.set_at((px, py), hi)
            if variant % 4 == 0:
                cx0 = variant % ts
                pygame.draw.line(surf, alt, (cx0, 0), (cx0 + 3, ts), 1)

        self._tile_cache[key] = surf
        return surf

    def _render_world(self, game_state) -> None:
        ts = self.config.TILE_SIZE
        world = game_state.world
        for y, row in enumerate(world.grid):
            for x, tile in enumerate(row):
                variant = _hash_xy(x, y) & 0xFFFF
                surf = self._get_tile_surface(tile.terrain.value, variant)
                self.screen.blit(surf, (x * ts, y * ts))

    def _render_grid_overlay(self, game_state) -> None:
        """Very subtle grid lines (cached)."""
        ts = self.config.TILE_SIZE
        w = game_state.world.width * ts
        h = game_state.world.height * ts

        if self._grid_overlay is None or self._grid_overlay.get_size() != (w, h):
            overlay = pygame.Surface((w, h), pygame.SRCALPHA)
            gc = (255, 255, 255, 10)
            for x in range(0, w, ts):
                pygame.draw.line(overlay, gc, (x, 0), (x, h))
            for y in range(0, h, ts):
                pygame.draw.line(overlay, gc, (0, y), (w, y))
            self._grid_overlay = overlay
        self.screen.blit(self._grid_overlay, (0, 0))

    # ══════════════════════════════════════════════════════════════════
    #  RESOURCES
    # ══════════════════════════════════════════════════════════════════

    def _render_resources(self, game_state) -> None:
        ts = self.config.TILE_SIZE
        world = game_state.world
        pulse = 0.5 + 0.5 * math.sin(self._anim_tick * 0.07)

        for res in world.resources:
            pal = self.RES_PALETTE.get(res.type, self.RES_PALETTE["scrap"])
            cx = res.x * ts + ts // 2
            cy = res.y * ts + ts // 2

            # ── glow ──
            glow_r = int(8 + 4 * pulse)
            glow_surf = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
            pygame.draw.circle(glow_surf, (*pal["fill"], int(40 + 25 * pulse)),
                               (glow_r, glow_r), glow_r)
            self.screen.blit(glow_surf, (cx - glow_r, cy - glow_r))

            # ── icon shape ──
            if res.type == "food":
                # Plus / medkit cross
                pygame.draw.rect(self.screen, pal["fill"], (cx - 5, cy - 2, 10, 4))
                pygame.draw.rect(self.screen, pal["fill"], (cx - 2, cy - 5, 4, 10))
                pygame.draw.rect(self.screen, pal["rim"], (cx - 5, cy - 2, 10, 4), 1)
                pygame.draw.rect(self.screen, pal["rim"], (cx - 2, cy - 5, 4, 10), 1)
            elif res.type == "ammo":
                # Bullet: pointed top, rect body
                pts = [(cx, cy - 6), (cx + 3, cy - 3), (cx + 3, cy + 5),
                       (cx - 3, cy + 5), (cx - 3, cy - 3)]
                pygame.draw.polygon(self.screen, pal["fill"], pts)
                pygame.draw.polygon(self.screen, pal["rim"], pts, 1)
                pygame.draw.line(self.screen, pal["rim"], (cx - 3, cy + 1), (cx + 3, cy + 1), 1)
            else:
                # Gear / cog
                pygame.draw.circle(self.screen, pal["fill"], (cx, cy), 5)
                pygame.draw.circle(self.screen, pal["rim"], (cx, cy), 5, 1)
                pygame.draw.circle(self.screen, pal["rim"], (cx, cy), 2, 1)
                for a in range(0, 360, 45):
                    ex = cx + int(7 * math.cos(math.radians(a)))
                    ey = cy + int(7 * math.sin(math.radians(a)))
                    pygame.draw.line(self.screen, pal["rim"], (cx, cy), (ex, ey), 1)

            # ── amount badge ──
            amt = getattr(res, "amount", 0)
            if amt > 0:
                txt = self.font_xs.render(str(int(amt)), True, (255, 255, 255))
                tx = cx - txt.get_width() // 2
                ty = cy + 7
                bg = pygame.Surface((txt.get_width() + 4, txt.get_height() + 2), pygame.SRCALPHA)
                bg.fill((0, 0, 0, 140))
                self.screen.blit(bg, (tx - 2, ty - 1))
                self.screen.blit(txt, (tx, ty))

    # ══════════════════════════════════════════════════════════════════
    #  FOG OF WAR
    # ══════════════════════════════════════════════════════════════════

    def _render_fog_of_war(self, game_state, local_agent_id) -> None:
        hero = next((a for a in game_state.agents if a.id == local_agent_id), None)
        if not hero:
            return

        ts = self.config.TILE_SIZE
        hero_px = hero.x * ts + ts // 2
        hero_py = hero.y * ts + ts // 2
        hero_pos = (hero_px, hero_py)

        if self._fog_cache is None or self._fog_hero_pos != hero_pos:
            fog = pygame.Surface((self.map_w, self.map_h), pygame.SRCALPHA)
            fog.fill((5, 5, 14, 180))

            view_radius = 10 * ts
            steps = 32
            for i in range(steps, 0, -1):
                r = int(view_radius * i / steps)
                alpha = int(180 * (i / steps) ** 1.5)
                pygame.draw.circle(fog, (5, 5, 14, alpha), hero_pos, r)

            self._fog_cache = fog
            self._fog_hero_pos = hero_pos

        self.screen.blit(self._fog_cache, (0, 0))

    # ══════════════════════════════════════════════════════════════════
    #  AGENTS  (on-map rendering)
    # ══════════════════════════════════════════════════════════════════

    def _render_agents(self, game_state, local_agent_id=1) -> None:
        ts = self.config.TILE_SIZE
        half = ts // 2

        for agent in game_state.agents:
            if agent.health <= 0:
                continue

            cx = agent.x * ts + half
            cy = agent.y * ts + half
            is_local = (agent.id == local_agent_id)
            pal = self.AGENT_COLORS.get(agent.id, self.AGENT_COLORS[2])

            # ── ground shadow ──
            shad = pygame.Surface((ts, ts), pygame.SRCALPHA)
            pygame.draw.ellipse(shad, (0, 0, 0, 55), (3, ts - 10, ts - 6, 9))
            self.screen.blit(shad, (agent.x * ts, agent.y * ts))

            # ── animated glow ring ──
            pulse = 0.5 + 0.5 * math.sin(self._anim_tick * 0.06 + agent.id * 1.7)
            gr = int(half * 0.6 + 3 * pulse)
            ga = int(30 + 30 * pulse)
            gs = pygame.Surface((gr * 2 + 6, gr * 2 + 6), pygame.SRCALPHA)
            pygame.draw.circle(gs, (*pal["glow"], ga), (gr + 3, gr + 3), gr)
            self.screen.blit(gs, (cx - gr - 3, cy - gr - 3))

            # ── body: layered diamond with bevelled look ──
            r = int(half * 0.52)
            diamond  = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
            ri = int(r * 0.64)
            inner    = [(cx, cy - ri), (cx + ri, cy), (cx, cy + ri), (cx - ri, cy)]
            ri2 = int(r * 0.30)
            core     = [(cx, cy - ri2), (cx + ri2, cy), (cx, cy + ri2), (cx - ri2, cy)]

            # Outer shadow offset
            shadow_off = [(cx + 1, cy - r + 1), (cx + r + 1, cy + 1),
                          (cx + 1, cy + r + 1), (cx - r + 1, cy + 1)]
            pygame.draw.polygon(self.screen, (0, 0, 0, 80) if False else (0, 0, 0), shadow_off)
            pygame.draw.polygon(self.screen, pal["dark"], diamond)
            pygame.draw.polygon(self.screen, pal["body"], inner)
            # Bright top-left highlight on inner
            hi_pts = [(cx, cy - ri), (cx + ri // 2, cy - ri // 2), (cx, cy), (cx - ri // 2, cy - ri // 2)]
            hi_surf = pygame.Surface((ts, ts), pygame.SRCALPHA)
            hi_pts_local = [(p[0] - agent.x * ts, p[1] - agent.y * ts) for p in hi_pts]
            pygame.draw.polygon(hi_surf, (*pal["accent"], 60), hi_pts_local)
            self.screen.blit(hi_surf, (agent.x * ts, agent.y * ts))
            pygame.draw.polygon(self.screen, pal["accent"], core)
            pygame.draw.polygon(self.screen, pal["accent"], diamond, 2)

            # ── "Agent N" banner above ──
            tag_text = pal.get("tag", f"Agent {agent.id}")
            banner_col = pal.get("banner", pal["dark"])
            tag_surf = self.font_tag.render(tag_text, True, (255, 255, 255))
            tw = tag_surf.get_width()
            th = tag_surf.get_height()
            tx = cx - (tw + 8) // 2
            ty = agent.y * ts - 24

            # Pill-shaped banner
            bw = tw + 10
            bh = th + 4
            banner = pygame.Surface((bw, bh), pygame.SRCALPHA)
            pygame.draw.rect(banner, (*banner_col, 210), (0, 0, bw, bh), border_radius=4)
            pygame.draw.rect(banner, (*pal["accent"], 180), (0, 0, bw, bh), 1, border_radius=4)
            # Small triangle pointer at bottom center
            tri_cx = bw // 2
            pygame.draw.polygon(banner, (*banner_col, 210),
                                [(tri_cx - 4, bh - 1), (tri_cx + 4, bh - 1), (tri_cx, bh + 3)])
            self.screen.blit(banner, (tx, ty))
            self.screen.blit(tag_surf, (tx + 5, ty + 2))

            # ── health bar (wide, 5px tall) ──
            max_hp = getattr(agent, "max_health", 100.0)
            hp_pct = max(0.0, min(1.0, agent.health / max_hp))
            bar_w = ts + 6
            bar_h = 5
            bar_x = agent.x * ts - 3
            bar_y = agent.y * ts - 8

            pygame.draw.rect(self.screen, (20, 0, 0), (bar_x, bar_y, bar_w, bar_h), border_radius=2)
            fill_w = max(1, int(bar_w * hp_pct))
            pygame.draw.rect(self.screen, _health_bar_color(hp_pct),
                             (bar_x, bar_y, fill_w, bar_h), border_radius=2)
            # shine
            shine = pygame.Surface((fill_w, max(1, bar_h // 2)), pygame.SRCALPHA)
            shine.fill((255, 255, 255, 45))
            self.screen.blit(shine, (bar_x, bar_y))
            # border
            pygame.draw.rect(self.screen, (180, 180, 180),
                             (bar_x, bar_y, bar_w, bar_h), 1, border_radius=2)

            # ── HP number right of bar ──
            hp_txt = self.font_xs.render(f"{int(agent.health)}", True, (255, 255, 255))
            self.screen.blit(hp_txt, (bar_x + bar_w + 3, bar_y - 1))

            # ── state badge BELOW agent (local agent with FSM) ──
            state_name = None
            if hasattr(agent, "fsm") and agent.fsm and getattr(agent.fsm, "current_state", None):
                state_name = agent.fsm.current_state.name

            if state_name:
                si = self.STATE_INFO.get(state_name, {"color": (200, 200, 200), "icon": "?", "desc": ""})
                st_col = si["color"]
                icon_str = si["icon"]
                label_str = f"{icon_str} {state_name}"

                lbl = self.font_state_map.render(label_str, True, st_col)
                lx = cx - lbl.get_width() // 2
                ly = agent.y * ts + ts + 2

                # Badge background
                bw2 = lbl.get_width() + 12
                bh2 = lbl.get_height() + 6
                badge_surf = pygame.Surface((bw2, bh2), pygame.SRCALPHA)
                pygame.draw.rect(badge_surf, (0, 0, 0, 190), (0, 0, bw2, bh2), border_radius=4)
                pygame.draw.rect(badge_surf, (*st_col, 200), (0, 0, bw2, bh2), 1, border_radius=4)
                # Colored left stripe
                pygame.draw.rect(badge_surf, (*st_col, 230), (0, 2, 3, bh2 - 4), border_radius=1)
                self.screen.blit(badge_surf, (lx - 6, ly - 3))
                self.screen.blit(lbl, (lx, ly))

    # ══════════════════════════════════════════════════════════════════
    #  RIGHT SIDE  INFO  PANEL
    # ══════════════════════════════════════════════════════════════════

    def _render_panel(self, game_state, local_agent_id) -> None:
        """Detailed right-side information panel."""
        pw = self.PANEL_W
        ph = self.win_h
        px = self.map_w  # panel x-offset

        # Background
        panel = pygame.Surface((pw, ph), pygame.SRCALPHA)
        panel.fill((*self.PANEL_BG, 240))
        # Gradient overlay at top
        for i in range(60):
            alpha = int(30 * (1.0 - i / 60.0))
            pygame.draw.line(panel, (40, 110, 200, alpha), (0, i), (pw, i))
        self.screen.blit(panel, (px, 0))

        # Left border line
        pygame.draw.line(self.screen, self.PANEL_BORDER, (px, 0), (px, ph), 2)

        y = 12
        pad = 12

        # ── Title ──
        title = self.font_lg.render("GOLAGULI", True, (80, 180, 255))
        self.screen.blit(title, (px + pw // 2 - title.get_width() // 2, y))
        y += title.get_height() + 2
        sub = self.font_xs.render("AI  Survival  Simulation", True, (100, 110, 130))
        self.screen.blit(sub, (px + pw // 2 - sub.get_width() // 2, y))
        y += sub.get_height() + 8
        pygame.draw.line(self.screen, (40, 50, 70), (px + pad, y), (px + pw - pad, y))
        y += 10

        # ── Game stats ──
        tick = getattr(game_state, "ticks", 0)
        fps = int(self.clock.get_fps())
        stats_text = f"TICK  {tick:>5}        FPS  {fps:>3}"
        st = self.font_sm.render(stats_text, True, (140, 145, 160))
        self.screen.blit(st, (px + pad, y))
        y += st.get_height() + 10
        pygame.draw.line(self.screen, (40, 50, 70), (px + pad, y), (px + pw - pad, y))
        y += 10

        agents = getattr(game_state, "agents", [])
        local_agent = None
        enemy_agent = None
        for a in agents:
            if a.id == local_agent_id:
                local_agent = a
            else:
                enemy_agent = a

        # ── AGENT 1 section ──
        y = self._render_agent_section(px, y, pad, pw, local_agent, agent_id=local_agent_id, label=f"AGENT  {local_agent_id}  (You)")

        pygame.draw.line(self.screen, (40, 50, 70), (px + pad, y), (px + pw - pad, y))
        y += 10

        # ── AGENT 2 section ──
        enemy_id = enemy_agent.id if enemy_agent else (2 if local_agent_id == 1 else 1)
        y = self._render_agent_section(px, y, pad, pw, enemy_agent, agent_id=enemy_id, label=f"AGENT  {enemy_id}  (Enemy)")

        pygame.draw.line(self.screen, (40, 50, 70), (px + pad, y), (px + pw - pad, y))
        y += 10

        # ── FSM State Detail Box (for local agent) ──
        y = self._render_state_detail(px, y, pad, pw, local_agent)

        # ── Terrain Legend ──
        self._render_terrain_legend(px, y, pad, pw)

    # ── helper: agent info block ──────────────────────────────────────

    def _render_agent_section(self, px, y, pad, pw, agent, agent_id, label) -> int:
        """Draw one agent's stats block; return new y."""
        pal = self.AGENT_COLORS.get(agent_id, self.AGENT_COLORS[2])
        accent = pal["accent"]
        banner_col = pal.get("banner", pal["dark"])

        # Section header with colored dot
        dot_r = 5
        dot_y = y + 7
        pygame.draw.circle(self.screen, pal["body"], (px + pad + dot_r, dot_y), dot_r)
        pygame.draw.circle(self.screen, accent, (px + pad + dot_r, dot_y), dot_r, 1)
        hdr = self.font_sm_b.render(label, True, accent)
        self.screen.blit(hdr, (px + pad + dot_r * 2 + 6, y))
        y += hdr.get_height() + 6

        if agent is None:
            na = self.font_sm.render("  Not visible", True, (80, 80, 100))
            self.screen.blit(na, (px + pad, y))
            return y + na.get_height() + 10

        max_hp = getattr(agent, "max_health", 100.0)
        hp_pct = max(0.0, min(1.0, agent.health / max_hp))

        # Health bar
        bar_x = px + pad
        bar_w = pw - pad * 2
        bar_h = 16
        pygame.draw.rect(self.screen, (25, 5, 5), (bar_x, y, bar_w, bar_h), border_radius=4)
        fill = max(1, int(bar_w * hp_pct))
        bar_c = _health_bar_color(hp_pct)
        pygame.draw.rect(self.screen, bar_c,
                         (bar_x, y, fill, bar_h), border_radius=4)
        # Glass shine
        shine = pygame.Surface((fill, bar_h // 2), pygame.SRCALPHA)
        shine.fill((255, 255, 255, 38))
        self.screen.blit(shine, (bar_x, y))
        pygame.draw.rect(self.screen, (120, 120, 120), (bar_x, y, bar_w, bar_h), 1, border_radius=4)
        # HP text centered on bar
        hp_str = f"HP  {int(agent.health)} / {int(max_hp)}"
        hp_txt = self.font_sm_b.render(hp_str, True, (255, 255, 255))
        self.screen.blit(hp_txt, (bar_x + bar_w // 2 - hp_txt.get_width() // 2,
                                  y + bar_h // 2 - hp_txt.get_height() // 2))
        y += bar_h + 8

        # Ammo / Food / Scrap with small icon-colored boxes
        inv = getattr(agent, "inventory", {})
        ammo_val  = getattr(agent, "ammo", 0)
        food_val  = inv.get("food", 0)
        scrap_val = inv.get("scrap", 0)

        res_items = [
            ("Ammo",  ammo_val,  (55, 180, 225)),
            ("Food",  food_val,  (230, 80, 65)),
            ("Scrap", scrap_val, (165, 165, 178)),
        ]
        ix = px + pad
        for rname, rval, rcol in res_items:
            # Small colored square
            pygame.draw.rect(self.screen, rcol, (ix, y + 2, 8, 8), border_radius=2)
            rl = self.font_xs.render(rname, True, rcol)
            self.screen.blit(rl, (ix + 11, y))
            rv = self.font_md_b.render(str(rval), True, (255, 255, 255))
            self.screen.blit(rv, (ix + 11, y + rl.get_height()))
            ix += 78

        y += 34

        # Position
        pos_str = f"Pos  ({agent.x}, {agent.y})"
        pos = self.font_xs.render(pos_str, True, (100, 110, 130))
        self.screen.blit(pos, (px + pad, y))
        y += pos.get_height() + 8

        return y

    # ── helper: state detail box ──────────────────────────────────────

    def _render_state_detail(self, px, y, pad, pw, local_agent) -> int:
        """Draw FSM state detail box for the local agent. Returns new y."""
        hdr = self.font_sm_b.render("CURRENT  FSM  STATE", True, (180, 180, 210))
        self.screen.blit(hdr, (px + pad, y))
        y += hdr.get_height() + 6

        state_name = None
        if local_agent and hasattr(local_agent, "fsm") and local_agent.fsm:
            cs = getattr(local_agent.fsm, "current_state", None)
            if cs:
                state_name = cs.name

        if not state_name:
            ns = self.font_sm.render("  Waiting...", True, (80, 80, 100))
            self.screen.blit(ns, (px + pad, y))
            return y + ns.get_height() + 12

        si = self.STATE_INFO.get(state_name, {"color": (200, 200, 200), "icon": "?", "desc": "Unknown"})
        sc = si["color"]

        # Animated glow pulse behind box
        pulse = 0.5 + 0.5 * math.sin(self._anim_tick * 0.05)

        # Colored box
        box_x = px + pad
        box_w = pw - pad * 2
        box_h = 56

        box_surf = pygame.Surface((box_w, box_h), pygame.SRCALPHA)
        bg_alpha = int(22 + 12 * pulse)
        pygame.draw.rect(box_surf, (*sc, bg_alpha), (0, 0, box_w, box_h), border_radius=6)
        pygame.draw.rect(box_surf, (*sc, 160), (0, 0, box_w, box_h), 2, border_radius=6)
        # Left accent bar (thicker)
        pygame.draw.rect(box_surf, (*sc, 240), (0, 3, 5, box_h - 6), border_radius=2)
        self.screen.blit(box_surf, (box_x, y))

        # Icon + State name (larger)
        icon_str = si["icon"]
        state_label = f" {icon_str}  {state_name}"
        sl = self.font_md_b.render(state_label, True, sc)
        self.screen.blit(sl, (box_x + 10, y + 7))

        # Description
        desc = self.font_sm.render(si["desc"], True, (175, 180, 200))
        self.screen.blit(desc, (box_x + 14, y + 8 + sl.get_height() + 2))

        y += box_h + 12
        return y

    # ── helper: terrain legend ────────────────────────────────────────

    def _render_terrain_legend(self, px, y, pad, pw) -> None:
        """Small terrain color legend at the bottom of the panel."""
        remaining = self.win_h - y
        if remaining < 80:
            return  # not enough space

        hdr = self.font_sm_b.render("TERRAIN", True, (140, 145, 160))
        self.screen.blit(hdr, (px + pad, y))
        y += hdr.get_height() + 4

        col1_x = px + pad
        col2_x = px + pad + 120
        items = list(self.TERRAIN_LABELS.items())
        for i, (tval, tname) in enumerate(items):
            tx = col1_x if i % 2 == 0 else col2_x
            ty = y + (i // 2) * 16

            c = self.TERRAIN_BASE[tval]
            pygame.draw.rect(self.screen, c, (tx, ty + 2, 10, 10))
            pygame.draw.rect(self.screen, (80, 80, 80), (tx, ty + 2, 10, 10), 1)
            lbl = self.font_xs.render(tname, True, (130, 135, 150))
            self.screen.blit(lbl, (tx + 14, ty + 1))
