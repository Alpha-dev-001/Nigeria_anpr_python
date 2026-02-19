"""
Nigerian ANPR - CLEAN VERSION
 Save with or without state (no blocking)
 Auto-zoom for state detection
 Smart backfill: new state fills all matching prefixes in DB
 Persistent counters
 State caching
"""

import cv2
import easyocr
import sqlite3
from datetime import datetime
from ultralytics import YOLO
import numpy as np
import re
import time
from collections import defaultdict
import config


class ANPR_Final:
    def __init__(self, camera_url):
        self.camera_url = camera_url

        print("Initializing ANPR System...")
        self.init_database()
        self.load_counters()
        self.load_vehicle_states()

        print("Loading YOLOv8...")
        self.detector = YOLO('yolov8n.pt')

        print("Loading EasyOCR...")
        self.reader = easyocr.Reader(['en'], gpu=False)

        self.STATE_NAMES = {
            'LAG': 'LAGOS',     'ABJ': 'ABUJA',      'KAN': 'KANO',
            'RIV': 'RIVERS',    'KAD': 'KADUNA',      'OYO': 'OYO',
            'OGU': 'OGUN',      'IMO': 'IMO',         'DLT': 'DELTA',
            'BEN': 'BENUE',     'KAT': 'KATSINA',     'ANA': 'ANAMBRA',
            'BOR': 'BORNO',     'AKW': 'AKWA IBOM',   'BAU': 'BAUCHI',
            'JIG': 'JIGAWA',    'ENU': 'ENUGU',       'ZAM': 'ZAMFARA',
            'SOK': 'SOKOTO',    'KEB': 'KEBBI',        'OND': 'ONDO',
            'ADA': 'ADAMAWA',   'CRS': 'CROSS RIVER', 'ABI': 'ABIA',
            'EDO': 'EDO',       'KWA': 'KWARA',        'NIG': 'NIGER',
            'GMB': 'GOMBE',     'OSU': 'OSUN',         'TAR': 'TARABA',
            'YOB': 'YOBE',      'EKI': 'EKITI',        'KOG': 'KOGI',
            'PLT': 'PLATEAU',   'BYS': 'BAYELSA',      'EBO': 'EBONYI',
            'NAS': 'NASSARAWA'
        }

        self.STATE_FUZZY = {
            'LAGOS': 'LAG',  'LAGO': 'LAG',   'LACOS': 'LAG',  'LACO': 'LAG',
            'ULIE': 'LAG',   'EXCELLENCE': 'LAG', 'CENTRE': 'LAG',
            'ABUJA': 'ABJ',  'FCT': 'ABJ',
            'KANO': 'KAN',   'RIVERS': 'RIV',  'RIVER': 'RIV',
            'KADUNA': 'KAD', 'OYO': 'OYO',
            'OGUN': 'OGU',   'GATEWAY': 'OGU',
            'DELTA': 'DLT',  'BENUE': 'BEN',
            'KATSINA': 'KAT','ANAMBRA': 'ANA',
            'BORNO': 'BOR',  'BORNU': 'BOR',
            'AKWA': 'AKW',   'AKWAIBOM': 'AKW',
            'BAUCHI': 'BAU', 'JIGAWA': 'JIG',
            'ENUGU': 'ENU',  'ZAMFARA': 'ZAM',
            'SOKOTO': 'SOK', 'KEBBI': 'KEB',
            'ADAMAWA': 'ADA','CROSS': 'CRS',
            'PLATEAU': 'PLT','BAYELSA': 'BYS',
            'EBONYI': 'EBO', 'NASSARAWA': 'NAS',
            'NASARAWA': 'NAS','TARABA': 'TAR',
            'KWARA': 'KWA',  'NIGER': 'NIG',
            'GOMBE': 'GMB',  'OSUN': 'OSU',
            'YOBE': 'YOB',   'EKITI': 'EKI',
            'KOGI': 'KOG',   'ABIA': 'ABI',
            'EDO': 'EDO',
        }

        self.plate_history = defaultdict(list)
        self.recent_detections = {}
        self._last_directions = {}
        self._plate_regions = {}
        self._plate_state_cache = {}
        self.cooldown_seconds = config.COOLDOWN_SECONDS
        self._last_detected_info = None
        self.running = False
        self.frame_count = 0

        self.load_state_cache()

        print(f" Ready! (Total: {self.total_detections} | IN: {self.total_entries} | OUT: {self.total_exits})\n")

    # ─────────────────────────────────────────────────────────
    # DATABASE
    # ─────────────────────────────────────────────────────────
    def init_database(self):
        conn = sqlite3.connect(config.DB_PATH)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS plate_detections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate_number TEXT NOT NULL,
            state_name TEXT,
            timestamp TEXT NOT NULL,
            direction TEXT NOT NULL,
            confidence REAL)''')
        c.execute('''CREATE TABLE IF NOT EXISTS vehicle_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate_number TEXT NOT NULL,
            state_name TEXT,
            first_seen TEXT NOT NULL,
            last_seen TEXT,
            entry_count INTEGER DEFAULT 0,
            exit_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'OUTSIDE',
            last_direction TEXT)''')
        conn.commit()
        conn.close()
        print(f"Database: {config.DB_PATH}")

    def load_counters(self):
        conn = sqlite3.connect(config.DB_PATH)
        c = conn.cursor()
        try:
            c.execute('SELECT COUNT(*) FROM plate_detections')
            self.total_detections = c.fetchone()[0]
            c.execute('SELECT SUM(entry_count), SUM(exit_count) FROM vehicle_tracking')
            r = c.fetchone()
            self.total_entries = r[0] or 0
            self.total_exits   = r[1] or 0
        except:
            self.total_detections = self.total_entries = self.total_exits = 0
        conn.close()

    def load_vehicle_states(self):
        conn = sqlite3.connect(config.DB_PATH)
        c = conn.cursor()
        try:
            c.execute('SELECT plate_number, entry_count, exit_count, last_direction FROM vehicle_tracking')
            for plate, entries, exits, last_dir in c.fetchall():
                if entries + exits > 0:
                    self.plate_history[plate] = list(range(entries + exits))
                if last_dir:
                    self._last_directions[plate] = last_dir
        except:
            pass
        conn.close()

    def load_state_cache(self):
        conn = sqlite3.connect(config.DB_PATH)
        c = conn.cursor()
        try:
            c.execute('SELECT plate_number, state_name FROM vehicle_tracking WHERE state_name IS NOT NULL')
            rows = c.fetchall()
            for plate, state in rows:
                self._plate_state_cache[plate] = state
            if rows:
                print(f"Loaded {len(rows)} plate-state mappings")
        except:
            pass
        conn.close()

    def backfill_state_by_prefix(self, prefix, state_name):
        """Fill NULL states for all plates sharing the same 3-letter prefix."""
        conn = sqlite3.connect(config.DB_PATH)
        c = conn.cursor()
        try:
            c.execute('''UPDATE vehicle_tracking SET state_name=?
                         WHERE state_name IS NULL AND plate_number LIKE ?''',
                      (state_name, f"{prefix}-%"))
            vt = c.rowcount
            c.execute('''UPDATE plate_detections SET state_name=?
                         WHERE state_name IS NULL AND plate_number LIKE ?''',
                      (state_name, f"{prefix}-%"))
            pd = c.rowcount
            conn.commit()
            if vt or pd:
                print(f"[BACKFILL] {prefix}-* → {state_name} ({vt} vehicles, {pd} detections)")
            # Update in-memory cache too
            for p in list(self._plate_state_cache):
                if p.startswith(f"{prefix}-") and not self._plate_state_cache.get(p):
                    self._plate_state_cache[p] = state_name
        except Exception as e:
            print(f"[BACKFILL ERROR] {e}")
        finally:
            conn.close()

    def log_detection(self, plate, state_name, direction, confidence):
        timestamp = datetime.now().isoformat()
        conn = sqlite3.connect(config.DB_PATH)
        c = conn.cursor()

        c.execute('INSERT INTO plate_detections (plate_number,state_name,timestamp,direction,confidence) VALUES (?,?,?,?,?)',
                  (plate, state_name, timestamp, direction, confidence))

        c.execute('SELECT id,entry_count,exit_count FROM vehicle_tracking WHERE plate_number=?', (plate,))
        vehicle = c.fetchone()

        if vehicle:
            vid, entries, exits = vehicle
            if direction == "IN":
                entries += 1; status = "INSIDE"
            else:
                exits += 1;   status = "OUTSIDE"
            c.execute('''UPDATE vehicle_tracking
                         SET last_seen=?,entry_count=?,exit_count=?,status=?,last_direction=?,state_name=?
                         WHERE id=?''',
                      (timestamp, entries, exits, status, direction, state_name, vid))
        else:
            entries = 1 if direction == "IN" else 0
            exits   = 0 if direction == "IN" else 1
            status  = "INSIDE" if direction == "IN" else "OUTSIDE"
            c.execute('''INSERT INTO vehicle_tracking
                         (plate_number,state_name,first_seen,last_seen,entry_count,exit_count,status,last_direction)
                         VALUES (?,?,?,?,?,?,?,?)''',
                      (plate, state_name, timestamp, timestamp, entries, exits, status, direction))

        conn.commit()
        conn.close()

        self._last_directions[plate] = direction
        if state_name:
            self._plate_state_cache[plate] = state_name

        self.total_detections += 1
        if direction == "IN":  self.total_entries += 1
        else:                  self.total_exits   += 1

        state_display = f" ({state_name})" if state_name else ""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {direction}: {plate}{state_display} - {confidence:.0%}")

    # ─────────────────────────────────────────────────────────
    # DETECTION & OCR
    # ─────────────────────────────────────────────────────────
    def is_plate_clear(self, img):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return cv2.Laplacian(gray, cv2.CV_64F).var() > config.BLUR_THRESHOLD

    def is_plate_stable(self, bbox):
        x, y, w, h = bbox
        key = (round(x/30)*30, round(y/30)*30, round(w/30)*30, round(h/30)*30)
        now = time.time()
        if key in self._plate_regions:
            t0, n = self._plate_regions[key]
            self._plate_regions[key] = (t0, n + 1)
            return (now - t0) >= config.STABILIZATION_TIME and n >= config.STABILIZATION_FRAMES
        self._plate_regions[key] = (now, 1)
        return False

    def detect_plates(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        adaptive = cv2.adaptiveThreshold(blur, 255,
                                         cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                         cv2.THRESH_BINARY, 11, 2)
        contours, _ = cv2.findContours(adaptive, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:10]

        plates = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            ar   = w / float(h) if h > 0 else 0
            area = w * h
            if (config.PLATE_ASPECT_RATIO_MIN <= ar   <= config.PLATE_ASPECT_RATIO_MAX and
                config.PLATE_WIDTH_MIN        <  w    <  frame.shape[1] * config.PLATE_WIDTH_MAX_RATIO and
                config.PLATE_HEIGHT_MIN       <  h    <  frame.shape[0] * config.PLATE_HEIGHT_MAX_RATIO and
                config.PLATE_AREA_MIN         <  area <  config.PLATE_AREA_MAX):
                plates.append((x, y, w, h))
        return plates[:config.MAX_PLATES_PER_FRAME]

    def clean_plate(self, text):
        t = re.sub(r'[^A-Z0-9]', '', text.upper())

        if len(t) == 8:
            p1, p2, p3 = t[:3], t[3:6], t[6:8]
            for s, d in [('0','O'),('1','I'),('5','S'),('8','B'),('6','G')]:
                p1 = p1.replace(s, d); p3 = p3.replace(s, d)
            for s, d in [('O','0'),('I','1'),('S','5'),('B','8'),('G','6'),
                         ('Z','2'),('T','7'),('L','1')]:
                p2 = p2.replace(s, d)
            t = p1 + p2 + p3

        if len(t) == 8 and t[:3].isalpha() and t[3:6].isdigit() and t[6:8].isalpha():
            return f"{t[:3]}-{t[3:6]}-{t[6:8]}"
        m = re.search(r'([A-Z]{3})(\d{3})([A-Z]{2})', t)
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None

    def extract_state(self, text):
        if not text:
            return None, None
        t = text.upper()
        t = t.replace('0','O').replace('1','I').replace('5','S').replace('8','B').replace('6','G')
        t = re.sub(r'[^A-Z\s]', '', t)
        tn = t.replace(' ', '')
        for pattern, code in self.STATE_FUZZY.items():
            if pattern in tn:
                return code, self.STATE_NAMES[code]
        for name in self.STATE_NAMES.values():
            nc = name.replace(' ', '')
            if len(nc) >= 4 and nc[:4] in tn:
                for c, n in self.STATE_NAMES.items():
                    if n == name:
                        return c, name
        return None, None

    def ocr_region(self, img):
        """Multi-pass OCR, returns list of (area, text, conf) deduplicated."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        _, thresh_clahe = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        _, thresh_plain = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                         cv2.THRESH_BINARY, 11, 2)
        raw = []
        for processed in [thresh_clahe, cv2.bitwise_not(thresh_plain), adaptive]:
            for (bbox, text, conf) in self.reader.readtext(processed, detail=1, paragraph=False):
                pts = np.array(bbox)
                w = np.linalg.norm(pts[1] - pts[0])
                h = np.linalg.norm(pts[2] - pts[1])
                raw.append((w * h, text, conf))

        seen, unique = set(), []
        for item in sorted(raw, reverse=True, key=lambda x: x[0]):
            key = item[1].strip().upper()
            if key not in seen:
                seen.add(key)
                unique.append(item)
        return unique

    def perform_ocr(self, plate_img):
        try:
            regions = self.ocr_region(plate_img)
            if not regions:
                return None, 0, None, None

            # Best valid plate number
            plate_number, confidence, plate_idx = None, 0, -1
            for i, (area, text, conf) in enumerate(regions):
                candidate = self.clean_plate(text)
                if candidate:
                    plate_number, confidence, plate_idx = candidate, conf, i
                    if config.DEBUG_MODE:
                        print(f"[OCR] '{text}' → {plate_number} ({conf:.0%})")
                    break

            # State from remaining regions
            state_code = state_name = None
            other = " ".join(t for i, (_, t, _) in enumerate(regions) if i != plate_idx)
            state_code, state_name = self.extract_state(other)

            # Auto-zoom if plate found but state missing
            if plate_number and not state_name and config.ENABLE_AUTO_ZOOM:
                h, w = plate_img.shape[:2]
                top = plate_img[0:int(h * config.AUTO_ZOOM_TOP_PERCENT), :]
                if top.size > 0:
                    zoomed = cv2.resize(top, None,
                                        fx=config.AUTO_ZOOM_SCALE,
                                        fy=config.AUTO_ZOOM_SCALE,
                                        interpolation=cv2.INTER_CUBIC)
                    zoom_text = " ".join(t for (_, t, _) in self.ocr_region(zoomed))
                    if zoom_text.strip():
                        state_code, state_name = self.extract_state(zoom_text)
                        if state_code and config.DEBUG_MODE:
                            print(f"[ZOOM]  {state_name}")

            return plate_number, confidence, state_code, state_name

        except Exception as e:
            if config.DEBUG_MODE:
                print(f"[OCR-ERROR] {e}")
            return None, 0, None, None

    def determine_direction(self, plate):
        last = self._last_directions.get(plate)
        return "OUT" if last == "IN" else "IN"

    # ─────────────────────────────────────────────────────────
    # MAIN LOOP
    # ─────────────────────────────────────────────────────────
    def process_frame(self, frame):
        self.frame_count += 1
        now = time.time()

        if self.frame_count % 30 == 0:
            self._plate_regions = {k: v for k, v in self._plate_regions.items()
                                   if now - v[0] < 5}

        for (x, y, w, h) in self.detect_plates(frame):
            plate_img = frame[y:y+h, x:x+w]

            if not self.is_plate_clear(plate_img):
                cv2.rectangle(frame, (x,y), (x+w,y+h), config.COLOR_BLURRY, 1)
                cv2.putText(frame, "BLURRY", (x,y-5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, config.COLOR_BLURRY, 1)
                continue

            if not self.is_plate_stable((x,y,w,h)):
                cv2.rectangle(frame, (x,y), (x+w,y+h), config.COLOR_STABILIZING, 1)
                cv2.putText(frame, "STABILIZING", (x,y-5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, config.COLOR_STABILIZING, 1)
                continue

            plate_number, confidence, state_code, state_name = self.perform_ocr(plate_img)

            # ── Resolve state ─────────────────────────────────
            if plate_number and not state_name:
                prefix = plate_number.split('-')[0]

                # 1. Exact plate cache
                if plate_number in self._plate_state_cache:
                    state_name = self._plate_state_cache[plate_number]
                    if config.DEBUG_MODE:
                        print(f"[CACHE] {plate_number} → {state_name}")

                # 2. Prefix cache (e.g. all APP-*)
                if not state_name:
                    for p, s in self._plate_state_cache.items():
                        if p.startswith(f"{prefix}-") and s:
                            state_name = s
                            if config.DEBUG_MODE:
                                print(f"[PREFIX-CACHE] {prefix}-* → {state_name}")
                            break

            # Cache & backfill if new state discovered
            if plate_number and state_name:
                prefix = plate_number.split('-')[0]
                if self._plate_state_cache.get(plate_number) != state_name:
                    self._plate_state_cache[plate_number] = state_name
                    self.backfill_state_by_prefix(prefix, state_name)

            # ── Save ─────────────────────────────────────────
            if plate_number and confidence > config.OCR_CONFIDENCE_THRESHOLD:
                last_seen = self.recent_detections.get(plate_number, 0)
                if now - last_seen > self.cooldown_seconds:
                    self.recent_detections[plate_number] = now
                    direction = self.determine_direction(plate_number)
                    self.log_detection(plate_number, state_name, direction, confidence)

                    self._last_detected_info = {
                        'plate': plate_number, 'state': state_name,
                        'direction': direction, 'time': now
                    }
                    color = config.COLOR_IN if direction == "IN" else config.COLOR_OUT
                    cv2.rectangle(frame, (x,y), (x+w,y+h), color, 3)
                    label = f"{plate_number}{' ('+state_name+')' if state_name else ''} - {direction}"
                    cv2.putText(frame, label, (x,y-10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                else:
                    rem = int(self.cooldown_seconds - (now - last_seen))
                    cv2.rectangle(frame, (x,y), (x+w,y+h), config.COLOR_COOLDOWN, 2)
                    cv2.putText(frame, f"{plate_number} - COOLDOWN {rem}s", (x,y-10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, config.COLOR_COOLDOWN, 2)
            elif plate_number:
                cv2.rectangle(frame, (x,y), (x+w,y+h), config.COLOR_READING, 2)
                cv2.putText(frame, "LOW CONFIDENCE", (x,y-5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, config.COLOR_READING, 1)

        # ── HUD ──────────────────────────────────────────────
        if self._last_detected_info:
            elapsed = now - self._last_detected_info['time']
            if elapsed < self.cooldown_seconds:
                rem   = int(self.cooldown_seconds - elapsed)
                plate = self._last_detected_info['plate']
                state = self._last_detected_info.get('state', '')
                dirn  = self._last_detected_info['direction']
                txt   = f"Last: {plate}{' ('+state+')' if state else ''} - {dirn} | {rem}s"
                cv2.putText(frame, txt, (10,60),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, config.COLOR_COOLDOWN, 2)

        cv2.putText(frame,
                    f"Total:{self.total_detections} IN:{self.total_entries} OUT:{self.total_exits}",
                    (10,30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)
        return frame

    def start(self):
        print("Connecting to camera...")
        cap = cv2.VideoCapture(self.camera_url)
        if not cap.isOpened():
            print(" Camera error!")
            return

        print(" Connected! Press 'q' to quit\n")
        self.running = True
        try:
            while self.running:
                ret, frame = cap.read()
                if not ret:
                    break
                cv2.imshow('Nigerian ANPR', self.process_frame(frame))
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
        except KeyboardInterrupt:
            print("\nStopping...")
        finally:
            cap.release()
            cv2.destroyAllWindows()
            print(f"\n Stopped | Total:{self.total_detections} IN:{self.total_entries} OUT:{self.total_exits}")


if __name__ == "__main__":
    print("=" * 60)
    print("NIGERIAN ANPR SYSTEM")
    print("=" * 60)
    ANPR_Final(camera_url=0).start()  # You can use "rtsp://username:password@ip_address:port/stream2" for IP cameras