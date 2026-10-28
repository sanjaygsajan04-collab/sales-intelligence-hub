import altair as alt
import pandas as pd
import streamlit as st
from db import run_query, run_command

st.set_page_config(page_title="Sales Intelligence Hub", layout="wide")

MONEY_COLUMNS = ["gross_sales", "received_amount", "pending_amount"]
PRODUCTS = ["DS", "DA", "BA", "FSD", "ML", "AI"]
PAYMENT_METHODS = ["Cash", "UPI", "Card"]

CSS = """
<style>
.hero {
    background: linear-gradient(90deg, #4f46e5 0%, #0ea5e9 100%);
    padding: 22px 28px; border-radius: 14px; margin-bottom: 20px;
}
.hero-title { color: #ffffff; font-size: 1.9rem; font-weight: 700; line-height: 1.2; }
.hero-sub { color: rgba(255,255,255,0.9); font-size: 1rem; margin-top: 4px; }
.user-card {
    background: rgba(79,70,229,0.12); border-radius: 12px;
    padding: 12px 14px; margin-bottom: 12px;
}
.user-card b { font-size: 1.05rem; }
.user-card span { opacity: 0.8; font-size: 0.85rem; }
</style>
"""


# ---------- Look and feel helpers ----------
def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def page_header(title, subtitle):
    st.markdown(
        f"<div class='hero'><div class='hero-title'>{title}</div>"
        f"<div class='hero-sub'>{subtitle}</div></div>",
        unsafe_allow_html=True,
    )


def money(value):
    return f"₹{value:,.0f}"


def tidy(df):
    """Copy of a table with date columns shown as plain dates."""
    out = df.copy()
    for col in ("date", "payment_date"):
        if col in out.columns:
            out[col] = pd.to_datetime(out[col]).dt.date
    return out


def csv_button(df, filename, label="Download CSV"):
    st.download_button(
        label,
        tidy(df).to_csv(index=False).encode("utf-8"),
        file_name=filename,
        mime="text/csv",
        key=f"dl_{filename}",
    )


def clicked(event, name, field):
    """Values the user clicked in an Altair chart (empty list if nothing is selected)."""
    try:
        return [row[field] for row in event.selection[name]]
    except Exception:
        return []


def clickable_bar(df, measure_label, key):
    """Bar chart. df has the columns Group and Value. Clicking a bar selects it."""
    pick = alt.selection_point(name="pick", fields=["Group"])
    order = list(df["Group"]) if key == "month" else "-y"
    chart = (
        alt.Chart(df)
        .mark_bar(cornerRadiusTopLeft=5, cornerRadiusTopRight=5)
        .encode(
            x=alt.X("Group:N", sort=order, title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("Value:Q", title=measure_label),
            color=alt.condition(pick, alt.value("#4f46e5"), alt.value("#c7d2fe")),
            tooltip=[alt.Tooltip("Group:N", title="Name"),
                     alt.Tooltip("Value:Q", title=measure_label, format=",.0f")],
        )
        .add_params(pick)
        .properties(height=340)
    )
    return st.altair_chart(chart, on_select="rerun", key=f"chart_{key}", width="stretch")


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
    page_header("Sales Intelligence Hub", "Branch-based sales and payment tracking")
    _, middle, _ = st.columns([1, 1.2, 1])
    with middle:
        with st.container(border=True):
            st.subheader("Sign in")
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


# ---------- Data loading (role rule is applied here, in the SQL) ----------
def get_branch_name(branch_id):
    df = run_query("SELECT branch_name FROM branches WHERE branch_id = %s", params=(branch_id,))
    return df.iloc[0]["branch_name"]


def load_sales(user):
    """All sales the user may see. An Admin only ever loads their own branch."""
    sql = (
        "SELECT s.sale_id, s.`date`, s.name, s.mobile_number, b.branch_name, "
        "s.product_name, s.gross_sales, s.received_amount, s.pending_amount "
        "FROM customer_sales s JOIN branches b ON s.branch_id = b.branch_id"
    )
    params = None
    if user["role"] == "Admin":
        sql += " WHERE s.branch_id = %s"
        params = (user["branch_id"],)
    sql += " ORDER BY s.sale_id"
    df = run_query(sql, params=params)
    for col in MONEY_COLUMNS:
        df[col] = df[col].astype(float)
    df["date"] = pd.to_datetime(df["date"])
    return df


def load_payments(user):
    """All payments the user may see, with the sale's branch, product and customer."""
    sql = (
        "SELECT p.payment_id, p.sale_id, p.payment_date, p.amount_paid, p.payment_method, "
        "s.name, b.branch_name, s.product_name "
        "FROM payment_splits p "
        "JOIN customer_sales s ON p.sale_id = s.sale_id "
        "JOIN branches b ON s.branch_id = b.branch_id"
    )
    params = None
    if user["role"] == "Admin":
        sql += " WHERE s.branch_id = %s"
        params = (user["branch_id"],)
    sql += " ORDER BY p.payment_id"
    df = run_query(sql, params=params)
    df["amount_paid"] = df["amount_paid"].astype(float)
    df["payment_date"] = pd.to_datetime(df["payment_date"])
    return df


# ---------- Sidebar: menu, filters, logout ----------
def sidebar_menu(user):
    st.sidebar.markdown(
        f"<div class='user-card'><b>{user['username']}</b><br>"
        f"<span>{user['role']}</span></div>",
        unsafe_allow_html=True,
    )
    pages = ["Dashboard", "Reports", "Data Entry"]
    if user["role"] == "Super Admin":
        pages.append("SQL Queries")
    return st.sidebar.radio("Menu", pages)


FILTER_KEYS = ["f_branch", "f_product", "f_method", "f_date", "f_search"]


def multi(label, options, key):
    """Multiselect where an empty choice means 'everything'."""
    chosen = st.sidebar.multiselect(label, options, placeholder="All", key=key)
    return chosen if chosen else list(options)


def reset_filters():
    for k in FILTER_KEYS:
        st.session_state.pop(k, None)


def sidebar_filters(user, sales):
    st.sidebar.divider()
    st.sidebar.subheader("Filters")

    if user["role"] == "Super Admin":
        branches = multi("Branch", sorted(sales["branch_name"].unique()), "f_branch")
    else:
        branches = [get_branch_name(user["branch_id"])]
        st.sidebar.write(f"Branch: **{branches[0]}**")

    products = multi("Product", sorted(sales["product_name"].unique()), "f_product")
    methods = multi("Payment method", PAYMENT_METHODS, "f_method")

    if sales.empty:
        today = pd.Timestamp.today().date()
        dmin = dmax = today
    else:
        dmin = sales["date"].min().date()
        dmax = sales["date"].max().date()
    picked = st.sidebar.date_input(
        "Sale date range", value=(dmin, dmax), min_value=dmin, max_value=dmax, key="f_date"
    )
    picked = tuple(picked) if isinstance(picked, (list, tuple)) else (picked,)
    start = picked[0]
    end = picked[1] if len(picked) > 1 else picked[0]

    search = st.sidebar.text_input("Search name or mobile", key="f_search")
    st.sidebar.button("Reset filters", on_click=reset_filters)

    return {
        "branches": branches, "products": products,
        "methods": methods, "start": start, "end": end, "search": search,
    }


def apply_filters(sales, payments, f):
    mask = (
        sales["branch_name"].isin(f["branches"])
        & sales["product_name"].isin(f["products"])
        & (sales["date"] >= pd.Timestamp(f["start"]))
        & (sales["date"] <= pd.Timestamp(f["end"]))
    )
    text = f["search"].strip().lower()
    if text:
        mask &= (
            sales["name"].str.lower().str.contains(text, regex=False)
            | sales["mobile_number"].astype(str).str.contains(text, regex=False)
        )
    filtered_sales = sales[mask]
    filtered_payments = payments[
        payments["sale_id"].isin(filtered_sales["sale_id"])
        & payments["payment_method"].isin(f["methods"])
    ]
    return filtered_sales, filtered_payments


# ---------- Dashboard page ----------
MEASURES = {"Total sales": "gross_sales", "Received": "received_amount", "Pending": "pending_amount"}
DETAIL_COLUMNS = ["sale_id", "name", "branch_name", "product_name",
                  "gross_sales", "received_amount", "pending_amount"]


def explorer(fs, fp):
    """Pick how to slice the data, then click a bar to see the records behind it."""
    st.subheader("Explore your sales")
    c1, c2 = st.columns([3, 2])
    view = c1.radio("View by", ["Branch", "Product", "Month", "Payment method"], horizontal=True)
    if view == "Payment method":
        c2.caption("Shows money collected per payment method.")
        measure = None
    else:
        measure = c2.radio("Measure", list(MEASURES.keys()), horizontal=True)

    if view == "Payment method":
        if fp.empty:
            st.info("No payments for the current filters.")
            return
        data = fp.groupby("payment_method")["amount_paid"].sum()
        label = "Collected"
        key = "method"
    else:
        column = MEASURES[measure]
        group_col = {"Branch": "branch_name", "Product": "product_name", "Month": "month"}[view]
        data = fs.assign(month=fs["date"].dt.to_period("M").astype(str)).groupby(group_col)[column].sum()
        label = measure
        key = view.lower()
    df = data.rename("Value").rename_axis("Group").reset_index()

    event = clickable_bar(df, label, key)
    picked = clicked(event, "pick", "Group")

    if not picked:
        st.caption("Tip: click a bar to see the records behind it. Hold Shift to pick several.")
        return

    st.markdown(f"#### Records for: {', '.join(str(p) for p in picked)}")
    if view == "Payment method":
        rows = fp[fp["payment_method"].isin(picked)]
        st.dataframe(tidy(rows), width="stretch", hide_index=True)
        csv_button(rows, "selected_payments.csv")
        return

    if view == "Branch":
        rows = fs[fs["branch_name"].isin(picked)]
    elif view == "Product":
        rows = fs[fs["product_name"].isin(picked)]
    else:
        rows = fs[fs["date"].dt.to_period("M").astype(str).isin(picked)]
    rows = rows.sort_values("pending_amount", ascending=False)
    st.dataframe(rows[DETAIL_COLUMNS], width="stretch", hide_index=True)
    csv_button(rows[DETAIL_COLUMNS], "selected_sales.csv")


def more_views(fs, fp):
    """Secondary charts, hidden inside tabs so the page stays clean."""
    tab_trend, tab_method, tab_pending = st.tabs(["Trend", "Payment methods", "Biggest pending"])

    with tab_trend:
        cumulative = st.toggle("Show running total")
        sales_m = fs.groupby(fs["date"].dt.to_period("M").astype(str))["gross_sales"].sum()
        paid_m = fp.groupby(fp["payment_date"].dt.to_period("M").astype(str))["amount_paid"].sum()
        trend = pd.concat([sales_m.rename("Sales booked"), paid_m.rename("Collected")], axis=1).fillna(0)
        if cumulative:
            trend = trend.cumsum()
        st.line_chart(trend)

    with tab_method:
        if fp.empty:
            st.info("No payments for the current filters.")
        else:
            by_method = fp.groupby("payment_method")["amount_paid"].sum().sort_values(ascending=False)
            st.bar_chart(by_method)

    with tab_pending:
        count = st.slider("How many customers", 5, 50, 10, step=5)
        top = fs.nlargest(count, "pending_amount")[DETAIL_COLUMNS]
        st.dataframe(top, width="stretch", hide_index=True)


def dashboard_page(fs, fp, scope):
    page_header("Dashboard", f"Overview for {scope}")
    if fs.empty:
        st.warning("No sales match the current filters.")
        return

    gross = fs["gross_sales"].sum()
    received = fs["received_amount"].sum()
    pending = fs["pending_amount"].sum()
    collection_pct = received / gross * 100 if gross else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Sales", money(gross), border=True)
    c2.metric("Received", money(received), border=True)
    c3.metric("Pending", money(pending), border=True)
    c4.metric("Collected", f"{collection_pct:.1f}%", border=True)

    with st.container(border=True):
        explorer(fs, fp)

    more_views(fs, fp)


# ---------- Reports page ----------
def reports_page(fs, fp, scope):
    page_header("Reports", f"Detailed tables for {scope}. Every table can be downloaded.")
    if fs.empty:
        st.warning("No sales match the current filters.")
        return

    tab_sales, tab_pending, tab_pay, tab_branch = st.tabs(
        ["Sales Report", "Pending Payments", "Payments", "Branch Summary"]
    )

    with tab_sales:
        st.subheader("Sales Report")
        st.write(f"{len(fs):,} sales")
        st.dataframe(tidy(fs), width="stretch", hide_index=True)
        csv_button(fs, "sales_report.csv")

    with tab_pending:
        st.subheader("Pending Payments")
        minimum = st.number_input("Show pending amounts above", min_value=0, value=0, step=5000)
        pend = fs[fs["pending_amount"] > minimum].sort_values("pending_amount", ascending=False)
        st.write(f"{len(pend):,} sales with a pending balance above ₹{minimum:,}")
        st.dataframe(tidy(pend), width="stretch", hide_index=True)
        csv_button(pend, "pending_payments.csv")

    with tab_pay:
        st.subheader("Payment History")
        if fp.empty:
            st.info("No payments for the current filters.")
        else:
            summary = fp.groupby("payment_method").agg(
                number_of_payments=("payment_id", "count"),
                total_collected=("amount_paid", "sum"),
            ).reset_index().sort_values("total_collected", ascending=False)
            st.markdown("**Summary by payment method**")
            st.dataframe(summary, width="stretch", hide_index=True)
            csv_button(summary, "payment_method_summary.csv")
            st.markdown("**All payments**")
            st.dataframe(tidy(fp), width="stretch", hide_index=True)
            csv_button(fp, "payments.csv")

    with tab_branch:
        st.subheader("Branch Summary")
        branch_table = fs.groupby("branch_name").agg(
            number_of_sales=("sale_id", "count"),
            gross_sales=("gross_sales", "sum"),
            received_amount=("received_amount", "sum"),
            pending_amount=("pending_amount", "sum"),
        )
        branch_table["collection_pct"] = (
            branch_table["received_amount"] / branch_table["gross_sales"] * 100
        ).round(1)
        branch_table["pending_pct"] = (100 - branch_table["collection_pct"]).round(1)
        branch_table = branch_table.sort_values("gross_sales", ascending=False).reset_index()
        st.dataframe(branch_table, width="stretch", hide_index=True)
        csv_button(branch_table, "branch_summary.csv")


# ---------- Data entry page ----------
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
        product = st.selectbox("Product", PRODUCTS)
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
        "WHERE s.pending_amount > 0"
    )
    params = None
    if user["role"] == "Admin":
        sql += " AND s.branch_id = %s"
        params = (user["branch_id"],)
    sql += " ORDER BY s.sale_id DESC LIMIT 200"
    open_sales = run_query(sql, params=params)

    if open_sales.empty:
        st.info("Every sale is fully paid. Nothing to add.")
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
        method = st.selectbox("Payment method", PAYMENT_METHODS)
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


def data_entry_page(user):
    page_header("Data Entry", "Record new sales and split payments")
    tab_sale, tab_payment = st.tabs(["Add Sale", "Add Payment"])
    with tab_sale:
        show_add_sale_form(user)
    with tab_payment:
        show_add_payment_form(user)


# ---------- SQL queries page (Super Admin) ----------
PREDEFINED_QUERIES = {
    "Q1. All sales": "SELECT * FROM customer_sales",
    "Q2. All branches": "SELECT * FROM branches",
    "Q4. Open sales": "SELECT * FROM customer_sales WHERE status = 'Open'",
    "Q5. Chennai branch sales": (
        "SELECT s.sale_id, s.`date`, s.name, s.product_name, s.gross_sales, "
        "s.received_amount, s.pending_amount FROM customer_sales s "
        "JOIN branches b ON s.branch_id = b.branch_id WHERE b.branch_name = 'Chennai'"
    ),
    "Q6. Total gross sales": "SELECT SUM(gross_sales) AS total_gross_sales FROM customer_sales",
    "Q7. Total received amount": "SELECT SUM(received_amount) AS total_received FROM customer_sales",
    "Q8. Total pending amount": "SELECT SUM(pending_amount) AS total_pending FROM customer_sales",
    "Q9. Sales count per branch": (
        "SELECT b.branch_name, COUNT(s.sale_id) AS total_sales FROM branches b "
        "LEFT JOIN customer_sales s ON b.branch_id = s.branch_id "
        "GROUP BY b.branch_name ORDER BY total_sales DESC"
    ),
    "Q11. Sales with branch name": (
        "SELECT s.sale_id, s.`date`, s.name, b.branch_name, s.product_name, s.gross_sales "
        "FROM customer_sales s JOIN branches b ON s.branch_id = b.branch_id ORDER BY s.sale_id"
    ),
    "Q12. Sales with total paid": (
        "SELECT s.sale_id, s.name, s.gross_sales, SUM(p.amount_paid) AS total_paid, "
        "COUNT(p.payment_id) AS number_of_payments FROM customer_sales s "
        "JOIN payment_splits p ON s.sale_id = p.sale_id "
        "GROUP BY s.sale_id, s.name, s.gross_sales ORDER BY s.sale_id"
    ),
    "Q13. Branch-wise gross sales": (
        "SELECT b.branch_name, SUM(s.gross_sales) AS total_gross_sales FROM branches b "
        "JOIN customer_sales s ON b.branch_id = s.branch_id "
        "GROUP BY b.branch_name ORDER BY total_gross_sales DESC"
    ),
    "Q15. Sales with branch admin": (
        "SELECT s.sale_id, s.name, b.branch_name, b.branch_admin_name, s.gross_sales "
        "FROM customer_sales s JOIN branches b ON s.branch_id = b.branch_id ORDER BY s.sale_id"
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


def sql_page():
    page_header("SQL Queries", "The 15 predefined analytical queries (Super Admin only)")
    choice = st.selectbox("Choose a query", list(PREDEFINED_QUERIES.keys()))
    sql = PREDEFINED_QUERIES[choice]
    st.code(sql, language="sql")
    if st.button("Run query"):
        result = run_query(sql)
        st.write(f"{len(result):,} rows")
        st.dataframe(result, width="stretch", hide_index=True)
        csv_button(result, "query_result.csv")


# ---------- App ----------
def main():
    inject_css()
    if "user" not in st.session_state:
        show_login_page()
        return

    user = st.session_state["user"]
    sales_all = load_sales(user)
    payments_all = load_payments(user)

    page = sidebar_menu(user)

    fs = fp = None
    scope = ""
    if page in ("Dashboard", "Reports"):
        filters = sidebar_filters(user, sales_all)
        fs, fp = apply_filters(sales_all, payments_all, filters)
        every_branch = set(filters["branches"]) == set(sales_all["branch_name"].unique())
        scope = "all branches" if every_branch else ", ".join(filters["branches"])

    st.sidebar.divider()
    if st.sidebar.button("Logout"):
        del st.session_state["user"]
        st.rerun()

    if page == "Dashboard":
        dashboard_page(fs, fp, scope)
    elif page == "Reports":
        reports_page(fs, fp, scope)
    elif page == "Data Entry":
        data_entry_page(user)
    elif page == "SQL Queries" and user["role"] == "Super Admin":
        sql_page()


main()
