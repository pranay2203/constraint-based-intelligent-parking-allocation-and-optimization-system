import streamlit as st
import sqlite3
import pandas as pd
import plotly.graph_objects as go
from dataclasses import dataclass
import random
import string
from datetime import datetime

# ---------------- PAGE CONFIG ----------------

st.set_page_config(
    page_title="AI Smart Parking System",
    layout="wide"
)

DB_PATH = "data/parking.db"

# ---------------- SESSION ----------------

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "role" not in st.session_state:
    st.session_state.role = ""

if "zone" not in st.session_state:
    st.session_state.zone = ""

if "super_admin_email" not in st.session_state:
    st.session_state.super_admin_email = ""

# ---------------- DATABASE ----------------

def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

# ---------------- INITIALIZE DATABASE ----------------

def initialize_database():

    conn = get_connection()
    cursor = conn.cursor()

    # SUPER ADMINS

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS super_admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        email TEXT UNIQUE,
        password TEXT
    )
    """)

    # ADMIN CODES

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admin_codes (
        code TEXT PRIMARY KEY,
        super_admin_email TEXT,
        zone TEXT
    )
    """)

    # ADMINS

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        email TEXT UNIQUE,
        password TEXT,
        code TEXT,
        zone TEXT
    )
    """)

    # PARKING SLOTS

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS parking_slots (
        slot TEXT PRIMARY KEY,
        vehicle_type TEXT,
        occupied INTEGER,
        zone TEXT,
        distance INTEGER,
        priority_reserved INTEGER,
        charging INTEGER
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vehicle_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vehicle_no TEXT,
    vehicle_type TEXT,
    priority TEXT,
    slot TEXT,
    zone TEXT,
    entry_time TEXT,
    exit_time TEXT,
    status TEXT
)
""")

    # INSERT DEFAULT SLOTS

    cursor.execute("SELECT COUNT(*) FROM parking_slots")

    count = cursor.fetchone()[0]

    if count == 0:

        slots = [

            ('A_B1', 'Bike', 0, 'Zone A', 5, 0, 0),
            ('A_C1', 'Car', 0, 'Zone A', 8, 0, 0),
            ('A_S1', 'SUV', 0, 'Zone A', 10, 1, 0),
            ('A_E1', 'EV', 0, 'Zone A', 4, 1, 1),

            ('B_B1', 'Bike', 0, 'Zone B', 7, 0, 0),
            ('B_C1', 'Car', 0, 'Zone B', 6, 0, 0),
            ('B_S1', 'SUV', 0, 'Zone B', 12, 1, 0),
            ('B_E1', 'EV', 0, 'Zone B', 3, 1, 1),

            ('C_B1', 'Bike', 0, 'Zone C', 5, 0, 0),
            ('C_C1', 'Car', 0, 'Zone C', 9, 0, 0),
            ('C_S1', 'SUV', 0, 'Zone C', 11, 1, 0),
            ('C_E1', 'EV', 0, 'Zone C', 2, 1, 1)

        ]

        cursor.executemany(
            "INSERT INTO parking_slots VALUES (?, ?, ?, ?, ?, ?, ?)",
            slots
        )

    conn.commit()
    conn.close()

initialize_database()

# ---------------- DATA MODEL ----------------

@dataclass
class Vehicle:
    vehicle_id: str
    vehicle_type: str
    priority: str
    zone: str

# ---------------- AUTH FUNCTIONS ----------------

def register_super_admin(username, email, password):

    conn = get_connection()
    cursor = conn.cursor()

    try:

        cursor.execute(
            '''
            INSERT INTO super_admins
            (username, email, password)
            VALUES (?, ?, ?)
            ''',
            (username, email, password)
        )

        conn.commit()
        conn.close()

        return True

    except:
        conn.close()
        return False

def login_super_admin(email, password):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        '''
        SELECT *
        FROM super_admins
        WHERE email=? AND password=?
        ''',
        (email, password)
    )

    result = cursor.fetchone()

    conn.close()

    return result is not None

