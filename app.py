import os
import re
import json
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

UPSTASH_URL = os.environ.get("UPSTASH_REDIS_REST_URL")
UPSTASH_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN")

def redis_set(key, value):
    headers = {"Authorization": f"Bearer {UPSTASH_TOKEN}"}
    data = json.dumps(value)
    requests.get(f"{UPSTASH_URL}/set/{key}/{requests.utils.quote(data)}", headers=headers)

def parse_daily_wash(text):
    data = {}
    total = re.search(r'(\d+)\s*Total Routes', text, re.IGNORECASE)
    if total: data['total_routes'] = total.group(1)
    reductions = re.search(r'(\d+)\s*Same day reductions?', text, re.IGNORECASE)
    if reductions: data['reductions'] = reductions.group(1)
    c1 = re.search(r'(\d+)\s*Cycle 1', text, re.IGNORECASE)
    if c1: data['cycle_1'] = c1.group(1)
    c0 = re.search(r'(\d+)\s*Cycle 0', text, re.IGNORECASE)
    if c0: data['cycle_0'] = c0.group(1)
    same_day = re.search(r'(\d+)\s*Same Day Routes', text, re.IGNORECASE)
    if same_day: data['same_day'] = same_day.group(1)
    flex = re.search(r'(\d+)\s*FLEX', text, re.IGNORECASE)
    if flex: data['flex'] = flex.group(1)
    c1_waves = re.findall(r'Wave (\d+)\s*First van in[:\-\s]*([\d:]+).*?Last van out[:\-\s]*([\d:]+)', text, re.IGNORECASE)
    if c1_waves:
        data['c1_waves'] = [{'wave': w[0], 'first_in': w[1], 'last_out': w[2]} for w in c1_waves]
    splits = re.search(r'(\d+)\s*Split[s]?[\s\-]*(.*?)(?:\n|$)', text, re.IGNORECASE)
    if splits:
        data['splits'] = splits.group(1)
        vans = splits.group(2).strip()
        if vans: data['split_vans'] = vans
    dropped = re.search(r'(\d+)\s*dropped[\s\-]*(.*?)(?:\n|$)', text, re.IGNORECASE)
    if dropped:
        data['dropped'] = dropped.group(1)
        van = dropped.group(2).strip()
        if van: data['dropped_vans'] = van
    extras = re.search(r'(\d+)\s*extras?', text, re.IGNORECASE)
    if extras: data['extras'] = extras.group(1)
    sweeper = re.search(r'(\d+)\s*sweeper', text, re.IGNORECASE)
    if sweeper: data['sweeper'] = sweeper.group(1)
    terminations = re.search(r'(\d+)\s*Terminations?', text, re.IGNORECASE)
    if terminations: data['terminations'] = terminations.group(1)
    training = re.search(r'(\d+)\s*Training', text, re.IGNORECASE)
    if training: data['training'] = training.group(1)
    return data

def parse_evening_wash(text):
    data = {}
    routes = re.search(r'(\d+)\s*Total Routes', text)
    if routes: data['total_routes'] = routes.group(1)
    dropped = re.search(r'(\d+)\s*dropped', text)
    if dropped: data['dropped'] = dropped.group(1)
    rescues = re.search(r'Rescues?:(.*?)(?:\n\n|\Z)', text, re.DOTALL)
    if rescues: data['rescues'] = rescues.group(1).strip()
    terminations = re.search(r'(\d+)\s*Terminations', text)
    if terminations: data['terminations'] = terminations.group(1)
    splits = re.search(r'(\d+)\s*Split', text)
    if splits: data['splits'] = splits.group(1)
    training = re.search(r'(\d+)\s*Training', text)
    if training: data['training'] = training.group(1)
    highlights = re.search(r'Highlights?:(.*?)(?:\n\n|\Z)', text, re.DOTALL | re.IGNORECASE)
    if highlights: data['highlights'] = highlights.group(1).strip()
    return data

def parse_capacity(text):
    weeks = []
    current_week = None
    current_cycle = None
    days = []
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
        week_match = re.search(r'week\s*(\d+).*?(cycle\s*\d+)', line, re.IGNORECASE)
        if week_match:
            if current_week and days:
                weeks.append({'week': current_week, 'cycle': current_cycle, 'days': days})
                days = []
            current_week = week_match.group(1)
            current_cycle = week_match.group(2).strip()
            continue
        cycle_match = re.search(r'(cycle\s*\d+)', line, re.IGNORECASE)
        if cycle_match and not week_match:
            if current_week and days:
                weeks.append({'week': current_week, 'cycle': current_cycle, 'days': days})
                days = []
            current_cycle = cycle_match.group(1).strip()
            continue
        day_match = re.search(
            r'(sun|mon|tue|wed|thu|fri|sat)\w*[\s\-:]*(\d+)\s*RT[\s\-]*(\d+)\s*ECP[\s\-]*(\d+)\s*DA',
            line, re.IGNORECASE
        )
        if day_match and current_week:
            days.append({
                'day': day_match.group(1).capitalize(),
                'rt': day_match.group(2),
                'ecp': day_match.group(3),
                'das': day_match.group(4)
            })
    if current_week and days:
        weeks.append({'week': current_week, 'cycle': current_cycle, 'days': days})
    return weeks

