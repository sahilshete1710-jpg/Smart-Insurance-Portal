import os
import random
from datetime import date, timedelta
from functools import wraps

import mysql.connector
from flask import (
    Flask, abort, flash, redirect, render_template,
    request, session, url_for
)
from mysql.connector import Error
from werkzeug.security import check_password_hash, generate_password_hash

from config import DB_CONFIG, SECRET_KEY

app = Flask(__name__)
app.secret_key = SECRET_KEY

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get(
        "COOKIE_SECURE", "false"
    ).lower() == "true"
)


# ---------------- DATABASE CONNECTION ----------------

def run(sql, params=(), fetch=None):
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute(sql, params)

        if fetch == "one":
            return cur.fetchone()

        if fetch == "all":
            return cur.fetchall()

        conn.commit()
        return cur.lastrowid

    finally:
        cur.close()
        conn.close()


# ---------------- HELPER FUNCTIONS ----------------

@app.template_filter("money")
def money(value):
    return f"₹{float(value or 0):,.2f}"


def current_user():
    return session.get("user")


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)
    return wrapper


def roles_required(*roles):
    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapper(*args, **kwargs):
            if session.get("role") not in roles:
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def db_error(error):
    if getattr(error, "errno", None) == 1062:
        message = "Duplicate entry. This value already exists."
    else:
        message = getattr(error, "msg", str(error))

    flash(message, "error")


# ---------------- LOGIN PROTECTION ----------------

@app.before_request
def protect_pages():
    allowed = {"login", "logout", "static"}

    if request.endpoint and request.endpoint not in allowed:
        if not current_user():
            return redirect(url_for("login", next=request.path))


# ---------------- LOGIN ----------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = run(
            "SELECT * FROM users WHERE username=%s AND is_active=1",
            (username,),
            "one"
        )

        if user and check_password_hash(
            user["password_hash"], password
        ):

            session.clear()

            session["user"] = user["username"]
            session["role"] = user["role"]
            session["user_id"] = user["id"]
            session["customer_id"] = user.get("customer_id")
            session["agent_id"] = user.get("agent_id")

            target = request.args.get("next")

            if target and target.startswith("/") and not target.startswith("//"):
                return redirect(target)

            return redirect(url_for("dashboard"))

        flash("Invalid username or password.", "error")

    return render_template("login.html")


# ---------------- LOGOUT ----------------

@app.route("/logout", methods=["POST", "GET"])
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


# ---------------- ROLE REDIRECTION ----------------

@app.route("/")
@login_required
def dashboard():

    role = session.get("role")

    if role == "Admin":
        return redirect(url_for("admin_dashboard"))

    if role == "Agent":
        return redirect(url_for("agent_dashboard"))

    if role == "Customer":
        return redirect(url_for("customer_dashboard"))

    abort(403)


# ==================================================
# ADMIN DASHBOARD
# ==================================================

@app.route("/admin")
@roles_required("Admin")
def admin_dashboard():

    run("""
        UPDATE policies
        SET status='Expired'
        WHERE status='Active'
        AND end_date < CURDATE()
    """)

    stats = run("""
        SELECT
            (SELECT COUNT(*) FROM customers) AS customers,
            (SELECT COUNT(*) FROM policies
             WHERE status='Active') AS active_policies,
            (SELECT COUNT(*) FROM claims
             WHERE status='Pending') AS pending_claims,
            (SELECT COALESCE(SUM(amount),0)
             FROM payments) AS revenue,
            (SELECT COUNT(*) FROM agents) AS agents
    """, fetch="one")

    by_cat = run("""
        SELECT pl.category AS label, COUNT(*) AS n
        FROM policies po
        JOIN plans pl ON pl.id=po.plan_id
        GROUP BY pl.category
    """, fetch="all")

    by_status = run("""
        SELECT status AS label, COUNT(*) AS n
        FROM claims
        GROUP BY status
    """, fetch="all")

    return render_template(
        "admin_dashboard.html",
        stats=stats,
        by_cat=by_cat,
        by_status=by_status
    )


# ==================================================
# AGENT DASHBOARD
# ==================================================

