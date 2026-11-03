
import mysql.connector
from werkzeug.security import generate_password_hash
from getpass import getpass
from config import DB_CONFIG


def create_account():
    print("\n===== SMART INSURANCE ACCOUNT CREATION =====")
    print("1. Admin")
    print("2. Agent")
    print("3. Customer")

    choice = input("\nSelect account type (1-3): ").strip()

    roles = {
        "1": "Admin",
        "2": "Agent",
        "3": "Customer"
    }

    if choice not in roles:
        print("Invalid account type.")
        return

    role = roles[choice]

    username = input("Enter username: ").strip()

    if not username:
        print("Username cannot be empty.")
        return

    password = getpass("Enter password: ")

    if len(password) < 8:
        print("Password must contain at least 8 characters.")
        return

    confirm = getpass("Confirm password: ")

    if password != confirm:
        print("Passwords do not match.")
        return

    password_hash = generate_password_hash(password)

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT id FROM users WHERE username = %s",
            (username,)
        )

        if cursor.fetchone():
            print("Username already exists.")
            return

        customer_id = None
        agent_id = None

        if role == "Agent":
            print("\n--- Agent Details ---")
            name = input("Full name: ").strip()
            email = input("Email: ").strip()
            phone = input("Phone: ").strip()
            specialization = input("Specialization: ").strip()
            commission = input("Commission: ").strip() or "0"

            if not name:
                print("Agent name is required.")
                return

            cursor.execute("""
                INSERT INTO agents
                (name, email, phone, specialization, commission, status)
                VALUES (%s, %s, %s, %s, %s, 'Active')
            """, (
                name, email or None, phone or None,
                specialization or None, commission
            ))

            agent_id = cursor.lastrowid

        elif role == "Customer":
            print("\n--- Customer Details ---")
            name = input("Full name: ").strip()
            email = input("Email: ").strip()
            phone = input("Phone: ").strip()
            dob = input("Date of birth (YYYY-MM-DD, optional): ").strip()
            address = input("Address: ").strip()

            if not name or not email or not phone:
                print("Name, email and phone are required.")
                return

            cursor.execute("""
                INSERT INTO customers
                (full_name, email, phone, dob, address)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                name, email, phone,
                dob or None, address or None
            ))

            customer_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO users
            (username, password_hash, role, customer_id, agent_id, is_active)
            VALUES (%s, %s, %s, %s, %s, 1)
        """, (
            username, password_hash, role,
            customer_id, agent_id
        ))

        conn.commit()

        print("\nAccount created successfully!")
        print("Username:", username)
        print("Role:", role)
        print("Login password was securely hashed.")

    except Exception as error:
        conn.rollback()
        print("\nAccount creation failed:", error)

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    create_account()
