"""
Nigerian ANPR System - Web Interface
Simple Flask-based dashboard for monitoring detections
"""

from flask import Flask, render_template, jsonify, Response, send_from_directory
import sqlite3
from datetime import datetime, timedelta
import json
import threading
import cv2
import os

app = Flask(__name__)

# Global ANPR instance
anpr_instance = None
anpr_thread = None

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect('anpr_database.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    """Main dashboard page"""
    # Read and serve the dashboard.html file from the same directory
    try:
        with open('dashboard.html', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return """
        <html>
        <body style="font-family: Arial; padding: 40px;">
            <h1>Dashboard not found</h1>
            <p>Please ensure 'dashboard.html' is in the same directory as web_interface.py</p>
            <p>Current directory: {}</p>
        </body>
        </html>
        """.format(os.getcwd()), 404

@app.route('/api/stats')
def get_stats():
    """Get current system statistics"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Overall stats
    cursor.execute('SELECT COUNT(*) as total FROM plate_detections')
    total = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as entries FROM plate_detections WHERE direction = 'IN'")
    entries = cursor.fetchone()['entries']
    
    cursor.execute("SELECT COUNT(*) as exits FROM plate_detections WHERE direction = 'OUT'")
    exits = cursor.fetchone()['exits']
    
    cursor.execute('SELECT COUNT(DISTINCT plate_number) as unique_count FROM vehicle_tracking')
    unique = cursor.fetchone()['unique_count']
    
    # Currently inside
    cursor.execute("SELECT COUNT(*) as inside FROM vehicle_tracking WHERE status = 'INSIDE'")
    inside = cursor.fetchone()['inside']
    
    conn.close()
    
    return jsonify({
        'total_detections': total,
        'total_entries': entries,
        'total_exits': exits,
        'unique_vehicles': unique,
        'currently_inside': inside
    })

@app.route('/api/recent')
def get_recent():
    """Get recent detections"""
    limit = 20
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT plate_number, timestamp, direction, confidence, state_name
        FROM plate_detections
        ORDER BY timestamp DESC
        LIMIT ?
    ''', (limit,))
    
    rows = cursor.fetchall()
    conn.close()
    
    detections = []
    for row in rows:
        detections.append({
            'plate_number': row['plate_number'],
            'timestamp': row['timestamp'],
            'direction': row['direction'],
            'confidence': row['confidence'] or 0,
            'state_name': row['state_name'] if 'state_name' in row.keys() else None
        })
    
    return jsonify(detections)

@app.route('/api/vehicles')
def get_vehicles():
    """Get all tracked vehicles"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if state_name column exists in vehicle_tracking
    cursor.execute("PRAGMA table_info(vehicle_tracking)")
    columns = [col['name'] for col in cursor.fetchall()]
    
    if 'state_name' in columns:
        cursor.execute('''
            SELECT plate_number, first_seen, last_seen, entry_count, exit_count, status, state_name
            FROM vehicle_tracking
            ORDER BY last_seen DESC
        ''')
    else:
        cursor.execute('''
            SELECT plate_number, first_seen, last_seen, entry_count, exit_count, status
            FROM vehicle_tracking
            ORDER BY last_seen DESC
        ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    vehicles = []
    for row in rows:
        vehicle_data = {
            'plate_number': row['plate_number'],
            'first_seen': row['first_seen'],
            'last_seen': row['last_seen'],
            'entry_count': row['entry_count'],
            'exit_count': row['exit_count'],
            'status': row['status']
        }
        
        if 'state_name' in row.keys():
            vehicle_data['state_name'] = row['state_name']
        else:
            vehicle_data['state_name'] = None
            
        vehicles.append(vehicle_data)
    
    return jsonify(vehicles)

@app.route('/api/vehicle/<plate>')
def get_vehicle_details(plate):
    """Get detailed analytics for a specific vehicle"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get vehicle basic info
    cursor.execute('''
        SELECT * FROM vehicle_tracking
        WHERE plate_number = ?
    ''', (plate,))
    vehicle = cursor.fetchone()
    
    if not vehicle:
        conn.close()
        return jsonify({'error': 'Vehicle not found'}), 404
    
    # Get all detections for this vehicle
    cursor.execute('''
        SELECT timestamp, direction
        FROM plate_detections
        WHERE plate_number = ?
        ORDER BY timestamp ASC
    ''', (plate,))
    detections = cursor.fetchall()
    
    # Calculate statistics
    total_time_inside = 0
    time_inside_today = 0
    longest_stay_duration = 0
    longest_stay_date = None
    stay_durations = []
    current_entry_time = None
    
    today = datetime.now().date()
    
    for detection in detections:
        timestamp = datetime.fromisoformat(detection['timestamp'])
        direction = detection['direction']
        
        if direction == 'IN':
            current_entry_time = timestamp
        elif direction == 'OUT' and current_entry_time:
            duration_seconds = (timestamp - current_entry_time).total_seconds()
            total_time_inside += duration_seconds
            stay_durations.append(duration_seconds)
            
            # Check if this is the longest stay
            if duration_seconds > longest_stay_duration:
                longest_stay_duration = duration_seconds
                longest_stay_date = current_entry_time.strftime('%b %d, %Y')
            
            # Add to today's time if applicable
            if current_entry_time.date() == today or timestamp.date() == today:
                if current_entry_time.date() == today and timestamp.date() == today:
                    time_inside_today += duration_seconds
                elif current_entry_time.date() == today:
                    # Entered today, hasn't left yet (shouldn't be OUT)
                    time_inside_today += duration_seconds
            
            current_entry_time = None
    
    # If vehicle is currently inside, calculate time so far
    if current_entry_time:
        now = datetime.now()
        duration_seconds = (now - current_entry_time).total_seconds()
        
        if current_entry_time.date() == today:
            time_inside_today += duration_seconds
        
        # Don't add to total_time_inside yet as they're still inside
    
    # Calculate average stay duration
    average_stay_duration = sum(stay_durations) / len(stay_durations) if stay_durations else 0
    
    # Get current status info
    current_status = vehicle['status']
    last_seen = datetime.fromisoformat(vehicle['last_seen'])
    status_time = f"Since {last_seen.strftime('%b %d, %I:%M %p')}"
    
    # Get recent activity (last 20 detections)
    cursor.execute('''
        SELECT timestamp, direction
        FROM plate_detections
        WHERE plate_number = ?
        ORDER BY timestamp DESC
        LIMIT 20
    ''', (plate,))
    recent = cursor.fetchall()
    
    # Calculate durations for recent activity
    recent_activity = []
    recent_detections_list = list(reversed(recent))  # Reverse to process chronologically
    
    for i, det in enumerate(recent_detections_list):
        activity_item = {
            'timestamp': det['timestamp'],
            'direction': det['direction'],
            'duration': None
        }
        
        # If this is an OUT detection, find the corresponding IN and calculate duration
        if det['direction'] == 'OUT' and i > 0:
            for j in range(i-1, -1, -1):
                if recent_detections_list[j]['direction'] == 'IN':
                    entry_time = datetime.fromisoformat(recent_detections_list[j]['timestamp'])
                    exit_time = datetime.fromisoformat(det['timestamp'])
                    activity_item['duration'] = int((exit_time - entry_time).total_seconds())
                    break
        
        recent_activity.append(activity_item)
    
    recent_activity.reverse()  # Reverse back to show most recent first
    
    conn.close()
    
    return jsonify({
        'plate_number': plate,
        'state_name': vehicle['state_name'] if 'state_name' in vehicle.keys() else None,
        'total_time_inside': int(total_time_inside),
        'time_inside_today': int(time_inside_today),
        'total_visits': vehicle['entry_count'],
        'current_status': current_status,
        'status_time': status_time,
        'longest_stay_duration': int(longest_stay_duration),
        'longest_stay_date': longest_stay_date,
        'average_stay_duration': int(average_stay_duration),
        'recent_activity': recent_activity
    })

@app.route('/api/states/today')
def get_states_today():
    """Get today's state distribution statistics"""
    today = datetime.now().date()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if state_name column exists
    cursor.execute("PRAGMA table_info(plate_detections)")
    columns = [col['name'] for col in cursor.fetchall()]
    
    if 'state_name' not in columns:
        conn.close()
        return jsonify([])
    
    cursor.execute('''
        SELECT 
            state_name,
            COUNT(*) as count
        FROM plate_detections
        WHERE DATE(timestamp) = ?
        AND state_name IS NOT NULL
        GROUP BY state_name
        ORDER BY count DESC
    ''', (today,))
    
    rows = cursor.fetchall()
    conn.close()
    
    states = []
    for row in rows:
        states.append({
            'state_name': row['state_name'],
            'count': row['count']
        })
    
    return jsonify(states)

@app.route('/api/today')
def get_today_stats():
    """Get today's statistics"""
    today = datetime.now().date()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            strftime('%H', timestamp) as hour,
            COUNT(*) as count,
            SUM(CASE WHEN direction = 'IN' THEN 1 ELSE 0 END) as entries,
            SUM(CASE WHEN direction = 'OUT' THEN 1 ELSE 0 END) as exits
        FROM plate_detections
        WHERE DATE(timestamp) = ?
        GROUP BY hour
        ORDER BY hour
    ''', (today,))
    
    rows = cursor.fetchall()
    conn.close()
    
    hourly_data = []
    for row in rows:
        hourly_data.append({
            'hour': int(row['hour']),
            'total': row['count'],
            'entries': row['entries'],
            'exits': row['exits']
        })
    
    return jsonify(hourly_data)

@app.route('/api/search/<plate>')
def search_plate(plate):
    """Search for specific plate number"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get vehicle info
    cursor.execute('''
        SELECT * FROM vehicle_tracking
        WHERE plate_number LIKE ?
    ''', (f'%{plate}%',))
    
    vehicle = cursor.fetchone()
    
    # Get detection history
    cursor.execute('''
        SELECT timestamp, direction, confidence
        FROM plate_detections
        WHERE plate_number LIKE ?
        ORDER BY timestamp DESC
    ''', (f'%{plate}%',))
    
    detections = cursor.fetchall()
    conn.close()
    
    result = {
        'vehicle': dict(vehicle) if vehicle else None,
        'history': [dict(d) for d in detections]
    }
    
    return jsonify(result)

@app.route('/api/system/status')
def system_status():
    """Get system status"""
    global anpr_instance
    
    if anpr_instance and hasattr(anpr_instance, 'running') and anpr_instance.running:
        stats = anpr_instance.get_stats() if hasattr(anpr_instance, 'get_stats') else {}
        status = 'running'
    else:
        stats = {}
        status = 'stopped'
    
    return jsonify({
        'status': status,
        'stats': stats
    })

if __name__ == '__main__':
    print("Starting ANPR Web Interface...")
    print("Access dashboard at: http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)