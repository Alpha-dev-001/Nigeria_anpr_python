"""
ANPR System Configuration
Modify these settings to customize behavior :)
Better to save a copy before making changes.
"""

# ============================================================
# DETECTION SETTINGS
# ============================================================
BLUR_THRESHOLD = 50  # Sharpness threshold (higher = stricter)
STABILIZATION_TIME = 0.15  # Seconds to wait before OCR
STABILIZATION_FRAMES = 2  # Minimum frames to see plate
COOLDOWN_SECONDS = 10  # Time before re-detecting same plate

# FALSE POSITIVE FILTERING
ENABLE_STRICT_VALIDATION = True  # Multi-layer validation to reject non-plates
MIN_CONTRAST = 20  # Minimum standard deviation (rejects uniform backgrounds)
MIN_HORIZONTAL_EDGES = 500  # Minimum horizontal edge strength (plates have text lines)
MIN_BRIGHT_RATIO = 0.15  # Minimum % of bright pixels
MAX_BRIGHT_RATIO = 0.9   # Maximum % of bright pixels
MIN_TEXT_COMPONENTS = 3  # Minimum character-like components
MAX_TEXT_COMPONENTS = 20  # Maximum character-like components

# ============================================================
# PLATE DETECTION CRITERIA
# ============================================================
PLATE_ASPECT_RATIO_MIN = 2.0
PLATE_ASPECT_RATIO_MAX = 6.0
PLATE_WIDTH_MIN = 100
PLATE_WIDTH_MAX_RATIO = 0.85  # Percentage of frame width
PLATE_HEIGHT_MIN = 35
PLATE_HEIGHT_MAX_RATIO = 0.5  # Percentage of frame height
PLATE_AREA_MIN = 3000
PLATE_AREA_MAX = 60000
MAX_PLATES_PER_FRAME = 3

# ============================================================
# OCR SETTINGS
# ============================================================
OCR_CONFIDENCE_THRESHOLD = 0.35  # Minimum confidence to accept
STATE_REGION_HEIGHT_RATIO = 0.4  # Top % of plate for state detection
REQUIRE_STATE_FOR_SAVE = True  # If True, only save detections with state

# ============================================================
# STATE DETECTION
# ============================================================
# Separate rectangle detection for state name
STATE_DETECTION_METHOD = "separate_rectangle"  # Options: "ocr_regions", "separate_rectangle", "both"

# AUTO-ZOOM: If plate detected but no state, zoom into top region for better OCR
ENABLE_AUTO_ZOOM = True  # Highly recommended!
AUTO_ZOOM_SCALE = 2.0  # Scale factor for zooming (2.0 = 2x larger)
AUTO_ZOOM_TOP_PERCENT = 0.35  # Top % of plate to zoom into

# For separate rectangle detection
STATE_RECT_ASPECT_RATIO_MIN = 2.0
STATE_RECT_ASPECT_RATIO_MAX = 8.0
STATE_RECT_HEIGHT_MIN = 15
STATE_RECT_HEIGHT_MAX = 50
STATE_RECT_AREA_MIN = 500
STATE_RECT_AREA_MAX = 5000

# ============================================================
# DATABASE SETTINGS
# ============================================================
DB_PATH = "anpr_database.db"
ENABLE_STATE_CACHE = True  # Use cached plate-state mappings
LOAD_COUNTERS_ON_START = True  # Load total counts from database

# ============================================================
# VISUAL SETTINGS
# ============================================================
SHOW_DEBUG_RECTANGLES = True  # Show detection boxes on screen
COLOR_BLURRY = (100, 100, 100)  # Gray
COLOR_STABILIZING = (255, 255, 0)  # Yellow
COLOR_READING = (0, 255, 255)  # Cyan
COLOR_COOLDOWN = (255, 165, 0)  # Orange
COLOR_IN = (0, 255, 0)  # Green
COLOR_OUT = (0, 0, 255)  # Red
COLOR_STATE_BOX = (255, 0, 255)  # Magenta for state rectangles

# ============================================================
# DEBUG SETTINGS
# ============================================================
DEBUG_MODE = True  # Show detailed logs
SAVE_PLATE_IMAGES = False  # Save detected plates to disk
SAVE_PLATES_DIR = "detected_plates"