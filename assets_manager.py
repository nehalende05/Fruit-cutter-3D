import os
import math
import numpy as np
import cv2
import pygame
from config import (
    ARUCO_MARKER_PATH, COLOR_RED, COLOR_YELLOW, COLOR_NEON_GREEN, COLOR_WHITE
)

# Initialize Pygame Mixer if possible
MIXER_INITIALIZED = False
try:
    pygame.mixer.init(frequency=22050, size=-16, channels=1)
    MIXER_INITIALIZED = True
except Exception as e:
    print(f"Warning: Could not initialize pygame mixer: {e}. Running without sound.")

class MockSound:
    """Fallback sound object when audio card is missing."""
    def play(self, *args, **kwargs): pass
    def stop(self): pass
    def set_volume(self, vol): pass

def synthesize_sound(sound_type):
    """Synthesizes sound effects procedurally and returns a pygame.Sound object (or MockSound)."""
    if not MIXER_INITIALIZED:
        return MockSound()

    sample_rate = 22050
    
    try:
        if sound_type == "slice":
            # Rising frequency sweep (swoosh/zap)
            duration = 0.15
            t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
            # Frequency sweep from 250Hz to 1800Hz
            freq = 250 + 1550 * (t / duration)
            samples = np.sin(2 * np.pi * freq * t)
            # Volume envelope (fast decay)
            envelope = np.exp(-4 * t / duration)
            samples = samples * envelope
            
        elif sound_type == "explosion":
            # Low-frequency noise burst
            duration = 0.8
            t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
            noise = np.random.uniform(-1.0, 1.0, len(t))
            # Low pass filter approximation via cumulative average
            noise = np.convolve(noise, np.ones(5)/5, mode='same')
            # Volume envelope (slow decay)
            envelope = np.exp(-5 * t / duration)
            samples = noise * envelope
            
        elif sound_type == "combo":
            # Arpeggio: chord of notes (C5, E5, G5) rising
            duration = 0.35
            t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
            f1 = 523.25 * (1 + 0.5 * t / duration) # C5
            f2 = 659.25 * (1 + 0.5 * t / duration) # E5
            f3 = 783.99 * (1 + 0.5 * t / duration) # G5
            samples = (np.sin(2 * np.pi * f1 * t) + 
                       np.sin(2 * np.pi * f2 * t) + 
                       np.sin(2 * np.pi * f3 * t)) / 3.0
            envelope = np.exp(-3 * t / duration)
            samples = samples * envelope
            
        elif sound_type == "click":
            # Fast high-pitched blip
            duration = 0.05
            t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
            samples = np.sin(2 * np.pi * 1000 * t)
            envelope = np.exp(-15 * t / duration)
            samples = samples * envelope
            
        elif sound_type == "lose_life":
            # Falling frequency sweep
            duration = 0.5
            t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
            freq = 600 - 450 * (t / duration)
            samples = np.sin(2 * np.pi * freq * t)
            envelope = np.exp(-3 * t / duration)
            samples = samples * envelope
            
        else:
            return MockSound()

        # Scale to 16-bit signed integers (-32768 to 32767)
        audio_data = (samples * 32767).astype(np.int16)
        
        # Adjust for stereo mixer if initialized
        mixer_init = pygame.mixer.get_init()
        if mixer_init and mixer_init[2] == 2:
            audio_data = np.column_stack((audio_data, audio_data))
            
        # Create Pygame Sound from numpy array
        return pygame.sndarray.make_sound(audio_data)
        
    except Exception as e:
        print(f"Error synthesizing sound '{sound_type}': {e}")
        return MockSound()

# Sound cache
SOUNDS = {}

def get_sound(sound_type):
    """Retrieves or synthesizes a cached sound effect."""
    if sound_type not in SOUNDS:
        SOUNDS[sound_type] = synthesize_sound(sound_type)
    return SOUNDS[sound_type]

def play_sound(sound_type, volume=0.5):
    """Helper to quickly play a sound with volume adjustment."""
    sound = get_sound(sound_type)
    if sound:
        sound.set_volume(volume)
        sound.play()