def generate_admin_code(super_admin_email, zone):

    conn = get_connection()
    cursor = conn.cursor()

    code = "ADM-" + ''.join(
        random.choices(
            string.ascii_uppercase + string.digits,
            k=6
        )
    )

    cursor.execute(
        '''
        INSERT INTO admin_codes
        (code, super_admin_email, zone)
        VALUES (?, ?, ?)
        ''',
        (
            code,
            super_admin_email,
            zone
        )
    )

    conn.commit()
    conn.close()

    return code

def register_admin(username, email, password, code):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        '''
        SELECT zone
        FROM admin_codes
        WHERE code=?
        ''',
        (code,)
    )

    result = cursor.fetchone()

    if not result:

        conn.close()
        return False

    zone = result[0]

    try:

        cursor.execute(
            '''
            INSERT INTO admins
            (username, email, password, code, zone)
            VALUES (?, ?, ?, ?, ?)
            ''',
            (
                username,
                email,
                password,
                code,
                zone
            )
        )

        conn.commit()
        conn.close()

        return True

    except:
        conn.close()
        return False

def login_admin(email, password):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        '''
        SELECT zone
        FROM admins
        WHERE email=? AND password=?
        ''',
        (email, password)
    )

    result = cursor.fetchone()

    conn.close()

    if result:
        return result[0]

    return None

# ---------------- PARKING FUNCTIONS ----------------

def load_slots(zone):

    conn = get_connection()

    df = pd.read_sql_query(
        f"SELECT * FROM parking_slots WHERE zone='{zone}'",
        conn
    )

    conn.close()

    return df

def constraint_filter(vehicle, slots_df):

    reasoning = []
    valid_slots = []

    for _, row in slots_df.iterrows():

        reasons = []

        if row["occupied"] == 1:
            reasons.append("Occupied")

        if row["vehicle_type"] != vehicle.vehicle_type:
            reasons.append("Vehicle Type Mismatch")

        if vehicle.priority == "Emergency" and row["priority_reserved"] == 0:
            reasons.append("Not Emergency Reserved")

        if len(reasons) == 0:

            valid_slots.append(row.to_dict())

            reasoning.append(
                f"✅ {row['slot']} Valid"
            )

        else:

            reasoning.append(
                f"❌ {row['slot']} Rejected → {', '.join(reasons)}"
            )

    return valid_slots, reasoning

def heuristic_score(slot):

    score = 0

    score += (100 - slot["distance"])

    if slot["charging"] == 1:
        score += 20

    return score

def allocate_slot(vehicle):

    df = load_slots(vehicle.zone)

    valid_slots, reasoning = constraint_filter(vehicle, df)

    if len(valid_slots) == 0:
        return None, reasoning

    ranked = sorted(
        valid_slots,
        key=lambda x: heuristic_score(x),
        reverse=True
    )

    selected = ranked[0]

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        '''
        UPDATE parking_slots
        SET occupied=1
        WHERE slot=?
        ''',
        (selected["slot"],)
    )

    conn.commit()
    conn.close()

    reasoning.append(
        f"🚗 Selected {selected['slot']} Using CSP Heuristic"
    )

    return selected["slot"], reasoning

def release_slot(slot):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        '''
        UPDATE parking_slots
        SET occupied=0
        WHERE slot=?
        ''',
        (slot,)
    )

    conn.commit()
    conn.close()

# ---------------- LOGIN PAGES ----------------

