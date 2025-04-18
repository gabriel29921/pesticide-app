
from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3
from datetime import datetime
from werkzeug.security import check_password_hash

app = Flask(__name__)
app.secret_key = 'secret123'  # cheia sesiunii

admin_username = 'admin'
admin_password_hash = 'scrypt:32768:8:1$qQCEK34sHF527eiy$df6f39edc4893e511f10a7b1d83b04c0ca8e271164c01a3eaf98d824cb3972137d35f5ff32224c00fdf20ecf9e9089af2fd98d405e762865da77dac838c209c7'

def init_db():
    with sqlite3.connect("pesticide.db") as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS pesticide (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nume TEXT,
            substanta_activ TEXT,
            cantitate REAL,
            data_achizitie TEXT,
            data_expirare TEXT
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS iesiri (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_pesticid INTEGER,
            cantitate REAL,
            data_iesire TEXT,
            cultura TEXT,
            FOREIGN KEY (id_pesticid) REFERENCES pesticide(id)
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS intrari (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_pesticid INTEGER,
            cantitate REAL,
            data_intrare TEXT,
            FOREIGN KEY (id_pesticid) REFERENCES pesticide(id)
        )''')

def login_required(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == admin_username and check_password_hash(admin_password_hash, password):
            session['user'] = username
            return redirect('/')
        else:
            error = "Utilizator sau parolă incorecte"
    return render_template("login.html", error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/')
@login_required
def index():
    conn = sqlite3.connect("pesticide.db")
    c = conn.cursor()
    c.execute("SELECT * FROM pesticide")
    pesticide = c.fetchall()
    c.execute("SELECT DISTINCT nume FROM pesticide")
    nume_existente = [row[0] for row in c.fetchall()]
    c.execute("SELECT nume, substanta_activ FROM pesticide")
    rows = c.fetchall()
    pesticide_map = {n: s for n, s in rows}
    azi = datetime.today().date().isoformat()
    conn.close()
    return render_template("index.html", pesticide=pesticide,
                           nume_existente=nume_existente,
                           pesticide_map=pesticide_map,
                           azi=azi)

@app.route('/adauga', methods=['POST'])
@login_required
def adauga():
    nume = request.form['nume'].strip()
    subst = request.form['substanta_activ'].strip()
    cant = float(request.form['cantitate'])
    data_ach = request.form['data_achizitie']
    data_exp = request.form['data_expirare']
    conn = sqlite3.connect("pesticide.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, cantitate FROM pesticide WHERE nume = ? AND substanta_activ = ?", (nume, subst))
    existing = cursor.fetchone()
    if existing:
        id_pest = existing[0]
        cant_noua = existing[1] + cant
        cursor.execute("UPDATE pesticide SET cantitate = ?, data_achizitie = ?, data_expirare = ? WHERE id = ?",
                       (cant_noua, data_ach, data_exp, id_pest))
        cursor.execute("INSERT INTO intrari (id_pesticid, cantitate, data_intrare) VALUES (?, ?, ?)",
                       (id_pest, cant, data_ach))
    else:
        cursor.execute("INSERT INTO pesticide (nume, substanta_activ, cantitate, data_achizitie, data_expirare) VALUES (?, ?, ?, ?, ?)",
                       (nume, subst, cant, data_ach, data_exp))
        id_pest = cursor.lastrowid
        cursor.execute("INSERT INTO intrari (id_pesticid, cantitate, data_intrare) VALUES (?, ?, ?)",
                       (id_pest, cant, data_ach))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/iesire', methods=['POST'])
@login_required
def iesire():
    id_pest = int(request.form['pesticid_id'])
    cant_folosita = float(request.form['cantitate_iesita'])
    data_iesire = request.form['data_iesire']
    cultura = request.form['cultura']
    conn = sqlite3.connect("pesticide.db")
    cursor = conn.cursor()
    cursor.execute("SELECT cantitate FROM pesticide WHERE id = ?", (id_pest,))
    rezultat = cursor.fetchone()
    if rezultat:
        cant_actuala = rezultat[0]
        cant_noua = max(cant_actuala - cant_folosita, 0)
        cursor.execute("UPDATE pesticide SET cantitate = ? WHERE id = ?", (cant_noua, id_pest))
        cursor.execute("INSERT INTO iesiri (id_pesticid, cantitate, data_iesire, cultura) VALUES (?, ?, ?, ?)",
                       (id_pest, cant_folosita, data_iesire, cultura))
        conn.commit()
    conn.close()
    return redirect('/')

@app.route('/sterge/<int:id>')
@login_required
def sterge(id):
    conn = sqlite3.connect("pesticide.db")
    conn.execute("DELETE FROM pesticide WHERE id = ?", (id,))
    conn.execute("DELETE FROM iesiri WHERE id_pesticid = ?", (id,))
    conn.execute("DELETE FROM intrari WHERE id_pesticid = ?", (id,))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/editeaza/<int:id>')
@login_required
def editeaza(id):
    conn = sqlite3.connect("pesticide.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pesticide WHERE id = ?", (id,))
    pesticid = cursor.fetchone()
    cursor.execute("SELECT cantitate, data_intrare FROM intrari WHERE id_pesticid = ?", (id,))
    intrari = [{'data': r[1], 'tip': 'Intrare', 'cantitate': r[0], 'cultura': None} for r in cursor.fetchall()]
    cursor.execute("SELECT cantitate, data_iesire, cultura FROM iesiri WHERE id_pesticid = ?", (id,))
    iesiri = [{'data': r[1], 'tip': 'Ieșire', 'cantitate': r[0], 'cultura': r[2]} for r in cursor.fetchall()]
    jurnal = intrari + iesiri
    jurnal.sort(key=lambda x: x['data'])
    sold = 0
    for r in jurnal:
        if r['tip'] == 'Intrare':
            sold += r['cantitate']
        elif r['tip'] == 'Ieșire':
            sold -= r['cantitate']
        r['sold'] = sold
    conn.close()
    return render_template("edit.html", pesticid=pesticid, jurnal=jurnal)

if __name__ == "__main__":
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
