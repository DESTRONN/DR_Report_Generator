from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import os
import re
from collections import defaultdict
from datetime import datetime
import json
from werkzeug.utils import secure_filename
import pprint

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# Configuration
UPLOAD_FOLDER = 'uploads'
LOG_FOLDER = 'logs'
ALLOWED_EXTENSIONS = {'log'}

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(LOG_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def calculate_duration_seconds(start_time: str, end_time: str) -> int:
    fmt = "%Y-%m-%d %H:%M:%S"
    start = datetime.strptime(start_time, fmt)
    end = datetime.strptime(end_time, fmt)
    return int((end - start).total_seconds())

def parse_log_file(filepath):
    """Parse the log file and extract all relevant information"""
    m_d = {"steps": [], "time_taken": [], "approved_by": []}
    other_errors = {}
    d = defaultdict(dict)
    DR_START_TIME = ""
    DR_END_TIME = ""
    DR_TOTAL_TIME = 0
    user_response_time = 0
    step_number = ""
    
    # Read log file
    with open(filepath, 'r', encoding='utf-8') as f:
        log_content = f.read()
    
    # All the patterns to match log entries
    step_pattern = re.compile(r"(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}) - (.+)")
    DR_start_pattern = re.compile(r"=== Disaster Recovery Execution Started at: (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) ===")
    DR_end_pattern = re.compile(r"=== Disaster Recovery Execution Completed at: (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) ===")
    user_response_pattern = re.compile(r"⏳ User took (\d+) seconds to respond to Step (\d+(?:\.\d+)?)")
    step_approval_pattern = re.compile(r"✅ Step (\d+(?:\.\d+)?) approved by (.+)")
    main_step_pattern = re.compile(r"STEP (\d+(?:\.\d+)?): (.+)")
    success_pattern = re.compile(r"✅ SUCCESS: (.+) \(Start: (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}), End: (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\)")
    failure_pattern = re.compile(r"ERROR - ❌ FAILURE: (.+) \(Start: (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}), End: (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\)")
    step_completed_pattern = re.compile(r"⏱️ STEP (\d+(?:\.\d+)?) Completed in (\d+) seconds")
    error_pattern = re.compile(r"ERROR - ❌ (.+)")
    
    # Parse log file
    for line in log_content.splitlines():
        match = step_pattern.match(line)
        if match:
            date, time, details = match.groups()

            DR_start_pattern_match = DR_start_pattern.search(details)
            if DR_start_pattern_match:
                DR_START_TIME = DR_start_pattern_match.group(1)
                continue

            DR_end_pattern_match = DR_end_pattern.search(details)
            if DR_end_pattern_match:
                DR_END_TIME = DR_end_pattern_match.group(1)
                DR_TOTAL_TIME = calculate_duration_seconds(DR_START_TIME, DR_END_TIME)
                continue

            user_response_match = user_response_pattern.search(details)
            if user_response_match:
                seconds, step_num = user_response_match.groups()
                user_response_time += int(seconds)
                step_number = step_num
                continue

            step_approval_match = step_approval_pattern.search(details)
            if step_approval_match:
                step_num, approved_by = step_approval_match.groups()
                m_d["approved_by"].append(approved_by)
                continue

            main_step_match = main_step_pattern.search(details)
            if main_step_match:
                step_num, step_desc = main_step_match.groups()
                m_d["steps"].append(step_desc)
                continue

            success_match = success_pattern.search(details)
            if success_match:
                step_name, start_time, end_time = success_match.groups()
                step_time = calculate_duration_seconds(start_time, end_time)
                d[step_number][step_name] = {
                    "status": "success",
                    "start_time": start_time,
                    "end_time": end_time,
                    "time_taken": step_time
                }
                continue

            failure_match = failure_pattern.search(details)
            if failure_match:
                step_name, start_time, end_time = failure_match.groups()
                step_time = calculate_duration_seconds(start_time, end_time)
                d[step_number][step_name] = {
                    "status": "failure",
                    "start_time": start_time,
                    "end_time": end_time,
                    "time_taken": step_time
                }
                continue

            error_pattern_match = error_pattern.search(details)
            if error_pattern_match:
                error_message = error_pattern_match.group(1)
                if step_number not in other_errors:
                    other_errors[step_number] = []
                other_errors[step_number].append(error_message)
                continue

            step_completed_match = step_completed_pattern.search(details)
            if step_completed_match:
                step_num, seconds = step_completed_match.groups()
                m_d["time_taken"].append(int(seconds))
                continue
    
    pprint.pprint(d)
    return {
        'steps_data': m_d,
        'step_details': dict(d),
        'other_errors': other_errors,
        'dr_start_time': DR_START_TIME,
        'dr_end_time': DR_END_TIME,
        'dr_total_time': DR_TOTAL_TIME,
        'user_response_time': user_response_time
    }


@app.route('/')
def index():
    # Get list of log files from the logs folder
    log_files = []
    if os.path.exists(LOG_FOLDER):
        log_files = [f for f in os.listdir(LOG_FOLDER) if f.endswith('.log')]
    
    return render_template('index.html', log_files=log_files)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file selected'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        # Store file info in session
        session['uploaded_file'] = filename
        session['file_path'] = filepath
        
        return jsonify({'success': True, 'filename': filename})
    
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/process', methods=['POST'])
def process_log():
    data = request.json
    rto = data.get('rto', 0)
    rpo = data.get('rpo', 0)
    selected_log = data.get('selected_log', '')
    use_uploaded = data.get('use_uploaded', False)
    
    # Store RTO and RPO in session
    session['rto'] = rto
    session['rpo'] = rpo
    
    # Determine which file to process
    if use_uploaded and 'file_path' in session:
        filepath = session['file_path']
        log_name = session['uploaded_file']
    elif selected_log:
        filepath = os.path.join(LOG_FOLDER, selected_log)
        log_name = selected_log
    else:
        return jsonify({'error': 'No file selected'}), 400
    
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404
    
    try:
        # Parse the log file
        parsed_data = parse_log_file(filepath)
        
        # Store parsed data in session
        session['parsed_data'] = parsed_data
        session['log_name'] = log_name
        
        return jsonify({'success': True, 'redirect_url': url_for('results')})
    
    except Exception as e:
        return jsonify({'error': f'Error processing file: {str(e)}'}), 500

@app.route('/results')
def results():
    if 'parsed_data' not in session:
        print('DEBUG: parsed_data missing from session. Session contents:', dict(session))
        return redirect(url_for('index'))

    parsed_data = session['parsed_data']
    log_name = session.get('log_name', 'Unknown')
    rto = session.get('rto', 0)
    rpo = session.get('rpo', 0)

    # Debug output for troubleshooting
    print('DEBUG: Rendering results page')
    print('DEBUG: parsed_data:', parsed_data)
    print('DEBUG: log_name:', log_name)
    print('DEBUG: rto:', rto, 'rpo:', rpo)

    # Check if objectives are met
    dr_total_time = parsed_data.get('dr_total_time', 0)
    rto_met = dr_total_time <= rto if rto else True
    rpo_met = True  # This would need actual RPO calculation based on your business logic

    return render_template('results.html', 
                         parsed_data=parsed_data,
                         log_name=log_name,
                         rto=rto,
                         rpo=rpo,
                         rto_met=rto_met,
                         rpo_met=rpo_met)

@app.route('/step/<step_number>')
def step_detail(step_number):
    if 'parsed_data' not in session:
        return redirect(url_for('index'))
    
    parsed_data = session['parsed_data']
    step_details = parsed_data['step_details'].get(step_number, {})
    step_name = ""
    
    # Get step name from steps list
    try:
        step_index = int(float(step_number)) - 1
        if 0 <= step_index < len(parsed_data['steps_data']['steps']):
            step_name = parsed_data['steps_data']['steps'][step_index]
    except (ValueError, IndexError):
        pass
    
    errors = parsed_data['other_errors'].get(step_number, [])
    
    return render_template('step_detail.html',
                         step_number=step_number,
                         step_name=step_name,
                         step_details=step_details,
                         errors=errors,
                         log_name=session.get('log_name', 'Unknown'))

if __name__ == '__main__':
    app.run(debug=True)