import os
import json
import cv2
import numpy as np
import pygame
from config import (
    CALIBRATION_FILE, DEFAULT_WEBCAM_INDEX, DEFAULT_TRACKING_MODE,
    DEFAULT_HSV_MIN, DEFAULT_HSV_MAX, SCREEN_WIDTH, SCREEN_HEIGHT,
    COLOR_NEON_BLUE, COLOR_NEON_PINK, COLOR_WHITE, COLOR_BG_DARK
)
from assets_manager import play_sound

def load_calibration_settings():
    """Loads calibration settings from JSON. Returns defaults if file doesn't exist."""
    if not os.path.exists(CALIBRATION_FILE):
        return {
            "webcam_index": DEFAULT_WEBCAM_INDEX,
            "tracking_mode": DEFAULT_TRACKING_MODE,
            "hsv_min": DEFAULT_HSV_MIN,
            "hsv_max": DEFAULT_HSV_MAX
        }
    
    try:
        with open(CALIBRATION_FILE, "r") as f:
            data = json.load(f)
            return {
                "webcam_index": int(data.get("webcam_index", DEFAULT_WEBCAM_INDEX)),
                "tracking_mode": str(data.get("tracking_mode", DEFAULT_TRACKING_MODE)),
                "hsv_min": list(data.get("hsv_min", DEFAULT_HSV_MIN)),
                "hsv_max": list(data.get("hsv_max", DEFAULT_HSV_MAX))
            }
    except Exception as e:
        print(f"Error reading calibration file: {e}. Using defaults.")
        return {
            "webcam_index": DEFAULT_WEBCAM_INDEX,
            "tracking_mode": DEFAULT_TRACKING_MODE,
            "hsv_min": DEFAULT_HSV_MIN,
            "hsv_max": DEFAULT_HSV_MAX
        }

def save_calibration_settings(webcam_index, tracking_mode, hsv_min, hsv_max):
    """Saves calibration settings to JSON file."""
    try:
        data = {
            "webcam_index": int(webcam_index),
            "tracking_mode": str(tracking_mode),
            "hsv_min": [int(x) for x in hsv_min],
            "hsv_max": [int(x) for x in hsv_max]
        }
        with open(CALIBRATION_FILE, "w") as f:
            json.dump(data, f, indent=4)
        print("Calibration settings saved.")
        return True
    except Exception as e:
        print(f"Failed to save calibration settings: {e}")
        return False

class Slider:
    def __init__(self, x, y, w, h, min_val, max_val, initial_val, label):
        self.rect = pygame.Rect(x, y, w, h)
        self.min_val = min_val
        self.max_val = max_val
        self.val = initial_val
        self.label = label
        self.dragging = False
        self.handle_width = 14
        self.handle_rect = pygame.Rect(0, y - 6, self.handle_width, h + 12)
        self._update_handle()
        
    def _update_handle(self):
        ratio = (self.val - self.min_val) / (self.max_val - self.min_val)
        self.handle_rect.centerx = self.rect.x + ratio * self.rect.width
        
    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                # Check handle collision or clicking inside slider track
                click_rect = self.rect.inflate(0, 15)
                if click_rect.collidepoint(event.pos):
                    self.dragging = True
                    self._move_to_mouse(event.pos[0])
                    return True
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1 and self.dragging:
                self.dragging = False
                return True
        elif event.type == pygame.MOUSEMOTION:
            if self.dragging:
                self._move_to_mouse(event.pos[0])
                return True
        return False
        
    def _move_to_mouse(self, mouse_x):
        mx = max(self.rect.x, min(mouse_x, self.rect.right))
        ratio = (mx - self.rect.x) / self.rect.width
        self.val = self.min_val + ratio * (self.max_val - self.min_val)
        self._update_handle()

    def draw(self, screen, font):
        # Draw label
        lbl_surf = font.render(f"{self.label}: {int(self.val)}", True, COLOR_WHITE)
        screen.blit(lbl_surf, (self.rect.x, self.rect.y - 20))
        
        # Draw track
        pygame.draw.rect(screen, (50, 45, 75), self.rect, border_radius=4)
        
        # Draw active track fill
        active_w = self.handle_rect.centerx - self.rect.x
        if active_w > 0:
            active_rect = pygame.Rect(self.rect.x, self.rect.y, active_w, self.rect.height)
            pygame.draw.rect(screen, COLOR_NEON_BLUE, active_rect, border_radius=4)
            
        # Draw handle
        pygame.draw.rect(screen, COLOR_WHITE, self.handle_rect, border_radius=4)
        pygame.draw.rect(screen, (200, 200, 200), self.handle_rect, 1, border_radius=4)