@app.route("/agent")
@roles_required("Agent")
def agent_dashboard():

    aid = session.get("agent_id")

    if not aid:
        abort(403)

    stats = run("""
        SELECT
            (SELECT COUNT(*) FROM customers
             WHERE agent_id=%s) AS customers,

            (SELECT COUNT(*) FROM policies po
             JOIN customers c ON c.id=po.customer_id
             WHERE c.agent_id=%s) AS policies,

            (SELECT COUNT(*) FROM claims cl
             JOIN policies po ON po.id=cl.policy_id
             JOIN customers c ON c.id=po.customer_id
             WHERE c.agent_id=%s
             AND cl.status='Pending') AS pending_claims
    """, (aid, aid, aid), "one")

    customers = run("""
        SELECT id, full_name, email, phone
        FROM customers
        WHERE agent_id=%s
        ORDER BY id DESC
        LIMIT 10
    """, (aid,), "all")

    policies = run("""
        SELECT
            po.policy_no,
            po.status,
            po.end_date,
            c.full_name,
            pl.name AS plan_name
        FROM policies po
        JOIN customers c ON c.id=po.customer_id
        JOIN plans pl ON pl.id=po.plan_id
        WHERE c.agent_id=%s
        ORDER BY po.id DESC
        LIMIT 10
    """, (aid,), "all")

    return render_template(
        "agent_dashboard.html",
        stats=stats,
        customers=customers,
        policies=policies
    )


# ==================================================
# CUSTOMER DASHBOARD
# ==================================================

@app.route("/customer")
@roles_required("Customer")
def customer_dashboard():

    cid = session.get("customer_id")

    if not cid:
        abort(403)

    customer = run(
        "SELECT * FROM customers WHERE id=%s",
        (cid,),
        "one"
    )

    if not customer:
        abort(404)

    policies = run("""
        SELECT po.*, pl.name AS plan_name,
               pl.category, pl.coverage_amount
        FROM policies po
        JOIN plans pl ON pl.id=po.plan_id
        WHERE po.customer_id=%s
        ORDER BY po.id DESC
    """, (cid,), "all")

    claims = run("""
        SELECT cl.*, po.policy_no
        FROM claims cl
        JOIN policies po ON po.id=cl.policy_id
        WHERE po.customer_id=%s
        ORDER BY cl.id DESC
    """, (cid,), "all")

    payments = run("""
        SELECT pm.*, po.policy_no
        FROM payments pm
        JOIN policies po ON po.id=pm.policy_id
        WHERE po.customer_id=%s
        ORDER BY pm.id DESC
    """, (cid,), "all")

    return render_template(
        "customer_dashboard.html",
        customer=customer,
        policies=policies,
        claims=claims,
        payments=payments
    )


# ==================================================
# CUSTOMER MANAGEMENT
# ==================================================

@app.route("/customers")
@roles_required("Admin", "Agent")
def customers():

    q = request.args.get("q", "").strip()

    if session["role"] == "Agent":

        sql = """
            SELECT c.*,
            (SELECT COUNT(*) FROM policies p
             WHERE p.customer_id=c.id) AS policy_count
            FROM customers c
            WHERE c.agent_id=%s
        """

        params = (session["agent_id"],)

    else:

        sql = """
            SELECT c.*,
            (SELECT COUNT(*) FROM policies p
             WHERE p.customer_id=c.id) AS policy_count
            FROM customers c
        """

        params = ()

    if q:
        sql += (
            " AND " if "WHERE" in sql else " WHERE "
        ) + """
            (c.full_name LIKE %s
            OR c.email LIKE %s
            OR c.phone LIKE %s)
        """

        params += (f"%{q}%",) * 3

    rows = run(
        sql + " ORDER BY c.id DESC",
        params,
        "all"
    )

    return render_template(
        "customers.html",
        rows=rows,
        q=q
    )


