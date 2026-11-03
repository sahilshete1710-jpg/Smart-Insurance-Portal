
import streamlit as st
import mysql.connector
from config import DB_CONFIG

st.set_page_config(
    page_title="Smart Insurance Management",
    page_icon="🛡️",
    layout="wide"
)

st.title("🛡️ Smart Insurance Management System")
st.write("Insurance management dashboard")

try:
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT COUNT(*) AS total FROM customers")
    customers = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM policies")
    policies = cursor.fetchone()["total"]

    cursor.execute(
        "SELECT COUNT(*) AS total FROM claims WHERE status = 'Pending'"
    )
    claims = cursor.fetchone()["total"]

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Customers", customers)
    col2.metric("Total Policies", policies)
    col3.metric("Pending Claims", claims)

    cursor.close()
    conn.close()

except mysql.connector.Error as e:
    st.error(f"Database connection or query failed: {e}")
    st.info("Check config.py, MySQL service, and your database tables.")
