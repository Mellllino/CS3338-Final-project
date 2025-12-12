from flask import Flask, render_template, redirect, url_for, request, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date

app = Flask(__name__)

# -------------------------
# CONFIG
# -------------------------
app.config['SECRET_KEY'] = '7d12fae4c8b94b25b97d2e4a3d9981ab'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///travel.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# -------------------------
# MODELS
# -------------------------

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='employee')  # 'employee' or 'manager'

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class TravelRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    destination = db.Column(db.String(200), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    estimated_cost = db.Column(db.Float, nullable=False)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default="Pending")  # Pending, Approved, Denied, Settled
    submitted_on = db.Column(db.Date, default=date.today)
    manager_comment = db.Column(db.Text)

    requester = db.relationship('User')


# -------------------------
# HELPERS
# -------------------------

def current_user():
    if "user_id" in session:
        return User.query.get(session["user_id"])
    return None


def login_required(f):
    from functools import wraps

    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user():
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return wrapper


def manager_required(f):
    from functools import wraps

    @wraps(f)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user or user.role != "manager":
            flash("Manager access required.", "danger")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)

    return wrapper


# -------------------------
# INITIAL DB SETUP
# -------------------------

def setup_database():
    with app.app_context():
        db.create_all()

        # 1. Ensure Users Exist
        employee = User.query.filter_by(email="employee@example.com").first()
        if not employee:
            employee = User(
                email="employee@example.com",
                name="Employee User",
                password_hash=generate_password_hash("password123"),
                role="employee"
            )
            db.session.add(employee)
            print("Created Employee User.")

        manager = User.query.filter_by(email="manager@example.com").first()
        if not manager:
            manager = User(
                email="manager@example.com",
                name="Manager User",
                password_hash=generate_password_hash("password123"),
                role="manager"
            )
            db.session.add(manager)
            print("Created Manager User.")
        
        # Commit users so we can use their IDs below
        db.session.commit()

        # 2. Ensure Sample Requests Exist
        # We check if the table is empty so we don't duplicate data on every restart
        if not TravelRequest.query.first():
            # Refetch employee to be safe
            emp = User.query.filter_by(email="employee@example.com").first()
            
            if emp:
                req1 = TravelRequest(
                    requester_id=emp.id,
                    destination="Paris, France",
                    start_date=date(2025, 5, 10),
                    end_date=date(2025, 5, 15),
                    estimated_cost=2500.00,
                    reason="Annual Global Tech Conference",
                    status="Pending"
                )

                req2 = TravelRequest(
                    requester_id=emp.id,
                    destination="Tokyo, Japan",
                    start_date=date(2025, 9, 1),
                    end_date=date(2025, 9, 7),
                    estimated_cost=3200.50,
                    reason="Meeting with Asian Pacific partners",
                    status="Approved",
                    manager_comment="Budget approved for Q3."
                )

                req3 = TravelRequest(
                    requester_id=emp.id,
                    destination="Austin, Texas",
                    start_date=date(2024, 11, 12),
                    end_date=date(2024, 11, 14),
                    estimated_cost=600.00,
                    reason="Domestic Sales Training",
                    status="Denied",
                    manager_comment="Travel freeze in effect for domestic trips."
                )

                db.session.add_all([req1, req2, req3])
                db.session.commit()
                print("Sample travel requests created.")
        else:
            print("Travel requests already exist. Skipping population.")


# -------------------------
# ROUTES
# -------------------------

@app.route('/')
def home():
    if current_user():
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


# ---- LOGIN / LOGOUT ----

@app.route('/login', methods=['GET', 'POST'])
def login():
    # If user is logged in, send to dashboard
    if current_user():
        return redirect(url_for("dashboard"))

    if request.method == 'POST':
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        found = User.query.filter_by(email=email).first()

        if found and found.check_password(password):
            session["user_id"] = found.id
            flash("Login successful.", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid email or password.", "danger")

    return render_template("login.html")


@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("login"))


# ---- DASHBOARD ----

@app.route('/dashboard')
@login_required
def dashboard():
    user = current_user()
    return render_template("dashboard.html", user=user)


# ---- CREATE NEW TRAVEL REQUEST ----

@app.route('/requests/new', methods=["GET", "POST"])
@login_required
def new_request():
    user = current_user()

    if request.method == "POST":
        destination = request.form.get("destination", "").strip()
        start = request.form.get("start_date", "")
        end = request.form.get("end_date", "")
        cost = request.form.get("estimated_cost", "")
        reason = request.form.get("reason", "").strip()

        # Basic validation
        if not destination or not start or not end or not cost or not reason:
            flash("All fields are required.", "danger")
            return render_template("new_request.html", user=user)

        try:
            start_date = date.fromisoformat(start)
            end_date = date.fromisoformat(end)
        except ValueError:
            flash("Invalid date format.", "danger")
            return render_template("new_request.html", user=user)

        try:
            estimated_cost = float(cost)
        except ValueError:
            flash("Estimated cost must be a number.", "danger")
            return render_template("new_request.html", user=user)

        tr = TravelRequest(
            requester_id=user.id,
            destination=destination,
            start_date=start_date,
            end_date=end_date,
            estimated_cost=estimated_cost,
            reason=reason,
            status="Pending"
        )

        db.session.add(tr)
        db.session.commit()

        flash("Travel request submitted.", "success")
        return redirect(url_for("my_requests"))

    return render_template("new_request.html", user=user)


# ---- VIEW MY REQUESTS ----

@app.route('/requests/my')
@login_required
def my_requests():
    user = current_user()
    status_filter = request.args.get("status", "All")

    query = TravelRequest.query.filter_by(requester_id=user.id)
    if status_filter != "All":
        query = query.filter_by(status=status_filter)

    requests_list = query.order_by(TravelRequest.submitted_on.desc()).all()
    
    # This renders my_requests.html. If this crashes, the file is missing/misnamed.
    return render_template(
        "my_requests.html",
        user=user,
        requests_list=requests_list,
        status_filter=status_filter
    )


# ---- MANAGER: VIEW / MANAGE ALL REQUESTS ----

@app.route('/requests/manage')
@manager_required
def manage_requests():
    user = current_user()
    requests_list = TravelRequest.query.order_by(TravelRequest.submitted_on.desc()).all()
    return render_template(
        "manager_requests.html",
        user=user,
        requests_list=requests_list
    )


# ---- REQUEST DETAIL + MANAGER ACTIONS ----

@app.route('/requests/<int:rid>', methods=["GET", "POST"])
@login_required
def request_detail(rid):
    user = current_user()
    tr = TravelRequest.query.get_or_404(rid)

    # Employee can only see their own
    if user.role != "manager" and tr.requester_id != user.id:
        flash("You are not allowed to view this request.", "danger")
        return redirect(url_for("dashboard"))

    if request.method == "POST" and user.role == "manager":
        action = request.form.get("action")
        comment = request.form.get("comment", "")

        if action == "approve":
            tr.status = "Approved"
        elif action == "deny":
            tr.status = "Denied"
        elif action == "settle":
            tr.status = "Settled"

        tr.manager_comment = comment
        db.session.commit()
        flash("Request updated.", "success")
        return redirect(url_for("manage_requests"))

    return render_template("request_detail.html", user=user, tr=tr)


# -------------------------
# MAIN ENTRY
# -------------------------

if __name__ == "__main__":
    setup_database()
    app.run(debug=True)