@app.route("/customers/new", methods=["GET", "POST"])
@roles_required("Admin", "Agent")
def customer_form():

    if request.method == "POST":

        f = request.form

        agent_id = (
            session.get("agent_id")
            if session["role"] == "Agent"
            else (f.get("agent_id") or None)
        )

        try:

            cid = run("""
                INSERT INTO customers
                (full_name,email,phone,dob,address,agent_id)
                VALUES (%s,%s,%s,%s,%s,%s)
            """, (
                f["full_name"],
                f["email"],
                f["phone"],
                f.get("dob") or None,
                f.get("address") or None,
                agent_id
            ))

            username = f.get("username", "").strip()
            password = f.get("password", "")

            if username or password:

                if not username or len(password) < 12:
                    raise ValueError(
                        "Enter a username and password of at least 12 characters."
                    )

                run("""
                    INSERT INTO users
                    (username,password_hash,role,customer_id)
                    VALUES (%s,%s,'Customer',%s)
                """, (
                    username,
                    generate_password_hash(password),
                    cid
                ))

            flash("Customer added successfully.", "success")
            return redirect(url_for("customers"))

        except (Error, ValueError) as e:

            if isinstance(e, Error):
                db_error(e)
            else:
                flash(str(e), "error")

    agents = []

    if session["role"] == "Admin":
        agents = run(
            "SELECT id,name FROM agents WHERE status='Active' ORDER BY name",
            fetch="all"
        )

    return render_template(
        "customer_form.html",
        agents=agents
    )


# ==================================================
# AGENT MANAGEMENT
# ==================================================

@app.route("/agents")
@roles_required("Admin")
def agents():

    rows = run("""
        SELECT a.*,
        (SELECT COUNT(*) FROM customers c
         WHERE c.agent_id=a.id) AS customer_count
        FROM agents a
        ORDER BY a.id DESC
    """, fetch="all")

    return render_template(
        "agents.html",
        rows=rows
    )


@app.route("/agents/new", methods=["GET", "POST"])
@roles_required("Admin")
def agent_new():

    if request.method == "POST":

        f = request.form

        try:

            aid = run("""
                INSERT INTO agents
                (name,email,phone,specialization,commission,status)
                VALUES (%s,%s,%s,%s,%s,'Active')
            """, (
                f["name"],
                f["email"],
                f["phone"],
                f.get("specialization") or None,
                f.get("commission") or 0
            ))

            run("""
                INSERT INTO users
                (username,password_hash,role,agent_id)
                VALUES (%s,%s,'Agent',%s)
            """, (
                f["username"].strip(),
                generate_password_hash(f["password"]),
                aid
            ))

            flash(
                "Agent and login account created successfully.",
                "success"
            )

            return redirect(url_for("agents"))

        except Error as e:
            db_error(e)

    return render_template("agent_form.html")


# ==================================================
# INSURANCE PLANS
# ==================================================

@app.route("/plans", methods=["GET", "POST"])
@login_required
def plans():

    if request.method == "POST":

        if session["role"] != "Admin":
            abort(403)

        f = request.form

        try:

            run("""
                INSERT INTO plans
                (name,category,coverage_amount,
                 annual_premium,term_years,description)
                VALUES (%s,%s,%s,%s,%s,%s)
            """, (
                f["name"],
                f["category"],
                f["coverage_amount"],
                f["annual_premium"],
                f["term_years"],
                f.get("description") or None
            ))

            flash("Insurance plan added.", "success")

        except Error as e:
            db_error(e)

        return redirect(url_for("plans"))

    rows = run(
        "SELECT * FROM plans ORDER BY category,name",
        fetch="all"
    )

    return render_template(
        "plans.html",
        rows=rows,
        can_manage=session["role"] == "Admin"
    )


# ==================================================
# POLICY MANAGEMENT
# ==================================================

@app.route("/policies")
@roles_required("Admin", "Agent", "Customer")
def policies():

    role = session["role"]
    cid = session.get("customer_id")
    aid = session.get("agent_id")

    sql = """
        SELECT po.*, c.full_name,
               pl.name AS plan_name,
               pl.category
        FROM policies po
        JOIN customers c ON c.id=po.customer_id
        JOIN plans pl ON pl.id=po.plan_id
    """

    params = ()

    if role == "Customer":
        sql += " WHERE po.customer_id=%s"
        params = (cid,)

    elif role == "Agent":
        sql += " WHERE c.agent_id=%s"
        params = (aid,)

    rows = run(
        sql + " ORDER BY po.id DESC",
        params,
        "all"
    )

    return render_template(
        "policies.html",
        rows=rows,
        status=""
    )


