try:
    import importlib

    mysql = importlib.import_module("mysql.connector")
    Error = mysql.Error
except ModuleNotFoundError:
    mysql = None

    class Error(Exception):
        """Fallback error raised when MySQL connector is unavailable."""

    mysql = None

from datetime import datetime
import hashlib


# =========================================================
# MYSQL CONFIGURATION
# =========================================================
# Change the password if your MySQL root password is different.

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "root123",
    "database": "insurance_management",
}


# =========================================================
# DATABASE CONNECTION
# =========================================================
def get_connection():
    """Create and return a MySQL database connection."""
    if mysql is None:
        print("mysql-connector-python is not installed. Install it with: pip install mysql-connector-python")
        return None

    try:
        connection = mysql.connector.connect(**DB_CONFIG)

        if connection.is_connected():
            return connection

    except Error as e:
        print("MySQL Connection Error:", e)

    return None


# =========================================================
# PASSWORD HASHING
# =========================================================
def hash_password(password):
    """Return SHA-256 hash of a password."""
    return hashlib.sha256(str(password).encode("utf-8")).hexdigest()


# =========================================================
# INITIALIZE DATABASE TABLES
# =========================================================
def init_db():
    """Create all required tables and the default admin account."""

    conn = get_connection()

    if conn is None:
        return False

    cursor = None

    try:
        cursor = conn.cursor()

        # -------------------------------------------------
        # USERS
        # -------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(100) NOT NULL UNIQUE,
                password VARCHAR(255) NOT NULL,
                full_name VARCHAR(150) NOT NULL,
                role VARCHAR(50) NOT NULL,
                email VARCHAR(150),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB
        """)

        # -------------------------------------------------
        # CUSTOMERS
        # -------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(150) NOT NULL,
                email VARCHAR(150),
                phone VARCHAR(30),
                address TEXT,
                dob DATE,
                gender VARCHAR(30),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB
        """)

        # -------------------------------------------------
        # POLICIES
        # -------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS policies (
                id INT AUTO_INCREMENT PRIMARY KEY,
                policy_number VARCHAR(100) NOT NULL UNIQUE,
                customer_id INT,
                policy_name VARCHAR(150) NOT NULL,
                category VARCHAR(100) NOT NULL,
                premium DECIMAL(15,2) DEFAULT 0,
                coverage_amount DECIMAL(15,2) DEFAULT 0,
                start_date DATE,
                end_date DATE,
                status VARCHAR(50) DEFAULT 'Active',

                CONSTRAINT fk_policy_customer
                    FOREIGN KEY (customer_id)
                    REFERENCES customers(id)
                    ON DELETE SET NULL
                    ON UPDATE CASCADE
            ) ENGINE=InnoDB
        """)

        # -------------------------------------------------
        # AGENTS
        # -------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(150) NOT NULL,
                email VARCHAR(150),
                phone VARCHAR(30),
                specialization VARCHAR(100),
                commission DECIMAL(10,2) DEFAULT 0,
                status VARCHAR(50) DEFAULT 'Active',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB
        """)

        # -------------------------------------------------
        # CLAIMS
        # -------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS claims (
                id INT AUTO_INCREMENT PRIMARY KEY,
                claim_number VARCHAR(100) NOT NULL UNIQUE,
                customer_id INT,
                policy_id INT,
                claim_amount DECIMAL(15,2) DEFAULT 0,
                claim_date DATE,
                description TEXT,
                status VARCHAR(50) DEFAULT 'Pending',

                CONSTRAINT fk_claim_customer
                    FOREIGN KEY (customer_id)
                    REFERENCES customers(id)
                    ON DELETE SET NULL
                    ON UPDATE CASCADE,

                CONSTRAINT fk_claim_policy
                    FOREIGN KEY (policy_id)
                    REFERENCES policies(id)
                    ON DELETE SET NULL
                    ON UPDATE CASCADE
            ) ENGINE=InnoDB
        """)

        # -------------------------------------------------
        # PAYMENTS
        # -------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INT AUTO_INCREMENT PRIMARY KEY,
                payment_number VARCHAR(100) NOT NULL UNIQUE,
                customer_id INT,
                policy_id INT,
                amount DECIMAL(15,2) DEFAULT 0,
                payment_date DATE,
                payment_method VARCHAR(50),
                status VARCHAR(50) DEFAULT 'Paid',

                CONSTRAINT fk_payment_customer
                    FOREIGN KEY (customer_id)
                    REFERENCES customers(id)
                    ON DELETE SET NULL
                    ON UPDATE CASCADE,

                CONSTRAINT fk_payment_policy
                    FOREIGN KEY (policy_id)
                    REFERENCES policies(id)
                    ON DELETE SET NULL
                    ON UPDATE CASCADE
            ) ENGINE=InnoDB
        """)

        # -------------------------------------------------
        # DEFAULT ADMIN
        # Username: admin
        # Password: admin123
        # -------------------------------------------------
        cursor.execute(
            "SELECT id FROM users WHERE username = %s",
            ("admin",)
        )

        if cursor.fetchone() is None:
            cursor.execute("""
                INSERT INTO users
                    (username, password, full_name, role, email, created_at)
                VALUES
                    (%s, %s, %s, %s, %s, %s)
            """, (
                "admin",
                hash_password("admin123"),
                "System Administrator",
                "Admin",
                "admin@insurance.com",
                datetime.now(),
            ))

        conn.commit()
        return True

    except Error as e:
        print("Database Initialization Error:", e)
        conn.rollback()
        return False

    finally:
        if cursor is not None:
            cursor.close()
        conn.close()


