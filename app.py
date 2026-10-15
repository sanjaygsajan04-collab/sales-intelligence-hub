import pandas as pd
import streamlit as st
from db import run_query, run_command

st.set_page_config(page_title="Sales Intelligence Hub", layout="wide")

MONEY_COLUMNS = ["gross_sales", "received_amount", "pending_amount"]


# ---------- Login ----------
def login(username, password):
    """Check the credentials against the users table. Returns a dict or None."""
    df = run_query(
        "SELECT user_id, username, role, branch_id FROM users "
        "WHERE username = %s AND password = %s",
        params=(username, password),
    )
    if df.empty:
        return None
    row = df.iloc[0]
    return {
        "user_id": int(row["user_id"]),
        "username": row["username"],
        "role": row["role"],
        "branch_id": None if pd.isna(row["branch_id"]) else int(row["branch_id"]),
    }


def show_login_page():
    st.title("Sales Intelligence Hub")
    st.subheader("Please log in")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
    if submitted:
        user = login(username, password)
        if user:
            st.session_state["user"] = user
            st.rerun()
        else:
            st.error("Invalid username or password")


# ---------- Data helpers ----------
def get_branch_name(branch_id):
    df = run_query("SELECT branch_name FROM branches WHERE branch_id = %s", params=(branch_id,))
    return df.iloc[0]["branch_name"]


def get_all_branch_names():
    df = run_query("SELECT branch_name FROM branches ORDER BY branch_name")
    return df["branch_name"].tolist()


def load_sales(branch_name):
    """Load sales with branch name. branch_name = 'All Branches' loads everything."""
    sql = (
        "SELECT s.sale_id, s.`date`, s.name, s.mobile_number, b.branch_name, "
        "s.product_name, s.gross_sales, s.received_amount, s.pending_amount, s.status "
        "FROM customer_sales s JOIN branches b ON s.branch_id = b.branch_id"
    )
    params = None
    if branch_name != "All Branches":
        sql += " WHERE b.branch_name = %s"
        params = (branch_name,)
    sql += " ORDER BY s.sale_id"
    df = run_query(sql, params=params)
    for col in MONEY_COLUMNS:
        df[col] = df[col].astype(float)
    return df


def money(value):
    return f"₹{value:,.0f}"


# ---------- Data entry ----------
def add_sale(branch_id, sale_date, name, mobile, product, gross):
    """Insert a new sale. received_amount starts at 0 and pending_amount is generated."""
    return run_command(
        "INSERT INTO customer_sales "
        "(branch_id, `date`, name, mobile_number, product_name, gross_sales) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        params=(branch_id, sale_date, name, mobile, product, gross),
    )


def add_payment(sale_id, pay_date, amount, method):
    """Insert a payment. The database trigger updates received_amount and status."""
    return run_command(
        "INSERT INTO payment_splits (sale_id, payment_date, amount_paid, payment_method) "
        "VALUES (%s, %s, %s, %s)",
        params=(sale_id, pay_date, amount, method),
    )


def show_add_sale_form(user):
    st.subheader("Add a New Sale")
    branches = run_query("SELECT branch_id, branch_name FROM branches ORDER BY branch_name")

    if user["role"] == "Super Admin":
        names = branches["branch_name"].tolist()
        chosen = st.selectbox("Branch", names, key="sale_branch")
        branch_id = int(branches[branches["branch_name"] == chosen].iloc[0]["branch_id"])
    else:
        branch_id = user["branch_id"]
        st.write(f"Branch: **{get_branch_name(branch_id)}**")

    with st.form("add_sale_form", clear_on_submit=True):
        sale_date = st.date_input("Date")
        name = st.text_input("Customer name")
        mobile = st.text_input("Mobile number")
        product = st.selectbox("Product", ["DS", "DA", "BA", "FSD", "ML", "AI"])
        gross = st.number_input("Gross sales amount", min_value=1.0, step=1000.0)
        submitted = st.form_submit_button("Add Sale")

    if submitted:
        if not name.strip() or not mobile.strip():
            st.error("Customer name and mobile number are required.")
            return
        try:
            new_id = add_sale(branch_id, sale_date, name.strip(), mobile.strip(), product, gross)
            st.success(f"Sale added. New sale ID: {new_id}")
        except Exception as e:
            st.error(f"Could not add the sale: {e}")