@app.route("/policies/new", methods=["GET", "POST"])
@roles_required("Admin", "Agent")
def policy_new():

    if session["role"] == "Agent":

        custs = run("""
            SELECT id,full_name,email
            FROM customers
            WHERE agent_id=%s
            ORDER BY full_name
        """, (session["agent_id"],), "all")

    else:

        custs = run("""
            SELECT id,full_name,email
            FROM customers
            ORDER BY full_name
        """, fetch="all")

    plans_ = run(
        "SELECT * FROM plans ORDER BY category,name",
        fetch="all"
    )

    if request.method == "POST":

        f = request.form

        cust = run(
            "SELECT id FROM customers WHERE id=%s",
            (f["customer_id"],),
            "one"
        )

        if not cust:
            abort(403)

        if session["role"] == "Agent":

            assigned = run("""
                SELECT id FROM customers
                WHERE id=%s AND agent_id=%s
            """, (
                f["customer_id"],
                session["agent_id"]
            ), "one")

            if not assigned:
                abort(403)

        plan = run(
            "SELECT * FROM plans WHERE id=%s",
            (f["plan_id"],),
            "one"
        )

        if not plan:
            abort(404)

        start = date.fromisoformat(f["start_date"])

        try:
            end = start.replace(
                year=start.year + int(plan["term_years"])
            )
        except ValueError:
            end = start + timedelta(
                days=365 * int(plan["term_years"])
            )

        for _ in range(5):

            policy_no = (
                f"POL{start:%y%m}{random.randint(10000,99999)}"
            )

            try:

                run("""
                    INSERT INTO policies
                    (policy_no,customer_id,plan_id,
                     start_date,end_date,premium)
                    VALUES (%s,%s,%s,%s,%s,%s)
                """, (
                    policy_no,
                    f["customer_id"],
                    plan["id"],
                    start,
                    end,
                    plan["annual_premium"]
                ))

                flash(
                    f"Policy {policy_no} issued successfully.",
                    "success"
                )

                return redirect(url_for("policies"))

            except Error as e:

                if e.errno == 1062:
                    continue

                db_error(e)
                break

    return render_template(
        "policy_form.html",
        custs=custs,
        plans=plans_,
        today=date.today(),
        can_issue=True
    )


# ==================================================
# CLAIM MANAGEMENT
# ==================================================

@app.route("/claims")
@roles_required("Admin", "Agent", "Customer")
def claims():

    role = session["role"]

    sql = """
        SELECT cl.*,po.policy_no,c.full_name,
               pl.coverage_amount
        FROM claims cl
        JOIN policies po ON po.id=cl.policy_id
        JOIN customers c ON c.id=po.customer_id
        JOIN plans pl ON pl.id=po.plan_id
    """

    params = ()

    if role == "Customer":
        sql += " WHERE po.customer_id=%s"
        params = (session["customer_id"],)

    elif role == "Agent":
        sql += " WHERE c.agent_id=%s"
        params = (session["agent_id"],)

    rows = run(
        sql + " ORDER BY cl.id DESC",
        params,
        "all"
    )

    return render_template(
        "claims.html",
        rows=rows,
        status=""
    )


@app.route("/claims/new", methods=["GET", "POST"])
@roles_required("Admin", "Agent", "Customer")
def claim_new():

    role = session["role"]

    sql = """
        SELECT po.id,po.policy_no,c.full_name,
               pl.name AS plan_name,
               pl.coverage_amount
        FROM policies po
        JOIN customers c ON c.id=po.customer_id
        JOIN plans pl ON pl.id=po.plan_id
        WHERE po.status='Active'
    """

    params = ()

    if role == "Customer":
        sql += " AND po.customer_id=%s"
        params = (session["customer_id"],)

    elif role == "Agent":
        sql += " AND c.agent_id=%s"
        params = (session["agent_id"],)

    pols = run(
        sql + " ORDER BY po.policy_no",
        params,
        "all"
    )

    if request.method == "POST":

        f = request.form

        pol = next(
            (p for p in pols
             if str(p["id"]) == f.get("policy_id")),
            None
        )

        try:

            amount = float(f["claim_amount"])

            if (
                not pol
                or amount <= 0
                or amount > float(pol["coverage_amount"])
            ):

                flash(
                    "Select an eligible policy and enter an amount within its coverage limit.",
                    "error"
                )

            else:

                claim_no = f"CLM-{random.randint(100000,999999)}"

                run("""
                    INSERT INTO claims
                    (claim_no,policy_id,claim_amount,
                     reason,filed_on)
                    VALUES (%s,%s,%s,%s,CURDATE())
                """, (
                    claim_no,
                    pol["id"],
                    amount,
                    f["reason"]
                ))

                flash(
                    f"Claim {claim_no} submitted successfully.",
                    "success"
                )

                return redirect(url_for("claims"))

        except (ValueError, Error) as e:

            if isinstance(e, Error):
                db_error(e)
            else:
                flash("Enter a valid claim amount.", "error")

    return render_template(
        "claim_form.html",
        pols=pols
    )


