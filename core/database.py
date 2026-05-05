import sqlite3
from datetime import datetime
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "omi_history.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transcripts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            speaker TEXT,
            text TEXT
        )
    ''')
    conn.commit()
    conn.close()

def add_transcript(speaker, text):
    if not text.strip():
        return
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO transcripts (speaker, text) VALUES (?, ?)', (speaker, text))
    conn.commit()
    conn.close()

def query_transcripts(limit=50, offset=0):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT timestamp, speaker, text FROM transcripts ORDER BY timestamp DESC LIMIT ? OFFSET ?', (limit, offset))
    rows = cursor.fetchall()
    conn.close()
    return rows

def search_transcripts(query):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT timestamp, speaker, text FROM transcripts WHERE text LIKE ? ORDER BY timestamp DESC', ('%' + query + '%',))
    rows = cursor.fetchall()
    conn.close()
    return rows

init_db()
