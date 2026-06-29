# Fruit Cutter 3D

An interactive 3D arcade fruit-cutting game in Python using Pygame and OpenCV. Slice fruits directly with your hands in front of the camera or using your smartphone as a virtual neon laser sword!

---

## 🌟 Key Features

* **👐 Hand Gesture Tracking (Default)**: Employs **MediaPipe Tasks HandLandmarker** to track the player's hand skeleton in real-time. The laser blade attaches directly to your index finger tip. Z-depth is estimated via hand scaling, allowing true 3D spatial coordinates.
* **📱 Smartphone Sword Tracking (ArUco)**: Displays a custom ArUco marker (`aruco_marker.png`) on your phone to track position, depth, and tilt angle with high responsiveness.
* **🟢 Colored Marker Tracking (HSV Fallback)**: Segments objects based on customized HSV colors (e.g. neon green objects) using OpenCV contours.
* **⚔️ Swept-Area Slicing Physics**: Solves the "bullet-through-paper" collision skip bug. Slicing checks verify if fruits intersect a 5-line swept quadrangle bounding the previous and current frame positions, guaranteeing 100% slice reliability during rapid swings.
* **📈 Float-Trajectory Projection**: Gravity (deceleration) and upward velocities are balanced to push fruits into high, floating arcs on a scrolling pseudo-3D neon perspective grid.
* **⚡ Slow-Motion Combo Mode**: Cutting 3 or more fruits in a single swing triggers a dramatic slow-motion time dilation, giving players visual feedback and time to plan slices.
* **💥 Bomb Hazard & Screen Shake**: Slicing a bomb triggers an explosion sound, violent screen shake offsets, and dense particle sprays leading to an immediate Game Over.
* **🔊 Procedural Sound Synthesizer**: Generates 16-bit sound waves dynamically using NumPy (slice sweeps, explosion rumbles, menu clicks, life losses, and combo chimes) so the game runs without needing external audio asset files.
* **📐 Interactive Calibration Wizard**: Switch tracking modes, cycle webcam indexes, view live feed overlays, and drag HSV color sliders with a custom GUI.
* **🏆 Leaderboard Records**: Stores top 5 high scores with name entries inside a local JSON file.

---

## 🛠️ Installation & Setup

### 1. Install Dependencies
Run the following pip command in your shell to download the required packages:
```bash
pip install pygame-ce opencv-python numpy mediapipe
```
*(Note: `pygame-ce` or Pygame Community Edition is recommended for compatibility).*

### 2. Launch the Game
Run the entry program:
```bash
python main.py
```

### 3. Controller Setup
* **For Hand Mode (Default)**: Stand about 1.0 - 1.5m away from the webcam. Raise your hand and point with your index finger. A green skeleton will lock onto your hand, and the neon blade will attach to your finger tip.
* **For Phone Mode**: Go to the project directory, locate the auto-generated `aruco_marker.png`, transfer it to your phone, and display it full-screen in front of your webcam.

---

## 🎮 Game Controls

### Main Menu
* **W / S or Up / Down Arrows**: Navigate menu options.
* **Space or Enter**: Select option.
* **D Key**: Toggle Difficulty (`EASY` / `MEDIUM` / `HARD`).

### Gameplay
* **Gesture swing**: Swipe your index finger (or smartphone) quickly through fruits. Ignored if movement speed is below the threshold.
* **Pause / Exit**: Click the window exit button to return to the main menu.

### Leaderboard Entry
* **Alphanumeric Keys & Backspace**: Enter name.
* **Enter**: Confirm and save score to the local scoreboard.

---

## 📁 Project Architecture

The codebase is split into modular components:

* `main.py`: Houses the central game loop, UI state machine, swept collision checks, and game rules.
* `camera_tracking.py`: Runs the background frame capture, EMA filters, dead-reckoning extrapolation, and MediaPipe hand landmarker processing.
* `game_objects.py`: Defines the visual entities (Fruit, SlicedFruit, Bomb, Particle, BladeTrail) and projects 3D spatial vectors to 2D coordinates.
* `calibration.py`: Renders the split-screen calibration menu, custom Sliders, camera selectors, and HSV color mask overlays.
* `assets_manager.py`: Synthesizes retro PCM audio waves dynamically and slices Pygame surfaces programmatically along arbitrary angles.
* `high_scores.py`: Manages the high-score leaderboard file parser.
* `config.py`: Stores window dimensions, game rules, gravity, and difficulty speed configurations.
