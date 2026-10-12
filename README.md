# Railway Management System (Flask + SQLite)

## Run locally
```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py                   # open http://127.0.0.1:5000
```
First run creates `railway.db` from `railway.sql` and seeds an admin account:
**admin@railway.com / admin123** (change it!). To reset all data, delete `railway.db`.

## Structure
```
railway_app/
├── app.py            routes, auth, DB access
├── railway.sql       schema, triggers, views, sample data + extended data (58 stations, 504 trains)
├── railway.db        ready-to-use database built from railway.sql (includes the admin account)
├── requirements.txt
├── tools/extend_railway_db.py   generator used to create the extra stations and trains
├── static/style.css  responsive, dark-mode aware
└── templates/        base, signup, login, index (search+book), my_bookings, admin
```

## Data included
58 stations and 504 trains (40 Rajdhani, 60 Shatabdi, 200 Superfast, 200 Express added on top of the original 4),
with routes, arrival/departure times, distances, classes and seat inventory for 2026-11-01 and 2026-11-02.
Train names, numbers and timings are generated sample data, not the real Indian Railways timetable.
Bookings for other dates still work: the app creates the seat inventory row on first booking.

## How it works
| Feature | Route | What happens in the database |
|---|---|---|
| Sign up | `/signup` | INSERT into `passengers`, then `users` (hashed password) in one transaction |
| Login | `/login` | Look up `users`, verify with `check_password_hash`, store id/role in session |
| Search | `/` | Self-join of `train_routes` (source stop before destination stop) + `v_fare_calc` |
| Book | `/book` | Ensure `seat_availability` row, INSERT booking; trigger decrements seats; INSERT payment |
| View | `/my-bookings` | `v_ticket` filtered by logged-in passenger |
| Cancel | `/cancel/<pnr>` | UPDATE status; trigger frees seat and inserts 80% refund |
| Admin | `/admin/*` | INSERT stations, trains, route stops, train classes; dashboard stats |

## Security notes
- Passwords hashed (PBKDF2 via Werkzeug), never stored in plain text.
- All SQL is parameterised (`?`), which prevents SQL injection.
- Cancellation checks ownership (`passenger_id`), and admin routes use `@admin_required`.
- Before deploying: set `SECRET_KEY` env var, turn off `debug=True`, add CSRF protection (Flask-WTF), and use HTTPS.

## Ideas to extend
Waitlist promotion on cancel, seat/berth numbers, PDF ticket, password reset, pagination, search by train number.