def generate_aruco_marker():
    """Generates an ArUco marker image and saves it to the workspace for the user's phone screen."""
    if os.path.exists(ARUCO_MARKER_PATH):
        return
        
    try:
        # Create DICT_4X4_50 marker
        dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        marker_id = 42  # Standard ID to track
        size_pixels = 512
        
        # Generate marker with white border
        marker_img = cv2.aruco.generateImageMarker(dictionary, marker_id, size_pixels)
        
        # Add a thick white border around it to help detection
        border_size = 64
        padded_img = cv2.copyMakeBorder(
            marker_img, border_size, border_size, border_size, border_size,
            cv2.BORDER_CONSTANT, value=255
        )
        
        # Save image
        cv2.imwrite(ARUCO_MARKER_PATH, padded_img)
        print(f"ArUco marker exported successfully to {ARUCO_MARKER_PATH}")
    except Exception as e:
        print(f"Error generating ArUco marker: {e}")

# Color mappings for fruits (for particles/splashes and labels)
FRUIT_COLORS = {
    "Apple": (230, 30, 30),      # Bright red
    "Orange": (255, 140, 0),     # Orange
    "Banana": (255, 230, 50),    # Yellow
    "Watermelon": (40, 180, 40),  # Green skin, but inside is red!
    "Mango": (255, 180, 0),      # Yellow-orange
    "Kiwi": (140, 190, 40),      # Kiwi green
    "Pineapple": (210, 170, 40), # Golden brown
    "Lemon": (245, 245, 0),      # Bright yellow
    "Strawberry": (240, 20, 70),  # Deep red
    "Bomb": (30, 30, 30)         # Dark grey/black
}

