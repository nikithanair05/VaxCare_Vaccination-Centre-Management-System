from flask import Flask, flash
import sqlite3
import os
from flask import render_template, request, redirect, url_for,session
import hashlib
from werkzeug.security import check_password_hash, generate_password_hash
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from flask import send_file
import io

app = Flask(__name__)
app.secret_key = "vaxcare_secret_key"

# Database path
DATABASE = os.path.join('database', 'vaccination.db')
from datetime import datetime


def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn
def auto_mark_missed_appointments(user_id):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE bookings
        SET status = 'missed'
        WHERE user_id = ?
          AND status = 'upcoming'
          AND datetime(
                (SELECT date || ' ' || end_time FROM slots 
                 WHERE slots.slot_id = bookings.slot_id)
              ) < datetime('now')
    """, (user_id,))

    conn.commit()
    conn.close()


@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        email = request.form['email']
        password = request.form['password']

        password_hash = generate_password_hash(password)

        conn = get_db_connection()
        conn.execute(
            "INSERT INTO users (name, phone, email, password_hash, role) VALUES (?, ?, ?, ?, ?)",
            (name, phone, email, password_hash, 'user')
        )
        conn.commit()
        conn.close()

        return redirect(url_for('home'))

    return render_template('register.html')


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("database/vaccination.db")
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        user = cur.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["user_id"]
            session["role"] = user["role"]

            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            else:
                return redirect(url_for("user_dashboard"))

        flash("Invalid email or password", "danger")

    # ✅ IMPORTANT FIX
    return render_template("index.html")


@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        admin = conn.execute(
            "SELECT * FROM users WHERE email=? AND role='admin'",
            (email,)
        ).fetchone()
        conn.close()

        if admin:
            # store admin login in session
            session['admin_logged_in'] = True
            session['admin_email'] = email

            return redirect(url_for('admin_dashboard'))
        else:
            return render_template('admin_login.html', error="Invalid admin credentials")

    return render_template('admin_login.html')



@app.route('/admin-dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    conn = get_db_connection()

    upcoming = conn.execute(
        "SELECT COUNT(*) FROM bookings WHERE status = 'upcoming'"
    ).fetchone()[0]

    completed = conn.execute(
        "SELECT COUNT(*) FROM bookings WHERE status = 'completed'"
    ).fetchone()[0]

    cancelled = conn.execute(
        "SELECT COUNT(*) FROM bookings WHERE status = 'cancelled'"
    ).fetchone()[0]

    missed = conn.execute(
        "SELECT COUNT(*) FROM bookings WHERE status = 'missed'"
    ).fetchone()[0]

    conn.close()

    return render_template(
        'admin_dashboard.html',
        upcoming=upcoming,
        completed=completed,
        cancelled=cancelled,
        missed=missed
    )

@app.route('/admin/centres', methods=['GET', 'POST'])
def admin_centres():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    conn = get_db_connection()

    if request.method == 'POST':
        name = request.form['name']
        address = request.form['address']
        contact = request.form['contact']

        conn.execute(
            "INSERT INTO centres (name, address, contact) VALUES (?, ?, ?)",
            (name, address, contact)
        )
        conn.commit()

    centres = conn.execute("SELECT * FROM centres").fetchall()
    conn.close()

    return render_template('admin_centres.html', centres=centres)
@app.route('/admin/centres/delete/<int:centre_id>')
def delete_centre(centre_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    conn.execute("DELETE FROM centres WHERE centre_id = ?", (centre_id,))
    conn.commit()
    conn.close()

    return redirect(url_for('admin_centres'))
@app.route('/admin/centres/edit/<int:centre_id>', methods=['GET', 'POST'])
def edit_centre(centre_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    conn = get_db_connection()

    if request.method == 'POST':
        name = request.form['name']
        address = request.form['address']
        contact = request.form['contact']

        conn.execute(
            "UPDATE centres SET name=?, address=?, contact=? WHERE centre_id=?",
            (name, address, contact, centre_id)
        )
        conn.commit()
        conn.close()

        return redirect(url_for('admin_centres'))

    centre = conn.execute(
        "SELECT * FROM centres WHERE centre_id = ?", (centre_id,)
    ).fetchone()
    conn.close()

    return render_template('admin_edit_centre.html', centre=centre)


@app.route('/admin/slots', methods=['GET', 'POST'])
def admin_slots():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    conn = get_db_connection()

    if request.method == 'POST':
        centre_id = request.form['centre_id']
        date = request.form['date']
        start_time = request.form['start_time']
        end_time = request.form['end_time']
        capacity = request.form['capacity']
        vaccine = request.form['vaccine']

        conn.execute("""
            INSERT INTO slots (centre_id, date, start_time, end_time, capacity, vaccine)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (centre_id, date, start_time, end_time, capacity, vaccine))

        conn.commit()

    centres = conn.execute("SELECT * FROM centres").fetchall()

    slots = conn.execute("""
        SELECT slots.*, centres.name AS centre_name
        FROM slots
        JOIN centres ON slots.centre_id = centres.centre_id
        ORDER BY date, start_time
    """).fetchall()

    conn.close()

    return render_template(
        'admin_slots.html',
        centres=centres,
        slots=slots
    )


