from flask import Flask, render_template, request, session, redirect, url_for
import mysql.connector
from datetime import date
import json

app = Flask(__name__)
app.secret_key = "medical_glass_secret"

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="deivanai@05", 
        database="medical_expiry"
    )

def get_expiry_status(expiry_date):
    today = date.today()
    days_left = (expiry_date - today).days
    if days_left < 0: return "Expired", "expired"
    elif days_left <= 15: return "Urgent", "expired"
    elif days_left <= 30: return "Expiring Soon", "soon"
    else: return "Safe", "safe"

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form['username']
        pwd = request.form['password']
        if user == "admin" and pwd == "admin123":
            session['user'] = user
            return redirect('/dashboard')
        return render_template('login.html', error="Invalid Credentials")
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session: return redirect('/')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM medicines")
    medicines = cursor.fetchall()
    
    total = len(medicines)
    expiring = 0
    expired = 0
    for m in medicines:
        status, _ = get_expiry_status(m['expiry_date'])
        if status in ["Expired", "Urgent"]: expired += 1
        elif status == "Expiring Soon": expiring += 1
    
    conn.close()
    return render_template('dashboard.html', total=total, expiring=expiring, expired=expired)

@app.route('/add', methods=['GET', 'POST'])
def add_medicine():
    if 'user' not in session: return redirect('/')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        name, batch = request.form['medicine_name'], request.form['batch_no']
        expiry, qty = request.form['expiry_date'], int(request.form['quantity'])
        entry = request.form.get('entry_date', date.today())
        
        cursor.execute("SELECT id FROM medicines WHERE medicine_name=%s AND batch_no=%s", (name, batch))
        existing = cursor.fetchone()
        if existing:
            cursor.execute("UPDATE medicines SET quantity = quantity + %s, entry_date=%s WHERE id=%s", (qty, entry, existing['id']))
        else:
            cursor.execute("INSERT INTO medicines (medicine_name, batch_no, expiry_date, quantity, entry_date) VALUES (%s,%s,%s,%s,%s)", (name, batch, expiry, qty, entry))
        conn.commit()
        return redirect('/add')

    cursor.execute("SELECT * FROM medicines ORDER BY entry_date DESC")
    medicines = cursor.fetchall()
    conn.close() 
    return render_template('add_medicine.html', medicines=medicines)

@app.route('/update-medicine', methods=['POST'])
def update_medicine():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE medicines SET medicine_name=%s, batch_no=%s, expiry_date=%s, quantity=%s, entry_date=%s WHERE id=%s",
                   (request.form['medicine_name'], request.form['batch_no'], request.form['expiry_date'], request.form['quantity'], request.form['entry_date'], request.form['id']))
    conn.commit()
    conn.close()
    return redirect('/add')

@app.route('/delete-medicine/<int:id>')
def delete_medicine(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM medicines WHERE id=%s", (id,))
    conn.commit()
    conn.close()
    return redirect(request.referrer or '/dashboard')

@app.route('/all_medicines')
def all_medicines():
    if 'user' not in session: return redirect('/')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM medicines ORDER BY medicine_name")
    medicines = cursor.fetchall()
    for m in medicines:
        m['status'], m['status_class'] = get_expiry_status(m['expiry_date'])
    conn.close()
    return render_template('all_medicines.html', medicines=medicines)

@app.route('/sales', methods=['GET'])
def sales_page():
    if 'user' not in session: return redirect('/')
    filter_date = request.args.get("filter_date")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    if filter_date:
        cursor.execute("SELECT * FROM sales_medicine WHERE entry_date = %s", (filter_date,))
    else:
        cursor.execute("SELECT * FROM sales_medicine ORDER BY id DESC")
    sales = cursor.fetchall()
    conn.close()
    return render_template("sales.html", sales=sales)

@app.route('/save-sales', methods=['POST'])
def save_sales():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO sales_medicine (medicine_name, batch_no, expiry_date, quantity, status, entry_date) VALUES (%s,%s,%s,%s,%s,%s)",
                   (request.form['medicine_name'], request.form['batch_no'], request.form['expiry_date'], request.form['quantity'], request.form['status'], date.today()))
    conn.commit()
    conn.close()
    return redirect('/sales')

@app.route('/expired')
def expired_medicines():
    if 'user' not in session: return redirect('/')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM medicines")
    all_meds = cursor.fetchall()
    expired_list = [m for m in all_meds if get_expiry_status(m['expiry_date'])[0] in ["Expired", "Urgent"]]
    conn.close()
    return render_template('expired.html', medicines=expired_list)

@app.route('/sales-prediction')
def prediction_page():
    if 'user' not in session: return redirect('/')
    search_query = request.args.get('search')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if search_query:
        cursor.execute("SELECT medicine_name, SUM(quantity) as total_sales FROM sales_medicine WHERE medicine_name LIKE %s AND status = 'Sold' GROUP BY medicine_name", (f"%{search_query}%",))
    else:
        cursor.execute("SELECT medicine_name, SUM(quantity) as total_sales FROM sales_medicine WHERE status = 'Sold' GROUP BY medicine_name ORDER BY total_sales DESC LIMIT 5")

    prediction_data = cursor.fetchall()
    conn.close()

    med_names = [row['medicine_name'] for row in prediction_data]
    med_sales = [int(row['total_sales']) for row in prediction_data]
    
    return render_template('predict.html', 
                           prediction=prediction_data,
                           med_names=json.dumps(med_names), 
                           med_sales=json.dumps(med_sales),
                           total_sales=sum(med_sales),
                           search=search_query)

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)