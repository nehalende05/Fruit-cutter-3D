import pygame
import math
import random
import time
import cv2
import numpy as np
from config import (
    SCREEN_WIDTH, SCREEN_HEIGHT, FPS, DIFFICULTIES,
    COLOR_BG_DARK, COLOR_BG_LIGHT, COLOR_NEON_BLUE, COLOR_NEON_GREEN,
    COLOR_NEON_PINK, COLOR_WHITE, COLOR_RED, COLOR_YELLOW, GRAVITY
)
from assets_manager import generate_aruco_marker, play_sound, FRUIT_COLORS
from camera_tracking import CameraTracker
from calibration import load_calibration_settings, CalibrationWizard
from game_objects import Fruit, SlicedFruit, Bomb, Particle, BladeTrail, project_3d
from high_scores import load_high_scores, add_high_score

def dist_point_to_segment(p, a, b):
    """Calculates the minimum distance from point P to line segment AB."""
    px, py = p
    ax, ay = a
    bx, by = b
    dx = bx - ax
    dy = by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    # Project point onto segment
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    # Closest point on segment
    cx = ax + t * dx
    cy = ay + t * dy
    return math.hypot(px - cx, py - cy)

class GameApp:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Fruit Cutter 3D")
        self.clock = pygame.time.Clock()
        
        # Load fonts
        try:
            self.font = pygame.font.Font(pygame.font.get_default_font(), 26)
            self.large_font = pygame.font.Font(pygame.font.get_default_font(), 48)
            self.title_font = pygame.font.Font(pygame.font.get_default_font(), 72)
        except:
            self.font = pygame.font.SysFont("Arial", 26)
            self.large_font = pygame.font.SysFont("Arial", 48)
            self.title_font = pygame.font.SysFont("Arial", 72)
            
        # Ensure ArUco marker is generated in folder
        generate_aruco_marker()
        
        # Initialize Tracker
        self.tracker = CameraTracker()
        self.load_and_apply_calibration()
        
        # Game States
        # States: "menu", "game", "calibration", "high_scores", "game_over"
        self.state = "menu"
        
        # Calibration Wizard Reference
        self.wizard = None
        
        # Settings & Score Parameters
        self.difficulty = "Medium"
        self.score = 0
        self.lives = 3
        
        # Combo logic
        self.swing_hits = 0
        self.combo_timer = 0.0
        self.combo_multiplier = 1
        self.active_combo_messages = []  # list of {"text": str, "pos": (x,y), "life": frames, "color": color}
        
        # Entity lists
        self.fruits = []
        self.sliced_fruits = []
        self.particles = []
        self.blade_trail = BladeTrail()
        
        # Spawning timers
        self.spawn_timer = 0
        self.game_start_time = 0
        
        # Visual Special Effects
        self.time_scale = 1.0  # Used for slow motion
        self.slow_mo_timer = 0  # Frame count for slow-mo
        self.screen_shake_intensity = 0
        self.screen_shake_frames = 0
        
        # High Score Entry Name (for keyboard input)
        self.player_name = ""
        self.high_score_entered = False
        
        # Menu Selection Index
        self.menu_index = 0
        self.menu_options = ["START GAME", "CALIBRATION WIZARD", "LEADERBOARD", "EXIT"]
        
        # Background Grid Animation
        self.grid_offset = 0.0
        
    def load_and_apply_calibration(self):
        """Loads settings from calibration.json and configures the camera tracker."""
        cal = load_calibration_settings()
        self.tracker.webcam_index = cal["webcam_index"]
        self.tracker.tracking_mode = cal["tracking_mode"]
        self.tracker.hsv_min = np.array(cal["hsv_min"], dtype=np.uint8)
        self.tracker.hsv_max = np.array(cal["hsv_max"], dtype=np.uint8)
        
    def run(self):
        # Start camera tracker immediately
        self.tracker.start()
        
        running = True
        while running:
            # Handle Pygame Events
            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT:
                    running = False
                    
                # State specific keyboard handlers
                if self.state == "menu":
                    self.handle_menu_events(event)
                elif self.state == "game_over":
                    self.handle_game_over_events(event)
                elif self.state == "high_scores":
                    if event.type == pygame.KEYDOWN:
                        play_sound("click")
                        self.state = "menu"
                        
            # State specific update/draw loops
            if self.state == "menu":
                self.update_menu()
                self.draw_menu()
            elif self.state == "game":
                self.update_game()
                self.draw_game()
            elif self.state == "calibration":
                # Let Wizard handle events and drawing
                self.wizard.update()
                for event in events:
                    res = self.wizard.handle_event(event)
                    if res == "back":
                        self.state = "menu"
                        self.load_and_apply_calibration()
                        # Restart tracker with game parameters
                        self.tracker.start()
                        self.wizard = None
                        break
                if self.wizard:
                    self.wizard.draw(self.screen, self.font, self.large_font)
            elif self.state == "high_scores":
                self.draw_high_scores()
            elif self.state == "game_over":
                self.update_game_over()
                self.draw_game_over()
                
            pygame.display.flip()
            self.clock.tick(FPS)
            
        self.tracker.stop()
        pygame.quit()

    # ================= MENU STATE =================
    
    def handle_menu_events(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP or event.key == pygame.K_w:
                play_sound("click")
                self.menu_index = (self.menu_index - 1) % len(self.menu_options)
            elif event.key == pygame.K_DOWN or event.key == pygame.K_s:
                play_sound("click")
                self.menu_index = (self.menu_index + 1) % len(self.menu_options)
            elif event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                play_sound("combo")
                self.trigger_menu_action()
            elif event.key == pygame.K_d:  # Toggle Difficulty
                play_sound("click")
                diffs = ["Easy", "Medium", "Hard"]
                curr_idx = diffs.index(self.difficulty)
                self.difficulty = diffs[(curr_idx + 1) % len(diffs)]
                
    def trigger_menu_action(self):
        choice = self.menu_options[self.menu_index]
        if choice == "START GAME":
            self.start_new_game()
        elif choice == "CALIBRATION WIZARD":
            self.tracker.stop()  # Stop standard tracker so wizard can take over indexing
            self.wizard = CalibrationWizard(self.tracker)
            self.state = "calibration"
        elif choice == "LEADERBOARD":
            self.state = "high_scores"
        elif choice == "EXIT":
            pygame.event.post(pygame.event.Event(pygame.QUIT))
            
    def update_menu(self):
        # Drift the retro background grid
        self.grid_offset = (self.grid_offset + 1.0) % 60.0

    def draw_retro_grid(self, surface):
        """Draws a beautiful perspective pseudo-3D grid line system."""
        surface.fill(COLOR_BG_DARK)
        
        # Draw concentric/linear grid lines in perspective
        grid_color = (30, 25, 60)
        vanishing_y = SCREEN_HEIGHT // 3
        
        # Vertical vanishing lines
        num_cols = 16
        for i in range(num_cols + 1):
            x_base = (i / num_cols) * SCREEN_WIDTH
            pygame.draw.line(surface, grid_color, (SCREEN_WIDTH // 2, vanishing_y), (x_base, SCREEN_HEIGHT), 1)
            
        # Horizontal scrolling grid lines
        # Spacing increases exponentially as it moves down towards the camera
        y_lines = []
        curr_y = self.grid_offset
        while curr_y < SCREEN_HEIGHT - vanishing_y:
            # exponential perspective scale
            scaled_y = vanishing_y + curr_y * (curr_y / (SCREEN_HEIGHT - vanishing_y))
            if scaled_y < SCREEN_HEIGHT:
                y_lines.append(int(scaled_y))
            curr_y += 35.0
            
        for y in y_lines:
            # Neon purple horizontal line
            pygame.draw.line(surface, grid_color, (0, y), (SCREEN_WIDTH, y), 1)
            
    def draw_menu(self):
        self.draw_retro_grid(self.screen)
        
        # 1. Main Title
        title_surf = self.title_font.render("FRUIT CUTTER 3D", True, COLOR_NEON_BLUE)
        title_rect = title_surf.get_rect(center=(SCREEN_WIDTH // 2, 160))
        # Title Neon drop shadow glow
        glow_surf = self.title_font.render("FRUIT CUTTER 3D", True, COLOR_NEON_PINK)
        self.screen.blit(glow_surf, (title_rect.x + 3, title_rect.y + 3))
        self.screen.blit(title_surf, title_rect)
        
        # Subtitle
        sub_surf = self.font.render("Swing your phone like a sword!", True, COLOR_WHITE)
        self.screen.blit(sub_surf, (SCREEN_WIDTH // 2 - sub_surf.get_width() // 2, 230))
        
        # 2. Render Difficulty toggle prompt
        diff_text = f"DIFFICULTY: {self.difficulty.upper()}  [ Press 'D' to Toggle ]"
        diff_surf = self.font.render(diff_text, True, COLOR_YELLOW)
        self.screen.blit(diff_surf, (SCREEN_WIDTH // 2 - diff_surf.get_width() // 2, 280))
        
        # 3. Render Menu Options
        menu_y = 360
        for i, option in enumerate(self.menu_options):
            is_selected = (i == self.menu_index)
            color = COLOR_NEON_GREEN if is_selected else COLOR_WHITE
            prefix = ">> " if is_selected else "   "
            
            opt_str = prefix + option
            opt_surf = self.large_font.render(opt_str, True, color)
            opt_rect = opt_surf.get_rect(left=SCREEN_WIDTH // 2 - 180, top=menu_y)
            
            # Subtle glow shadow for selected option
            if is_selected:
                glow_opt = self.large_font.render(opt_str, True, (0, 100, 0))
                self.screen.blit(glow_opt, (opt_rect.x + 2, opt_rect.y + 2))
                
            self.screen.blit(opt_surf, opt_rect)
            menu_y += 65
            
        # Draw camera detection mini-status
        track = self.tracker.get_tracking_data()
        cam_status_str = f"Sword Status: {'ACTIVE' if track['is_detected'] else 'DISCONNECTED'}"
        cam_status_color = COLOR_NEON_GREEN if track['is_detected'] else COLOR_NEON_PINK
        cam_status_surf = self.font.render(cam_status_str, True, cam_status_color)
        self.screen.blit(cam_status_surf, (30, SCREEN_HEIGHT - 45))
        
        # Tips prompt
        tips_surf = self.font.render("[ Arrow Keys to Navigate, Enter to Select ]", True, (140, 140, 160))
        self.screen.blit(tips_surf, (SCREEN_WIDTH - tips_surf.get_width() - 30, SCREEN_HEIGHT - 45))

    # ================= GAMEPLAY STATE =================
    
    def start_new_game(self):
        self.score = 0
        self.lives = 3
        self.fruits.clear()
        self.sliced_fruits.clear()
        self.particles.clear()
        self.active_combo_messages.clear()
        self.blade_trail.clear()
        self.game_start_time = time.time()
        self.spawn_timer = 0
        self.time_scale = 1.0
        self.slow_mo_timer = 0
        self.screen_shake_frames = 0
        self.state = "game"
        
        # Set difficulty settings
        diff_profile = DIFFICULTIES.get(self.difficulty, DIFFICULTIES["Medium"])
        self.tracker.swing_speed_threshold = diff_profile["speed_threshold"]
        
        # Reset and verify camera tracking
        self.load_and_apply_calibration()
        if not self.tracker.running:
            self.tracker.start()

    def update_game(self):
        # 1. Update visual effects (Slow Motion & Screen Shake)
        if self.slow_mo_timer > 0:
            self.slow_mo_timer -= 1
            self.time_scale = 0.30  # Slowed physics
        else:
            self.time_scale = 1.0
            
        if self.screen_shake_frames > 0:
            self.screen_shake_frames -= 1
            
        # 2. Get Camera Tracking Data
        track = self.tracker.get_tracking_data()
        
        if track["is_detected"]:
            # Track positions
            self.blade_trail.add_point(track["pos"], track["angle"], track["depth"])
        else:
            self.blade_trail.clear()
            
        # 3. Handle Slicing Intersections
        if track["is_detected"] and track["is_swinging"]:
            self.check_slices()
        else:
            # Player stopped swinging, reset combo tracking
            if self.swing_hits > 0:
                self.finalize_swing_combo()
                
        # 4. Update Entities (apply slow motion scale to physics)
        dt_physics = self.time_scale
        
        # Update fruits
        for fruit in self.fruits[:]:
            # Scale coordinates/velocity update by time scale
            fruit.vx_scaled = fruit.vx * dt_physics
            fruit.vy_scaled = fruit.vy * dt_physics
            fruit.vz_scaled = fruit.vz * dt_physics
            
            # Apply update logic modified by dt
            fruit.x += fruit.vx_scaled
            fruit.y += fruit.vy_scaled
            fruit.z += fruit.vz_scaled
            fruit.vy += GRAVITY * dt_physics
            fruit.angle = (fruit.angle + fruit.rot_speed * dt_physics) % 360
            
            # Check OOB
            if fruit.is_out_of_bounds():
                if isinstance(fruit, Fruit) and not fruit.sliced:
                    # Player missed a fruit! Lose life!
                    self.lives -= 1
                    play_sound("lose_life")
                    if self.lives <= 0:
                        self.trigger_game_over()
                self.fruits.remove(fruit)
                
        # Update sliced fruits
        for sf in self.sliced_fruits[:]:
            sf.x += sf.vx * dt_physics
            sf.y += sf.vy * dt_physics
            sf.z += sf.vz * dt_physics
            sf.vy += GRAVITY * dt_physics
            
            sf.ax += sf.avx * dt_physics
            sf.ay += sf.avy * dt_physics
            sf.bx += sf.bvx * dt_physics
            sf.by += sf.bvy * dt_physics
            sf.avy += 0.2 * dt_physics
            sf.bvy += 0.2 * dt_physics
            
            sf.a_angle = (sf.a_angle + sf.a_rot_speed * dt_physics) % 360
            sf.b_angle = (sf.b_angle + sf.b_rot_speed * dt_physics) % 360
            sf.lifetime += dt_physics
            
            if sf.is_out_of_bounds():
                self.sliced_fruits.remove(sf)
                
        # Update particles
        for p in self.particles[:]:
            p.life -= dt_physics
            if p.is_dead():
                self.particles.remove(p)
                continue
                
            if p.is_lens_splat:
                p.screen_y += p.drip_speed * dt_physics
            else:
                p.x += p.vx * dt_physics
                p.y += p.vy * dt_physics
                p.z += p.vz * dt_physics
                p.vy += 0.2 * dt_physics
                
        # Update combo text notifications
        for msg in self.active_combo_messages[:]:
            msg["life"] -= 1
            # Floating upwards
            msg["pos"] = (msg["pos"][0], msg["pos"][1] - 1)
            if msg["life"] <= 0:
                self.active_combo_messages.remove(msg)
                
        # 5. Spawning Spatials (Fruits/Bombs)
        self.update_spawner()
        
    def update_spawner(self):
        diff_profile = DIFFICULTIES.get(self.difficulty, DIFFICULTIES["Medium"])
        speed_scale = diff_profile["speed_scale"]
        
        # Difficulty ramp: spawn interval decreases slowly as game time increases
        elapsed = time.time() - self.game_start_time
        difficulty_ramp = max(0.5, 1.0 - (elapsed / 120.0))  # Max difficulty ramp at 2 minutes
        current_spawn_interval = max(diff_profile["spawn_interval"] * difficulty_ramp, 0.5)
        
        self.spawn_timer += 1 / FPS
        if self.spawn_timer >= current_spawn_interval:
            self.spawn_timer = 0
            
            # Spawn random entity: Fruit or Bomb
            bomb_chance = diff_profile["bomb_chance"]
            if random.random() < bomb_chance:
                # Spawn a Bomb
                self.fruits.append(Bomb())
            else:
                # Spawn a Fruit
                fruit_types = ["Apple", "Orange", "Banana", "Watermelon", "Mango", "Kiwi", "Pineapple", "Lemon", "Strawberry"]
                selected = random.choice(fruit_types)
                f = Fruit(selected)
                # Adjust velocities by speed scale
                f.vx *= speed_scale
                f.vy *= speed_scale
                f.vz *= speed_scale
                self.fruits.append(f)
                
    def check_slices(self):
        # Retrieve current and previous blade segments to check the entire swept area
        curr_seg = self.blade_trail.get_blade_segment_at(-1)
        prev_seg = self.blade_trail.get_blade_segment_at(-2)
        
        if curr_seg is None:
            return
            
        curr_base, curr_tip = curr_seg
        
        # We check collision in projected 2D screen coordinates
        for entity in self.fruits[:]:
            if entity.sliced:
                continue
                
            # Get projected 2D center and radius
            px, py, scale = project_3d(entity.x, entity.y, entity.z)
            radius = int(entity.size_3d * scale)
            
            if radius <= 0:
                continue
                
            # Check collision against current blade segment
            hit = False
            dist = dist_point_to_segment((px, py), curr_base, curr_tip)
            if dist <= radius:
                hit = True
                
            # Check collision against swept segments if previous frame exists
            if not hit and prev_seg is not None:
                prev_base, prev_tip = prev_seg
                # 1. Previous blade segment
                if dist_point_to_segment((px, py), prev_base, prev_tip) <= radius:
                    hit = True
                # 2. Tip sweep line
                elif dist_point_to_segment((px, py), prev_tip, curr_tip) <= radius:
                    hit = True
                # 3. Base sweep line
                elif dist_point_to_segment((px, py), prev_base, curr_base) <= radius:
                    hit = True
                # 4. Diagonals (helps cover center of fast rotations)
                elif dist_point_to_segment((px, py), prev_base, curr_tip) <= radius:
                    hit = True
                elif dist_point_to_segment((px, py), prev_tip, curr_base) <= radius:
                    hit = True
                    
            if hit:
                # Hit detected!
                entity.sliced = True
                
                if isinstance(entity, Bomb):
                    self.trigger_bomb_explosion(entity)
                    break
                else:
                    self.slice_fruit(entity, curr_seg)

    def slice_fruit(self, fruit, blade_seg):
        # 1. Play sound
        play_sound("slice")
        
        # 2. Add score & increment swing hits
        self.score += 10 * self.combo_multiplier
        self.swing_hits += 1
        
        # Reset combo decay timer
        self.combo_timer = time.time()
        
        # Remove from active lists
        if fruit in self.fruits:
            self.fruits.remove(fruit)
            
        # 3. Create SlicedFruit halves
        # Angle of slice is the angle of the blade vector
        p_base, p_tip = blade_seg
        dx = p_tip[0] - p_base[0]
        dy = p_tip[1] - p_base[1]
        slice_angle = math.atan2(dy, dx)
        
        sf = SlicedFruit(fruit, slice_angle)
        self.sliced_fruits.append(sf)
        
        # 4. Spawn splatters and sprays particles
        # Spray 3D particles outwards
        num_particles = random.randint(12, 18)
        for _ in range(num_particles):
            p_ang = random.uniform(0, 2 * math.pi)
            p_spd = random.uniform(2.0, 7.0)
            
            pvx = fruit.vx + p_spd * math.cos(p_ang)
            pvy = fruit.vy + p_spd * math.sin(p_ang) - 3.0
            pvz = fruit.vz + random.uniform(-1.0, 1.0)
            
            self.particles.append(
                Particle(fruit.x, fruit.y, fruit.z, pvx, pvy, pvz, fruit.color)
            )
            
        # 10% chance to splash onto screen lens
        if random.random() < 0.15:
            # Spawn screen splat
            self.particles.append(
                Particle(0, 0, 0, 0, 0, 0, fruit.color, is_lens_splat=True)
            )

    def finalize_swing_combo(self):
        """Analyzes hits after a swing is finished and awards combo bonuses."""
        if self.swing_hits >= 2:
            # Calculate bonus
            bonus = self.swing_hits * 15
            self.score += bonus
            
            # Increase combo multiplier
            self.combo_multiplier = min(5, self.combo_multiplier + 1)
            
            # Create floating combo message
            track = self.tracker.get_tracking_data()
            c_pos = track["pos"]
            
            # Choose color based on combo size
            c_color = COLOR_NEON_GREEN if self.swing_hits == 2 else (COLOR_NEON_PINK if self.swing_hits == 3 else COLOR_YELLOW)
            
            msg = {
                "text": f"{self.swing_hits}x COMBO! +{bonus}",
                "pos": (c_pos[0], c_pos[1] - 40),
                "life": 45,  # frames duration
                "color": c_color
            }
            self.active_combo_messages.append(msg)
            play_sound("combo")
            
            # Trigger SLOW MOTION if combo is 3 or more!
            if self.swing_hits >= 3:
                self.slow_mo_timer = 40  # 40 frames of slow-mo (~0.7 seconds of game time)
        else:
            # Decay combo multiplier if we only hit 0 or 1 fruit in a swing
            self.combo_multiplier = max(1, self.combo_multiplier - 1)
            
        self.swing_hits = 0

    def trigger_bomb_explosion(self, bomb):
        play_sound("explosion")
        
        # Remove bomb
        if bomb in self.fruits:
            self.fruits.remove(bomb)
            
        # Shake screen violently
        self.screen_shake_intensity = 30
        self.screen_shake_frames = 30  # shake for 0.5s
        
        # Spawn massive orange/black sparks
        px, py, scale = project_3d(bomb.x, bomb.y, bomb.z)
        for _ in range(40):
            p_ang = random.uniform(0, 2 * math.pi)
            p_spd = random.uniform(5.0, 15.0)
            pvx = bomb.vx + p_spd * math.cos(p_ang)
            pvy = bomb.vy + p_spd * math.sin(p_ang) - 5.0
            pvz = bomb.vz + random.uniform(-4.0, 4.0)
            color = random.choice([(255, 100, 0), (255, 200, 0), (40, 40, 40)])
            self.particles.append(
                Particle(bomb.x, bomb.y, bomb.z, pvx, pvy, pvz, color)
            )
            
        # Trigger immediate game over after brief frames of explosion
        self.lives = 0
        
    def trigger_game_over(self):
        self.state = "game_over"
        self.player_name = ""
        self.high_score_entered = False
        play_sound("lose_life")
        
    def draw_game(self):
        # Create game surface to support screenshake offset blitting
        game_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        
        # A. Draw Background Grid
        self.draw_retro_grid(game_surf)
        
        # B. Draw Sliced Fruits
        for sf in self.sliced_fruits:
            sf.draw(game_surf)
            
        # C. Draw Fruits & Bombs
        for fruit in self.fruits:
            fruit.draw(game_surf)
            
        # D. Draw 3D Spray Particles
        for p in self.particles:
            if not p.is_lens_splat:
                p.draw(game_surf)
                
        # E. Draw Laser Blade and Swoosh Trail
        self.blade_trail.draw(game_surf)
        
        # F. Draw Screen Lens Splats (flat overlay)
        for p in self.particles:
            if p.is_lens_splat:
                p.draw(game_surf)
                
        # G. Render HUD overlay on game surface
        self.draw_hud(game_surf)
        
        # Blit game_surf to screen with screenshake offset
        shake_x, shake_y = 0, 0
        if self.screen_shake_frames > 0:
            shake_x = random.randint(-self.screen_shake_intensity, self.screen_shake_intensity)
            shake_y = random.randint(-self.screen_shake_intensity, self.screen_shake_intensity)
            # decay intensity
            self.screen_shake_intensity = max(1, self.screen_shake_intensity - 1)
            
        self.screen.blit(game_surf, (shake_x, shake_y))
        
    def draw_hud(self, surface):
        # 1. Draw Score (Top Left)
        score_surf = self.large_font.render(f"SCORE: {self.score}", True, COLOR_NEON_GREEN)
        score_rect = score_surf.get_rect(topleft=(30, 25))
        # shadow glow
        glow = self.large_font.render(f"SCORE: {self.score}", True, (0, 80, 0))
        surface.blit(glow, (score_rect.x + 2, score_rect.y + 2))
        surface.blit(score_surf, score_rect)
        
        # Display Combo Multiplier indicator
        if self.combo_multiplier > 1:
            mult_surf = self.font.render(f"{self.combo_multiplier}x Multiplier Active", True, COLOR_YELLOW)
            surface.blit(mult_surf, (30, 75))
            
        # 2. Draw Lives (Top Right - Digital LED Hearts)
        heart_x = SCREEN_WIDTH - 180
        heart_y = 25
        for i in range(3):
            # Filled heart if life remains, empty heart if lost
            color = COLOR_RED if i < self.lives else (50, 20, 30)
            rect = pygame.Rect(heart_x + i * 50, heart_y, 35, 30)
            
            # Draw cute procedural pixel heart
            if i < self.lives:
                pygame.draw.circle(surface, color, (rect.x + 10, rect.y + 10), 10)
                pygame.draw.circle(surface, color, (rect.x + 25, rect.y + 10), 10)
                pygame.draw.polygon(surface, color, [(rect.x, rect.y + 12), (rect.x + 35, rect.y + 12), (rect.x + 18, rect.y + 30)])
            else:
                # Broken/Dead heart outline
                pygame.draw.rect(surface, color, rect, 2, border_radius=4)
                pygame.draw.line(surface, color, (rect.left, rect.top), (rect.right, rect.bottom), 2)
                
        # 3. Draw floating combo text overlays
        for msg in self.active_combo_messages:
            txt_surf = self.font.render(msg["text"], True, msg["color"])
            surface.blit(txt_surf, (msg["pos"][0] - txt_surf.get_width()//2, msg["pos"][1]))
            
        # 4. Draw Webcam Picture-In-Picture Preview (Bottom Left Corner)
        # Background bezel for webcam preview
        pip_rect = pygame.Rect(30, SCREEN_HEIGHT - 160, 172, 132)
        pygame.draw.rect(surface, (30, 25, 50), pip_rect, border_radius=6)
        pygame.draw.rect(surface, COLOR_NEON_BLUE, pip_rect, 2, border_radius=6)
        
        preview_surf = self.tracker.get_preview_surface()
        if preview_surf is not None:
            surface.blit(preview_surf, (36, SCREEN_HEIGHT - 154))
        else:
            # Loading camera text
            lbl = pygame.font.SysFont("Arial", 12).render("NO CAMERA", True, COLOR_NEON_PINK)
            surface.blit(lbl, (pip_rect.centerx - lbl.get_width()//2, pip_rect.centery - lbl.get_height()//2))
            
        # Draw camera label overlay
        cam_lbl = pygame.font.SysFont("Arial", 12).render(f"CAM FEED ({self.tracker.tracking_mode.upper()})", True, COLOR_NEON_BLUE)
        surface.blit(cam_lbl, (pip_rect.x, pip_rect.y - 18))
        
        # 5. Slow Mo overlay visual tint
        if self.slow_mo_timer > 0:
            slow_tint = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            # Deep purple/blue transparent vignette
            pygame.draw.rect(slow_tint, (80, 0, 100, 30), (0,0,SCREEN_WIDTH,SCREEN_HEIGHT))
            surface.blit(slow_tint, (0,0))
            
            # Slow mo label
            slo_lbl = self.font.render("SLOW-MO COMBO ACTIVE", True, COLOR_NEON_PINK)
            surface.blit(slo_lbl, (SCREEN_WIDTH//2 - slo_lbl.get_width()//2, 80))

    # ================= LEADERBOARD STATE =================
    
    def draw_high_scores(self):
        self.draw_retro_grid(self.screen)
        
        # Header
        title = self.large_font.render("LEADERBOARD", True, COLOR_NEON_BLUE)
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 80))
        
        # Load scores
        scores = load_high_scores()
        
        # Table UI Coordinates
        start_y = 180
        spacing = 55
        
        # Render Table headers
        rank_h = self.font.render("RANK", True, COLOR_NEON_PINK)
        name_h = self.font.render("PLAYER NAME", True, COLOR_NEON_PINK)
        score_h = self.font.render("HIGH SCORE", True, COLOR_NEON_PINK)
        
        self.screen.blit(rank_h, (SCREEN_WIDTH//2 - 250, start_y))
        self.screen.blit(name_h, (SCREEN_WIDTH//2 - 100, start_y))
        self.screen.blit(score_h, (SCREEN_WIDTH//2 + 150, start_y))
        
        pygame.draw.line(self.screen, (50, 45, 90), (SCREEN_WIDTH//2 - 270, start_y + 35), (SCREEN_WIDTH//2 + 270, start_y + 35), 2)
        
        row_y = start_y + 55
        for i, entry in enumerate(scores):
            # Styling for rank 1
            color = COLOR_YELLOW if i == 0 else (COLOR_NEON_GREEN if i == 1 else COLOR_WHITE)
            
            rank_txt = self.font.render(f"#{i+1}", True, color)
            name_txt = self.font.render(entry["name"], True, color)
            score_txt = self.font.render(str(entry["score"]), True, color)
            
            self.screen.blit(rank_txt, (SCREEN_WIDTH//2 - 240, row_y))
            self.screen.blit(name_txt, (SCREEN_WIDTH//2 - 100, row_y))
            self.screen.blit(score_txt, (SCREEN_WIDTH//2 + 150, row_y))
            
            row_y += spacing
            
        # Prompt to return
        prompt = self.font.render("[ Press ANY KEY to return to Main Menu ]", True, COLOR_NEON_BLUE)
        self.screen.blit(prompt, (SCREEN_WIDTH // 2 - prompt.get_width() // 2, 580))

    # ================= GAME OVER STATE =================
    
    def handle_game_over_events(self, event):
        if event.type == pygame.KEYDOWN:
            if not self.high_score_entered:
                # Text Input processing
                if event.key == pygame.K_RETURN:
                    # Save Score!
                    name_to_save = self.player_name.strip() if self.player_name.strip() else "Blade Master"
                    add_high_score(name_to_save, self.score)
                    self.high_score_entered = True
                    play_sound("combo")
                elif event.key == pygame.K_BACKSPACE:
                    self.player_name = self.player_name[:-1]
                else:
                    # Limit name to 12 alphanumeric characters
                    if len(self.player_name) < 12 and event.unicode.isalnum() or event.unicode == ' ':
                        self.player_name += event.unicode
            else:
                # High score has been entered, any key returns to main menu
                play_sound("click")
                self.state = "menu"
                
    def update_game_over(self):
        # Update elements in background
        dt_physics = 1.0
        for sf in self.sliced_fruits[:]:
            sf.update()
            if sf.is_out_of_bounds():
                self.sliced_fruits.remove(sf)
        for p in self.particles[:]:
            p.update()
            if p.is_dead():
                self.particles.remove(p)

    def draw_game_over(self):
        # Background Grid (static)
        self.draw_retro_grid(self.screen)
        
        # Render trailing particles / sliced halves in background
        for sf in self.sliced_fruits:
            sf.draw(self.screen)
        for p in self.particles:
            if not p.is_lens_splat:
                p.draw(self.screen)
                
        # Main Header
        go_surf = self.title_font.render("GAME OVER", True, COLOR_RED)
        go_rect = go_surf.get_rect(center=(SCREEN_WIDTH // 2, 140))
        # Glow shadow
        glow = self.title_font.render("GAME OVER", True, (80, 0, 0))
        self.screen.blit(glow, (go_rect.x + 3, go_rect.y + 3))
        self.screen.blit(go_surf, go_rect)
        
        # Score readout
        score_surf = self.large_font.render(f"FINAL SCORE: {self.score}", True, COLOR_NEON_GREEN)
        self.screen.blit(score_surf, (SCREEN_WIDTH // 2 - score_surf.get_width() // 2, 220))
        
        # Leaderboard checking
        scores = load_high_scores()
        is_highscore = len(scores) < 5 or self.score > scores[-1]["score"]
        
        if is_highscore and not self.high_score_entered:
            # Ask player to enter name
            name_prompt = self.font.render("NEW HIGH SCORE! Enter your name:", True, COLOR_YELLOW)
            self.screen.blit(name_prompt, (SCREEN_WIDTH // 2 - name_prompt.get_width() // 2, 300))
            
            # Draw input field bezel
            input_rect = pygame.Rect(SCREEN_WIDTH // 2 - 200, 350, 400, 50)
            pygame.draw.rect(self.screen, (30, 25, 55), input_rect, border_radius=6)
            pygame.draw.rect(self.screen, COLOR_NEON_BLUE, input_rect, 2, border_radius=6)
            
            # Cursor blink
            cursor = "|" if int(time.time() * 2) % 2 == 0 else ""
            name_surf = self.large_font.render(self.player_name + cursor, True, COLOR_WHITE)
            self.screen.blit(name_surf, (input_rect.x + 15, input_rect.y + (input_rect.height//2 - name_surf.get_height()//2)))
            
            hint = self.font.render("[ Press ENTER to Save Name ]", True, COLOR_NEON_BLUE)
            self.screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, 420))
        else:
            # Standard game over prompts
            if self.high_score_entered:
                saved_surf = self.font.render(f"High score saved as '{self.player_name}'!", True, COLOR_NEON_GREEN)
                self.screen.blit(saved_surf, (SCREEN_WIDTH // 2 - saved_surf.get_width() // 2, 320))
                
            retry_surf = self.large_font.render("[ Press ANY KEY to return to Menu ]", True, COLOR_NEON_BLUE)
            self.screen.blit(retry_surf, (SCREEN_WIDTH // 2 - retry_surf.get_width() // 2, 460))

if __name__ == "__main__":
    app = GameApp()
    app.run()