if not st.session_state.logged_in:

    st.sidebar.title("Portal")

    menu = st.sidebar.selectbox(
        "Portal",
        [
            "Super Admin Register",
            "Super Admin Login",
            "Admin Register",
            "Admin Login"
        ]
    )

    # SUPER ADMIN REGISTER

    if menu == "Super Admin Register":

        st.title("👑 Super Admin Register")

        username = st.text_input("Username")
        email = st.text_input("Email")
        password = st.text_input(
            "Password",
            type="password"
        )

        if st.button("Create Super Admin"):

            created = register_super_admin(
                username,
                email,
                password
            )

            if created:
                st.success("Super Admin Registered")
            else:
                st.error("Email Already Exists")

    # SUPER ADMIN LOGIN

    elif menu == "Super Admin Login":

        st.title("🔐 Super Admin Login")

        email = st.text_input("Email")
        password = st.text_input(
            "Password",
            type="password"
        )

        if st.button("Login"):

            valid = login_super_admin(
                email,
                password
            )

            if valid:

                st.session_state.logged_in = True
                st.session_state.role = "super_admin"
                st.session_state.super_admin_email = email

                st.success("Login Successful")

                st.rerun()

            else:
                st.error("Invalid Credentials")

    # ADMIN REGISTER

    elif menu == "Admin Register":

        st.title("📝 Admin Register")

        username = st.text_input("Username")
        email = st.text_input("Email")
        password = st.text_input(
            "Password",
            type="password"
        )

        code = st.text_input("Admin Code")

        if st.button("Register Admin"):

            created = register_admin(
                username,
                email,
                password,
                code
            )

            if created:
                st.success("Admin Registered Successfully")
            else:
                st.error("Invalid Admin Code")

    # ADMIN LOGIN

    elif menu == "Admin Login":

        st.title("🔑 Admin Login")

        email = st.text_input("Email")
        password = st.text_input(
            "Password",
            type="password"
        )

        if st.button("Admin Login"):

            zone = login_admin(
                email,
                password
            )

            if zone:

                st.session_state.logged_in = True
                st.session_state.role = "admin"
                st.session_state.zone = zone

                st.success(
                    f"Login Successful - {zone}"
                )

                st.rerun()

            else:
                st.error("Invalid Login")

    st.stop()

# ---------------- SUPER ADMIN DASHBOARD ----------------

if st.session_state.role == "super_admin":

    st.sidebar.title("👑 Super Admin")

    page = st.sidebar.radio(
        "Navigation",
        [
            "Dashboard",
            "Vehicle Monitoring",
            "Vehicle History",
            "Admin Management",
            "Generated Codes",
            "Analytics"
        ]
    )

    # ---------------- DASHBOARD ----------------

    if page == "Dashboard":

        st.title("👑 Super Admin Dashboard")

        conn = get_connection()

        total_slots = pd.read_sql_query(
            "SELECT COUNT(*) total FROM parking_slots",
            conn
        ).iloc[0]["total"]

        occupied_slots = pd.read_sql_query(
            """
            SELECT COUNT(*) total
            FROM parking_slots
            WHERE occupied=1
            """,
            conn
        ).iloc[0]["total"]

        total_admins = pd.read_sql_query(
            "SELECT COUNT(*) total FROM admins",
            conn
        ).iloc[0]["total"]

        available_slots = total_slots - occupied_slots

        conn = get_connection()

        try:

            vehicle_count = pd.read_sql_query(
                """
                SELECT COUNT(*) total
                FROM vehicle_logs
                WHERE status='Parked'
                """,
                conn
            ).iloc[0]["total"]

        except:

            vehicle_count = 0

        c1, c2, c3, c4, c5 = st.columns(5)

        c1.metric("Total Slots", total_slots)
        c2.metric("Occupied", occupied_slots)
        c3.metric("Available", available_slots)
        c4.metric("Admins", total_admins)
        c5.metric("Vehicles", vehicle_count)

        conn.close()

    # ---------------- VEHICLE MONITORING ----------------

    elif page == "Vehicle Monitoring":

        st.title("🚗 Vehicle Monitoring")

        conn = get_connection()

        try:

            vehicles = pd.read_sql_query(
                """
                SELECT *
                FROM vehicle_logs
                WHERE status='Parked'
                """,
                conn
            )

            st.dataframe(
                vehicles,
                use_container_width=True
            )

        except:

            st.warning(
                "vehicle_logs table not created yet."
            )

        conn.close()

    # ---------------- VEHICLE HISTORY ----------------

    elif page == "Vehicle History":

        st.title("📜 Vehicle History")

        conn = get_connection()

        try:

            history = pd.read_sql_query(
                """
                SELECT *
                FROM vehicle_logs
                ORDER BY id DESC
                """,
                conn
            )

            st.dataframe(
                history,
                use_container_width=True
            )

        except:

            st.warning(
                "vehicle_logs table not created yet."
            )

        conn.close()

    # ---------------- ADMIN MANAGEMENT ----------------

    elif page == "Admin Management":

        st.title("👮 Admin Management")

        conn = get_connection()

        admins = pd.read_sql_query(
            """
            SELECT
            username,
            email,
            zone
            FROM admins
            """,
            conn
        )

        st.dataframe(
            admins,
            use_container_width=True
        )

        conn.close()

    # ---------------- GENERATED CODES ----------------

    elif page == "Generated Codes":

        st.title("🔑 Generated Codes")

        zone = st.selectbox(
            "Select Zone",
            [
                "Zone A",
                "Zone B",
                "Zone C"
            ]
        )

        if st.button("Generate Admin Code"):

            code = generate_admin_code(
                st.session_state.super_admin_email,
                zone
            )

            st.success(
                f"Generated Code: {code}"
            )

        conn = get_connection()

        codes = pd.read_sql_query(
            """
            SELECT *
            FROM admin_codes
            """,
            conn
        )

        st.dataframe(
            codes,
            use_container_width=True
        )

        conn.close()

    # ---------------- ANALYTICS ----------------

    elif page == "Analytics":

        st.title("📊 Analytics")

        conn = get_connection()

        occupied = pd.read_sql_query(
            """
            SELECT COUNT(*) total
            FROM parking_slots
            WHERE occupied=1
            """,
            conn
        ).iloc[0]["total"]

        free = pd.read_sql_query(
            """
            SELECT COUNT(*) total
            FROM parking_slots
            WHERE occupied=0
            """,
            conn
        ).iloc[0]["total"]

        fig = go.Figure(
            data=[
                go.Pie(
                    labels=["Occupied","Available"],
                    values=[occupied,free],
                    hole=0.5
                )
            ]
        )

        st.plotly_chart(
            fig,
            use_container_width=True
        )

        conn.close()

    # ---------------- LOGOUT ----------------

    if st.sidebar.button("Logout"):

        st.session_state.logged_in = False
        st.session_state.role = ""
        st.session_state.zone = ""
        st.session_state.super_admin_email = ""

        st.rerun()

    st.stop()

