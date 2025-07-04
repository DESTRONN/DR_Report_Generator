# Imports

import os
import re
from collections import defaultdict
from datetime import datetime
import pprint


# All the variables used in the code

m_d = {"steps":[],"time_taken":[],"approved_by":[]}
other_errors = {}
d = defaultdict(dict)
DR_START_TIME = ""
DR_END_TIME = ""
DR_TOTAL_TIME = 0
user_response_time = 0
step_number = ""


# function to evaluate the time taken for each step

def calculate_duration_seconds(start_time: str, end_time: str) -> int:
    fmt = "%Y-%m-%d %H:%M:%S"
    start = datetime.strptime(start_time, fmt)
    end = datetime.strptime(end_time, fmt)
    return int((end - start).total_seconds())

# Directory containing log file
LOG_DIR = "log"


# Read log file

filename = filename = os.listdir(LOG_DIR)[0]
if filename in os.listdir(LOG_DIR) and filename.endswith('.log'):
    with open(os.path.join(LOG_DIR, filename), 'r', encoding='utf-8') as f:
                    log_content = f.read()
else:
    raise FileNotFoundError(f"No log file found in {LOG_DIR} directory or the file is not a .log file.")


# All the pattrens to match log entries

step_pattern = re.compile(r"(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}) - (.+)")
DR_start_pattern = re.compile(r"=== Disaster Recovery Execution Started at: (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) ===")
DR_end_pattern = re.compile(r"=== Disaster Recovery Execution Completed at: (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) ===")
user_respoonse_pattern = re.compile(r"⏳ User took (\d+) seconds to respond to Step (\d+(?:\.\d+)?)")
step_approval_pattern = re.compile(r"✅ Step (\d+(?:\.\d+)?) approved by (.+)")
main_step_pattern = re.compile(r"STEP (\d+(?:\.\d+)?): (.+)")
success_pattern = re.compile(r"✅ SUCCESS: (.+) \(Start: (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}), End: (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\)")
failure_pattern = re.compile(r"ERROR - ❌ FAILURE: (.+) \(Start: (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}), End: (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\)")
step_completed_pattern = re.compile(r"⏱️ STEP (\d+(?:\.\d+)?) Completed in (\d+) seconds")
error_pattern = re.compile(r"ERROR - ❌ (.+)")


# parsing log file

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

        user_response_match = user_respoonse_pattern.search(details)
        if user_response_match:
            seconds, step_num= user_response_match.groups()
            user_response_time += int(seconds)
            step_number = step_num
            print(step_number)
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
    else:
         continue

