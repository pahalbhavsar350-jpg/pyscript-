import os, sqlite3, secrets
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-change-this")
DB_URL = os.environ.get("DATABASE_URL", "")

def db():
    if DB_URL:
        import psycopg
        return psycopg.connect(DB_URL)
    c = sqlite3.connect("tuition.db")
    c.row_factory = sqlite3.Row
    return c

def init_db():
    if DB_URL:
        conn = db(); cur = conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS students(id SERIAL PRIMARY KEY, code TEXT UNIQUE NOT NULL, name TEXT NOT NULL, parent_name TEXT, phone TEXT, email TEXT, class_name TEXT, subject TEXT, batch TEXT, joining_date TEXT, monthly_fee REAL DEFAULT 0, discount REAL DEFAULT 0, status TEXT DEFAULT 'Active', address TEXT, notes TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS payments(id SERIAL PRIMARY KEY, student_id INTEGER REFERENCES students(id) ON DELETE CASCADE, month TEXT NOT NULL, amount REAL NOT NULL, paid_on TEXT, method TEXT, receipt_no TEXT UNIQUE, notes TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS expenses(id SERIAL PRIMARY KEY, title TEXT NOT NULL, amount REAL NOT NULL, expense_date TEXT, category TEXT, notes TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        conn.commit(); cur.close(); conn.close()
    else:
        conn=db(); conn.executescript("""CREATE TABLE IF NOT EXISTS students(id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE NOT NULL, name TEXT NOT NULL, parent_name TEXT, phone TEXT, email TEXT, class_name TEXT, subject TEXT, batch TEXT, joining_date TEXT, monthly_fee REAL DEFAULT 0, discount REAL DEFAULT 0, status TEXT DEFAULT 'Active', address TEXT, notes TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP); CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY AUTOINCREMENT, student_id INTEGER REFERENCES students(id) ON DELETE CASCADE, month TEXT NOT NULL, amount REAL NOT NULL, paid_on TEXT, method TEXT, receipt_no TEXT UNIQUE, notes TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP); CREATE TABLE IF NOT EXISTS expenses(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, amount REAL NOT NULL, expense_date TEXT, category TEXT, notes TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);"""); conn.commit(); conn.close()

def rows(sql,args=()):
    conn=db(); cur=conn.cursor(); cur.execute(sql,args); out=cur.fetchall(); cur.close(); conn.close(); return out
def one(sql,args=()):
    r=rows(sql,args); return r[0] if r else None
def execute(sql,args=()):
    conn=db(); cur=conn.cursor(); cur.execute(sql,args); conn.commit(); rid=getattr(cur,'lastrowid',None); cur.close(); conn.close(); return rid

@app.get('/health')
def health(): return jsonify(ok=True)
@app.route('/',methods=['GET','POST'])
def login():
    if request.method=='POST':
        if request.form.get('username')=='admin' and request.form.get('password')==os.environ.get('ADMIN_PASSWORD','admin123'):
            session['admin']=True; return redirect(url_for('dashboard'))
        flash('Invalid login')
    return render_template('login.html')
@app.get('/logout')
def logout(): session.clear(); return redirect(url_for('login'))
def auth(): return session.get('admin')
@app.get('/dashboard')
def dashboard():
    if not auth(): return redirect(url_for('login'))
    students=one('SELECT COUNT(*) FROM students')[0]; payments=one('SELECT COALESCE(SUM(amount),0) FROM payments')[0]; expenses=one('SELECT COALESCE(SUM(amount),0) FROM expenses')[0]
    return render_template('dashboard.html',students=students,payments=payments,expenses=expenses)
@app.route('/students',methods=['GET','POST'])
def students_page():
    if not auth(): return redirect(url_for('login'))
    if request.method=='POST':
        try:
            execute('INSERT INTO students(code,name,parent_name,phone,email,class_name,subject,batch,joining_date,monthly_fee,discount,status,address,notes) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',tuple(request.form.get(k,'') for k in ['code','name','parent_name','phone','email','class_name','subject','batch','joining_date','monthly_fee','discount','status','address','notes'])); flash('Student added.')
        except Exception as e: flash('Could not add student: '+str(e))
        return redirect(url_for('students_page'))
    return render_template('students.html',students=rows('SELECT * FROM students ORDER BY id DESC'))
@app.get('/ledger')
def ledger():
    if not auth(): return redirect(url_for('login'))
    month=datetime.now().strftime('%Y-%m'); data=rows('SELECT s.id,s.code,s.name,s.monthly_fee,s.discount,s.status,COALESCE((SELECT SUM(p.amount) FROM payments p WHERE p.student_id=s.id AND p.month=?),0) paid FROM students s ORDER BY s.name',(month,)); return render_template('ledger.html',students=data,month=month)
@app.route('/payment',methods=['GET','POST'])
def payment():
    if not auth(): return redirect(url_for('login'))
    if request.method=='POST':
        execute('INSERT INTO payments(student_id,month,amount,paid_on,method,receipt_no,notes) VALUES(?,?,?,?,?,?,?)',(request.form['student_id'],request.form['month'],request.form['amount'],request.form['paid_on'],request.form['method'],'RC-'+datetime.now().strftime('%Y%m%d%H%M%S%f'),request.form.get('notes',''))); flash('Payment recorded.'); return redirect(url_for('ledger'))
    return render_template('payment.html',students=rows("SELECT id,name,code FROM students WHERE status='Active' ORDER BY name"))
@app.route('/expenses',methods=['GET','POST'])
def expenses():
    if not auth(): return redirect(url_for('login'))
    if request.method=='POST': execute('INSERT INTO expenses(title,amount,expense_date,category,notes) VALUES(?,?,?,?,?)',tuple(request.form.get(k,'') for k in ['title','amount','expense_date','category','notes'])); flash('Expense recorded.'); return redirect(url_for('expenses'))
    return render_template('expenses.html',expenses=rows('SELECT * FROM expenses ORDER BY id DESC'))
@app.get('/receipts')
def receipts():
    if not auth(): return redirect(url_for('login'))
    return render_template('receipts.html',payments=rows('SELECT p.*,s.name,s.code FROM payments p JOIN students s ON s.id=p.student_id ORDER BY p.id DESC LIMIT 100'))
if __name__=='__main__':
    init_db(); app.run(host='0.0.0.0',port=int(os.environ.get('PORT',5000)))