def show_add_payment_form(user):
    st.subheader("Add a Payment")
    sql = (
        "SELECT s.sale_id, s.name, b.branch_name, s.gross_sales, s.pending_amount "
        "FROM customer_sales s JOIN branches b ON s.branch_id = b.branch_id "
        "WHERE s.status = 'Open'"
    )
    params = None
    if user["role"] == "Admin":
        sql += " AND s.branch_id = %s"
        params = (user["branch_id"],)
    sql += " ORDER BY s.sale_id DESC LIMIT 200"
    open_sales = run_query(sql, params=params)

    if open_sales.empty:
        st.info("There are no open sales to add a payment to.")
        return

    labels = {
        int(r.sale_id): f"#{int(r.sale_id)} - {r.name} ({r.branch_name}) - pending ₹{float(r.pending_amount):,.0f}"
        for r in open_sales.itertuples()
    }
    sale_id = st.selectbox("Sale", list(labels.keys()), format_func=lambda k: labels[k])
    pending = float(open_sales[open_sales["sale_id"] == sale_id].iloc[0]["pending_amount"])
    st.write(f"Pending balance: **₹{pending:,.2f}**")

    with st.form("add_payment_form", clear_on_submit=True):
        pay_date = st.date_input("Payment date")
        amount = st.number_input("Amount paid", min_value=1.0, step=500.0)
        method = st.selectbox("Payment method", ["Cash", "UPI", "Card"])
        submitted = st.form_submit_button("Add Payment")

    if submitted:
        if amount > pending:
            st.error(f"Amount cannot be more than the pending balance of ₹{pending:,.2f}.")
            return
        try:
            add_payment(sale_id, pay_date, amount, method)
            st.success("Payment added. Received and pending amounts were updated by the trigger.")
        except Exception as e:
            st.error(f"Could not add the payment: {e}")


# ---------- Insights ----------
def load_payment_summary(branch_name):
    sql = (
        "SELECT p.payment_method, COUNT(*) AS number_of_payments, "
        "SUM(p.amount_paid) AS total_collected "
        "FROM payment_splits p "
        "JOIN customer_sales s ON p.sale_id = s.sale_id "
        "JOIN branches b ON s.branch_id = b.branch_id"
    )
    params = None
    if branch_name != "All Branches":
        sql += " WHERE b.branch_name = %s"
        params = (branch_name,)
    sql += " GROUP BY p.payment_method ORDER BY total_collected DESC"
    df = run_query(sql, params=params)
    df["total_collected"] = df["total_collected"].astype(float)
    return df


def show_insights(sales, branch_choice):
    st.subheader("Payment Method Summary")
    pm = load_payment_summary(branch_choice)
    col1, col2 = st.columns(2)
    col1.dataframe(pm, hide_index=True)
    col2.bar_chart(pm.set_index("payment_method")["total_collected"])

    st.subheader("Branch Comparison")
    by_branch = sales.groupby("branch_name")[MONEY_COLUMNS].sum()
    by_branch["collection_pct"] = (by_branch["received_amount"] / by_branch["gross_sales"] * 100).round(1)
    st.dataframe(by_branch.sort_values("gross_sales", ascending=False))
    st.bar_chart(by_branch[["received_amount", "pending_amount"]])

    st.subheader("Monthly Sales Trend")
    monthly = sales.copy()
    monthly["month"] = pd.to_datetime(monthly["date"]).dt.to_period("M").astype(str)
    trend = monthly.groupby("month")["gross_sales"].sum()
    st.line_chart(trend)
    growth = trend.pct_change().mul(100).round(1).rename("growth_%")
    st.dataframe(pd.concat([trend, growth], axis=1))


