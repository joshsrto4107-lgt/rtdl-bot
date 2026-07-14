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
    return data

def parse_daily_wash(text):
    data = {}
    routes = re.search(r'(\d+)\s*Total Routes', text)
    if routes: data['total_routes'] = routes.group(1)
    sp = re.search(r'(\d+)\s*SP', text)
    if sp: data['sp_routes'] = sp.group(1)
    c0 = re.search(r'(\d+)\s*Cycle 0', text)
    if c0: data['cycle_0'] = c0.group(1)
    splits = re.search(r'(\d+)\s*Split', text)
    if splits: data['splits'] = splits.group(1)
    dropped = re.search(r'(\d+)\s*dropped', text)
    if dropped: data['dropped'] = dropped.group(1)
    return data

def parse_capacity(text):
    weeks = []
    week_blocks = re.findall(r'Week (\d+):.*?(\d+/\d+)\s*-\s*(\d+/\d+)\s*\((Cycle \d+)\)(.*?)(?=Week \d+:|$)', text, re.DOTALL)
    for block in week_blocks:
        week_num, start, end, cycle, content = block
        days = []
        day_matches = re.findall(r'(Sunday|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday)\s*-?\s*(\d+)\s*RT\s*-\s*(\d+)\s*ECP\s*-\s*(\d+)\s*DAs?', content)
        for day in day_matches:
            days.append({'day': day[0], 'rt': day[1], 'ecp': day[2], 'das': day[3]})
        weeks.append({'week': week_num, 'start': start, 'end': end, 'cycle': cycle, 'days': days})
    return weeks

@app.route('/slack/events', methods=['POST'])
def slack_events():
    data = request.json
    if data.get('type') == 'url_verification':
        return jsonify({'challenge': data['challenge']})
    if 'event' in data:
        event = data['event']
        if event.get('type') == 'message' and not event.get('bot_id'):
            text = event.get('text', '')
            channel_name = event.get('channel', '')
            print(f"Message in channel {channel_name}: {text[:100]}")
            if 'Total Routes' in text and 'Fleet Report' in text:
                parsed = parse_evening_wash(text)
                redis_set('evening_wash_latest', parsed)
                print(f"Evening wash saved: {parsed}")
            elif 'Total Routes' in text:
                parsed = parse_daily_wash(text)
                redis_set('daily_wash_latest', parsed)
                print(f"Daily wash saved: {parsed}")
            elif 'Week Capacity Report' in text or ('RT' in text and 'ECP' in text and 'DAs' in text):
                parsed = parse_capacity(text)
                redis_set('capacity_latest', parsed)
                print(f"Capacity saved: {parsed}")
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