# =========================================================
# LOGIN
# =========================================================
def authenticate_user(username, password):
    """Return user dictionary if login is valid, otherwise None."""

    conn = get_connection()

    if conn is None:
        return None

    cursor = None

    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT id, username, full_name, role, email, created_at
            FROM users
            WHERE username = %s
              AND password = %s
        """, (
            username,
            hash_password(password),
        ))

        return cursor.fetchone()

    except Error as e:
        print("Authentication Error:", e)
        return None

    finally:
        if cursor is not None:
            cursor.close()
        conn.close()


# =========================================================
# USERS
# =========================================================
def add_user(username, password, full_name, role, email):
    conn = get_connection()

    if conn is None:
        return False

    cursor = None

    try:
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO users
                (username, password, full_name, role, email, created_at)
            VALUES
                (%s, %s, %s, %s, %s, %s)
        """, (
            username,
            hash_password(password),
            full_name,
            role,
            email,
            datetime.now(),
        ))

        conn.commit()
        return True

    except Error as e:
        print("Add User Error:", e)
        conn.rollback()
        return False

    finally:
        if cursor is not None:
            cursor.close()
        conn.close()


def get_users():
    conn = get_connection()

    if conn is None:
        return []

    cursor = None

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, username, full_name, role, email, created_at
            FROM users
            ORDER BY id DESC
        """)
        return cursor.fetchall()

    except Error as e:
        print("Get Users Error:", e)
        return []

    finally:
        if cursor is not None:
            cursor.close()
        conn.close()


# =========================================================
# CUSTOMERS
# =========================================================
def add_customer(name, email, phone, address, dob, gender):
    conn = get_connection()

    if conn is None:
        return False

    cursor = None

    try:
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO customers
                (name, email, phone, address, dob, gender, created_at)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s)
        """, (
            name,
            email,
            phone,
            address,
            dob,
            gender,
            datetime.now(),
        ))

        conn.commit()
        return True

    except Error as e:
        print("Add Customer Error:", e)
        conn.rollback()
        return False

    finally:
        if cursor is not None:
            cursor.close()
        conn.close()