def parse_fleet_report(text):
    data = {'raw': text, 'date': text.split('\n')[0]}
    van_ids = re.findall(r'\b([A-Z]{1,3}\d+)\b', text)
    data['vans_mentioned'] = list(set(van_ids))
    grounded = re.findall(r'([A-Z]{1,3}\d+).*?ground', text, re.IGNORECASE)
    data['grounded'] = list(set(grounded))
    ungrounded = re.findall(r'([A-Z]{1,3}\d+).*?unground', text, re.IGNORECASE)
    data['ungrounded'] = list(set(ungrounded))
    afs = re.findall(r'AFS.*?([A-Z]{1,3}\d+)', text, re.IGNORECASE)
    data['afs_mentions'] = list(set(afs))
    pave_setup = re.search(r'PAVE Setup:\s*(\d+)', text, re.IGNORECASE)
    if pave_setup: data['pave_total'] = pave_setup.group(1)
    pave_done = re.findall(r'PAVE Complete:\s*([A-Z]{1,3}\d+)', text, re.IGNORECASE)
    data['pave_completed'] = pave_done
    repairs = re.findall(r'([A-Z]{1,3}\d+).*?repair', text, re.IGNORECASE)
    data['repairs'] = list(set(repairs))
    return data

@app.route('/slack/events', methods=['POST'])
def slack_events():
    data = request.json
    if data.get('type') == 'url_verification':
        return jsonify({'challenge': data['challenge']})
    if 'event' in data:
        event = data['event']
        if event.get('type') == 'message' and not event.get('bot_id'):
            text = event.get('text', '')
print(f"Full event: {json.dumps(event)[:500]}")
            if 'Daily Wash Report' in text:
                parsed = parse_daily_wash(text)
                redis_set('daily_wash_latest', parsed)
                print(f"Daily wash saved: {parsed}")
            elif 'Evening Wash Report' in text:
                parsed = parse_evening_wash(text)
                redis_set('evening_wash_latest', parsed)
                print(f"Evening wash saved: {parsed}")
            elif 'Capacity Planning Report' in text:
                parsed = parse_capacity(text)
                redis_set('capacity_latest', parsed)
                print(f"Capacity saved: {parsed}")
            elif 'Fleet Report' in text:
                parsed = parse_fleet_report(text)
                redis_set('fleet_latest', parsed)
                print(f"Fleet saved: {parsed}")
            elif 'Incident Report' in text:
                redis_set('incident_latest', {'raw': text, 'date': text.split('\n')[0]})
                print(f"Incident saved")
            elif 'Write-Up Report' in text:
                redis_set('writeup_latest', {'raw': text, 'date': text.split('\n')[0]})
                print(f"Write-up saved")
            elif 'Training Report' in text:
                redis_set('training_latest', {'raw': text, 'date': text.split('\n')[0]})
                print(f"Training saved")
            elif 'Payroll Correction' in text:
                redis_set('payroll_correction_latest', {'raw': text, 'date': text.split('\n')[0]})
                print(f"Payroll correction saved")
            elif 'Expense Report' in text:
                redis_set('expense_latest', {'raw': text, 'date': text.split('\n')[0]})
                print(f"Expense saved")
            elif 'Hiring Update' in text:
                redis_set('hiring_latest', {'raw': text, 'date': text.split('\n')[0]})
                print(f"Hiring update saved")
            elif 'Termination Report' in text:
                redis_set('termination_latest', {'raw': text, 'date': text.split('\n')[0]})
                print(f"Termination saved")
    return jsonify({'status': 'ok'})

@app.route('/data/<key>', methods=['GET'])
def get_data(key):
    headers = {"Authorization": f"Bearer {UPSTASH_TOKEN}"}
    response = requests.get(f"{UPSTASH_URL}/get/{key}", headers=headers)
    result = response.json()
    return jsonify(result)

@app.route('/', methods=['GET'])
def home():
    return 'Riptide Command Bot is running.'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