class CalibrationWizard:
    def __init__(self, tracker):
        self.tracker = tracker
        
        # Load current settings
        settings = load_calibration_settings()
        self.webcam_index = settings["webcam_index"]
        self.tracking_mode = settings["tracking_mode"]
        self.hsv_min = settings["hsv_min"]
        self.hsv_max = settings["hsv_max"]
        
        # UI controls coordinate layout
        self.panel_x = 750
        self.slider_w = 400
        
        # Create Sliders for HSV (H: 0-180, S: 0-255, V: 0-255)
        slider_y_start = 220
        spacing = 65
        self.sliders = [
            Slider(self.panel_x, slider_y_start + 0*spacing, self.slider_w, 10, 0, 180, self.hsv_min[0], "H Min"),
            Slider(self.panel_x, slider_y_start + 1*spacing, self.slider_w, 10, 0, 180, self.hsv_max[0], "H Max"),
            Slider(self.panel_x, slider_y_start + 2*spacing, self.slider_w, 10, 0, 255, self.hsv_min[1], "S Min"),
            Slider(self.panel_x, slider_y_start + 3*spacing, self.slider_w, 10, 0, 255, self.hsv_max[1], "S Max"),
            Slider(self.panel_x, slider_y_start + 4*spacing, self.slider_w, 10, 0, 255, self.hsv_min[2], "V Min"),
            Slider(self.panel_x, slider_y_start + 5*spacing, self.slider_w, 10, 0, 255, self.hsv_max[2], "V Max")
        ]
        
        # Action Buttons rect definitions
        self.btn_cam_prev = pygame.Rect(self.panel_x, 90, 45, 35)
        self.btn_cam_next = pygame.Rect(self.panel_x + 195, 90, 45, 35)
        self.btn_mode_toggle = pygame.Rect(self.panel_x, 140, 240, 35)
        
        self.btn_save = pygame.Rect(self.panel_x, 620, 185, 45)
        self.btn_back = pygame.Rect(self.panel_x + 215, 620, 185, 45)
        
        # Status indicators
        self.status_msg = "Adjust tracking parameters."
        self.status_color = COLOR_WHITE
        self.status_timer = 0
        
        # Start tracking thread with local index
        self.tracker.start(self.webcam_index, self.tracking_mode)
        self.update_tracker_hsv()
        
    def update_tracker_hsv(self):
        """Passes calibration's HSV ranges to the running camera tracker."""
        self.tracker.hsv_min = np.array(self.hsv_min, dtype=np.uint8)
        self.tracker.hsv_max = np.array(self.hsv_max, dtype=np.uint8)

    def handle_event(self, event):
        # Handle sliders
        if self.tracking_mode == "color":
            for idx, slider in enumerate(self.sliders):
                if slider.handle_event(event):
                    # Value changed, update our settings
                    if idx % 2 == 0:
                        self.hsv_min[idx // 2] = int(slider.val)
                    else:
                        self.hsv_max[idx // 2] = int(slider.val)
                    self.update_tracker_hsv()
                    return True
                    
        # Handle buttons
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mpos = event.pos
            
            # Webcam index adjustment
            if self.btn_cam_prev.collidepoint(mpos):
                play_sound("click")
                if self.webcam_index > 0:
                    self.webcam_index -= 1
                    self.tracker.start(self.webcam_index, self.tracking_mode)
                    self.update_tracker_hsv()
                    self.show_status(f"Camera set to {self.webcam_index}")
                return True
                
            elif self.btn_cam_next.collidepoint(mpos):
                play_sound("click")
                self.webcam_index += 1
                self.tracker.start(self.webcam_index, self.tracking_mode)
                self.update_tracker_hsv()
                self.show_status(f"Camera set to {self.webcam_index}")
                return True
                
            # Mode toggle
            elif self.btn_mode_toggle.collidepoint(mpos):
                play_sound("click")
                from camera_tracking import HAS_MEDIAPIPE
                modes = ["hand", "aruco", "color"] if HAS_MEDIAPIPE else ["aruco", "color"]
                curr_idx = modes.index(self.tracking_mode) if self.tracking_mode in modes else 0
                self.tracking_mode = modes[(curr_idx + 1) % len(modes)]
                
                self.tracker.tracking_mode = self.tracking_mode
                self.tracker.start(self.webcam_index, self.tracking_mode)
                self.update_tracker_hsv()
                self.show_status(f"Mode switched to {self.tracking_mode.upper()}")
                return True
                
            # Save button
            elif self.btn_save.collidepoint(mpos):
                play_sound("click")
                success = save_calibration_settings(
                    self.webcam_index, self.tracking_mode,
                    self.hsv_min, self.hsv_max
                )
                if success:
                    self.show_status("Settings saved successfully!", COLOR_NEON_BLUE)
                else:
                    self.show_status("Error saving settings!", COLOR_NEON_PINK)
                return True
                
            # Back button
            elif self.btn_back.collidepoint(mpos):
                play_sound("click")
                # Close/Stop tracking so state machine caller can restart it cleanly in game index settings
                self.tracker.stop()
                return "back"
                
        return False
        
    def show_status(self, msg, color=COLOR_WHITE):
        self.status_msg = msg
        self.status_color = color
        self.status_timer = 120  # frames duration (~2 seconds)

    def update(self):
        if self.status_timer > 0:
            self.status_timer -= 1

    def draw(self, screen, font, title_font):
        screen.fill(COLOR_BG_DARK)
        
        # 1. RENDER WIZARD HEADER
        title_surf = title_font.render("TRACKING CALIBRATION", True, COLOR_NEON_BLUE)
        screen.blit(title_surf, (50, 30))
        
        desc_surf = font.render("Align camera, select mode, and verify the sword tracking quality.", True, COLOR_WHITE)
        screen.blit(desc_surf, (50, 75))
        
        # 2. RENDER LIVE CAMERA FEED (LEFT COLUMN)
        # Webcam container
        cam_box = pygame.Rect(50, 110, 640, 480)
        pygame.draw.rect(screen, (30, 25, 50), cam_box, border_radius=8)
        
        raw_frame = self.tracker.get_raw_frame()
        if raw_frame is not None:
            # Map raw capture frame size to 640x480 surface
            rgb_frame = cv2.cvtColor(raw_frame, cv2.COLOR_BGR2RGB)
            cam_surface = pygame.surfarray.make_surface(np.transpose(rgb_frame, (1, 0, 2)))
            cam_surface_scaled = pygame.transform.smoothscale(cam_surface, (640, 480))
            screen.blit(cam_surface_scaled, (50, 110))
            
            # Overlay crosshair if phone is detected
            track = self.tracker.get_tracking_data()
            if track["is_detected"]:
                # Map scaled tracking coordinate to cam coordinates (X in [0, screen_w], mapped to [50, 690])
                tx = 50 + int((track["pos"][0] / SCREEN_WIDTH) * 640)
                ty = 110 + int((track["pos"][1] / SCREEN_HEIGHT) * 480)
                
                # Draw neon crosshair
                pygame.draw.circle(screen, COLOR_NEON_BLUE, (tx, ty), 10, 2)
                pygame.draw.line(screen, COLOR_NEON_BLUE, (tx - 20, ty), (tx + 20, ty), 2)
                pygame.draw.line(screen, COLOR_NEON_BLUE, (tx, ty - 20), (tx, ty + 20), 2)
                
            # If in Color tracking mode, render picture-in-picture of binary mask
            if self.tracking_mode == "color":
                hsv = cv2.cvtColor(raw_frame, cv2.COLOR_BGR2HSV)
                mask = cv2.inRange(hsv, self.tracker.hsv_min, self.tracker.hsv_max)
                # Denoise
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
                mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
                
                # Convert 1-channel mask to 3-channel grayscale for Pygame
                mask_rgb = cv2.cvtColor(mask, cv2.COLOR_GRAY2RGB)
                mask_surf = pygame.surfarray.make_surface(np.transpose(mask_rgb, (1, 0, 2)))
                mask_surf_scaled = pygame.transform.smoothscale(mask_surf, (160, 120))
                
                # Render in bottom right corner of webcam view
                screen.blit(mask_surf_scaled, (50 + 640 - 170, 110 + 480 - 130))
                pygame.draw.rect(screen, COLOR_NEON_PINK, (50 + 640 - 171, 110 + 480 - 131, 162, 122), 2)
                
                mask_lbl = font.render("COLOR MASK", True, COLOR_NEON_PINK)
                screen.blit(mask_lbl, (50 + 640 - 170, 110 + 480 - 150))
        else:
            # Camera loading placeholder
            loading_surf = font.render("INITIALIZING WEBCAM FEED...", True, COLOR_NEON_PINK)
            screen.blit(loading_surf, (50 + 320 - loading_surf.get_width()//2, 110 + 240 - 10))
            
        # 3. RENDER CONTROLS PANEL (RIGHT COLUMN)
        # Title of right panel
        panel_title = title_font.render("SETTINGS", True, COLOR_NEON_PINK)
        screen.blit(panel_title, (self.panel_x, 30))
        
        # A. Webcam Index control
        cam_lbl = font.render("Webcam Device Index:", True, COLOR_WHITE)
        screen.blit(cam_lbl, (self.panel_x, 97))
        
        # Decrement Button
        pygame.draw.rect(screen, (50, 45, 75), self.btn_cam_prev, border_radius=4)
        prev_txt = font.render("<", True, COLOR_WHITE)
        screen.blit(prev_txt, (self.btn_cam_prev.centerx - prev_txt.get_width()//2, self.btn_cam_prev.centery - prev_txt.get_height()//2))
        
        # Display Current Index
        idx_txt = font.render(str(self.webcam_index), True, COLOR_NEON_BLUE)
        screen.blit(idx_txt, (self.panel_x + 95, 97))
        
        # Increment Button
        pygame.draw.rect(screen, (50, 45, 75), self.btn_cam_next, border_radius=4)
        next_txt = font.render(">", True, COLOR_WHITE)
        screen.blit(next_txt, (self.btn_cam_next.centerx - next_txt.get_width()//2, self.btn_cam_next.centery - next_txt.get_height()//2))
        
        # B. Tracking Mode control
        pygame.draw.rect(screen, (50, 45, 75), self.btn_mode_toggle, border_radius=4)
        mode_txt = font.render(f"Mode: {self.tracking_mode.upper()}", True, COLOR_NEON_BLUE)
        screen.blit(mode_txt, (self.btn_mode_toggle.centerx - mode_txt.get_width()//2, self.btn_mode_toggle.centery - mode_txt.get_height()//2))
        
        # C. Render HSV Sliders (Only if Mode is Color)
        if self.tracking_mode == "color":
            for slider in self.sliders:
                slider.draw(screen, font)
        elif self.tracking_mode == "hand":
            # Draw Hand tracking prompt description
            hand_desc_box = pygame.Rect(self.panel_x, 220, self.slider_w, 240)
            pygame.draw.rect(screen, (30, 25, 50), hand_desc_box, border_radius=8)
            pygame.draw.rect(screen, COLOR_NEON_BLUE, hand_desc_box, 1, border_radius=8)
            
            prompt_y = 240
            prompts = [
                "HAND TRACKING MODE (DEFAULT)",
                "",
                "1. Face the webcam and stand clear.",
                "2. Hold your hand up and point with your",
                "   index finger towards the screen.",
                "3. A green skeleton will track your hand.",
                "4. Move your hand to position the blade.",
                "5. Swing your hand quickly to slice fruits!",
                "   (No phone or marker needed)"
            ]
            for prompt_line in prompts:
                color = COLOR_NEON_BLUE if "HAND" in prompt_line else COLOR_WHITE
                p_surf = font.render(prompt_line, True, color)
                screen.blit(p_surf, (self.panel_x + 15, prompt_y))
                prompt_y += 22
        else:
            # Draw ArUco marker prompt description
            aruco_desc_box = pygame.Rect(self.panel_x, 220, self.slider_w, 240)
            pygame.draw.rect(screen, (30, 25, 50), aruco_desc_box, border_radius=8)
            pygame.draw.rect(screen, COLOR_NEON_BLUE, aruco_desc_box, 1, border_radius=8)
            
            prompt_y = 240
            prompts = [
                "ARUCO TRACKING (RECOMMENDED)",
                "",
                "1. Open the file 'aruco_marker.png' inside",
                "   your game workspace folder.",
                "2. Send it to your smartphone and display it",
                "   full-screen on your phone's display.",
                "3. Hold your phone in front of the camera.",
                "4. The phone center and tilt angle will be",
                "   detected instantly with minimal latency."
            ]
            for prompt_line in prompts:
                color = COLOR_NEON_BLUE if "ARUCO" in prompt_line else COLOR_WHITE
                p_surf = font.render(prompt_line, True, color)
                screen.blit(p_surf, (self.panel_x + 15, prompt_y))
                prompt_y += 22
                
        # D. Diagnostics / Quality indicators
        diag_y = 480 if self.tracking_mode == "color" else 480
        pygame.draw.line(screen, (60, 60, 90), (self.panel_x, diag_y), (self.panel_x + self.slider_w, diag_y), 1)
        
        track = self.tracker.get_tracking_data()
        det_status = "DETECTED" if track["is_detected"] else "NOT DETECTED"
        det_color = COLOR_NEON_GREEN if track["is_detected"] else COLOR_NEON_PINK
        
        status_lbl = font.render("Tracking Quality Monitor:", True, COLOR_WHITE)
        screen.blit(status_lbl, (self.panel_x, diag_y + 15))
        
        q_lbl = font.render(f"Status: {det_status}", True, det_color)
        screen.blit(q_lbl, (self.panel_x, diag_y + 40))
        
        if track["is_detected"]:
            pos_lbl = font.render(f"Coordinates: X={int(track['pos'][0])}, Y={int(track['pos'][1])}, Z={int(track['depth'])}", True, COLOR_WHITE)
            screen.blit(pos_lbl, (self.panel_x, diag_y + 65))
            
            spd_lbl = font.render(f"Swing Speed: {track['speed']:.1f} pix/fr", True, COLOR_NEON_BLUE)
            screen.blit(spd_lbl, (self.panel_x, diag_y + 90))
        else:
            p_hint = font.render("Bring marker or colored object into webcam frame", True, (160, 160, 160))
            screen.blit(p_hint, (self.panel_x, diag_y + 65))
            
        # 4. ACTION BUTTONS (BOTTOM RIGHT)
        # Save Settings button
        pygame.draw.rect(screen, (30, 120, 60), self.btn_save, border_radius=6)
        save_txt = font.render("SAVE SETTINGS", True, COLOR_WHITE)
        screen.blit(save_txt, (self.btn_save.centerx - save_txt.get_width()//2, self.btn_save.centery - save_txt.get_height()//2))
        
        # Back button
        pygame.draw.rect(screen, (150, 30, 60), self.btn_back, border_radius=6)
        back_txt = font.render("BACK TO MENU", True, COLOR_WHITE)
        screen.blit(back_txt, (self.btn_back.centerx - back_txt.get_width()//2, self.btn_back.centery - back_txt.get_height()//2))
        
        # Show bottom status message
        if self.status_timer > 0:
            status_surf = font.render(self.status_msg, True, self.status_color)
            screen.blit(status_surf, (50, 620))