@app.route('/admin/slots/edit/<int:slot_id>', methods=['GET', 'POST'])
def edit_slot(slot_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    conn = get_db_connection()

    if request.method == 'POST':
        centre_id = request.form['centre_id']
        date = request.form['date']
        start_time = request.form['start_time']
        end_time = request.form['end_time']
        capacity = request.form['capacity']
        vaccine = request.form['vaccine']

        conn.execute("""
            UPDATE slots
            SET centre_id=?, date=?, start_time=?, end_time=?, capacity=?, vaccine=?
            WHERE slot_id=?
        """, (centre_id, date, start_time, end_time, capacity, vaccine, slot_id))

        conn.commit()
        conn.close()

        return redirect(url_for('admin_slots'))

    slot = conn.execute(
        "SELECT * FROM slots WHERE slot_id = ?", (slot_id,)
    ).fetchone()

    centres = conn.execute("SELECT * FROM centres").fetchall()
    conn.close()

    return render_template(
        'admin_edit_slot.html',
        slot=slot,
        centres=centres
    )
@app.route('/admin/slots/delete/<int:slot_id>')
def delete_slot(slot_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM slots WHERE slot_id = ?', (slot_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin_slots'))

@app.route('/admin/bookings')
def admin_bookings():

    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    status = request.args.get('status')

    conn = get_db_connection()

    query = """
    SELECT 
        b.booking_id,
        u.name,
        u.email,
        c.name AS centre_name,
        s.date,
        s.start_time,
        s.end_time,
        s.vaccine,
        b.status
    FROM bookings b
    JOIN users u ON b.user_id = u.user_id
    JOIN slots s ON b.slot_id = s.slot_id
    JOIN centres c ON s.centre_id = c.centre_id
    """

    if status:
        query += " WHERE b.status = ?"
        bookings = conn.execute(query,(status,)).fetchall()
    else:
        bookings = conn.execute(query).fetchall()

    conn.close()

    return render_template("admin_bookings.html", bookings=bookings)