def get_customers():
    conn = get_connection()

    if conn is None:
        return []

    cursor = None

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT *
            FROM customers
            ORDER BY id DESC
        """)
        return cursor.fetchall()

    except Error as e:
        print("Get Customers Error:", e)
        return []

    finally:
        if cursor is not None:
            cursor.close()
        conn.close()


def update_customer(customer_id, name, email, phone, address, dob, gender):
    conn = get_connection()

    if conn is None:
        return False

    cursor = None

    try:
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE customers
            SET name = %s,
                email = %s,
                phone = %s,
                address = %s,
                dob = %s,
                gender = %s
            WHERE id = %s
        """, (
            name, email, phone, address, dob, gender, customer_id
        ))

        conn.commit()
        return cursor.rowcount > 0

    except Error as e:
        print("Update Customer Error:", e)
        conn.rollback()
        return False

    finally:
        if cursor is not None:
            cursor.close()
        conn.close()


def delete_customer(customer_id):
    conn = get_connection()

    if conn is None:
        return False

    cursor = None

    try:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM customers WHERE id = %s",
            (customer_id,)
        )
        conn.commit()
        return cursor.rowcount > 0

    except Error as e:
        print("Delete Customer Error:", e)
        conn.rollback()
        return False

    finally:
        if cursor is not None:
            cursor.close()
        conn.close()


# =========================================================
# POLICIES
# =========================================================
def add_policy(
    policy_number,
    customer_id,
    policy_name,
    category,
    premium,
    coverage_amount,
    start_date,
    end_date,
    status="Active",
):
    conn = get_connection()

    if conn is None:
        return False

    cursor = None

    try:
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO policies
                (
                    policy_number,
                    customer_id,
                    policy_name,
                    category,
                    premium,
                    coverage_amount,
                    start_date,
                    end_date,
                    status
                )
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            policy_number,
            customer_id,
            policy_name,
            category,
            premium,
            coverage_amount,
            start_date,
            end_date,
            status,
        ))

        conn.commit()
        return True

    except Error as e:
        print("Add Policy Error:", e)
        conn.rollback()
        return False

    finally:
        if cursor is not None:
            cursor.close()
        conn.close()


def get_policies():
    conn = get_connection()

    if conn is None:
        return []

    cursor = None

    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                policies.*,
                customers.name AS customer_name
            FROM policies
            LEFT JOIN customers
                ON policies.customer_id = customers.id
            ORDER BY policies.id DESC
        """)

        return cursor.fetchall()

    except Error as e:
        print("Get Policies Error:", e)
        return []

    finally:
        if cursor is not None:
            cursor.close()
        conn.close()


def update_policy(
    policy_id,
    policy_number,
    customer_id,
    policy_name,
    category,
    premium,
    coverage_amount,
    start_date,
    end_date,
    status,
):
    conn = get_connection()

    if conn is None:
        return False

    cursor = None

    try:
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE policies
            SET policy_number = %s,
                customer_id = %s,
                policy_name = %s,
                category = %s,
                premium = %s,
                coverage_amount = %s,
                start_date = %s,
                end_date = %s,
                status = %s
            WHERE id = %s
        """, (
            policy_number,
            customer_id,
            policy_name,
            category,
            premium,
            coverage_amount,
            start_date,
            end_date,
            status,
            policy_id,
        ))

        conn.commit()
        return cursor.rowcount > 0

    except Error as e:
        print("Update Policy Error:", e)
        conn.rollback()
        return False

    finally:
        if cursor is not None:
            cursor.close()
        conn.close()


def delete_policy(policy_id):
    conn = get_connection()

    if conn is None:
        return False

    cursor = None

    try:
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM policies WHERE id = %s",
            (policy_id,)
        )

        conn.commit()
        return cursor.rowcount > 0

    except Error as e:
        print("Delete Policy Error:", e)
        conn.rollback()
        return False

    finally:
        if cursor is not None:
            cursor.close()
        conn.close()


