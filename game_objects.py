import pygame
import math
import random
from config import (
    SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_CENTER, FOCAL_LENGTH, GRAVITY,
    COLOR_NEON_BLUE, COLOR_NEON_PINK, COLOR_WHITE, COLOR_RED
)
from assets_manager import draw_fruit_procedural, split_sprite_in_half, FRUIT_COLORS

# Cache for pre-drawn fruit sprites to avoid redraw overhead
SPRITE_CACHE = {}

def get_base_sprite(fruit_type, size=120):
    """Retrieves a cached fruit sprite or draws a new one."""
    key = (fruit_type, size)
    if key not in SPRITE_CACHE:
        SPRITE_CACHE[key] = draw_fruit_procedural(fruit_type, size)
    return SPRITE_CACHE[key]

def project_3d(x, y, z):
    """
    Projects 3D coordinates (X, Y, Z) to 2D screen coordinates.
    Z = 0 is the interactive blade plane. Positive Z goes deeper into the screen.
    """
    # Prevent divide by zero or negative depth issues
    depth = max(1.0, z + FOCAL_LENGTH)
    scale = FOCAL_LENGTH / depth
    
    proj_x = int(SCREEN_CENTER[0] + x * scale)
    proj_y = int(SCREEN_CENTER[1] + y * scale)
    
    return proj_x, proj_y, scale