# ---------------- MODERN DASHBOARD UI ----------------

st.markdown("""
<style>


/* Hide Streamlit UI */
#MainMenu,
footer,
header,
[data-testid="stDeployButton"],
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"] {
    display: none !important;
}

/* Reduce top padding */
.block-container {
    padding-top: 1rem !important;
}

/* App Background */
.stApp {
    background: #f5f7fb;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: linear-gradient(
        180deg,
        #081b4b,
        #03122e
    );
}

section[data-testid="stSidebar"] * {
    color: white !important;
}

/* Titles */
h1, h2, h3 {
    color: #001845;
}

/* Metric Cards */
.metric-card {
    background: white;
    border-radius: 18px;
    padding: 20px;
    box-shadow: 0 4px 15px rgba(0,0,0,.08);
    text-align: center;
    transition: .3s;
}

.metric-card:hover {
    transform: translateY(-3px);
}

/* Slot Cards */
.slot-free {
    background: #e8f5e9;
    border: 2px solid #81c784;
    color: #1b5e20;
    border-radius: 12px;
    padding: 15px;
    margin: 6px;
    text-align: center;
    font-weight: 600;
}

.slot-occupied {
    background: #ffebee;
    border: 2px solid #ef5350;
    color: #b71c1c;
    border-radius: 12px;
    padding: 15px;
    margin: 6px;
    text-align: center;
    font-weight: 600;
}

/* CSP Trace */
.trace-box {
    background: white;
    border-left: 5px solid #2563eb;
    border-radius: 10px;
    padding: 15px;
    margin: 8px 0;
    box-shadow: 0 2px 8px rgba(0,0,0,.05);
}

/* Metrics */
div[data-testid="stMetric"] {
    background: white;
    border-radius: 15px;
    padding: 10px;
    box-shadow: 0 2px 10px rgba(0,0,0,.05);
}

/* Selectbox */
.stSelectbox div[data-baseweb="select"] > div {
    background: white !important;
    color: black !important;
    border-radius: 10px !important;
}

.stSelectbox span {
    color: black !important;
}

div[role="listbox"] {
    background: white !important;
}

div[role="option"] {
    color: black !important;
    background: white !important;
}

div[role="option"]:hover {
    background: #f1f5f9 !important;
}
/* ============================= */
/* HIDE STREAMLIT BRANDING/UI */
/* ============================= */

/* Main Menu */
#MainMenu {
    visibility: hidden !important;
}

/* Footer */
footer {
    visibility: hidden !important;
}

/* Header */
header {
    visibility: hidden !important;
}

/* Toolbar */
[data-testid="stToolbar"] {
    display: none !important;
}

/* Deploy Button */
[data-testid="stDeployButton"] {
    display: none !important;
}

/* Decoration */
[data-testid="stDecoration"] {
    display: none !important;
}

/* Status Widget */
[data-testid="stStatusWidget"] {
    display: none !important;
}

/* Header Actions */
[data-testid="stHeaderActionElements"] {
    display: none !important;
}

/* Floating Toolbar */
div[data-testid="stToolbar"] {
    display: none !important;
}

/* Full Header */
header[data-testid="stHeader"] {
    display: none !important;
}

/* Top Right Controls */
button[kind="header"] {
    display: none !important;
}

/* GitHub/Fork Buttons (older versions) */
.st-emotion-cache-18ni7ap,
.st-emotion-cache-z5fcl4,
.st-emotion-cache-1avcm0n,
.st-emotion-cache-79elbk,
.st-emotion-cache-1wbqy5l {
    display: none !important;
}

/* Hide Anchor Links Near Titles */
a[href^="#"] {
    display: none !important;
}

/* Remove Extra Top Space */
.block-container {
    padding-top: 1rem !important;
}

/* Hide Streamlit Hamburger */
button[title="View fullscreen"] {
    display: none !important;
}

/* Hide File Upload Decoration */
[data-testid="stFileUploaderDropzoneInstructions"] {
    display: none !important;
}

</style>
""", unsafe_allow_html=True)

