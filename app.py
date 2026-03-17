import sqlite3
from flask import Flask

app = Flask(__name__)

DB_FILE = "v3_plus.db"


def init_db():
    db = sqlite3.connect(DB_FILE)
    cur = db.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        chat_id INTEGER PRIMARY KEY,
        name TEXT,
        username TEXT,
        last_seen TEXT,
        blocked INTEGER DEFAULT 0,
        favorite INTEGER DEFAULT 0,
        note TEXT DEFAULT ''
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    db.commit()
    db.close()


def get_stats():
    db = sqlite3.connect(DB_FILE)
    cur = db.cursor()

    cur.execute("SELECT COUNT(*) FROM users")
    total_users = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM users WHERE blocked=1")
    blocked_users = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM users WHERE favorite=1")
    favorite_users = cur.fetchone()[0]

    db.close()
    return total_users, blocked_users, favorite_users


def get_users():
    db = sqlite3.connect(DB_FILE)
    cur = db.cursor()

    cur.execute("""
    SELECT chat_id, name, username, last_seen, blocked, favorite, note
    FROM users
    ORDER BY last_seen DESC
    LIMIT 50
    """)

    rows = cur.fetchall()
    db.close()
    return rows


@app.route("/")
def home():
    total_users, blocked_users, favorite_users = get_stats()
    users = get_users()

    html = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <title>Панель управления ботом</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background: #f4f4f4;
                padding: 20px;
            }}
            .card {{
                background: white;
                border-radius: 12px;
                padding: 20px;
                margin-bottom: 20px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.08);
            }}
            h1 {{
                margin-top: 0;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                background: white;
            }}
            th, td {{
                border: 1px solid #ddd;
                padding: 10px;
                text-align: left;
            }}
            th {{
                background: #222;
                color: white;
            }}
            .yes {{
                color: red;
                font-weight: bold;
            }}
            .fav {{
                color: green;
                font-weight: bold;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>Панель управления ботом</h1>
            <p><b>Всего пользователей:</b> {total_users}</p>
            <p><b>Заблокировано:</b> {blocked_users}</p>
            <p><b>Избранных:</b> {favorite_users}</p>
        </div>

        <div class="card">
            <h2>Последние пользователи</h2>
            <table>
                <tr>
                    <th>Chat ID</th>
                    <th>Имя</th>
                    <th>Username</th>
                    <th>Последний визит</th>
                    <th>Бан</th>
                    <th>Избранное</th>
                    <th>Заметка</th>
                </tr>
    """

    for chat_id, name, username, last_seen, blocked, favorite, note in users:
        username_text = f"@{username}" if username else "без username"
        blocked_text = "Да" if blocked else "Нет"
        favorite_text = "Да" if favorite else "Нет"

        html += f"""
                <tr>
                    <td>{chat_id}</td>
                    <td>{name}</td>
                    <td>{username_text}</td>
                    <td>{last_seen}</td>
                    <td class="yes">{blocked_text if blocked else 'Нет'}</td>
                    <td class="fav">{favorite_text if favorite else 'Нет'}</td>
                    <td>{note if note else ''}</td>
                </tr>
        """

    html += """
            </table>
        </div>
    </body>
    </html>
    """
    return html


if __name__ == "__main__":
     init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)