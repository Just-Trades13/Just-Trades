import sqlite3
import logging
import asyncio
import argparse
from flask import Flask, request, jsonify, render_template, redirect, url_for
from datetime import datetime

app = Flask(__name__)
logger = logging.getLogger(__name__)

def init_db():
    conn = sqlite3.connect('trading_webhook.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS webhooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            method TEXT NOT NULL,
            headers TEXT,
            body TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

@app.route('/')
def index():
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/accounts')
def accounts():
    return render_template('account_management.html')

@app.route('/strategies')
def strategies():
    return render_template('strategies.html')

@app.route('/recorders', methods=['GET'])
def recorders_list():
    demo_recorders = [
        {'id': idx, 'name': name}
        for idx, name in enumerate([
            'JADDCAVIX', 'JADDCAVIXES', 'JADES', 'JADIND50', 'JADNQ', 'TEST2'
        ], start=1)
    ]
    return render_template('recorders_list.html', recorders=demo_recorders)

@app.route('/recorders/new')
def recorders_new():
    return render_template('recorders.html')

@app.route('/recorders/<int:recorder_id>')
def recorders_edit(recorder_id):
    return render_template('recorders.html')

@app.route('/traders')
def traders_list():
    demo_traders = [
        {'id': idx, 'name': name}
        for idx, name in enumerate(['JADDCAVIXES', 'JADES', 'JADIND50', 'JADNQ'], start=1)
    ]
    return render_template(
        'traders.html',
        mode='list',
        traders=demo_traders
    )

@app.route('/traders/new')
def traders_new():
    accounts = ['1302271','1367612','1381296','1393592','1492972','1503862','1523896','1536745','DEMO3890283','DEMO4419847-2','DEMO5253444']
    return render_template(
        'traders.html',
        mode='builder',
        header_title='Create New Trader',
        header_cta='Create Trader',
        strategy_names=['JADDCAVIX','JADES','JADIND50','JADNQ'],
        accounts=accounts
    )

@app.route('/traders/<int:trader_id>')
def traders_edit(trader_id):
    accounts = ['1302271','1367612','1381296','1393592','1492972','1503862','1523896','1536745','DEMO3890283','DEMO4419847-2','DEMO5253444']
    return render_template(
        'traders.html',
        mode='builder',
        header_title='Edit Trader',
        header_cta='Update Trader',
        strategy_names=['JADDCAVIX','JADES','JADIND50','JADNQ'],
        accounts=accounts
    )

@app.route('/control-center')
def control_center():
    return render_template('control_center.html')

@app.route('/settings')
def settings():
    return render_template('settings.html')

@app.route('/webhooks', methods=['POST'])
def create_webhook():
    data = request.get_json()
    url = data.get('url')
    method = data.get('method')
    headers = data.get('headers')
    body = data.get('body')

    if not url or not method:
        return jsonify({'error': 'URL and method are required'}), 400

    conn = sqlite3.connect('trading_webhook.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO webhooks (url, method, headers, body)
        VALUES (?, ?, ?, ?)
    ''', (url, method, headers, body))
    conn.commit()
    conn.close()

    return jsonify({'message': 'Webhook created successfully'}), 201

@app.route('/webhooks', methods=['GET'])
def get_webhooks():
    conn = sqlite3.connect('trading_webhook.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM webhooks')
    webhooks = cursor.fetchall()
    conn.close()

    return jsonify([{
        'id': w[0],
        'url': w[1],
        'method': w[2],
        'headers': w[3],
        'body': w[4],
        'created_at': w[5]
    } for w in webhooks])

@app.route('/webhooks/<int:id>', methods=['GET'])
def get_webhook(id):
    conn = sqlite3.connect('trading_webhook.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM webhooks WHERE id = ?', (id,))
    webhook = cursor.fetchone()
    conn.close()

    if webhook:
        return jsonify({
            'id': webhook[0],
            'url': webhook[1],
            'method': webhook[2],
            'headers': webhook[3],
            'body': webhook[4],
            'created_at': webhook[5]
        })
    return jsonify({'error': 'Webhook not found'}), 404

@app.route('/webhooks/<int:id>', methods=['DELETE'])
def delete_webhook(id):
    conn = sqlite3.connect('trading_webhook.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM webhooks WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return '', 204

if __name__ == '__main__':
    # I will add argument parsing to accept a port from the command line
    parser = argparse.ArgumentParser(description='Start the trading webhook server.')
    parser.add_argument('--port', type=int, default=8082, help='Port to run the server on.')
    args = parser.parse_args()

    init_db()
    
    # Use the port from the arguments
    port = args.port
    logger.info(f"Starting ultra-simple trading webhook server on 0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port)
