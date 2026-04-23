import json 
from flask import Flask, render_template, request, session, url_for,redirect
import mysql.connector
from datetime import date, datetime

app = Flask(__name__)
app.secret_key = "medical_secret"


def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="root123",
        database="medical_expiry"
    )


# ✅ SAFE DATE HANDLING (🔥 FIX)
def get_expiry_status(expiry_date):
    today = date.today()

    # convert if string
    if isinstance(expiry_date, str):
        expiry_date = datetime.strptime(expiry_date, "%Y-%m-%d").date()

    days_left = (expiry_date - today).days

    if days_left < 0:
        return "Expired", "expired"
    elif days_left <= 15:
        return "Urgent", "expired"
    elif days_left <= 30:
        return "Expiring Soon", "soon"
    else:
        return "Safe", "safe"


def get_notifications():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM medicines")
    medicines = cursor.fetchall()
    notifications = []
    for m in medicines:
        status, _ = get_expiry_status(m['expiry_date'])
        if status == "Expired":
            notifications.append(f"{m['medicine_name']} is expired ❌")
        elif status == "Urgent":
            notifications.append(f"{m['medicine_name']} expiring soon ⚠️")
        if m['quantity'] <= 5:
            notifications.append(f"{m['medicine_name']} low stock 📉")
    conn.close()
    return notifications   
@app.route('/', methods=['GET', 'POST'])
def login():
    message = request.args.get('message')
    if request.method == 'POST':
        user = request.form.get('username')
        pwd = request.form.get('password')
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s", (user, pwd))
        account = cursor.fetchone()
        conn.close()
        if account:
            session['user'] = account['username']
            return redirect('/dashboard')
        return render_template('login.html', error="Invalid Username or Password!")
    return render_template('login.html', message=message)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user = request.form.get('username')
        pwd = request.form.get('password')
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (user, pwd))
            conn.commit()
            return redirect(url_for('login', message="Account Created! Login now."))
        except:
            return render_template('register.html', error="Username already exists!")
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/forgot', methods=['GET', 'POST'])
def forgot():
    if request.method == 'POST':
        user = request.form.get('username')
        new_pwd = request.form.get('new_password')
        
        # Check if password is not empty
        if not new_pwd:
            return render_template('forgot.html', error="Password cannot be empty!")

        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Update panrom
        cursor.execute("UPDATE users SET password = %s WHERE username = %s", (new_pwd, user))
        conn.commit()
        conn.close()
        
        # url_for ippo work aagum, error varathu
        return redirect(url_for('login', message="Password Reset Success!"))
    return render_template('forgot.html')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM medicines")
    medicines = cursor.fetchall()

    total = len(medicines)
    expiring = 0
    expired = 0

    for m in medicines:
        status, _ = get_expiry_status(m['expiry_date'])

        if status in ["Expired", "Urgent"]:
            expired += 1
        elif status == "Expiring Soon":
            expiring += 1

    conn.close()

    notifications = get_notifications()

    return render_template(
        'dashboard.html',
        total=total,
        expiring=expiring,
        expired=expired,
        notifications=notifications
    )
@app.route('/notifications')
def notifications_page():
    if 'user' not in session: return redirect('/')
    
    # Mark notifications as "seen" so the badge disappears on the dashboard
    session['notifications_seen'] = True
    
    notifications = get_notifications()
    return render_template('notifications.html', notifications=notifications)


@app.route('/add', methods=['GET', 'POST'])
def add_medicine():
    if 'user' not in session:
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True, buffered=True)

    if request.method == 'POST':
        cursor.execute("""
            INSERT INTO medicines 
            (medicine_name, batch_no, entry_date, expiry_date, quantity) 
            VALUES (%s,%s,%s,%s,%s)
        """, (
            request.form['medicine_name'],
            request.form['batch_no'],
            request.form['entry_date'],
            request.form['expiry_date'],
            request.form['quantity']
        ))

        conn.commit()
        return redirect('/add')

    cursor.execute("SELECT * FROM medicines")
    medicines = cursor.fetchall()
    conn.close()

    return render_template(
        'add_medicine.html',
        medicines=medicines,
        notifications=get_notifications()
    )