def draw_fruit_procedural(fruit_type, size=120):
    """Draws a beautiful fruit sprite procedurally on a Pygame Surface with transparency."""
    surface = pygame.Surface((size, size), pygame.SRCALPHA)
    cx, cy = size // 2, size // 2
    
    if fruit_type == "Apple":
        # Draw stem
        pygame.draw.line(surface, (120, 70, 30), (cx, cy - size//3), (cx - 10, cy - size//2), 4)
        # Draw leaf
        pygame.draw.ellipse(surface, (50, 180, 50), (cx - 12, cy - size//2 - 4, 16, 10))
        # Draw overlapping red lobes for apple shape
        pygame.draw.circle(surface, (220, 20, 20), (cx - 15, cy + 5), size//3)
        pygame.draw.circle(surface, (220, 20, 20), (cx + 15, cy + 5), size//3)
        pygame.draw.circle(surface, (200, 10, 10), (cx, cy + 12), size//4)
        # 3D Highlight
        pygame.draw.ellipse(surface, (255, 150, 150), (cx - 22, cy - 15, 15, 8))
        
    elif fruit_type == "Orange":
        # Outer skin
        pygame.draw.circle(surface, (255, 120, 0), (cx, cy), size//2 - 2)
        # Inner white rind
        pygame.draw.circle(surface, (255, 240, 220), (cx, cy), size//2 - 6)
        # Segments
        pygame.draw.circle(surface, (255, 150, 0), (cx, cy), size//2 - 9)
        # Slice wedges
        for i in range(8):
            angle = i * (math.pi / 4)
            ex = cx + int((size//2 - 8) * math.cos(angle))
            ey = cy + int((size//2 - 8) * math.sin(angle))
            pygame.draw.line(surface, (255, 240, 220), (cx, cy), (ex, ey), 2)
        pygame.draw.circle(surface, (255, 240, 220), (cx, cy), 6)
        
    elif fruit_type == "Banana":
        # Curved crescent yellow shape
        pts = []
        r_outer = size // 2.2
        r_inner = size // 2.8
        # Center of arc
        ax, ay = cx + size//4, cy - size//4
        # We draw a polygon sweep
        for deg in range(120, 270, 10):
            rad = math.radians(deg)
            pts.append((ax + r_outer * math.cos(rad), ay + r_outer * math.sin(rad)))
        for deg in range(260, 110, -10):
            rad = math.radians(deg)
            pts.append((ax + r_inner * math.cos(rad), ay + r_inner * math.sin(rad)))
            
        if len(pts) > 2:
            pygame.draw.polygon(surface, (255, 220, 30), pts)
            # Brown tips
            pygame.draw.circle(surface, (90, 60, 20), (int(pts[0][0]), int(pts[0][1])), 6)
            pygame.draw.circle(surface, (90, 60, 20), (int(pts[-1][0]), int(pts[-1][1])), 4)
            
    elif fruit_type == "Watermelon":
        # Dark green outer skin
        pygame.draw.circle(surface, (20, 100, 20), (cx, cy), size//2 - 2)
        # Light green/white rind
        pygame.draw.circle(surface, (220, 255, 220), (cx, cy), size//2 - 7)
        # Red flesh
        pygame.draw.circle(surface, (230, 30, 60), (cx, cy), size//2 - 12)
        # Seeds
        seeds = [(-15, -15), (15, -15), (-20, 10), (20, 10), (0, -25), (0, 20)]
        for sx, sy in seeds:
            pygame.draw.circle(surface, (30, 30, 30), (cx + sx, cy + sy), 3)
            
    elif fruit_type == "Mango":
        # Smooth oblong mango shape (represented as skewed circles)
        pygame.draw.circle(surface, (240, 180, 10), (cx - 10, cy), size//3.2)
        pygame.draw.circle(surface, (255, 200, 20), (cx + 8, cy - 5), size//3.5)
        pygame.draw.circle(surface, (220, 140, 10), (cx - 15, cy + 12), size//4.5)
        # Stem dot
        pygame.draw.circle(surface, (100, 70, 20), (cx + 12, cy - 20), 4)
        
    elif fruit_type == "Kiwi":
        # Fuzzy brown skin
        pygame.draw.circle(surface, (120, 90, 50), (cx, cy), size//2 - 2)
        # Kiwi green flesh
        pygame.draw.circle(surface, (130, 190, 30), (cx, cy), size//2 - 8)
        # Light green inner core
        pygame.draw.ellipse(surface, (210, 235, 140), (cx - 12, cy - 10, 24, 20))
        # Seeds ring
        for i in range(12):
            angle = i * (math.pi / 6)
            rx = cx + int(18 * math.cos(angle))
            ry = cy + int(15 * math.sin(angle))
            pygame.draw.circle(surface, (30, 30, 30), (rx, ry), 2)
            
    elif fruit_type == "Pineapple":
        # Green leaves top
        for i in range(-2, 3):
            leaf_surface = pygame.Surface((30, 60), pygame.SRCALPHA)
            # Draw rotated leaf
            pygame.draw.polygon(leaf_surface, (30, 140, 40), [(15, 0), (5, 60), (25, 60)])
            rot_leaf = pygame.transform.rotate(leaf_surface, -i * 15)
            surface.blit(rot_leaf, (cx - rot_leaf.get_width()//2 + i*10, cy - size//2))
            
        # Yellow-brown patterned body
        body_rect = pygame.Rect(cx - size//3, cy - size//4, size//1.5, size//1.8)
        pygame.draw.ellipse(surface, (210, 160, 30), body_rect)
        # Draw checkers
        for dy in range(-size//4, size//3, 15):
            for dx in range(-size//3, size//3, 15):
                if (dx*dx)/(size//3)**2 + (dy*dy)/(size//3)**2 < 1.0:
                    pygame.draw.line(surface, (140, 90, 20), (cx + dx - 6, cy + dy - 6), (cx + dx + 6, cy + dy + 6), 2)
                    pygame.draw.line(surface, (140, 90, 20), (cx + dx + 6, cy + dy - 6), (cx + dx - 6, cy + dy + 6), 2)
                    
    elif fruit_type == "Lemon":
        # Lemon oval
        lemon_rect = pygame.Rect(cx - size//2.5, cy - size//3.2, size//1.25, size//1.6)
        pygame.draw.ellipse(surface, (255, 230, 20), lemon_rect)
        # Lemon tips
        pygame.draw.polygon(surface, (230, 200, 10), [(cx - size//2.2, cy), (cx - size//2.5, cy - 8), (cx - size//2.5, cy + 8)])
        pygame.draw.polygon(surface, (230, 200, 10), [(cx + size//2.2, cy), (cx + size//2.5, cy - 8), (cx + size//2.5, cy + 8)])
        # Inner details
        pygame.draw.ellipse(surface, (255, 255, 180), (cx - size//3, cy - size//4.5, size//1.5, size//2.25))
        
    elif fruit_type == "Strawberry":
        # Strawberry red heart
        pygame.draw.circle(surface, (220, 20, 60), (cx - 12, cy - 10), size//3.8)
        pygame.draw.circle(surface, (220, 20, 60), (cx + 12, cy - 10), size//3.8)
        pygame.draw.polygon(surface, (220, 20, 60), [(cx - 22, cy - 6), (cx + 22, cy - 6), (cx, cy + size//3)])
        # Green leafy crown
        pygame.draw.polygon(surface, (40, 150, 40), [(cx, cy - 12), (cx - 20, cy - 25), (cx - 5, cy - 20)])
        pygame.draw.polygon(surface, (40, 150, 40), [(cx, cy - 12), (cx + 20, cy - 25), (cx + 5, cy - 20)])
        pygame.draw.polygon(surface, (30, 130, 30), [(cx, cy - 12), (cx, cy - 28), (cx - 8, cy - 22)])
        # Seeds
        for i in range(-3, 4):
            for j in range(-2, 3):
                sx = cx + i * 8 + (j % 2) * 4
                sy = cy + j * 12
                # Only draw if inside strawberry boundary
                if (sy - cy) < size//3 and abs(sx - cx) < (22 - (sy - cy) * 0.4):
                    pygame.draw.circle(surface, (255, 230, 100), (sx, sy), 2)
                    
    elif fruit_type == "Bomb":
        # Fuse wire
        fuse_pts = [(cx, cy - size//3), (cx + 10, cy - size//2.2), (cx + 22, cy - size//2)]
        pygame.draw.lines(surface, (140, 140, 140), False, fuse_pts, 3)
        # Spark
        spark_cx, spark_cy = fuse_pts[-1]
        pygame.draw.circle(surface, (255, 200, 0), (spark_cx, spark_cy), 10)
        pygame.draw.circle(surface, (255, 50, 0), (spark_cx, spark_cy), 5)
        # Black bomb body
        pygame.draw.circle(surface, (40, 40, 40), (cx, cy), size//3)
        # Shading / shine
        pygame.draw.circle(surface, (60, 60, 60), (cx - 8, cy - 8), size//4)
        pygame.draw.circle(surface, (255, 255, 255), (cx - 15, cy - 15), 6)
        
    return surface

def split_sprite_in_half(surface, angle_rad, center_offset=(0, 0)):
    """
    Slices a Pygame surface into two halves (A and B) along an angle passing through the center.
    Uses numpy array alpha masking to do it cleanly.
    Returns: (half_a_surf, half_b_surf)
    """
    width, height = surface.get_size()
    cx, cy = width // 2 + center_offset[0], height // 2 + center_offset[1]
    
    # Copy original surface
    half_a = surface.copy()
    half_b = surface.copy()
    
    # Reference pixel alphas (locks surface, need to delete refs later)
    alpha_a = pygame.surfarray.pixels_alpha(half_a)
    alpha_b = pygame.surfarray.pixels_alpha(half_b)
    
    # Compute normal vector of the cut plane
    # The blade cuts along the angle_rad. The splitting is perpendicular to it.
    cos_theta = math.cos(angle_rad)
    sin_theta = math.sin(angle_rad)
    
    # Grid of coordinates
    y, x = np.ogrid[:height, :width]
    dx = x - cx
    dy = y - cy
    
    # Distance projection relative to cut line
    # Positive side = half A, Negative side = half B
    proj = dx * cos_theta + dy * sin_theta
    
    # Clear matching sides
    alpha_a[proj < 0] = 0
    alpha_b[proj >= 0] = 0
    
    # Unlock surfaces
    del alpha_a
    del alpha_b
    
    return half_a, half_b
