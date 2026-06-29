# Fruit Cutter 3D

An interactive 3D arcade fruit-cutting game in Python using Pygame and OpenCV. Slice fruits directly with your hands in front of the camera or using your smartphone as a virtual neon laser sword!

---

##  Key Features

* ** Hand Gesture Tracking (Default)**: Employs **MediaPipe Tasks HandLandmarker** to track the player's hand skeleton in real-time. The laser blade attaches directly to your index finger tip. Z-depth is estimated via hand scaling, allowing true 3D spatial coordinates.
* ** Smartphone Sword Tracking (ArUco)**: Displays a custom ArUco marker (`aruco_marker.png`) on your phone to track position, depth, and tilt angle with high responsiveness.
* ** Colored Marker Tracking (HSV Fallback)**: Segments objects based on customized HSV colors (e.g. neon green objects) using OpenCV contours.
* ** Swept-Area Slicing Physics**: Solves the "bullet-through-paper" collision skip bug. Slicing checks verify if fruits intersect a 5-line swept quadrangle bounding the previous and current frame positions, guaranteeing 100% slice reliability during rapid swings.
* ** Float-Trajectory Projection**: Gravity (deceleration) and upward velocities are balanced to push fruits into high, floating arcs on a scrolling pseudo-3D neon perspective grid.
* ** Slow-Motion Combo Mode**: Cutting 3 or more fruits in a single swing triggers a dramatic slow-motion time dilation, giving players visual feedback and time to plan slices.
* ** Bomb Hazard & Screen Shake**: Slicing a bomb triggers an explosion sound, violent screen shake offsets, and dense particle sprays leading to an immediate Game Over.
* ** Procedural Sound Synthesizer**: Generates 16-bit sound waves dynamically using NumPy (slice sweeps, explosion rumbles, menu clicks, life losses, and combo chimes) so the game runs without needing external audio asset files.
* ** Interactive Calibration Wizard**: Switch tracking modes, cycle webcam indexes, view live feed overlays, and drag HSV color sliders with a custom GUI.
* ** Leaderboard Records**: Stores top 5 high scores with name entries inside a local JSON file.

---

