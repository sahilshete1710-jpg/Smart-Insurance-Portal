# Smart Insurance Management System (Flask + MySQL)

## Features
- Admin login (hashed password)
- Dashboard: KPIs, charts (policies by category, claims by status), policies expiring in 30 days
- Customers: add / edit / delete / search
- Plans: Health, Life, Vehicle, Home, Travel with coverage, premium and term
- Policies: auto policy number, auto end date and premium from the plan, cancel, auto-expire
- Claims: file (validated against coverage), approve / reject with remarks,
  approval blocked if total approved claims would exceed coverage
- Payments: record premium payments, running total

## Setup (Windows)
1. **MySQL Workbench**: connect to your server -> File > Open SQL Script -> `schema.sql` -> run all.
   This creates database `smart_insurance`, tables and sample data.
2. Edit `config.py`: set your MySQL `user` and `password`.
3. In PowerShell, inside this folder:
   ```
   python -m pip install -r requirements.txt
   python app.py
   ```
4. Open http://127.0.0.1:5000 and log in with **admin / admin123**.

## Troubleshooting
- Access denied -> wrong password in config.py
- Unknown database -> run schema.sql first
- Auth plugin error -> in Workbench:
  `ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY 'your_password';`
- Charts blank -> the dashboard loads Chart.js from a CDN, so it needs internet access.

## Database (ER summary)
customers 1--N policies N--1 plans ; policies 1--N claims ; policies 1--N payments ; users (admin login)
