# Sales Intelligence Hub

A branch-based sales management system built with **MySQL, Python and Streamlit**.
It tracks sales across branches, supports split payments, and updates received and
pending amounts automatically using a database trigger and a generated column.

## Features
- Login and logout with session handling
- Role-based access: Super Admin (all branches) and Admin (own branch only)
- KPI cards: total sales, received, pending, collection %
- Sales report with branch filter, pending payments, Open vs Close status
- Add a new sale and add split payments
- Insights: payment method summary, branch comparison, monthly sales trend
- Predefined SQL queries runner (Super Admin)

## Database design
| Table | Purpose |
|---|---|
| branches | Branch name and admin |
| users | Login accounts with role (Super Admin / Admin) |
| customer_sales | Sales; `pending_amount` is a generated column |
| payment_splits | Multiple payments per sale |

Relationships: branches (1) to (many) customer_sales, customer_sales (1) to (many)
payment_splits, branches (1) to (many) users.

## Automation
- `pending_amount = gross_sales - received_amount` is a **STORED generated column**.
- An **AFTER INSERT trigger** on `payment_splits` recalculates the total paid for the
  sale, updates `received_amount`, and sets `status` to Close when fully paid.
- `received_amount` is never updated manually.

## Project files
| File | Description |
|---|---|
| schema.sql | Creates the database and tables |
| triggers.sql | Creates the payment trigger |
| load_data.py | Loads the CSV data (trigger fills received_amount) |
| queries.sql | 15 analytical SQL queries |
| db.py | Python-MySQL connection helpers |
| app.py | Streamlit dashboard |

## How to run
1. Install MySQL 8 and Python 3.9+.
2. `pip install streamlit pandas mysql-connector-python`
3. Create the schema and trigger:
   `mysql -u root -p < schema.sql` then `mysql -u root -p < triggers.sql`
4. Put the CSV files in the project folder and run `python load_data.py`.
5. Set your MySQL password in `db.py`.
6. Start the app: `streamlit run app.py`

## Demo logins
| Username | Password | Role |
|---|---|---|
| superadmin | super123 | Super Admin |
| admin_chennai | admin123 | Admin (Chennai) |

(Demo data only. A production system would store hashed passwords.)

## Key insights
- Total gross sales: 36,768,000; received: 19,028,113; pending: 17,739,887
  (about 52% collected, 48% pending).
- Kolkata has the highest revenue; Mumbai has the most sales by count.
- Payments are spread almost equally across Card, Cash and UPI.

## Notes
- `mobile_number` is UNIQUE as required, so one customer has one sale record.
- Overpayment is blocked in the app (payment cannot exceed the pending balance).