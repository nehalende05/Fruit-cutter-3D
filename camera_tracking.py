import cv2
import numpy as np
import threading
import math
import time
import pygame
from config import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    DEFAULT_WEBCAM_INDEX, DEFAULT_TRACKING_MODE, DEFAULT_SMOOTHING_FACTOR,
    DEFAULT_SWING_SPEED_THRESHOLD, DEFAULT_HSV_MIN, DEFAULT_HSV_MAX
)

# Optional MediaPipe import for Hand Tracking using the new Tasks API
import os
HAS_MEDIAPIPE = False
try:
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision as mp_vision
    HAS_MEDIAPIPE = True
except Exception as e:
    print(f"Warning: Could not import mediapipe: {e}. Hand tracking will be unavailable.")

class CameraTracker:
    def __init__(self):
        # Settings
        self.webcam_index = DEFAULT_WEBCAM_INDEX
        self.tracking_mode = DEFAULT_TRACKING_MODE  # "aruco" or "color"
        self.smoothing_factor = DEFAULT_SMOOTHING_FACTOR
        self.swing_speed_threshold = DEFAULT_SWING_SPEED_THRESHOLD
        
        # HSV Color ranges
        self.hsv_min = np.array(DEFAULT_HSV_MIN, dtype=np.uint8)
        self.hsv_max = np.array(DEFAULT_HSV_MAX, dtype=np.uint8)
        
        # Threading control
        self.running = False
        self.cap = None
        self.thread = None
        self.lock = threading.Lock()
        
        # Latest results (Thread-safe read)
        self.detected_pos = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)  # (X, Y) scaled to screen
        self.detected_depth = 100.0  # Z coordinate (estimated)
        self.detected_angle = 0.0    # Phone tilt in radians
        self.is_detected = False
        self.velocity = (0.0, 0.0)
        self.speed = 0.0
        self.is_swinging = False
        
        # Camera visual frame for preview in Pygame
        self.latest_frame = None       # Raw frame in BGR
        self.pygame_preview = None     # Prepared pygame surface (small size)
        
        # Historical state (for smoothing and derivatives)
        self.raw_pos = None
        self.raw_depth = 100.0
        self.prev_pos = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
        self.lost_frames = 0
        self.lost_frames_limit = 6  # Number of frames to extrapolate during motion-blurred swings
        
        # ArUco parameters
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        self.aruco_params = cv2.aruco.DetectorParameters()
        self.aruco_detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.aruco_params)
        
        # MediaPipe parameters for Hand Tracking using Tasks HandLandmarker
        self.hands = None
        if HAS_MEDIAPIPE:
            try:
                model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hand_landmarker.task')
                if not os.path.exists(model_path):
                    model_path = 'hand_landmarker.task'
                    
                options = mp_vision.HandLandmarkerOptions(
                    base_options=mp_python.BaseOptions(model_asset_path=model_path),
                    running_mode=mp_vision.RunningMode.IMAGE
                )
                self.hands = mp_vision.HandLandmarker.create_from_options(options)
                print("MediaPipe Tasks HandLandmarker initialized successfully.")
            except Exception as e:
                print(f"Error initializing MediaPipe Tasks HandLandmarker: {e}")
        
    def start(self, webcam_index=None, tracking_mode=None):
        """Starts the camera capture and tracking background thread."""
        if self.running:
            self.stop()
            
        if webcam_index is not None:
            self.webcam_index = webcam_index
        if tracking_mode is not None:
            self.tracking_mode = tracking_mode
            
        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
        
    def stop(self):
        """Stops the camera tracking thread and releases camera resources."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
            self.thread = None
            
        with self.lock:
            if self.cap:
                self.cap.release()
                self.cap = None
            self.is_detected = False
            self.speed = 0.0
            self.is_swinging = False
            
    def _capture_loop(self):
        # Open camera
        self.cap = cv2.VideoCapture(self.webcam_index)
        if not self.cap.isOpened():
            print(f"Error: Could not open camera with index {self.webcam_index}")
            self.running = False
            return
            
        # Optimize camera resolution (640x480 is fast and optimal for CV)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        # Read back actual resolution
        cam_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        cam_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if cam_w == 0 or cam_h == 0:
            cam_w, cam_h = 640, 480
            
        prev_time = time.time()
        
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.01)
                continue
                
            # Mirror the frame so left-right alignment is intuitive for the user
            frame = cv2.flip(frame, 1)
            
            # Tracking logic
            detected = False
            raw_x, raw_y = 0.0, 0.0
            raw_z = 100.0  # Default depth
            angle_rad = 0.0
            
            if self.tracking_mode == "hand" and HAS_MEDIAPIPE and self.hands is not None:
                # MediaPipe Tasks Hand Tracking
                try:
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
                    result = self.hands.detect(mp_image)
                    
                    if result.hand_landmarks:
                        hand_landmarks = result.hand_landmarks[0]
                        # Track index finger tip (landmark 8)
                        tip = hand_landmarks[8]
                        wrist = hand_landmarks[0]
                        mcp = hand_landmarks[9]
                        
                        raw_x = tip.x * cam_w
                        raw_y = tip.y * cam_h
                        
                        # Estimate Z depth using hand scale (distance from wrist to middle finger MCP)
                        dx_hand = (mcp.x - wrist.x) * cam_w
                        dy_hand = (mcp.y - wrist.y) * cam_h
                        hand_size = math.hypot(dx_hand, dy_hand)
                        if hand_size > 0:
                            raw_z = 18000.0 / hand_size
                            
                        # Estimate rotation angle from index finger MCP (5) to tip (8)
                        mcp_idx = hand_landmarks[5]
                        dx_finger = (tip.x - mcp_idx.x) * cam_w
                        dy_finger = (tip.y - mcp_idx.y) * cam_h
                        angle_rad = math.atan2(dy_finger, dx_finger) + math.pi/2
                        
                        detected = True
                        
                        # Draw glowing hand skeleton using custom drawing utility
                        self._draw_hand_skeleton(frame, hand_landmarks)
                except Exception as e:
                    print(f"Error in Hand Tracking: {e}")
            elif self.tracking_mode == "aruco":
                # ArUco detection
                corners, ids, _ = self.aruco_detector.detectMarkers(frame)
                
                if ids is not None and len(ids) > 0:
                    # Look for marker ID 42 (from assets_manager) or use the first detected marker
                    target_idx = 0
                    for idx, val in enumerate(ids):
                        if val[0] == 42:
                            target_idx = idx
                            break
                            
                    marker_corners = corners[target_idx][0] # 4 corners: TL, TR, BR, BL
                    
                    # Compute center (centroid) of the 4 corners
                    raw_x = np.mean(marker_corners[:, 0])
                    raw_y = np.mean(marker_corners[:, 1])
                    
                    # Compute rotation angle using top edge vector (TR - TL)
                    dx = marker_corners[1, 0] - marker_corners[0, 0]
                    dy = marker_corners[1, 1] - marker_corners[0, 1]
                    angle_rad = math.atan2(dy, dx)
                    
                    # Estimate depth using average side length
                    # Side length is inversely proportional to depth
                    # Let's say if the marker is 120 pixels wide, it's at depth Z = 100
                    p1 = marker_corners[0]
                    p2 = marker_corners[1]
                    p3 = marker_corners[2]
                    side1 = math.hypot(p2[0]-p1[0], p2[1]-p1[1])
                    side2 = math.hypot(p3[0]-p2[0], p3[1]-p2[1])
                    avg_side = (side1 + side2) / 2.0
                    
                    # Z depth formula: Z = K / side_length
                    if avg_side > 0:
                        raw_z = 15000.0 / avg_side  # Reference calibration value
                        
                    detected = True
                    
            elif self.tracking_mode == "color":
                # Fallback HSV Color Tracking
                hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                mask = cv2.inRange(hsv, self.hsv_min, self.hsv_max)
                
                # Morphological opening/closing to denoise
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
                mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
                mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
                
                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                if contours:
                    # Select largest contour
                    largest_cnt = max(contours, key=cv2.contourArea)
                    area = cv2.contourArea(largest_cnt)
                    
                    if area > 150:  # Threshold area
                        # Calculate centroid
                        M = cv2.moments(largest_cnt)
                        if M["m00"] != 0:
                            raw_x = int(M["m10"] / M["m00"])
                            raw_y = int(M["m01"] / M["m00"])
                            
                            # Estimate depth using square root of area
                            # Larger area = closer to camera (lower Z)
                            raw_z = 25000.0 / math.sqrt(area)
                            
                            # Approximate rotation angle using minimum area rectangle tilt
                            rect = cv2.minAreaRect(largest_cnt)
                            # rect returns ((cx, cy), (w, h), angle)
                            angle_deg = rect[2]
                            # Handle rect angle format
                            if rect[1][0] < rect[1][1]:
                                angle_deg = angle_deg + 90
                            angle_rad = math.radians(angle_deg)
                            
                            detected = True
            
            # Apply EMA smoothing & scale coordinates to match game screen size (1280x720)
            now = time.time()
            dt = now - prev_time
            prev_time = now
            
            with self.lock:
                self.is_detected = detected
                self.latest_frame = frame.copy()
                
                if detected:
                    # Map X: from [0, cam_w] to [0, SCREEN_WIDTH]
                    target_x = (raw_x / cam_w) * SCREEN_WIDTH
                    # Map Y: from [0, cam_h] to [0, SCREEN_HEIGHT]
                    target_y = (raw_y / cam_h) * SCREEN_HEIGHT
                    
                    # Apply EMA smoothing to X, Y
                    smooth_x = self.smoothing_factor * target_x + (1 - self.smoothing_factor) * self.detected_pos[0]
                    smooth_y = self.smoothing_factor * target_y + (1 - self.smoothing_factor) * self.detected_pos[1]
                    
                    # Store previous position
                    self.prev_pos = self.detected_pos
                    self.detected_pos = (smooth_x, smooth_y)
                    
                    # Smooth depth
                    self.detected_depth = self.smoothing_factor * raw_z + (1 - self.smoothing_factor) * self.detected_depth
                    # Smooth angle
                    # Account for angle wrapping
                    diff_angle = angle_rad - self.detected_angle
                    # Normalize diff to [-pi, pi]
                    diff_angle = (diff_angle + math.pi) % (2 * math.pi) - math.pi
                    self.detected_angle += self.smoothing_factor * diff_angle
                    
                    # Compute speed in pixels/frame (assuming 60fps target, scale velocity vector)
                    # We compute movement delta
                    dx = self.detected_pos[0] - self.prev_pos[0]
                    dy = self.detected_pos[1] - self.prev_pos[1]
                    
                    self.velocity = (dx, dy)
                    self.speed = math.hypot(dx, dy)
                    
                    # Determine swing state
                    self.is_swinging = (self.speed >= self.swing_speed_threshold)
                    self.lost_frames = 0
                else:
                    # Dead-reckoning / extrapolation: if tracking drops out during a high-speed swing (likely due to motion blur)
                    if self.lost_frames < self.lost_frames_limit and self.speed > 5.0:
                        self.lost_frames += 1
                        self.is_detected = True  # Keep sword active in game engine
                        
                        # Extrapolate next position based on last velocity with air resistance decay
                        self.velocity = (self.velocity[0] * 0.85, self.velocity[1] * 0.85)
                        self.speed = math.hypot(self.velocity[0], self.velocity[1])
                        
                        self.prev_pos = self.detected_pos
                        new_x = max(0.0, min(float(SCREEN_WIDTH), self.detected_pos[0] + self.velocity[0]))
                        new_y = max(0.0, min(float(SCREEN_HEIGHT), self.detected_pos[1] + self.velocity[1]))
                        self.detected_pos = (new_x, new_y)
                        
                        self.is_swinging = (self.speed >= self.swing_speed_threshold)
                    else:
                        # Decay speed if not detected and not swinging
                        self.velocity = (0.0, 0.0)
                        self.speed *= 0.5
                        if self.speed < 1.0:
                            self.speed = 0.0
                        self.is_swinging = False
                
                # Create a small resized Pygame surface for webcam preview display in-game
                # Convert BGR frame to RGB and scale to 160x120
                preview_small = cv2.resize(frame, (160, 120))
                # Draw visual tracking indicator in the preview frame (dot on center)
                if detected:
                    # Map coordinates back to preview scale
                    px = int((raw_x / cam_w) * 160)
                    py = int((raw_y / cam_h) * 120)
                    # Draw target crosshair
                    cv2.circle(preview_small, (px, py), 6, (0, 255, 0), -1)
                    cv2.line(preview_small, (px - 10, py), (px + 10, py), (0, 255, 0), 2)
                    cv2.line(preview_small, (px, py - 10), (px, py + 10), (0, 255, 0), 2)
                    
                # Convert BGR (OpenCV) to RGB for Pygame
                preview_rgb = cv2.cvtColor(preview_small, cv2.COLOR_BGR2RGB)
                # Convert to pygame surface
                self.pygame_preview = pygame.surfarray.make_surface(np.transpose(preview_rgb, (1, 0, 2)))

            # Limit capture loop speed to avoid consuming 100% CPU
            time.sleep(0.01)

    def _draw_hand_skeleton(self, frame, landmarks):
        """Draws a beautiful digital glowing skeleton on the hand frame using OpenCV."""
        h, w = frame.shape[:2]
        connections = [
            (0, 1), (1, 2), (2, 3), (3, 4),      # Thumb
            (0, 5), (5, 6), (6, 7), (7, 8),      # Index finger
            (9, 10), (10, 11), (11, 12),         # Middle finger
            (13, 14), (14, 15), (15, 16),        # Ring finger
            (0, 17), (17, 18), (18, 19), (19, 20), # Pinky
            (5, 9), (9, 13), (13, 17)            # Knuckles
        ]
        # Draw skeleton lines
        for p1_idx, p2_idx in connections:
            if p1_idx < len(landmarks) and p2_idx < len(landmarks):
                p1 = landmarks[p1_idx]
                p2 = landmarks[p2_idx]
                x1, y1 = int(p1.x * w), int(p1.y * h)
                x2, y2 = int(p2.x * w), int(p2.y * h)
                cv2.line(frame, (x1, y1), (x2, y2), (57, 255, 20), 2)  # Neon green line
                
        # Draw joint circles
        for lm in landmarks:
            x, y = int(lm.x * w), int(lm.y * h)
            cv2.circle(frame, (x, y), 4, (0, 246, 255), -1)  # Neon blue dots

    def get_tracking_data(self):
        """Returns a snapshot of the current tracking values."""
        with self.lock:
            return {
                "pos": self.detected_pos,
                "prev_pos": self.prev_pos,
                "depth": self.detected_depth,
                "angle": self.detected_angle,
                "is_detected": self.is_detected,
                "velocity": self.velocity,
                "speed": self.speed,
                "is_swinging": self.is_swinging
            }
            
    def get_preview_surface(self):
        """Returns the pre-drawn Pygame preview surface."""
        with self.lock:
            return self.pygame_preview

    def get_raw_frame(self):
        """Returns the raw numpy frame (BGR). For use in calibration overlay."""
        with self.lock:
            if self.latest_frame is not None:
                return self.latest_frame.copy()
            return None