# =========================================================
# AGENTS
# =========================================================
def add_agent(
    name,
    email,
    phone,
    specialization,
    commission,
    status="Active",
):
    conn = get_connection()

    if conn is None:
        return False

    cursor = None

    try:
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO agents
                (
                    name,
                    email,
                    phone,
                    specialization,
                    commission,
                    status,
                    created_at
                )
            VALUES
                (%s, %s, %s, %s, %s, %s, %s)
        """, (
            name,
            email,
            phone,
            specialization,
            commission,
            status,
            datetime.now(),
        ))

        conn.commit()
        return True

    except Error as e:
        print("Add Agent Error:", e)
        conn.rollback()
        return False

    finally:
        if cursor is not None:
            cursor.close()
        conn.close()


def get_agents():
    conn = get_connection()

    if conn is None:
        return []

    cursor = None

    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT *
            FROM agents
            ORDER BY id DESC
        """)

        return cursor.fetchall()

    except Error as e:
        print("Get Agents Error:", e)
        return []

    finally:
        if cursor is not None:
            cursor.close()
        conn.close()


def update_agent(
    agent_id,
    name,
    email,
    phone,
    specialization,
    commission,
    status,
):
    conn = get_connection()

    if conn is None:
        return False

    cursor = None

    try:
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE agents
            SET name = %s,
                email = %s,
                phone = %s,
                specialization = %s,
                commission = %s,
                status = %s
            WHERE id = %s
        """, (
            name,
            email,
            phone,
            specialization,
            commission,
            status,
            agent_id,
        ))

        conn.commit()
        return cursor.rowcount > 0

    except Error as e:
        print("Update Agent Error:", e)
        conn.rollback()
        return False

    finally:
        if cursor is not None:
            cursor.close()
        conn.close()


def delete_agent(agent_id):
    conn = get_connection()

    if conn is None:
        return False

    cursor = None

    try:
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM agents WHERE id = %s",
            (agent_id,)
        )

        conn.commit()
        return cursor.rowcount > 0

    except Error as e:
        print("Delete Agent Error:", e)
        conn.rollback()
        return False

    finally:
        if cursor is not None:
            cursor.close()
        conn.close()


# =========================================================
# CLAIMS
# =========================================================
def add_claim(
    claim_number,
    customer_id,
    policy_id,
    claim_amount,
    claim_date,
    description,
):
    conn = get_connection()

    if conn is None:
        return False

    cursor = None

    try:
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO claims
                (
                    claim_number,
                    customer_id,
                    policy_id,
                    claim_amount,
                    claim_date,
                    description,
                    status
                )
            VALUES
                (%s, %s, %s, %s, %s, %s, %s)
        """, (
            claim_number,
            customer_id,
            policy_id,
            claim_amount,
            claim_date,
            description,
            "Pending",
        ))

        conn.commit()
        return True

    except Error as e:
        print("Add Claim Error:", e)
        conn.rollback()
        return False

    finally:
        if cursor is not None:
            cursor.close()
        conn.close()


def get_claims():
    conn = get_connection()

    if conn is None:
        return []

    cursor = None

    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                claims.*,
                customers.name AS customer_name,
                policies.policy_number
            FROM claims
            LEFT JOIN customers
                ON claims.customer_id = customers.id
            LEFT JOIN policies
                ON claims.policy_id = policies.id
            ORDER BY claims.id DESC
        """)

        return cursor.fetchall()

    except Error as e:
        print("Get Claims Error:", e)
        return []

    finally:
        if cursor is not None:
            cursor.close()
        conn.close()


def update_claim_status(claim_id, status):
    conn = get_connection()

    if conn is None:
        return False

    cursor = None

    try:
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE claims
            SET status = %s
            WHERE id = %s
        """, (status, claim_id))

        conn.commit()
        return cursor.rowcount > 0

    except Error as e:
        print("Update Claim Status Error:", e)
        conn.rollback()
        return False

    finally:
        if cursor is not None:
            cursor.close()
        conn.close()


def delete_claim(claim_id):
    conn = get_connection()

    if conn is None:
        return False

    cursor = None

    try:
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM claims WHERE id = %s",
            (claim_id,)
        )

        conn.commit()
        return cursor.rowcount > 0

    except Error as e:
        print("Delete Claim Error:", e)
        conn.rollback()
        return False

    finally:
        if cursor is not None:
            cursor.close()
        conn.close()