@app.route('/delete-medicine/<int:id>', methods=['GET', 'POST']) # GET sethachu
def delete_medicine(id):
    if 'user' not in session:
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM medicines WHERE id=%s", (id,))
    conn.commit()
    conn.close()

    # Request vandha athe expiry page-ke thirumba poga ithu correct-u
    return redirect(request.referrer)
   

@app.route('/update-medicine', methods=['POST'])
def update_medicine():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE medicines SET
        medicine_name=%s,
        batch_no=%s,
        entry_date=%s,
        expiry_date=%s,
        quantity=%s
        WHERE id=%s
    """, (
        request.form['medicine_name'],
        request.form['batch_no'],
        request.form['entry_date'],
        request.form['expiry_date'],
        request.form['quantity'],
        request.form['id']
    ))

    conn.commit()
    conn.close()

    return redirect('/add')


@app.route('/all_medicines')
def all_medicines():
    if 'user' not in session:
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM medicines")
    medicines = cursor.fetchall()

    for m in medicines:
        m['status'], m['status_class'] = get_expiry_status(m['expiry_date'])

    conn.close()

    return render_template(
        'all_medicines.html',
        medicines=medicines,
        notifications=get_notifications()
    )
@app.route('/sales')
def sales_page():
    if 'user' not in session:
        return redirect('/')

    filter_date = request.args.get("filter_date")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if filter_date:
        # Neenga save pannum bodhu 'expiry_date' column-la dhaan podreenga
        # Adhanaala inga column name 'expiry_date' nu irukanum
        cursor.execute("SELECT * FROM sales_medicine WHERE expiry_date=%s", (filter_date,))
    else:
        cursor.execute("SELECT * FROM sales_medicine ORDER BY id DESC")

    sales = cursor.fetchall()

    # Notification count kaata indha logic help pannum
    cursor.execute("SELECT * FROM seen_notification")
    notifications = cursor.fetchall()

    conn.close()

    return render_template("sales.html", sales=sales, notifications=notifications)

@app.route('/save-sales', methods=['POST'])
def save_sales():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Form-la irundhu vara 'sales_date'-a database-la 'expiry_date' column-la podurom
    cursor.execute("""
        INSERT INTO sales_medicine 
        (medicine_name, batch_no, expiry_date, quantity, status)
        VALUES (%s,%s,%s,%s,%s)
    """, (
        request.form.get('medicine_name'),
        request.form.get('batch_no'),
        request.form.get('sales_date'), # HTML-la irukura name correct-a irukanum
        request.form.get('quantity'),
        request.form.get('status')
    ))

    conn.commit()
    conn.close()

    return redirect('/sales')

@app.route('/expired')
def expired_medicines():
    if 'user' not in session:
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM medicines")

    expired_list = [
        m for m in cursor.fetchall()
        if get_expiry_status(m['expiry_date'])[0] in ["Expired", "Urgent"]
    ]

    conn.close()

    return render_template(
        'expired.html',
        medicines=expired_list,
        notifications=get_notifications()
    )
@app.route('/prediction')
@app.route('/sales-prediction')   # 🔥 ADD THIS LINE
def sales_prediction():
   
    search_query = request.args.get('search')
    notifications = []  
    if search_query:
        labels = [str(i) for i in range(1, 31)] 
        values = [200, 400, 350, 500, 900, 800]
    else:
        labels = ["Paracetamol", "Amoxicillin", "Ibuprofen", "Metformin"]
        values = [85, 72, 63, 48]
    
    return render_template(
        "prediction.html",
        med_names=json.dumps(labels),
        med_sales=json.dumps(values),
        search_query=search_query,
        total_count=432,
        notifications=notifications
    )
@app.route('/clear-sales', methods=['POST'])
def clear_sales():
    if 'user' not in session:
        return redirect('/')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM sales_medicine")
    conn.commit()
    conn.close()

    return redirect('/sales')


@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/')


if __name__ == '__main__':
    app.run(debug=True)