@app.route('/admin/booking/complete/<int:booking_id>')
def complete_booking(booking_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    conn.execute("""
        UPDATE bookings
        SET status = 'completed'
        WHERE booking_id = ?
    """, (booking_id,))
    conn.commit()
    conn.close()

    return redirect(url_for('admin_bookings'))
@app.route('/admin/booking/cancel/<int:booking_id>')
def admin_cancel_booking(booking_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    conn = get_db_connection()

    booking = conn.execute("""
        SELECT slot_id FROM bookings
        WHERE booking_id = ?
    """, (booking_id,)).fetchone()

    if booking:
        conn.execute("""
            UPDATE bookings
            SET status = 'cancelled'
            WHERE booking_id = ?
        """, (booking_id,))

        conn.execute("""
            UPDATE slots
            SET capacity = capacity + 1
            WHERE slot_id = ?
        """, (booking["slot_id"],))

        conn.commit()

    conn.close()

    return redirect(url_for('admin_bookings'))

import csv
from flask import Response

@app.route('/admin/bookings/export')
def export_bookings():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    conn = get_db_connection()

    bookings = conn.execute("""
        SELECT 
            b.booking_id,
            u.name,
            u.email,
            c.name AS centre_name,
            s.date,
            s.start_time,
            s.end_time,
            s.vaccine,
            b.status
        FROM bookings b
        JOIN users u ON b.user_id = u.user_id
        JOIN slots s ON b.slot_id = s.slot_id
        JOIN centres c ON s.centre_id = c.centre_id
        ORDER BY s.date DESC
    """).fetchall()

    conn.close()

    def generate():
        data = csv.writer(open('temp.csv', 'w', newline=''))
        yield "Booking ID,Name,Email,Centre,Date,Start Time,End Time,Vaccine,Status\n"
        for b in bookings:
            yield f"{b['booking_id']},{b['name']},{b['email']},{b['centre_name']},{b['date']},{b['start_time']},{b['end_time']},{b['vaccine']},{b['status']}\n"

    return Response(
        generate(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=bookings_report.csv"}
    )

@app.route('/admin/staff', methods=['GET','POST'])
def admin_staff():

    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    conn = get_db_connection()

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])

        conn.execute("""
            INSERT INTO staff (name,email,password)
            VALUES (?,?,?)
        """,(name,email,password))

        conn.commit()

    staff = conn.execute("SELECT * FROM staff").fetchall()
    conn.close()

    return render_template("admin_staff.html", staff=staff)

@app.route('/admin/staff/delete/<int:staff_id>')
def delete_staff(staff_id):

    conn = get_db_connection()

    conn.execute("DELETE FROM staff WHERE staff_id=?",(staff_id,))
    conn.commit()

    conn.close()

    return redirect(url_for('admin_staff'))

@app.route("/admin/analytics")
def admin_analytics():

    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    selected_month = request.args.get("month")

    conn = get_db_connection()
    cur = conn.cursor()

    month_filter = ""
    params = []

    if selected_month:
        month_filter = "AND strftime('%Y-%m', s.date) = ?"
        params.append(selected_month)

    centre_stats = cur.execute(f"""
        SELECT c.name, COUNT(b.booking_id)
        FROM bookings b
        JOIN slots s ON b.slot_id = s.slot_id
        JOIN centres c ON s.centre_id = c.centre_id
        WHERE b.status='completed' {month_filter}
        GROUP BY c.name
    """, params).fetchall()

    vaccine_stats = cur.execute(f"""
        SELECT s.vaccine, COUNT(b.booking_id)
        FROM bookings b
        JOIN slots s ON b.slot_id = s.slot_id
        WHERE b.status='completed' {month_filter}
        GROUP BY s.vaccine
    """, params).fetchall()

    daily_stats = cur.execute(f"""
        SELECT s.date, COUNT(b.booking_id)
        FROM bookings b
        JOIN slots s ON b.slot_id = s.slot_id
        WHERE 1=1 {month_filter}
        GROUP BY s.date
        ORDER BY s.date DESC
    """, params).fetchall()

    conn.close()

    return render_template(
        "admin_analytics.html",
        centre_stats=centre_stats,
        vaccine_stats=vaccine_stats,
        daily_stats=daily_stats,
        selected_month=selected_month
    )

@app.route('/logout')
def logout():
    session.clear()   # clears all session data
    return redirect(url_for('home'))

from datetime import date, datetime

@app.route("/user/dashboard")
def user_dashboard():
    if "user_id" not in session or session["role"] != "user":
        return redirect(url_for("login"))

    user_id = session["user_id"]

    # 🔥 STEP 3 — CALL THE FUNCTION HERE
    auto_mark_missed_appointments(user_id)

    conn = get_db_connection()
    cur = conn.cursor()

    today = date.today()

    conn = get_db_connection()
    cur = conn.cursor()

    # User name
    user = cur.execute(
        "SELECT name FROM users WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    # Upcoming appointments count
    upcoming = cur.execute("""
        SELECT COUNT(*)
        FROM bookings
        WHERE user_id = ? AND status = 'upcoming'
    """, (user_id,)).fetchone()[0]

    # Completed vaccinations
    completed = cur.execute("""
        SELECT COUNT(*)
        FROM records r
        JOIN bookings b ON r.booking_id = b.booking_id
        WHERE b.user_id = ?
    """, (user_id,)).fetchone()[0]

    # Vaccination status
    if completed == 0:
        vaccination_status = "Not Started"
    elif completed == 1:
        vaccination_status = "Partially Vaccinated"
    else:
        vaccination_status = "Fully Vaccinated"

    # Recent activity
    recent = cur.execute("""
        SELECT booked_at, status
        FROM bookings
        WHERE user_id = ?
        ORDER BY booked_at DESC
        LIMIT 3
    """, (user_id,)).fetchall()

    # 🔥 GET NEAREST UPCOMING VACCINATION DATE
    next_booking = cur.execute("""
        SELECT slots.date
        FROM bookings
        JOIN slots ON bookings.slot_id = slots.slot_id
        WHERE bookings.user_id = ?
          AND bookings.status = 'upcoming'
        ORDER BY slots.date ASC
        LIMIT 1
    """, (user_id,)).fetchone()

    progress = None

    if next_booking:
        vaccine_date = datetime.strptime(next_booking["date"], "%Y-%m-%d").date()
        days_left = (vaccine_date - today).days

        total_window = 30  # days window for progress calculation
        percent = max(0, min(100, int(((total_window - days_left) / total_window) * 100)))

        progress = {
            "date": vaccine_date.strftime("%d %b %Y"),
            "days_left": days_left,
            "percent": percent
        }
    # 🔔 Appointment Reminder Notification

    notification = None

    next_booking = cur.execute("""
        SELECT slots.date, slots.start_time
        FROM bookings
        JOIN slots ON bookings.slot_id = slots.slot_id
        WHERE bookings.user_id = ?
        AND bookings.status = 'upcoming'
        ORDER BY slots.date ASC
        LIMIT 1
    """, (user_id,)).fetchone()

    if next_booking:
        vaccine_date = datetime.strptime(next_booking["date"], "%Y-%m-%d").date()
        days_left = (vaccine_date - today).days

        if days_left == 0:
            notification = f"🔔 Reminder: Your vaccination is today at {next_booking['start_time']}."
        elif days_left == 1:
            notification = f"🔔 Reminder: Your vaccination is tomorrow at {next_booking['start_time']}."
        elif days_left <= 3:
            notification = f"🔔 Upcoming vaccination on {next_booking['date']} at {next_booking['start_time']}."
    conn.close()
    return render_template(
    "user_dashboard.html",
    name=user["name"],
    upcoming=upcoming,
    completed=completed,
    vaccination_status=vaccination_status,
    recent=recent,
    progress=progress,
    notification=notification
)
    





@app.route("/user/centres")
def user_centres():
    if "user_id" not in session or session["role"] != "user":
        return redirect(url_for("login"))

    conn = get_db_connection()

    centres = conn.execute("""
        SELECT * FROM centres
    """).fetchall()

    conn.close()

    return render_template(
        "user_centres.html",
        centres=centres
    )
from datetime import date, timedelta

@app.route("/user/centres/<int:centre_id>/slots")
def user_centre_slots(centre_id):
    if "user_id" not in session or session["role"] != "user":
        return redirect(url_for("login"))

    selected_date = request.args.get("date")

    conn = get_db_connection()

    centre = conn.execute(
        "SELECT * FROM centres WHERE centre_id = ?",
        (centre_id,)
    ).fetchone()

    # Generate next 10 days
    today = date.today()
    dates = [(today + timedelta(days=i)) for i in range(10)]

    if not selected_date:
        selected_date = dates[0].isoformat()

    slots = conn.execute("""
    SELECT 
    slots.*,
    (slots.capacity - (
    SELECT COUNT(*) FROM bookings
    WHERE bookings.slot_id = slots.slot_id
    AND bookings.status != 'cancelled'
    )) AS remaining,

    (
    SELECT COUNT(*)
    FROM bookings
    WHERE bookings.slot_id = slots.slot_id
    AND bookings.status != 'cancelled'
    ) * 5 AS wait_time

    FROM slots
    WHERE centre_id = ?
    AND date = ?
    ORDER BY start_time
    """, (centre_id, selected_date)).fetchall()

    # Determine recommended slot
    recommended_slot_id = None
    if slots:
        recommended_slot_id = slots[0]["slot_id"]

    conn.close()

    return render_template(
    "user_slots.html",
    centre=centre,
    slots=slots,
    dates=dates,
    selected_date=selected_date,
    recommended_slot_id=recommended_slot_id
)



@app.route('/user/slots')
def user_slots():
    conn = get_db_connection()
    slots = conn.execute("""
        SELECT * FROM slots
        WHERE capacity > 0
    """).fetchall()
    conn.close()

    return render_template('user_slots.html', slots=slots)

@app.route('/user/book/<int:slot_id>')
def book_slot(slot_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    conn = get_db_connection()
    cur = conn.cursor()

    # 🔒 Check capacity
    slot = cur.execute("""
        SELECT capacity FROM slots WHERE slot_id = ?
    """, (slot_id,)).fetchone()

    if not slot or slot["capacity"] <= 0:
        conn.close()
        flash("This slot is already full. Please choose another slot.", "danger")
        return redirect(request.referrer)

    # ✅ Proceed with booking
    cur.execute("""
        INSERT INTO bookings (user_id, slot_id, status)
        VALUES (?, ?, 'upcoming')
    """, (user_id, slot_id))

    cur.execute("""
        UPDATE slots
        SET capacity = capacity - 1
        WHERE slot_id = ?
    """, (slot_id,))

    conn.commit()
    conn.close()

    return redirect(url_for("booking_success", slot_id=slot_id))

@app.route('/user/bookings')
def user_bookings():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    # — CALL AGAIN HERE
    auto_mark_missed_appointments(user_id)

    conn = get_db_connection()
    cur = conn.cursor()


    conn = get_db_connection()
    bookings = conn.execute("""
        SELECT 
            bookings.booking_id,
            slots.date,
            slots.start_time,
            slots.end_time,
            slots.vaccine,
            bookings.status
        FROM bookings
        JOIN slots ON bookings.slot_id = slots.slot_id
        WHERE bookings.user_id = ?
          AND bookings.status != 'cancelled'
        ORDER BY bookings.booked_at DESC
    """, (user_id,)).fetchall()

    conn.close()
    return render_template('user_bookings.html', bookings=bookings)




@app.route("/user/booking/success/<int:slot_id>")
def booking_success(slot_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()

    booking = conn.execute("""
        SELECT c.name AS centre_name,
               s.date, s.start_time, s.end_time, s.vaccine
        FROM bookings b
        JOIN slots s ON b.slot_id = s.slot_id
        JOIN centres c ON s.centre_id = c.centre_id
        WHERE s.slot_id = ?
        ORDER BY b.booking_id DESC
        LIMIT 1
    """, (slot_id,)).fetchone()

    conn.close()

    return render_template(
        "booking_success.html",
        booking=booking
    )
@app.route("/user/status")
def user_status():
    if "user_id" not in session or session["role"] != "user":
        return redirect(url_for("login"))

    user_id = session["user_id"]
    conn = get_db_connection()
    cur = conn.cursor()

    # Total completed vaccinations
    completed = cur.execute("""
        SELECT COUNT(*)
        FROM records r
        JOIN bookings b ON r.booking_id = b.booking_id
        WHERE b.user_id = ?
    """, (user_id,)).fetchone()[0]

    # Upcoming bookings
    upcoming = cur.execute("""
        SELECT slots.date, slots.start_time, slots.end_time, slots.vaccine
        FROM bookings
        JOIN slots ON bookings.slot_id = slots.slot_id
        WHERE bookings.user_id = ?
        AND bookings.status = 'upcoming'
        ORDER BY slots.date
    """, (user_id,)).fetchall()

    # Status logic
    if completed == 0:
        status = "Not Started"
    elif completed == 1:
        status = "Partially Vaccinated"
    else:
        status = "Fully Vaccinated"

    conn.close()

    return render_template(
        "user_status.html",
        status=status,
        completed=completed,
        upcoming=upcoming
    )

@app.route('/user/cancel/<int:booking_id>')
def cancel_booking(booking_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    conn = get_db_connection()
    cur = conn.cursor()

    # Get slot_id to restore capacity
    booking = cur.execute("""
        SELECT slot_id FROM bookings
        WHERE booking_id = ? AND user_id = ? AND status = 'upcoming'
    """, (booking_id, user_id)).fetchone()

    if not booking:
        conn.close()
        flash("Invalid or already processed booking.", "danger")
        return redirect(url_for("user_bookings"))

    slot_id = booking["slot_id"]

    # Cancel booking
    cur.execute("""
        UPDATE bookings
        SET status = 'cancelled'
        WHERE booking_id = ?
    """, (booking_id,))

    # Restore slot capacity
    cur.execute("""
        UPDATE slots
        SET capacity = capacity + 1
        WHERE slot_id = ?
    """, (slot_id,))

    conn.commit()
    conn.close()

    flash("Appointment cancelled successfully.", "success")
    return redirect(url_for("user_bookings"))

@app.route("/staff/dashboard")
def staff_dashboard():

    if "staff_id" not in session or session.get("role") != "staff":
        return redirect(url_for("staff_login"))

    status_filter = request.args.get("status")
    search_query = request.args.get("search")

    conn = get_db_connection()
    cur = conn.cursor()

    # -----------------------------
    # BASE QUERY
    # -----------------------------
    query = """
        SELECT 
            b.booking_id,
            u.name AS user_name,
            u.phone,
            s.date,
            s.start_time,
            s.end_time,
            s.vaccine,
            b.status
        FROM bookings b
        JOIN users u ON b.user_id = u.user_id
        JOIN slots s ON b.slot_id = s.slot_id
        WHERE s.date = DATE('now')
    """

    params = []

    # -----------------------------
    # STATUS FILTER (Clickable cards)
    # -----------------------------
    if status_filter:
        query += " AND b.status = ?"
        params.append(status_filter)

    # -----------------------------
    # SEARCH FILTER
    # -----------------------------
    if search_query:
        query += """
            AND (
                u.name LIKE ?
                OR u.phone LIKE ?
                OR CAST(b.booking_id AS TEXT) LIKE ?
            )
        """
        params.extend([
            f"%{search_query}%",
            f"%{search_query}%",
            f"%{search_query}%"
        ])

    query += " ORDER BY s.start_time"

    appointments = cur.execute(query, params).fetchall()

    # -----------------------------
    # DASHBOARD STATISTICS
    # -----------------------------

    total_today = cur.execute("""
        SELECT COUNT(*)
        FROM bookings b
        JOIN slots s ON b.slot_id = s.slot_id
        WHERE s.date = DATE('now')
    """).fetchone()[0]

    completed_today = cur.execute("""
        SELECT COUNT(*)
        FROM bookings b
        JOIN slots s ON b.slot_id = s.slot_id
        WHERE s.date = DATE('now')
        AND b.status='completed'
    """).fetchone()[0]

    pending_today = cur.execute("""
        SELECT COUNT(*)
        FROM bookings b
        JOIN slots s ON b.slot_id = s.slot_id
        WHERE s.date = DATE('now')
        AND b.status='upcoming'
    """).fetchone()[0]

    missed_today = cur.execute("""
        SELECT COUNT(*)
        FROM bookings b
        JOIN slots s ON b.slot_id = s.slot_id
        WHERE s.date = DATE('now')
        AND b.status='missed'
    """).fetchone()[0]

    conn.close()

    return render_template(
        "staff_dashboard.html",
        appointments=appointments,
        total_today=total_today,
        completed_today=completed_today,
        pending_today=pending_today,
        missed_today=missed_today,
        status_filter=status_filter,
        search_query=search_query
    )


@app.route("/staff/login", methods=["GET", "POST"])
def staff_login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db_connection()
        cur = conn.cursor()

        staff = cur.execute("""
            SELECT * FROM staff
            WHERE email = ?
        """, (email,)).fetchone()

        conn.close()

        if staff and check_password_hash(staff["password"], password):
            session["staff_id"] = staff["staff_id"]
            session["role"] = "staff"
            return redirect(url_for("staff_dashboard"))

        return render_template("staff_login.html", error="Invalid credentials")

    return render_template("staff_login.html")

@app.route("/staff/start/<int:booking_id>")
def start_vaccination(booking_id):
    if "staff_id" not in session:
        return redirect(url_for("staff_login"))

    staff_id = session["staff_id"]
    conn = get_db_connection()
    cur = conn.cursor()

    # Update booking status
    cur.execute("""
        UPDATE bookings
        SET status = 'in_progress'
        WHERE booking_id = ?
    """, (booking_id,))

    # Insert record with start time
    cur.execute("""
        INSERT OR IGNORE INTO records 
        (booking_id, staff_id, started_at)
        VALUES (?, ?, datetime('now'))
    """, (booking_id, staff_id))

    conn.commit()
    conn.close()

    return redirect(url_for("staff_dashboard"))

@app.route("/staff/finish/<int:booking_id>", methods=["POST"])
def finish_vaccination(booking_id):

    if "staff_id" not in session:
        return redirect(url_for("staff_login"))

    vaccine_type = request.form["vaccine_type"]
    batch_no = request.form["batch_no"]

    conn = get_db_connection()
    cur = conn.cursor()

    # Update booking status
    cur.execute("""
        UPDATE bookings
        SET status = 'completed'
        WHERE booking_id = ?
    """, (booking_id,))

    # Update record
    cur.execute("""
        UPDATE records
        SET finished_at = datetime('now'),
            vaccine = ?,
            batch_no = ?
        WHERE booking_id = ?
    """, (vaccine_type, batch_no, booking_id))

    conn.commit()
    conn.close()

    return redirect(url_for("staff_dashboard"))

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from flask import send_file
import io
import qrcode


@app.route("/certificate/<int:booking_id>")
def download_certificate(booking_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()

    data = conn.execute("""
        SELECT 
            u.name,
            s.vaccine,
            r.batch_no,
            r.finished_at,
            c.name AS centre_name
        FROM records r
        JOIN bookings b ON r.booking_id = b.booking_id
        JOIN users u ON b.user_id = u.user_id
        JOIN slots s ON b.slot_id = s.slot_id
        JOIN centres c ON s.centre_id = c.centre_id
        WHERE r.booking_id = ?
    """, (booking_id,)).fetchone()

    conn.close()

    if not data:
        return "Certificate not available"

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)

    width, height = letter

    # Background border
    pdf.setStrokeColor(HexColor("#1f3c88"))
    pdf.setLineWidth(6)
    pdf.rect(20, 20, width-40, height-40)

    # Title
    pdf.setFont("Helvetica-Bold", 24)
    pdf.drawCentredString(width/2, 720, "VACCINATION CERTIFICATE")

    pdf.setFont("Helvetica", 14)

    pdf.drawString(100, 640, f"Name: {data['name']}")
    pdf.drawString(100, 610, f"Vaccine: {data['vaccine']}")
    pdf.drawString(100, 580, f"Batch Number: {data['batch_no']}")
    pdf.drawString(100, 550, f"Vaccination Centre: {data['centre_name']}")
    pdf.drawString(100, 520, f"Date: {data['finished_at']}")

    pdf.drawString(
        100,
        470,
        "This certifies that the above person has been successfully vaccinated."
    )

    # Generate QR Code
    qr_data = f"http://127.0.0.1:5000/verify-certificate/{booking_id}"

    qr = qrcode.make(qr_data)
    qr_path = "temp_qr.png"
    qr.save(qr_path)

    pdf.drawImage(qr_path, 420, 500, width=120, height=120)

    # Signature
    pdf.setFont("Helvetica", 12)
    pdf.drawString(400, 200, "Authorized Signature")

    pdf.save()

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="vaccination_certificate.pdf",
        mimetype="application/pdf"
    )
@app.route("/verify-certificate/<int:booking_id>")
def verify_certificate(booking_id):

    conn = get_db_connection()

    data = conn.execute("""
        SELECT 
            u.name,
            s.vaccine,
            r.batch_no,
            r.finished_at,
            c.name AS centre_name
        FROM records r
        JOIN bookings b ON r.booking_id = b.booking_id
        JOIN users u ON b.user_id = u.user_id
        JOIN slots s ON b.slot_id = s.slot_id
        JOIN centres c ON s.centre_id = c.centre_id
        WHERE r.booking_id = ?
    """, (booking_id,)).fetchone()

    conn.close()

    if not data:
        return "Invalid Certificate"

    return render_template("verify_certificate.html", data=data)

@app.route("/admin/export-analytics")
def export_analytics():

    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    selected_month = request.args.get("month")

    conn = get_db_connection()
    cur = conn.cursor()

    month_filter = ""
    params = []

    if selected_month:
        month_filter = "AND strftime('%Y-%m', s.date) = ?"
        params.append(selected_month)

    data = cur.execute(f"""
        SELECT c.name, s.vaccine, COUNT(b.booking_id)
        FROM bookings b
        JOIN slots s ON b.slot_id = s.slot_id
        JOIN centres c ON s.centre_id = c.centre_id
        WHERE b.status='completed' {month_filter}
        GROUP BY c.name, s.vaccine
    """, params).fetchall()

    conn.close()

    import csv
    from flask import Response

    def generate():
        yield "Centre,Vaccine,Total Vaccinations\n"
        for row in data:
            yield f"{row[0]},{row[1]},{row[2]}\n"

    return Response(
        generate(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=analytics_report.csv"}
    )
if __name__ == '__main__':
    app.run(debug=True)
