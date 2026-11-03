# Flask role-based dashboards patch

This is a replacement Flask app and templates for the uploaded Flask application.
It is NOT the Streamlit application.

## Roles
- Admin: overall dashboard; manage agents/customers; view all records; issue policies;
  record payments; approve/reject claims; manage plans.
- Agent: own dashboard; view only assigned customers and their policies/claims/payments;
  add customers; issue policies and record payments for assigned customers; submit claims.
- Customer: own dashboard; view own policies, claims and payments; view plans; submit
  claims only for their own active policies.

## Before applying
1. Back up the database.
2. Ensure `config.py` points to the intended MySQL database.
3. Run `role_dashboard_migration.sql` against `insurance_management`.
4. Copy `app.py` over your existing Flask `app.py`.
5. Copy this entire `templates/` folder into the same folder as `app.py`.
6. Install packages: `python -m pip install -r requirements.txt`.
7. Restart: `python app.py`.

## Admin account
The existing users table needs role/customer_id/agent_id/is_active columns. Existing
users are assigned role Admin by the migration default. Login with your existing
admin username and password hash. Do not use a default password in production.

## Creating accounts
- Admin dashboard has "Create Agent + Login" and "Create Customer + Login".
- Agent accounts are linked to an agent record.
- Customer login is optional when creating a customer; if username/password are entered,
  both are required and password must be at least 12 characters.
- Assign customers to agents from the Admin customer creation form.

## Important implementation notes
- The patch assumes the uploaded Flask schema columns: customers.full_name; policies.policy_no;
  claims.claim_no/reason/filed_on; payments.reference/paid_on/method.
- `database.py` and `streamlit_app.py` are not imported by this Flask app and should not be
  mixed into this deployment.
- This is a starter role-based access implementation. Before production use, add CSRF
  protection, password reset, audit logging, stronger validation, and review all business
  rules. Use HTTPS on Render and set COOKIE_SECURE=true.