# ---------- Predefined SQL queries ----------
PREDEFINED_QUERIES = {
    "Q6. Total gross sales": "SELECT SUM(gross_sales) AS total_gross_sales FROM customer_sales",
    "Q7. Total received amount": "SELECT SUM(received_amount) AS total_received FROM customer_sales",
    "Q8. Total pending amount": "SELECT SUM(pending_amount) AS total_pending FROM customer_sales",
    "Q9. Sales count per branch": (
        "SELECT b.branch_name, COUNT(s.sale_id) AS total_sales FROM branches b "
        "LEFT JOIN customer_sales s ON b.branch_id = s.branch_id "
        "GROUP BY b.branch_name ORDER BY total_sales DESC"
    ),
    "Q13. Branch-wise gross sales": (
        "SELECT b.branch_name, SUM(s.gross_sales) AS total_gross_sales FROM branches b "
        "JOIN customer_sales s ON b.branch_id = s.branch_id "
        "GROUP BY b.branch_name ORDER BY total_gross_sales DESC"
    ),
    "Q16. Pending amount above 5000": (
        "SELECT sale_id, name, gross_sales, received_amount, pending_amount "
        "FROM customer_sales WHERE pending_amount > 5000 ORDER BY pending_amount DESC"
    ),
    "Q18. Top branch by gross sales": (
        "SELECT b.branch_name, SUM(s.gross_sales) AS total_gross_sales FROM branches b "
        "JOIN customer_sales s ON b.branch_id = s.branch_id "
        "GROUP BY b.branch_name ORDER BY total_gross_sales DESC LIMIT 1"
    ),
    "Q20. Payment method-wise collection": (
        "SELECT payment_method, COUNT(*) AS number_of_payments, SUM(amount_paid) AS total_collected "
        "FROM payment_splits GROUP BY payment_method ORDER BY total_collected DESC"
    ),
}


def show_sql_runner():
    st.subheader("Predefined SQL Queries")
    st.caption("Company-wide reports (Super Admin only).")
    choice = st.selectbox("Choose a query", list(PREDEFINED_QUERIES.keys()))
    sql = PREDEFINED_QUERIES[choice]
    st.code(sql, language="sql")
    if st.button("Run query"):
        st.dataframe(run_query(sql), hide_index=True)


# ---------- Dashboard ----------
def show_dashboard():
    user = st.session_state["user"]

    st.sidebar.write(f"Logged in as **{user['username']}**")
    st.sidebar.write(f"Role: {user['role']}")

    # Role-based access: Super Admin picks a branch, Admin is locked to their own
    if user["role"] == "Super Admin":
        options = ["All Branches"] + get_all_branch_names()
        branch_choice = st.sidebar.selectbox("Branch filter", options)
    else:
        branch_choice = get_branch_name(user["branch_id"])
        st.sidebar.write(f"Branch: **{branch_choice}**")

    if st.sidebar.button("Logout"):
        del st.session_state["user"]
        st.rerun()

    st.title("Sales Intelligence Hub")
    st.caption(f"Showing data for: {branch_choice}")

    sales = load_sales(branch_choice)

    # KPI cards
    total_gross = sales["gross_sales"].sum()
    total_received = sales["received_amount"].sum()
    total_pending = sales["pending_amount"].sum()
    collection_pct = (total_received / total_gross * 100) if total_gross else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Sales", money(total_gross))
    c2.metric("Received", money(total_received))
    c3.metric("Pending", money(total_pending))
    c4.metric("Collection %", f"{collection_pct:.1f}%")

    # Tabs (the SQL Queries tab exists only for the Super Admin)
    tab_names = ["Sales Report", "Pending Payments", "Sales Status", "Insights",
                 "Add Sale", "Add Payment"]
    if user["role"] == "Super Admin":
        tab_names.append("SQL Queries")
    tabs = st.tabs(tab_names)

    with tabs[0]:
        st.subheader("Sales Report")
        st.write(f"{len(sales)} sales")
        st.dataframe(sales, width="stretch", hide_index=True)

    with tabs[1]:
        st.subheader("Pending Payments")
        pending = sales[sales["pending_amount"] > 0].sort_values("pending_amount", ascending=False)
        st.write(f"{len(pending)} sales with a pending balance")
        st.dataframe(pending, width="stretch", hide_index=True)

    with tabs[2]:
        st.subheader("Sales Status (Open vs Close)")
        status_counts = sales["status"].value_counts().reset_index()
        status_counts.columns = ["status", "number_of_sales"]
        st.dataframe(status_counts, hide_index=True)
        st.bar_chart(status_counts.set_index("status"))

    with tabs[3]:
        show_insights(sales, branch_choice)

    with tabs[4]:
        show_add_sale_form(user)

    with tabs[5]:
        show_add_payment_form(user)

    if user["role"] == "Super Admin":
        with tabs[6]:
            show_sql_runner()


# Only show the dashboard if someone is logged in
if "user" in st.session_state:
    show_dashboard()
else:
    show_login_page()