# =========================================================
# PAYMENTS
# =========================================================
def add_payment(
    payment_number,
    customer_id,
    policy_id,
    amount,
    payment_date,
    payment_method,
):
    conn = get_connection()

    if conn is None:
        return False

    cursor = None

    try:
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO payments
                (
                    payment_number,
                    customer_id,
                    policy_id,
                    amount,
                    payment_date,
                    payment_method,
                    status
                )
            VALUES
                (%s, %s, %s, %s, %s, %s, %s)
        """, (
            payment_number,
            customer_id,
            policy_id,
            amount,
            payment_date,
            payment_method,
            "Paid",
        ))

        conn.commit()
        return True

    except Error as e:
        print("Add Payment Error:", e)
        conn.rollback()
        return False

    finally:
        if cursor is not None:
            cursor.close()
        conn.close()


def get_payments():
    conn = get_connection()

    if conn is None:
        return []

    cursor = None

    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                payments.*,
                customers.name AS customer_name,
                policies.policy_number
            FROM payments
            LEFT JOIN customers
                ON payments.customer_id = customers.id
            LEFT JOIN policies
                ON payments.policy_id = policies.id
            ORDER BY payments.id DESC
        """)

        return cursor.fetchall()

    except Error as e:
        print("Get Payments Error:", e)
        return []

    finally:
        if cursor is not None:
            cursor.close()
        conn.close()


# =========================================================
# DASHBOARD STATISTICS
# =========================================================
def get_dashboard_stats():
    conn = get_connection()

    if conn is None:
        return {
            "customers": 0,
            "policies": 0,
            "claims": 0,
            "pending_claims": 0,
            "agents": 0,
            "revenue": 0.0,
        }

    cursor = None

    try:
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM customers")
        customers = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM policies")
        policies = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM claims")
        claims = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*)
            FROM claims
            WHERE status = 'Pending'
        """)
        pending_claims = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM agents")
        agents = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0)
            FROM payments
            WHERE status = 'Paid'
        """)
        revenue = cursor.fetchone()[0]

        return {
            "customers": customers,
            "policies": policies,
            "claims": claims,
            "pending_claims": pending_claims,
            "agents": agents,
            "revenue": float(revenue or 0),
        }

    except Error as e:
        print("Dashboard Statistics Error:", e)
        return {
            "customers": 0,
            "policies": 0,
            "claims": 0,
            "pending_claims": 0,
            "agents": 0,
            "revenue": 0.0,
        }

    finally:
        if cursor is not None:
            cursor.close()
        conn.close()


# =========================================================
# POLICY CATEGORY REPORT
# =========================================================
def get_policy_categories():
    conn = get_connection()

    if conn is None:
        return []

    cursor = None

    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                category,
                COUNT(*) AS total
            FROM policies
            GROUP BY category
            ORDER BY total DESC
        """)

        return cursor.fetchall()

    except Error as e:
        print("Policy Category Error:", e)
        return []

    finally:
        if cursor is not None:
            cursor.close()
        conn.close()


# =========================================================
# CLAIM STATUS REPORT
# =========================================================
def get_claim_status():
    conn = get_connection()

    if conn is None:
        return []

    cursor = None

    try:
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                status,
                COUNT(*) AS total
            FROM claims
            GROUP BY status
            ORDER BY total DESC
        """)

        return cursor.fetchall()

    except Error as e:
        print("Claim Status Error:", e)
        return []

    finally:
        if cursor is not None:
            cursor.close()
        conn.close()


# =========================================================
# TEST CONNECTION
# =========================================================
if __name__ == "__main__":
    print("Testing Insurance Management System database...")

    connection = get_connection()

    if connection:
        print("MySQL connection successful.")
        connection.close()

        if init_db():
            print("Database tables initialized successfully.")
            print("Default login:")
            print("Username: admin")
            print("Password: admin123")
        else:
            print("Database initialization failed.")
    else:
        print("Could not connect to MySQL.")
        print("Check MySQL service, username, password, and database name.")