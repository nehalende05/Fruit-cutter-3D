import os

# Screen Settings
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS = 60

# File Paths
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
CALIBRATION_FILE = os.path.join(DATA_DIR, "calibration.json")
HIGH_SCORE_FILE = os.path.join(DATA_DIR, "high_scores.json")
ARUCO_MARKER_PATH = os.path.join(DATA_DIR, "aruco_marker.png")

# Tracking Defaults
DEFAULT_WEBCAM_INDEX = 0
DEFAULT_TRACKING_MODE = "hand"  # "hand", "aruco" or "color"
DEFAULT_SMOOTHING_FACTOR = 0.35  # Exponential Moving Average smoothing (lower = smoother, higher = more responsive)
DEFAULT_SWING_SPEED_THRESHOLD = 15.0  # Speed in pixels/frame required to register a slice

# HSV Color Tracking Defaults (for bright colored marker on phone)
# Default is set to a bright neon green
DEFAULT_HSV_MIN = [35, 60, 60]
DEFAULT_HSV_MAX = [85, 255, 255]

# Game Mechanics
LIVES_DEFAULT = 3
COMBO_TIME_WINDOW = 0.8  # Seconds allowed between cuts to build a combo
GRAVITY = 0.32  # Acceleration downwards (pixels/frame^2)
FRUIT_SPAWN_INTERVAL = 1.8  # Start spawning interval in seconds
MIN_SPAWN_INTERVAL = 0.6  # Minimum spawn interval as game gets harder
DIFFICULTY_SPEED_SCALE = 1.0  # Scale factor for velocities

# 3D Projection Settings
FOCAL_LENGTH = 400
SCREEN_CENTER = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)

# Colors (HEX / RGB)
COLOR_BG_DARK = (15, 12, 28)       # Deep space blue
COLOR_BG_LIGHT = (40, 36, 64)      # Inner glow
COLOR_NEON_GREEN = (57, 255, 20)
COLOR_NEON_BLUE = (0, 246, 255)
COLOR_NEON_PINK = (255, 0, 127)
COLOR_WHITE = (255, 255, 255)
COLOR_RED = (255, 50, 50)
COLOR_YELLOW = (255, 230, 0)

# Difficulty settings profiles
DIFFICULTIES = {
    "Easy": {
        "speed_scale": 0.8,
        "spawn_interval": 2.2,
        "bomb_chance": 0.1,
        "speed_threshold": 10.0
    },
    "Medium": {
        "speed_scale": 1.1,
        "spawn_interval": 1.7,
        "bomb_chance": 0.2,
        "speed_threshold": 15.0
    },
    "Hard": {
        "speed_scale": 1.4,
        "spawn_interval": 1.2,
        "bomb_chance": 0.35,
        "speed_threshold": 22.0
    }
}
