import sqlite3

def setup_database():
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    # Crea la tabella se non esiste
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER,
            link_fansale TEXT,
            concert_date TEXT,
            artist_name TEXT,
            PRIMARY KEY(user_id, link_fansale, concert_date)
        )
    ''')
    conn.commit()
    conn.close()

def update_user_data(user_id, artist_name, link_fansale, concert_date):
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    c.execute('''
        INSERT OR IGNORE INTO users (user_id, artist_name, link_fansale, concert_date) 
        VALUES (?, ?, ?, ?)
    ''', (user_id, artist_name, link_fansale, concert_date))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    c.execute('SELECT user_id, artist_name, link_fansale, concert_date FROM users')
    users = c.fetchall()
    conn.close()
    return users

def get_user_trackers(user_id):
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    c.execute('SELECT artist_name, link_fansale, concert_date FROM users WHERE user_id = ?', (user_id,))
    trackers = c.fetchall()
    conn.close()
    return trackers

def remove_tracker(user_id, link_fansale, concert_date):
    conn = sqlite3.connect('user_data.db')
    c = conn.cursor()
    c.execute('''
        DELETE FROM users 
        WHERE user_id = ? AND link_fansale = ? AND concert_date = ?
    ''', (user_id, link_fansale, concert_date))
    conn.commit()
    conn.close()
