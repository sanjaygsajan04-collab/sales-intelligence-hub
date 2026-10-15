import getpass
import pandas as pd
import mysql.connector

# 1. Connect (password is typed at runtime, never saved in the file)
password = getpass.getpass("MySQL root password: ")
conn = mysql.connector.connect(
    host="localhost", user="root", password=password,
    database="sales_management_system",
)
cur = conn.cursor()

# 2. Read the CSV files (mobile numbers as text, not numbers)
branches = pd.read_csv("branches.csv")
users = pd.read_csv("users.csv")
users["branch_id"] = users["branch_id"].astype("Int64")   # allows empty values
sales_original = pd.read_csv("customer_sales.csv", dtype={"mobile_number": str})
sales = sales_original.copy()
sales["received_amount"] = 0          # the trigger will fill this in
payments = pd.read_csv("payment_splits.csv")


def to_rows(df):
    """Convert a DataFrame to a list of tuples, turning empty values into None (NULL)."""
    rows = []
    for r in df.itertuples(index=False, name=None):
        rows.append(tuple(
            None if pd.isna(v) else (v.item() if hasattr(v, "item") else v)
            for v in r
        ))
    return rows


# 3. Clear old data (children first, then parents) so the script can be re-run
for table in ["payment_splits", "users", "customer_sales", "branches"]:
    cur.execute(f"DELETE FROM {table}")

# 4. Load in the correct order
cur.executemany(
    "INSERT INTO branches (branch_id, branch_name, branch_admin_name) VALUES (%s, %s, %s)",
    to_rows(branches),
)
cur.executemany(
    "INSERT INTO users (user_id, username, password, branch_id, role, email) "
    "VALUES (%s, %s, %s, %s, %s, %s)",
    to_rows(users),
)
cur.executemany(
    "INSERT INTO customer_sales "
    "(sale_id, branch_id, `date`, name, mobile_number, product_name, gross_sales, received_amount, status) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
    to_rows(sales),
)
cur.executemany(
    "INSERT INTO payment_splits (payment_id, sale_id, payment_date, amount_paid, payment_method) "
    "VALUES (%s, %s, %s, %s, %s)",
    to_rows(payments),
)
conn.commit()

# 5. Check the row counts
for table in ["branches", "users", "customer_sales", "payment_splits"]:
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    print(f"{table}: {cur.fetchone()[0]} rows")

# 6. Show what the trigger calculated
cur.execute("SELECT COUNT(*), SUM(gross_sales), SUM(received_amount), SUM(pending_amount) FROM customer_sales")
print("sales count, gross, received, pending:", cur.fetchone())

cur.execute("SELECT DISTINCT payment_method FROM payment_splits")
print("payment methods:", [r[0] for r in cur.fetchall()])

cur.execute("SELECT COUNT(*) - COUNT(DISTINCT mobile_number) FROM customer_sales")
print("repeated mobile numbers:", cur.fetchone()[0])

cur.execute("SELECT COUNT(*) FROM customer_sales WHERE pending_amount < 0")
print("sales with negative pending (overpaid):", cur.fetchone()[0])

cur.execute("SELECT status, COUNT(*) FROM customer_sales GROUP BY status")
print("status counts:", cur.fetchall())

cur.close()
conn.close()