@app.route("/claims/<int:cid>/<action>", methods=["POST"])
@roles_required("Admin")
def claim_action(cid, action):

    if action not in ("approve", "reject"):
        abort(404)

    claim = run(
        "SELECT * FROM claims WHERE id=%s",
        (cid,),
        "one"
    )

    if not claim:
        abort(404)

    if claim["status"] != "Pending":
        flash("This claim has already been processed.", "error")
        return redirect(url_for("claims"))

    if action == "approve":

        policy = run("""
            SELECT pl.coverage_amount
            FROM policies po
            JOIN plans pl ON pl.id=po.plan_id
            WHERE po.id=%s
        """, (claim["policy_id"],), "one")

        paid = run("""
            SELECT COALESCE(SUM(claim_amount),0) AS total
            FROM claims
            WHERE policy_id=%s AND status='Approved'
        """, (claim["policy_id"],), "one")["total"]

        if paid + claim["claim_amount"] > policy["coverage_amount"]:

            flash(
                "Approval would exceed policy coverage.",
                "error"
            )

            return redirect(url_for("claims"))

    status = "Approved" if action == "approve" else "Rejected"

    run("""
        UPDATE claims
        SET status=%s,remarks=%s
        WHERE id=%s
    """, (
        status,
        request.form.get("remarks") or None,
        cid
    ))

    flash(f"Claim {status.lower()}.", "success")

    return redirect(url_for("claims"))


# ==================================================
# PAYMENT MANAGEMENT
# ==================================================

@app.route("/payments")
@roles_required("Admin", "Agent", "Customer")
def payments():

    role = session["role"]

    sql = """
        SELECT pm.*,po.policy_no,c.full_name
        FROM payments pm
        JOIN policies po ON po.id=pm.policy_id
        JOIN customers c ON c.id=po.customer_id
    """

    params = ()

    if role == "Customer":
        sql += " WHERE po.customer_id=%s"
        params = (session["customer_id"],)

    elif role == "Agent":
        sql += " WHERE c.agent_id=%s"
        params = (session["agent_id"],)

    rows = run(
        sql + " ORDER BY pm.id DESC",
        params,
        "all"
    )

    total = sum(float(r["amount"]) for r in rows)

    return render_template(
        "payments.html",
        rows=rows,
        total=total
    )


@app.route("/payments/new", methods=["GET", "POST"])
@roles_required("Admin", "Agent")
def payment_new():

    if session["role"] == "Agent":

        pols = run("""
            SELECT po.id,po.policy_no,po.premium,c.full_name
            FROM policies po
            JOIN customers c ON c.id=po.customer_id
            WHERE po.status='Active'
            AND c.agent_id=%s
        """, (session["agent_id"],), "all")

    else:

        pols = run("""
            SELECT po.id,po.policy_no,po.premium,c.full_name
            FROM policies po
            JOIN customers c ON c.id=po.customer_id
            WHERE po.status='Active'
        """, fetch="all")

    if request.method == "POST":

        f = request.form

        allowed = {
            str(p["id"]) for p in pols
        }

        if f.get("policy_id") not in allowed:
            abort(403)

        try:

            run("""
                INSERT INTO payments
                (reference,policy_id,amount,paid_on,method)
                VALUES (%s,%s,%s,CURDATE(),%s)
            """, (
                f"PAY-{random.randint(100000,999999)}",
                f["policy_id"],
                f["amount"],
                f["method"]
            ))

            flash("Payment recorded successfully.", "success")

            return redirect(url_for("payments"))

        except Error as e:
            db_error(e)

    return render_template(
        "payment_form.html",
        pols=pols
    )


# ---------------- ERROR HANDLER ----------------

@app.errorhandler(403)
def forbidden(_):

    return render_template(
        "message.html",
        title="Access denied",
        message="Your account does not have permission to access this page."
    ), 403


# ---------------- RUN APPLICATION ----------------

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )