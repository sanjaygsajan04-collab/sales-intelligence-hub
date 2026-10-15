import warnings
warnings.filterwarnings("ignore", message="pandas only supports SQLAlchemy")

import mysql.connector
import pandas as pd

# Connection settings. Change DB_PASSWORD to your MySQL root password.
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
   "password": "YOUR_MYSQL_PASSWORD",
    "database": "sales_management_system",
}


def get_connection():
    """Open and return a new connection to the database."""
    return mysql.connector.connect(**DB_CONFIG)


def run_query(sql, params=None):
    """Run a SELECT query and return the result as a pandas DataFrame."""
    conn = get_connection()
    try:
        return pd.read_sql(sql, conn, params=params)
    finally:
        conn.close()


def run_command(sql, params=None):
    """Run an INSERT/UPDATE/DELETE command and save the change."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()