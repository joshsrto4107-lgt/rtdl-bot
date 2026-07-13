import os
import re
from flask import Flask, request, jsonify

app = Flask(__name__)

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

@app.route('/slack/events', methods=['POST'])
def slack_events():
    data = request.json
    print(f"Incoming event: {data}")
    if data.get('type') == 'url_verification':
        return jsonify({'challenge': data['challenge']})
    if 'event' in data:
        event = data['event']
        print(f"Event type: {event.get('type')}")
        print(f"Channel: {event.get('channel')}")
        print(f"Text: {event.get('text', '')[:100]}")
        if event.get('type') == 'message' and not event.get('bot_id'):
            text = event.get('text', '')
            parsed = parse_evening_wash(text)
            print(f"Parsed data: {parsed}")
    return jsonify({'status': 'ok'})

@app.route('/', methods=['GET'])
def home():
    return 'Riptide Command Bot is running.'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