st.title("🚗 AI Smart Parking Dashboard")

# ---------------- SIDEBAR ----------------

st.sidebar.title("AI SMART PARKING")

menu = st.sidebar.radio(
    "MENU",
    [
        "Dashboard",
        "Allocate Parking",
        "Release Parking",
        "Analytics"
    ]
)

zone = st.session_state.zone

df = load_slots(zone)

occupied = len(df[df["occupied"] == 1])
free = len(df[df["occupied"] == 0])
total = len(df)

# ---------------- DASHBOARD ----------------

if menu == "Dashboard":

    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        st.markdown(f'''
        <div class="metric-card">
            <h4>Total Slots</h4>
            <h1>{total}</h1>
        </div>
        ''', unsafe_allow_html=True)

    with c2:
        st.markdown(f'''
        <div class="metric-card">
            <h4>Occupied Slots</h4>
            <h1>{occupied}</h1>
        </div>
        ''', unsafe_allow_html=True)

    with c3:
        st.markdown(f'''
        <div class="metric-card">
            <h4>Available Slots</h4>
            <h1>{free}</h1>
        </div>
        ''', unsafe_allow_html=True)

    with c4:

        rate = round((occupied / total) * 100, 2) if total > 0 else 0

        st.markdown(f'''
        <div class="metric-card">
            <h4>Occupancy Rate</h4>
            <h1>{rate}%</h1>
        </div>
        ''', unsafe_allow_html=True)

    # get vehicle count for display
    conn = get_connection()
    try:
        vehicle_count = pd.read_sql_query(
            """
            SELECT COUNT(*) total
            FROM vehicle_logs
            WHERE status='Parked'
            """,
            conn
        ).iloc[0]["total"]
    except Exception:
        vehicle_count = 0
    finally:
        conn.close()

    with c5:

        st.markdown(f'''
        <div class="metric-card">
            <h4>Vehicles</h4>
            <h1>{vehicle_count}</h1>
        </div>
        ''', unsafe_allow_html=True)
    left, right = st.columns(2)

    # PIE CHART

    with left:

        st.subheader("📊 Slot Occupancy Overview")

        fig = go.Figure(data=[
            go.Pie(
                labels=["Occupied", "Available"],
                values=[occupied, free],
                hole=0.5
            )
        ])

        st.plotly_chart(
            fig,
            use_container_width=True
        )

    # SLOT VISUALIZATION

    with right:

        st.subheader("🅿 Live Parking Layout")

        conn = get_connection()

    try:

        vehicle_df = pd.read_sql_query(
            """
            SELECT
                slot,
                vehicle_no,
                vehicle_type
            FROM vehicle_logs
            WHERE status='Parked'
            """,
            conn
        )

    except:

        vehicle_df = pd.DataFrame()

    conn.close()

    cols = st.columns(2)

    for i, row in df.iterrows():

        slot_name = row["slot"]

        if row["occupied"] == 1:

            info = vehicle_df[
                vehicle_df["slot"] == slot_name
            ]

            if len(info) > 0:

                vehicle_no = info.iloc[0]["vehicle_no"]
                vehicle_type = info.iloc[0]["vehicle_type"]

                cols[i % 2].markdown(
                    f"""
                    <div class="slot-occupied">
                        <b>{slot_name}</b><br>
                        {vehicle_no}<br>
                        {vehicle_type}
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            else:

                cols[i % 2].markdown(
                    f"""
                    <div class="slot-occupied">
                        <b>{slot_name}</b>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

        else:

            cols[i % 2].markdown(
                f"""
                <div class="slot-free">
                    <b>{slot_name}</b>
                </div>
                """,
                unsafe_allow_html=True
            )

# ---------------- ALLOCATE ----------------

elif menu == "Allocate Parking":

    st.subheader("🚘 AI Parking Allocation (CSP)")

    vehicle_type = st.selectbox(
        "Vehicle Type",
        ["Bike", "Car", "SUV", "EV"]
    )

    priority = st.selectbox(
        "Priority",
        ["Normal", "VIP", "Emergency"]
    )

    vehicle_no = st.text_input(
    "Vehicle Number Plate"
)

    if st.button("Find & Allocate Slot"):

        vehicle = Vehicle(
            vehicle_id=vehicle_no,
            vehicle_type=vehicle_type,
            priority=priority,
            zone=zone
        )

        slot, trace = allocate_slot(vehicle)

        if slot:

            st.success(
                f"✅ Slot Allocated: {slot}"
            )

            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO vehicle_logs(
                    vehicle_no,
                    vehicle_type,
                    priority,
                    slot,
                    zone,
                    entry_time,
                    status
                )
                VALUES(?,?,?,?,?,?,?)
                """,
                (
                    vehicle_no,
                    vehicle_type,
                    priority,
                    slot,
                    zone,
                    datetime.now().strftime("%d-%m-%Y %H:%M"),
                    "Parked"
                )
            )

            conn.commit()
            conn.close()

        else:

            st.error(
                "❌ No Valid Slot Available"
            )

        st.subheader("🧠 CSP Reasoning Trace")

        for step in trace:

            st.markdown(
                f'<div class="trace-box">{step}</div>',
                unsafe_allow_html=True
            )

# ---------------- RELEASE ----------------

elif menu == "Release Parking":

    st.subheader("🔓 Release Parking")

    occupied_slots = df[df["occupied"] == 1]["slot"].tolist()

    if occupied_slots:

        selected = st.selectbox(
            "Occupied Slots",
            occupied_slots
        )

        if st.button("Release Slot"):

            release_slot(selected)

            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE vehicle_logs
                SET exit_time=?,
                    status='Released'
                WHERE slot=?
                AND status='Parked'
                """,
                (
                    datetime.now().strftime("%d-%m-%Y %H:%M"),
                    selected
                )
            )

            conn.commit()
            conn.close()

            st.success(
                f"{selected} Released Successfully"
            )

            st.rerun()

    else:
        st.info("No Occupied Slots")

# ---------------- ANALYTICS ----------------

elif menu == "Analytics":

    st.subheader("📈 Parking Analytics")

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=df["slot"],
            y=df["distance"],
            name="Distance"
        )
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

# ---------------- LOGOUT ----------------

if st.sidebar.button("Logout"):

    st.session_state.logged_in = False
    st.session_state.role = ""
    st.session_state.zone = ""
    st.session_state.super_admin_email = ""

    st.rerun()