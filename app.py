"""Railway Management System: Flask + SQLite frontend."""
import os
import sqlite3
from datetime import date
from functools import wraps

from flask import (Flask, flash, g, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "railway.db")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-production")


# ---------------------------------------------------------------- database
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db:
        db.close()


def init_db():
    """Create the DB from railway.sql on first run and add the auth table."""
    first_run = not os.path.exists(DB_PATH)
    con = sqlite3.connect(DB_PATH)
    if first_run:
        with open(os.path.join(BASE, "railway.sql")) as f:
            con.executescript(f.read())
    con.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id       INTEGER PRIMARY KEY,
            email         TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role          TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user','admin')),
            passenger_id  INTEGER REFERENCES passengers(passenger_id)
        );
    """)
    if not con.execute("SELECT 1 FROM users WHERE role='admin'").fetchone():
        con.execute("INSERT INTO users(email, password_hash, role) VALUES (?,?,'admin')",
                    ("admin@railway.com", generate_password_hash("admin123")))
    con.commit()
    con.close()


# ---------------------------------------------------------------- auth helpers
def login_required(view):
    @wraps(view)
    def wrapped(*a, **kw):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login", next=request.path))
        return view(*a, **kw)
    return wrapped


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*a, **kw):
        if session.get("role") != "admin":
            flash("Admins only.", "danger")
            return redirect(url_for("index"))
        return view(*a, **kw)
    return wrapped


# ---------------------------------------------------------------- signup / login
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        f = request.form
        name, email = f["name"].strip(), f["email"].strip().lower()
        password = f["password"]
        if len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
            return render_template("signup.html")
        db = get_db()
        try:
            cur = db.execute(
                "INSERT INTO passengers(name, age, gender, phone, email) VALUES (?,?,?,?,?)",
                (name, int(f["age"]), f["gender"], f["phone"].strip(), email))
            db.execute(
                "INSERT INTO users(email, password_hash, passenger_id) VALUES (?,?,?)",
                (email, generate_password_hash(password), cur.lastrowid))
            db.commit()
        except sqlite3.IntegrityError:
            db.rollback()
            flash("That email is already registered.", "danger")
            return render_template("signup.html")
        flash("Account created. Please log in.", "success")
        return redirect(url_for("login"))
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        user = get_db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], request.form["password"]):
            session.clear()
            session.update(user_id=user["user_id"], role=user["role"],
                           passenger_id=user["passenger_id"], email=user["email"])
            nxt = request.args.get("next", "")
            if nxt.startswith("/"):
                return redirect(nxt)
            return redirect(url_for("admin" if user["role"] == "admin" else "index"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ---------------------------------------------------------------- search & booking
@app.route("/", methods=["GET", "POST"])
def index():
    db = get_db()
    stations = db.execute("SELECT * FROM stations ORDER BY name").fetchall()
    results, params = None, {}
    if request.method == "POST":
        params = request.form
        frm, to, jdate = int(params["from"]), int(params["to"]), params["date"]
        if frm == to:
            flash("Source and destination must differ.", "danger")
        else:
            results = db.execute("""
                SELECT t.train_id, t.train_no, t.name, t.train_type,
                       a.departure, b.arrival, (b.distance_km - a.distance_km) AS km
                FROM trains t
                JOIN train_routes a ON a.train_id = t.train_id AND a.station_id = ?
                JOIN train_routes b ON b.train_id = t.train_id AND b.station_id = ?
                                   AND b.stop_order > a.stop_order
                ORDER BY a.departure""", (frm, to)).fetchall()
            results = [dict(r, classes=db.execute("""
                SELECT c.class_id, c.code, f.fare,
                       COALESCE(s.available, tc.total_seats) AS available
                FROM train_classes tc
                JOIN classes c ON c.class_id = tc.class_id
                JOIN v_fare_calc f ON f.train_id = tc.train_id AND f.class_id = tc.class_id
                                  AND f.from_station = ? AND f.to_station = ?
                LEFT JOIN seat_availability s ON s.train_id = tc.train_id
                       AND s.class_id = tc.class_id AND s.journey_date = ?
                WHERE tc.train_id = ?""", (frm, to, jdate, r["train_id"])).fetchall())
                for r in results]
    return render_template("index.html", stations=stations, results=results,
                           params=params, today=date.today().isoformat())


@app.route("/book", methods=["POST"])
@login_required
def book():
    f = request.form
    train_id, class_id = int(f["train_id"]), int(f["class_id"])
    frm, to, jdate = int(f["from"]), int(f["to"]), f["date"]
    if session.get("passenger_id") is None:
        flash("Admin accounts cannot book tickets.", "danger")
        return redirect(url_for("index"))
    if jdate < date.today().isoformat():
        flash("Journey date cannot be in the past.", "danger")
        return redirect(url_for("index"))
    db = get_db()
    fare = db.execute("""SELECT fare FROM v_fare_calc WHERE train_id=? AND class_id=?
                         AND from_station=? AND to_station=?""",
                      (train_id, class_id, frm, to)).fetchone()
    if not fare:
        flash("Invalid route for that train.", "danger")
        return redirect(url_for("index"))

    # make sure an inventory row exists for this date, then check seats
    db.execute("""INSERT OR IGNORE INTO seat_availability
                  SELECT train_id, ?, class_id, total_seats FROM train_classes
                  WHERE train_id=? AND class_id=?""", (jdate, train_id, class_id))
    left = db.execute("""SELECT available FROM seat_availability
                         WHERE train_id=? AND class_id=? AND journey_date=?""",
                      (train_id, class_id, jdate)).fetchone()["available"]
    status = "CONFIRMED" if left > 0 else "WAITLIST"

    cur = db.execute("""INSERT INTO bookings(passenger_id, train_id, class_id, journey_date,
                        from_station, to_station, fare, status) VALUES (?,?,?,?,?,?,?,?)""",
                     (session["passenger_id"], train_id, class_id, jdate, frm, to,
                      fare["fare"], status))
    if status == "CONFIRMED":
        db.execute("INSERT INTO payments(pnr, amount, mode) VALUES (?,?,?)",
                   (cur.lastrowid, fare["fare"], f.get("mode", "UPI")))
    db.commit()
    flash(f"Booking {status.lower()}! Your PNR is {cur.lastrowid}.", "success")
    return redirect(url_for("my_bookings"))


@app.route("/my-bookings")
@login_required
def my_bookings():
    rows = get_db().execute(
        "SELECT * FROM v_ticket WHERE pnr IN (SELECT pnr FROM bookings WHERE passenger_id=?) "
        "ORDER BY journey_date DESC, pnr DESC", (session.get("passenger_id"),)).fetchall()
    return render_template("my_bookings.html", bookings=rows)


@app.route("/cancel/<int:pnr>", methods=["POST"])
@login_required
def cancel(pnr):
    db = get_db()
    # ownership check: users can only cancel their own tickets
    cur = db.execute("""UPDATE bookings SET status='CANCELLED'
                        WHERE pnr=? AND passenger_id=? AND status IN ('CONFIRMED','WAITLIST')""",
                     (pnr, session.get("passenger_id")))
    db.commit()
    flash("Ticket cancelled. 80% refund initiated." if cur.rowcount
          else "Could not cancel that ticket.", "success" if cur.rowcount else "danger")
    return redirect(url_for("my_bookings"))


# ---------------------------------------------------------------- admin
@app.route("/admin")
@admin_required
def admin():
    db = get_db()
    return render_template(
        "admin.html",
        stations=db.execute("SELECT * FROM stations ORDER BY name").fetchall(),
        trains=db.execute("SELECT * FROM trains ORDER BY train_no").fetchall(),
        bookings=db.execute("SELECT * FROM v_ticket ORDER BY pnr DESC LIMIT 50").fetchall(),
        stats=db.execute("""
            SELECT (SELECT COUNT(*) FROM bookings WHERE status='CONFIRMED') AS confirmed,
                   (SELECT COUNT(*) FROM bookings WHERE status='CANCELLED') AS cancelled,
                   (SELECT COUNT(*) FROM passengers) AS passengers,
                   (SELECT ROUND(COALESCE(SUM(CASE WHEN is_refund=0 THEN amount ELSE -amount END),0),2)
                      FROM payments) AS revenue""").fetchone())


@app.route("/admin/station", methods=["POST"])
@admin_required
def add_station():
    f = request.form
    try:
        get_db().execute("INSERT INTO stations(code, name, city) VALUES (?,?,?)",
                         (f["code"].strip().upper(), f["name"].strip(), f["city"].strip()))
        get_db().commit()
        flash("Station added.", "success")
    except sqlite3.IntegrityError:
        flash("Station code already exists.", "danger")
    return redirect(url_for("admin"))


@app.route("/admin/train", methods=["POST"])
@admin_required
def add_train():
    f = request.form
    try:
        get_db().execute("INSERT INTO trains(train_no, name, train_type) VALUES (?,?,?)",
                         (f["train_no"].strip(), f["name"].strip(), f["train_type"]))
        get_db().commit()
        flash("Train added.", "success")
    except sqlite3.IntegrityError:
        flash("Train number already exists.", "danger")
    return redirect(url_for("admin"))


@app.route("/admin/route", methods=["POST"])
@admin_required
def add_route_stop():
    f = request.form
    try:
        get_db().execute("""INSERT INTO train_routes(train_id, station_id, stop_order,
                            arrival, departure, distance_km) VALUES (?,?,?,?,?,?)""",
                         (int(f["train_id"]), int(f["station_id"]), int(f["stop_order"]),
                          f["arrival"] or None, f["departure"] or None, int(f["distance_km"])))
        get_db().commit()
        flash("Route stop added.", "success")
    except sqlite3.IntegrityError:
        flash("That stop order or station is already on this train's route.", "danger")
    return redirect(url_for("admin"))


@app.route("/admin/train-class", methods=["POST"])
@admin_required
def add_train_class():
    f = request.form
    try:
        get_db().execute("INSERT INTO train_classes(train_id, class_id, total_seats) VALUES (?,?,?)",
                         (int(f["train_id"]), int(f["class_id"]), int(f["total_seats"])))
        get_db().commit()
        flash("Class added to train.", "success")
    except sqlite3.IntegrityError:
        flash("That class already exists for this train.", "danger")
    return redirect(url_for("admin"))


@app.context_processor
def inject_classes():
    return {"all_classes": get_db().execute("SELECT * FROM classes").fetchall()
            if session.get("role") == "admin" else []}


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