class Fruit:
    def __init__(self, fruit_type):
        self.fruit_type = fruit_type
        self.size_3d = 40.0  # Physical 3D radius
        
        # Spawn coordinates in 3D space
        # X: Random horizontal position
        # Y: Off-screen at the bottom (positive Y is down in Pygame, so spawn at e.g., 300)
        # Z: Depth layer (100 to 300)
        self.z = random.uniform(150, 300)
        
        # Calculate horizontal bounds at spawn depth
        scale_at_spawn = FOCAL_LENGTH / (self.z + FOCAL_LENGTH)
        max_x = (SCREEN_WIDTH // 2) / scale_at_spawn - 50
        
        self.x = random.uniform(-max_x * 0.8, max_x * 0.8)
        self.y = (SCREEN_HEIGHT // 2) / scale_at_spawn + 50  # Just below screen
        
        # Initial velocities (Increased upward velocity for higher arcing trajectories)
        # vx: Aim towards screen center
        # vy: Upward thrust
        # vz: Fly forward towards the camera (Z decreases towards 0)
        self.vx = -self.x * random.uniform(0.015, 0.025)
        self.vy = -random.uniform(15.5, 19.5)
        self.vz = -random.uniform(2.5, 4.0)  # Move towards screen
        
        # Rotation
        self.angle = random.uniform(0, 360)
        self.rot_speed = random.uniform(-4, 4)
        
        # Sprite cache references
        self.base_size = 120
        self.base_surf = get_base_sprite(self.fruit_type, self.base_size)
        self.color = FRUIT_COLORS.get(self.fruit_type, COLOR_RED)
        
        self.sliced = False
        
    def update(self):
        # Apply velocity
        self.x += self.vx
        self.y += self.vy
        self.z += self.vz
        
        # Apply gravity to Y velocity
        self.vy += GRAVITY
        
        # Rotate
        self.angle = (self.angle + self.rot_speed) % 360
        
    def is_out_of_bounds(self):
        """Returns True if the fruit has fallen below the screen or zoomed past the camera."""
        proj_x, proj_y, scale = project_3d(self.x, self.y, self.z)
        # Check if depth is past camera plane (Z <= -FOCAL_LENGTH + 10) or falls off bottom
        if self.z < -250:
            return True
        if proj_y > SCREEN_HEIGHT + 150 and self.vy > 0:
            return True
        return False
        
    def get_screen_rect(self):
        """Returns the 2D bounding rect on screen for collision mapping."""
        px, py, scale = project_3d(self.x, self.y, self.z)
        r = int(self.size_3d * scale)
        return pygame.Rect(px - r, py - r, r * 2, r * 2)

    def draw(self, screen):
        px, py, scale = project_3d(self.x, self.y, self.z)
        r = int(self.size_3d * scale)
        
        if r <= 0:
            return
            
        # 1. Draw 3D floor shadow
        # Project shadow onto floor plane (e.g., Y = 680)
        floor_y = SCREEN_HEIGHT - 40
        # Shadow size scales inversely with distance from floor
        dist_to_floor = floor_y - py
        shadow_scale = max(0.1, 1.0 - (dist_to_floor / 600.0))
        shadow_w = int(r * 2 * shadow_scale)
        shadow_h = int(r * 0.5 * shadow_scale)
        
        if shadow_w > 0 and shadow_h > 0:
            shadow_surf = pygame.Surface((shadow_w, shadow_h), pygame.SRCALPHA)
            # Fade shadow based on height
            shadow_alpha = int(120 * shadow_scale)
            pygame.draw.ellipse(shadow_surf, (0, 0, 0, shadow_alpha), (0, 0, shadow_w, shadow_h))
            screen.blit(shadow_surf, (px - shadow_w // 2, floor_y - shadow_h // 2))
            
        # 2. Draw Fruit Sprite
        # Resize based on 3D perspective depth scale
        draw_size = int(self.base_size * scale)
        if draw_size > 5:
            scaled_surf = pygame.transform.smoothscale(self.base_surf, (draw_size, draw_size))
            rotated_surf = pygame.transform.rotate(scaled_surf, self.angle)
            
            # Center Blit
            screen.blit(
                rotated_surf, 
                (px - rotated_surf.get_width() // 2, py - rotated_surf.get_height() // 2)
            )

class SlicedFruit:
    def __init__(self, parent_fruit, cut_angle_rad):
        self.fruit_type = parent_fruit.fruit_type
        self.color = parent_fruit.color
        
        # Maintain parent's 3D coordinates and velocities
        self.x = parent_fruit.x
        self.y = parent_fruit.y
        self.z = parent_fruit.z
        self.vx = parent_fruit.vx
        self.vy = parent_fruit.vy
        self.vz = parent_fruit.vz
        
        # Calculate split surfaces
        # We split the base sprite and scale them later
        half_a_raw, half_b_raw = split_sprite_in_half(
            parent_fruit.base_surf, 
            cut_angle_rad
        )
        
        self.half_a = half_a_raw
        self.half_b = half_b_raw
        self.base_size = parent_fruit.base_size
        self.size_3d = parent_fruit.size_3d
        
        # Push vector (perpendicular to cut angle)
        # Push the two halves away from each other
        push_speed = 3.0
        push_vx = push_speed * math.sin(cut_angle_rad)
        push_vy = -push_speed * math.cos(cut_angle_rad)
        
        # Half A states
        self.ax, self.ay = 0.0, 0.0  # Offsets from center
        self.avx, self.avy = push_vx, push_vy
        self.a_angle = parent_fruit.angle
        self.a_rot_speed = parent_fruit.rot_speed - random.uniform(5, 10)
        
        # Half B states
        self.bx, self.by = 0.0, 0.0  # Offsets from center
        self.bvx, self.bvy = -push_vx, -push_vy
        self.b_angle = parent_fruit.angle
        self.b_rot_speed = parent_fruit.rot_speed + random.uniform(5, 10)
        
        self.lifetime = 0
        
    def update(self):
        # Update parent movement (arc)
        self.x += self.vx
        self.y += self.vy
        self.z += self.vz
        self.vy += GRAVITY
        
        # Update relative splits (flying apart)
        self.ax += self.avx
        self.ay += self.avy
        self.bx += self.bvx
        self.by += self.bvy
        
        # Apply gravity to split halves as well (they drift downwards relatively)
        self.avy += 0.2
        self.bvy += 0.2
        
        # Rotate
        self.a_angle = (self.a_angle + self.a_rot_speed) % 360
        self.b_angle = (self.b_angle + self.b_rot_speed) % 360
        
        self.lifetime += 1
        
    def is_out_of_bounds(self):
        proj_x, proj_y, scale = project_3d(self.x, self.y, self.z)
        return proj_y > SCREEN_HEIGHT + 100 or self.z < -250 or self.lifetime > 120
        
    def draw(self, screen):
        px, py, scale = project_3d(self.x, self.y, self.z)
        r = int(self.size_3d * scale)
        
        if r <= 0:
            return
            
        draw_size = int(self.base_size * scale)
        if draw_size <= 5:
            return
            
        # Draw half A
        scaled_a = pygame.transform.smoothscale(self.half_a, (draw_size, draw_size))
        rotated_a = pygame.transform.rotate(scaled_a, self.a_angle)
        # Shift half A by relative offset scaled by depth
        apx = px + int(self.ax * scale)
        apy = py + int(self.ay * scale)
        screen.blit(
            rotated_a, 
            (apx - rotated_a.get_width() // 2, apy - rotated_a.get_height() // 2)
        )
        
        # Draw half B
        scaled_b = pygame.transform.smoothscale(self.half_b, (draw_size, draw_size))
        rotated_b = pygame.transform.rotate(scaled_b, self.b_angle)
        # Shift half B by relative offset scaled by depth
        bpx = px + int(self.bx * scale)
        bpy = py + int(self.by * scale)
        screen.blit(
            rotated_b, 
            (bpx - rotated_b.get_width() // 2, bpy - rotated_b.get_height() // 2)
        )

class Bomb:
    def __init__(self):
        self.size_3d = 38.0
        self.z = random.uniform(150, 300)
        
        scale_at_spawn = FOCAL_LENGTH / (self.z + FOCAL_LENGTH)
        max_x = (SCREEN_WIDTH // 2) / scale_at_spawn - 50
        
        self.x = random.uniform(-max_x * 0.8, max_x * 0.8)
        self.y = (SCREEN_HEIGHT // 2) / scale_at_spawn + 50
        
        self.vx = -self.x * random.uniform(0.015, 0.025)
        self.vy = -random.uniform(14.5, 18.5)
        self.vz = -random.uniform(2.5, 4.0)
        
        self.angle = 0
        self.rot_speed = random.uniform(-2, 2)
        
        self.base_size = 120
        self.base_surf = get_base_sprite("Bomb", self.base_size)
        self.color = (30, 30, 30)
        
        self.sliced = False
        self.fuse_tick = 0
        
    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.z += self.vz
        self.vy += GRAVITY
        self.angle = (self.angle + self.rot_speed) % 360
        self.fuse_tick += 1
        
    def is_out_of_bounds(self):
        proj_x, proj_y, scale = project_3d(self.x, self.y, self.z)
        if self.z < -250:
            return True
        if proj_y > SCREEN_HEIGHT + 150 and self.vy > 0:
            return True
        return False
        
    def get_screen_rect(self):
        px, py, scale = project_3d(self.x, self.y, self.z)
        r = int(self.size_3d * scale)
        return pygame.Rect(px - r, py - r, r * 2, r * 2)
        
    def draw(self, screen):
        px, py, scale = project_3d(self.x, self.y, self.z)
        r = int(self.size_3d * scale)
        
        if r <= 0:
            return
            
        # Draw shadow
        floor_y = SCREEN_HEIGHT - 40
        dist_to_floor = floor_y - py
        shadow_scale = max(0.1, 1.0 - (dist_to_floor / 600.0))
        shadow_w = int(r * 2 * shadow_scale)
        shadow_h = int(r * 0.5 * shadow_scale)
        if shadow_w > 0 and shadow_h > 0:
            shadow_surf = pygame.Surface((shadow_w, shadow_h), pygame.SRCALPHA)
            pygame.draw.ellipse(shadow_surf, (0, 0, 0, int(150 * shadow_scale)), (0, 0, shadow_w, shadow_h))
            screen.blit(shadow_surf, (px - shadow_w // 2, floor_y - shadow_h // 2))
            
        # Draw bomb body
        draw_size = int(self.base_size * scale)
        if draw_size > 5:
            scaled_surf = pygame.transform.smoothscale(self.base_surf, (draw_size, draw_size))
            rotated_surf = pygame.transform.rotate(scaled_surf, self.angle)
            screen.blit(
                rotated_surf, 
                (px - rotated_surf.get_width() // 2, py - rotated_surf.get_height() // 2)
            )
            
            # Animate spark particles around the fuse position
            # Fuse tip in the local sprite is roughly at top-right
            # Draw tiny yellow/red spark circles at screen coords
            if self.fuse_tick % 2 == 0:
                for _ in range(3):
                    spark_r = random.randint(2, 5)
                    # Add offset relative to bomb center (scaled by depth)
                    # Fuse tip is roughly at dx = 22, dy = -60 in 120px scale
                    dx = int(22 * scale)
                    dy = int(-60 * scale)
                    # Add noise
                    noise_x = random.randint(-8, 8)
                    noise_y = random.randint(-8, 8)
                    spark_color = random.choice([(255, 255, 100), (255, 100, 0), (255, 0, 0)])
                    pygame.draw.circle(
                        screen, 
                        spark_color, 
                        (px + dx + noise_x, py + dy + noise_y), 
                        spark_r
                    )

class Particle:
    def __init__(self, x, y, z, vx, vy, vz, color, is_lens_splat=False):
        # 3D spatial properties
        self.x = x
        self.y = y
        self.z = z
        self.vx = vx
        self.vy = vy
        self.vz = vz
        self.color = color
        
        # Splat vs Spray
        self.is_lens_splat = is_lens_splat
        
        # 2D Screen Splat properties
        if self.is_lens_splat:
            # Splotch coordinate fixed on screen
            self.screen_x = random.randint(0, SCREEN_WIDTH)
            self.screen_y = random.randint(0, SCREEN_HEIGHT)
            self.splat_size = random.uniform(12.0, 30.0)
            self.drip_speed = random.uniform(0.1, 0.4)
            self.max_life = random.randint(90, 150)
        else:
            # 3D Spray
            self.size = random.uniform(4.0, 8.0)
            self.max_life = random.randint(30, 60)
            
        self.life = self.max_life
        
    def update(self):
        self.life -= 1
        
        if self.is_lens_splat:
            # Slighly drip downwards
            self.screen_y += self.drip_speed
        else:
            # 3D physics spray
            self.x += self.vx
            self.y += self.vy
            self.z += self.vz
            self.vy += 0.2  # Gravity on particle
            
    def is_dead(self):
        return self.life <= 0
        
    def draw(self, screen):
        alpha = int((self.life / self.max_life) * 255)
        
        if self.is_lens_splat:
            # Draw semi-transparent splat directly on 2D screen
            splat_surf = pygame.Surface((int(self.splat_size * 2), int(self.splat_size * 2)), pygame.SRCALPHA)
            color_with_alpha = self.color + (int(alpha * 0.75),)
            
            # Draw organic shape (overlapping circles)
            cx = int(self.splat_size)
            pygame.draw.circle(splat_surf, color_with_alpha, (cx, cx), int(self.splat_size))
            for _ in range(4):
                ox = random.randint(-int(cx//2), int(cx//2))
                oy = random.randint(-int(cx//2), int(cx//2))
                sr = random.randint(int(cx//4), int(cx//1.5))
                pygame.draw.circle(splat_surf, color_with_alpha, (cx + ox, cx + oy), sr)
                
            screen.blit(splat_surf, (int(self.screen_x - self.splat_size), int(self.screen_y - self.splat_size)))
        else:
            # Project 3D spray
            px, py, scale = project_3d(self.x, self.y, self.z)
            r = int(self.size * scale)
            
            if r > 0 and 0 <= px < SCREEN_WIDTH and 0 <= py < SCREEN_HEIGHT:
                particle_surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
                pygame.draw.circle(particle_surf, self.color + (alpha,), (r, r), r)
                screen.blit(particle_surf, (px - r, py - r))

class BladeTrail:
    def __init__(self, max_length=15):
        self.points = []  # List of dicts: {"pos": (x,y), "angle": tilt_rad, "depth": Z, "time": t}
        self.max_length = max_length
        self.blade_length = 160.0  # Size of the laser blade
        
    def add_point(self, pos, angle, depth):
        self.points.append({
            "pos": pos,
            "angle": angle,
            "depth": depth
        })
        if len(self.points) > self.max_length:
            self.points.pop(0)
            
    def clear(self):
        self.points.clear()
        
    def draw(self, screen):
        if len(self.points) < 2:
            return
            
        # 1. Draw Sword Blade at Current Head Position
        # The sword blade is drawn as a glowing laser cylinder from the last point
        head = self.points[-1]
        hx, hy = head["pos"]
        h_angle = head["angle"]
        h_depth = head["depth"]
        
        # Calculate screen scale based on depth
        scale = FOCAL_LENGTH / (h_depth + FOCAL_LENGTH)
        draw_len = self.blade_length * scale
        
        # Sword direction vector: along the tilt angle
        # Draw blade extending symmetrically or as a single blade.
        # Let's draw it extending upwards from hx, hy
        bx_end = hx + draw_len * math.cos(h_angle - math.pi/2)
        by_end = hy + draw_len * math.sin(h_angle - math.pi/2)
        bx_base = hx - 20 * scale * math.cos(h_angle - math.pi/2)
        by_base = hy - 20 * scale * math.sin(h_angle - math.pi/2)
        
        # Draw blade layers for a beautiful neon glowing effect
        # Layer 1: Thick outer blur (neon pink/blue)
        glow_color = COLOR_NEON_BLUE
        core_color = COLOR_WHITE
        
        pygame.draw.line(screen, glow_color, (bx_base, by_base), (bx_end, by_end), int(12 * scale))
        pygame.draw.line(screen, COLOR_NEON_PINK, (bx_base, by_base), (bx_end, by_end), int(8 * scale))
        # Layer 2: White core
        pygame.draw.line(screen, core_color, (bx_base, by_base), (bx_end, by_end), int(4 * scale))
        # Draw crossguard/hilt circle
        pygame.draw.circle(screen, (80, 80, 80), (int(bx_base), int(by_base)), int(8 * scale))
        pygame.draw.circle(screen, COLOR_NEON_BLUE, (int(bx_base), int(by_base)), int(6 * scale), int(2 * scale))
        
        # 2. Draw Swoosh Motion Trail
        # Reconstruct trail based on points history
        # We can draw overlapping filled polygons or thick lines between subsequent steps.
        # To make it taper off, we reduce width and opacity for older points.
        for i in range(len(self.points) - 1):
            p1 = self.points[i]
            p2 = self.points[i+1]
            
            # Progress factor (0 to 1, where 1 is the newest)
            factor = i / (len(self.points) - 1)
            
            # Width and opacity fade
            width = int(14 * factor * (FOCAL_LENGTH / (p1["depth"] + FOCAL_LENGTH)))
            alpha = int(180 * factor)
            
            if width <= 0:
                continue
                
            # Draw line segment on a scratch surface for transparency
            trail_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            
            # Outer glow
            pygame.draw.line(
                trail_surf, 
                COLOR_NEON_BLUE + (alpha // 2,), 
                p1["pos"], p2["pos"], 
                width + 6
            )
            # Inner core
            pygame.draw.line(
                trail_surf, 
                COLOR_NEON_PINK + (alpha,), 
                p1["pos"], p2["pos"], 
                width
            )
            pygame.draw.line(
                trail_surf, 
                COLOR_WHITE + (alpha,), 
                p1["pos"], p2["pos"], 
                max(1, width // 3)
            )
            
            screen.blit(trail_surf, (0, 0))
            
    def get_blade_segment_at(self, index):
        """Returns the blade line segment (base_pos, tip_pos) at a historical index."""
        if not self.points or abs(index) > len(self.points):
            return None
        head = self.points[index]
        hx, hy = head["pos"]
        h_angle = head["angle"]
        h_depth = head["depth"]
        scale = FOCAL_LENGTH / (h_depth + FOCAL_LENGTH)
        draw_len = self.blade_length * scale
        
        bx_end = hx + draw_len * math.cos(h_angle - math.pi/2)
        by_end = hy + draw_len * math.sin(h_angle - math.pi/2)
        bx_base = hx - 20 * scale * math.cos(h_angle - math.pi/2)
        by_base = hy - 20 * scale * math.sin(h_angle - math.pi/2)
        
        return (bx_base, by_base), (bx_end, by_end)

    def get_blade_segment(self):
        """Returns the current blade line segment (base_pos, tip_pos) for collision detection."""
        return self.get_blade_segment_at(-1)
