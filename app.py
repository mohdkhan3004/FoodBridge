import os
import sqlite3
import hashlib
import secrets
from datetime import datetime, date, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "data", "foodbridge.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

st.set_page_config(page_title="FoodBridge | Food Waste Management", page_icon="🥗", layout="wide")

# ----------------------------- Database ------------------------------------
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('Donor','NGO','Admin')),
            organization TEXT DEFAULT '',
            location TEXT DEFAULT '',
            verified INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS donations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            donor_id INTEGER NOT NULL,
            food_name TEXT NOT NULL,
            category TEXT NOT NULL,
            quantity REAL NOT NULL CHECK(quantity > 0),
            unit TEXT NOT NULL DEFAULT 'meals',
            location TEXT NOT NULL,
            description TEXT DEFAULT '',
            prepared_at TEXT NOT NULL,
            expiry_at TEXT NOT NULL,
            deadline TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Available',
            created_at TEXT NOT NULL,
            FOREIGN KEY(donor_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            donation_id INTEGER NOT NULL,
            ngo_id INTEGER NOT NULL,
            requested_quantity REAL NOT NULL CHECK(requested_quantity > 0),
            message TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Pending',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(donation_id) REFERENCES donations(id),
            FOREIGN KEY(ngo_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS pickups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL UNIQUE,
            actual_quantity REAL NOT NULL CHECK(actual_quantity > 0),
            picked_up_at TEXT NOT NULL,
            notes TEXT DEFAULT '',
            FOREIGN KEY(request_id) REFERENCES requests(id)
        );
        """)
        # A demo admin is created only when the database has no admin account.
        admin = conn.execute("SELECT id FROM users WHERE role='Admin' LIMIT 1").fetchone()
        if not admin:
            conn.execute(
                """INSERT INTO users(name,email,password_hash,role,organization,location,verified,created_at)
                   VALUES(?,?,?,?,?,?,?,?)""",
                ("FoodBridge Administrator", "admin@foodbridge.local",
                 hash_password("Admin@123"), "Admin", "FoodBridge", "Hyderabad", 1, now_str())
            )

def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 180000).hex()
    return f"{salt}${digest}"

def verify_password(password, stored):
    try:
        salt, digest = stored.split("$", 1)
        return secrets.compare_digest(hash_password(password, salt).split("$", 1)[1], digest)
    except (ValueError, AttributeError):
        return False

def query_df(sql, params=()):
    with get_conn() as conn:
        return pd.read_sql_query(sql, conn, params=params)

def execute(sql, params=()):
    with get_conn() as conn:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.lastrowid

def get_user(user_id):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()

init_db()

def seed_demo_data():
    """Create realistic sample records once, so every dashboard has useful demo content."""
    with get_conn() as conn:
        existing = conn.execute("SELECT COUNT(*) FROM donations").fetchone()[0]
        if existing:
            return

        now = datetime.now()
        stamp = lambda delta: (now + delta).strftime("%Y-%m-%d %H:%M:%S")
        demo_password = hash_password("FoodBridgeDemo@123")

        sample_users = [
            ("Ayesha Rahman", "ayesha.donor@example.com", "Donor", "Green Bowl Cafe", "Banjara Hills", 1),
            ("Rahul Sharma", "rahul.donor@example.com", "Donor", "Campus Canteen", "Mehdipatnam", 1),
            ("Sara Thomas", "sara.donor@example.com", "Donor", "Fresh Basket Market", "Jubilee Hills", 1),
            ("Hope Community Kitchen", "hope.ngo@example.com", "NGO", "Hope Community Kitchen", "Banjara Hills", 1),
            ("Care & Share Foundation", "care.ngo@example.com", "NGO", "Care & Share Foundation", "Mehdipatnam", 1),
            ("Nourish Hyderabad", "nourish.ngo@example.com", "NGO", "Nourish Hyderabad", "Jubilee Hills", 0),
        ]
        ids = {}
        for name, email, role, organization, location, verified in sample_users:
            conn.execute(
                """INSERT OR IGNORE INTO users(name,email,password_hash,role,organization,location,verified,created_at)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (name, email, demo_password, role, organization, location, verified, stamp(timedelta(days=-7)))
            )
            row = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
            ids[email] = row["id"]

        donations = [
            (ids["ayesha.donor@example.com"], "Vegetarian lunch boxes", "Prepared meals", 45, "meals", "Banjara Hills",
             "Freshly prepared vegetarian meals, packed individually.", -2, 2, 1, "Available"),
            (ids["rahul.donor@example.com"], "Fresh bananas and apples", "Fruits", 30, "kg", "Mehdipatnam",
             "Ripe fruit from today's campus canteen stock.", -1, 1, 0.5, "Reserved"),
            (ids["sara.donor@example.com"], "Assorted bread loaves", "Bakery", 18, "packs", "Jubilee Hills",
             "Sealed bakery packs, stored in a clean dry area.", -3, 1, 0.25, "Collected"),
            (ids["ayesha.donor@example.com"], "Rice and dal meal trays", "Prepared meals", 60, "meals", "Banjara Hills",
             "Vegetarian meal trays available for same-day collection.", -1, 1, 0.3, "Available"),
            (ids["rahul.donor@example.com"], "Seasonal vegetables", "Vegetables", 22, "kg", "Mehdipatnam",
             "Mixed seasonal vegetables suitable for immediate distribution.", -2, 2, 0.5, "Collected"),
            (ids["sara.donor@example.com"], "Packaged snack boxes", "Packaged food", 25, "boxes", "Jubilee Hills",
             "Unopened snack boxes with clear packaging.", -1, 2, 1, "Available"),
        ]
        donation_ids = []
        for donor_id, food, category, qty, unit, location, desc, prepared_days, expiry_days, deadline_days, status in donations:
            cur = conn.execute(
                """INSERT INTO donations(donor_id,food_name,category,quantity,unit,location,description,
                   prepared_at,expiry_at,deadline,status,created_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (donor_id, food, category, qty, unit, location, desc,
                 stamp(timedelta(days=prepared_days)), stamp(timedelta(days=expiry_days)),
                 stamp(timedelta(days=deadline_days)), status, stamp(timedelta(days=prepared_days)))
            )
            donation_ids.append(cur.lastrowid)

        requests = [
            (donation_ids[1], ids["hope.ngo@example.com"], 20, "We can distribute fruit packs to nearby families.", "Accepted", -1),
            (donation_ids[2], ids["care.ngo@example.com"], 15, "Bread packs for our evening community meal.", "Collected", -2),
            (donation_ids[3], ids["hope.ngo@example.com"], 40, "We have volunteers available for same-day pickup.", "Pending", -0.2),
            (donation_ids[4], ids["care.ngo@example.com"], 18, "Vegetable kits for our community kitchen.", "Collected", -1),
            (donation_ids[5], ids["nourish.ngo@example.com"], 10, "We would like to share these with local residents.", "Declined", -0.5),
        ]
        request_ids = {}
        for donation_id, ngo_id, qty, message, status, created_days in requests:
            created = stamp(timedelta(days=created_days))
            cur = conn.execute(
                """INSERT INTO requests(donation_id,ngo_id,requested_quantity,message,status,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?)""",
                (donation_id, ngo_id, qty, message, status, created, stamp(timedelta(hours=-2)))
            )
            request_ids[donation_id] = cur.lastrowid

        for donation_id, qty, notes, days_ago in [
            (donation_ids[2], 15, "Collected by NGO volunteer team; all packs checked.", 1),
            (donation_ids[4], 18, "Pickup completed and quantity confirmed.", 0.5),
        ]:
            conn.execute(
                "INSERT INTO pickups(request_id,actual_quantity,picked_up_at,notes) VALUES(?,?,?,?)",
                (request_ids[donation_id], qty, stamp(timedelta(days=days_ago)), notes)
            )

        conn.commit()

seed_demo_data()

# ----------------------------- Styling -------------------------------------
st.markdown("""
<style>
.main .block-container {padding-top: 1.1rem; padding-bottom: 3rem; max-width: 1450px;}
.hero {
  padding: 1.7rem 1.9rem; border-radius: 22px;
  background: linear-gradient(115deg,#dcfce7 0%,#effdf5 48%,#e0f2fe 100%);
  border: 1px solid #c9eed6; position: relative; overflow: hidden;
  animation: fb-enter .7s ease-out both;
}
.hero:after {
  content:"🥬"; position:absolute; right:5%; top:2%; font-size:5rem; opacity:.13;
  animation: fb-float 4s ease-in-out infinite;
}
.hero h1 {margin: 0; color: #14532d; letter-spacing:-.04em; font-size:2.4rem;}
.hero p {margin: .45rem 0 0 0; color: #355a47; max-width: 760px;}
.small-muted {color: #64748b; font-size: .9rem;}
div[data-testid="stMetric"] {
  background: linear-gradient(145deg,#ffffff,#f7fdf9); border: 1px solid #dfeee4;
  padding: 16px; border-radius: 16px; transition: transform .2s ease, box-shadow .2s ease;
  animation: fb-enter .55s ease-out both;
}
div[data-testid="stMetric"]:hover {transform: translateY(-3px); box-shadow: 0 10px 24px #14532d12;}
div[data-testid="stMetricValue"] {color:#166534;}
.stButton > button {border-radius: 11px; transition: transform .16s ease, box-shadow .16s ease;}
.stButton > button:hover {transform: translateY(-2px); box-shadow: 0 7px 18px #14532d18;}
div[data-testid="stExpander"] {border-radius: 14px;}
div[data-testid="stDataFrame"] {border-radius: 12px; overflow:hidden;}
section[data-testid="stSidebar"] {border-right:1px solid #e5eee7;}
@keyframes fb-enter {from {opacity:0; transform:translateY(10px)} to {opacity:1; transform:translateY(0)}}
@keyframes fb-float {0%,100% {transform:translateY(0) rotate(-5deg)} 50% {transform:translateY(-9px) rotate(5deg)}}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {animation:none !important; transition:none !important; scroll-behavior:auto !important;}
}
</style>
""", unsafe_allow_html=True)

# ----------------------------- Auth ----------------------------------------
def register_user(name, email, password, role, organization, location):
    email = email.strip().lower()
    if not name.strip() or not email or not password:
        return False, "Please complete all required fields."
    if len(password) < 8:
        return False, "Password must contain at least 8 characters."
    if role not in ("Donor", "NGO"):
        return False, "Choose Donor or NGO."
    try:
        execute("""INSERT INTO users(name,email,password_hash,role,organization,location,verified,created_at)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (name.strip(), email, hash_password(password), role, organization.strip(),
                 location.strip(), 0 if role == "NGO" else 1, now_str()))
        return True, "Account created. NGOs need administrator verification before requesting donations."
    except sqlite3.IntegrityError:
        return False, "An account with this email already exists."

def login_user(email, password):
    with get_conn() as conn:
        user = conn.execute("SELECT * FROM users WHERE email=?", (email.strip().lower(),)).fetchone()
    if user and verify_password(password, user["password_hash"]):
        return user
    return None

# ----------------------------- Sidebar -------------------------------------
with st.sidebar:
    st.markdown("# 🥗 FoodBridge")
    st.caption("AI-inspired food donation matching")
    st.divider()
    if "user_id" in st.session_state:
        current_user = get_user(st.session_state.user_id)
        if current_user:
            st.write(f"**{current_user['name']}**")
            st.caption(f"{current_user['role']} · {current_user['email']}")
            if current_user["role"] == "NGO":
                st.caption("Verification: " + ("Verified ✓" if current_user["verified"] else "Pending"))
            if st.button("Log out", use_container_width=True):
                for key in ("user_id",):
                    st.session_state.pop(key, None)
                st.rerun()
    st.divider()
    st.caption("SDG 2 · Zero Hunger")
    st.caption("SDG 12 · Responsible Consumption and Production")

# ----------------------------- Public landing/auth -------------------------
if "user_id" not in st.session_state:
    st.markdown("""
    <div class="hero">
      <h1>🥗 FoodBridge</h1>
      <p>Rescue surplus food. Connect donors with verified NGOs. Track every pickup and celebrate measurable community impact.</p>
    </div>
    """, unsafe_allow_html=True)
    st.write("")
    left, right = st.columns([1.05, 1])
    with left:
        st.subheader("How FoodBridge works")
        st.markdown("""
        - **Donors** list safe surplus food with a collection deadline.
        - **NGOs** discover suitable donations and submit requests.
        - **Administrators** verify NGOs and moderate donation listings.
        - **Pickup records** help track the quantity actually collected.
        """)
        st.info("Matching uses category, location and deadline filters. It is a practical rules-based matching system, not a trained machine-learning model.")
    with right:
        tab_login, tab_register = st.tabs(["🔐 Login", "📝 Create account"])
        with tab_login:
            with st.form("login_form"):
                email = st.text_input("Email", key="login_email")
                password = st.text_input("Password", type="password", key="login_password")
                submitted = st.form_submit_button("Login", type="primary", use_container_width=True)
            if submitted:
                user = login_user(email, password)
                if user:
                    st.session_state.user_id = user["id"]
                    st.rerun()
                else:
                    st.error("Invalid email or password.")
        with tab_register:
            with st.form("register_form"):
                name = st.text_input("Full name *")
                reg_email = st.text_input("Email *")
                reg_password = st.text_input("Password (8+ characters) *", type="password")
                role = st.selectbox("Account type", ["Donor", "NGO"])
                organization = st.text_input("Organization / business name")
                location = st.text_input("City / collection area", placeholder="e.g. Hyderabad")
                submitted = st.form_submit_button("Create account", type="primary", use_container_width=True)
            if submitted:
                ok, message = register_user(name, reg_email, reg_password, role, organization, location)
                (st.success if ok else st.error)(message)
    st.stop()

user = get_user(st.session_state.user_id)
if not user:
    st.session_state.pop("user_id", None)
    st.rerun()

# ----------------------------- Shared helpers ------------------------------
def donation_status_badge(status):
    return {"Available":"🟢 Available", "Reserved":"🟠 Reserved", "Collected":"🔵 Collected",
            "Expired":"⚫ Expired", "Removed":"🔴 Removed"}.get(status, status)

def refresh_expired():
    execute("UPDATE donations SET status='Expired' WHERE status='Available' AND deadline < ?",
            (now_str(),))

refresh_expired()

def show_donation_table(df):
    if df.empty:
        st.info("No donations match these filters.")
        return
    view = df.copy()
    for col in ("prepared_at", "expiry_at", "deadline", "created_at"):
        if col in view.columns:
            view[col] = view[col].astype(str)
    st.dataframe(view, use_container_width=True, hide_index=True)

def admin_export_button(df, filename, label="⬇️ Export CSV"):
    if not df.empty:
        st.download_button(
            label, data=df.to_csv(index=False).encode("utf-8"),
            file_name=filename, mime="text/csv", use_container_width=False
        )

# ----------------------------- Header --------------------------------------
st.markdown(f"""
<div class="hero">
  <h1>🥗 FoodBridge</h1>
  <p>Welcome, {user['name']} — make surplus food count.</p>
</div>
""", unsafe_allow_html=True)

pages = ["Dashboard", "🌱 Impact Center", "🔔 Activity feed"]
if user["role"] == "Donor":
    pages += ["Add donation", "My donations", "Donation requests"]
elif user["role"] == "NGO":
    pages += ["Find food", "My requests", "Pickup history"]
else:
    pages += ["Admin verification", "Manage donations", "All requests", "Pickup records", "Users"]

page = st.sidebar.radio("Navigate", pages)

# ----------------------------- Impact Center -------------------------------
if page == "🌱 Impact Center":
    st.subheader("🌱 Community impact")
    st.write("Explore how food redistribution turns surplus into community support.")
    donations = query_df("SELECT category,quantity,unit,status,created_at FROM donations")
    pickups = query_df("""SELECT p.actual_quantity,p.picked_up_at,d.category,d.unit,d.food_name
                          FROM pickups p JOIN requests r ON p.request_id=r.id
                          JOIN donations d ON r.donation_id=d.id""")
    requests_df = query_df("SELECT status FROM requests")
    total_pickups = len(pickups)
    collected = float(pickups["actual_quantity"].sum()) if not pickups.empty else 0.0
    total_donations = len(donations)
    accepted_or_done = int(requests_df["status"].isin(["Accepted","Collected"]).sum()) if not requests_df.empty else 0
    a,b,c,d = st.columns(4)
    a.metric("Pickup missions completed", f"{total_pickups:,}")
    b.metric("Quantity redistributed", f"{collected:,.1f}")
    c.metric("Donation listings", f"{total_donations:,}")
    d.metric("Accepted / completed requests", f"{accepted_or_done:,}")
    st.progress(min(total_pickups / max(total_donations, 1), 1.0), text="Pickup completion ratio across listings")
    st.caption("Quantities may use different units. The total is an activity indicator, not a physical weight or meal-equivalent estimate.")
    left, right = st.columns(2)
    with left:
        st.markdown("#### 🏆 Community milestones")
        milestones = [
            ("First listing", total_donations >= 1, "Publish the first food donation"),
            ("First successful pickup", total_pickups >= 1, "Complete a pickup"),
            ("10 listings", total_donations >= 10, "Reach 10 food listings"),
            ("5 pickups", total_pickups >= 5, "Record 5 completed pickups"),
        ]
        for label, unlocked, hint in milestones:
            st.markdown(f"{'✅' if unlocked else '🔒'} **{label}** — {hint}")
    with right:
        st.markdown("#### 📦 What is being shared?")
        if not donations.empty:
            cat_df = donations.groupby("category", as_index=False).size().rename(columns={"size":"listings"})
            st.plotly_chart(px.pie(cat_df, names="category", values="listings", hole=.55,
                                   title="Listings by food category"), use_container_width=True)
        else:
            st.info("Your community's food categories will appear here once donations are listed.")
    st.markdown("#### 💡 Next impact goal")
    goal = st.select_slider("Choose a community target", options=[5,10,25,50,100], value=25, format_func=lambda x: f"{x} completed pickups")
    st.progress(min(total_pickups / goal, 1.0), text=f"{total_pickups} of {goal} pickups completed")
    if total_pickups >= goal:
        st.success("Milestone reached! Your community is making a difference. 🎉")
    else:
        st.info(f"{goal-total_pickups} more completed pickup(s) to reach this target.")

# ----------------------------- Activity feed -------------------------------
elif page == "🔔 Activity feed":
    st.subheader("🔔 Activity feed")
    st.write("A quick timeline of recent activity relevant to your account.")
    if user["role"] == "Donor":
        activity = query_df("""SELECT r.id AS reference_id, d.food_name AS item, r.status,
                                      r.updated_at AS activity_time, u.name AS other_party,
                                      r.requested_quantity AS quantity, d.unit
                               FROM requests r JOIN donations d ON r.donation_id=d.id
                               JOIN users u ON u.id=r.ngo_id
                               WHERE d.donor_id=? ORDER BY r.updated_at DESC LIMIT 100""", (user["id"],))
        label = "NGO"
    elif user["role"] == "NGO":
        activity = query_df("""SELECT r.id AS reference_id, d.food_name AS item, r.status,
                                      r.updated_at AS activity_time, u.name AS other_party,
                                      r.requested_quantity AS quantity, d.unit
                               FROM requests r JOIN donations d ON r.donation_id=d.id
                               JOIN users u ON u.id=d.donor_id
                               WHERE r.ngo_id=? ORDER BY r.updated_at DESC LIMIT 100""", (user["id"],))
        label = "Donor"
    else:
        activity = query_df("""SELECT r.id AS reference_id, d.food_name AS item, r.status,
                                      r.updated_at AS activity_time, nu.name AS other_party,
                                      r.requested_quantity AS quantity, d.unit
                               FROM requests r JOIN donations d ON r.donation_id=d.id
                               JOIN users nu ON nu.id=r.ngo_id
                               ORDER BY r.updated_at DESC LIMIT 100""")
        label = "NGO"
    if activity.empty:
        st.info("No activity yet. Once a donation request is submitted, updates will appear here.")
    else:
        filter_status = st.multiselect("Filter by status", sorted(activity["status"].dropna().unique().tolist()),
                                       default=sorted(activity["status"].dropna().unique().tolist()))
        filtered_activity = activity[activity["status"].isin(filter_status)]
        for row in filtered_activity.itertuples():
            icon = {"Pending":"🕓","Accepted":"✅","Declined":"↩️","Collected":"🚚"}.get(row.status,"🔔")
            with st.container(border=True):
                x,y = st.columns([5,1])
                with x:
                    st.markdown(f"**{icon} {row.item}** · Request #{row.reference_id}")
                    st.caption(f"{label}: {row.other_party} · {row.quantity:g} {row.unit}")
                with y:
                    st.markdown(f"**{row.status}**")
                    st.caption(str(row.activity_time)[:16])

# ----------------------------- Dashboard -----------------------------------
elif page == "Dashboard":
    st.subheader("📊 Impact dashboard")
    donations = query_df("SELECT * FROM donations")
    pickups = query_df("""SELECT p.actual_quantity, p.picked_up_at, r.donation_id, d.category, d.food_name
                          FROM pickups p JOIN requests r ON p.request_id=r.id
                          JOIN donations d ON r.donation_id=d.id""")
    requests_df = query_df("SELECT * FROM requests")
    total_listed = float(donations["quantity"].sum()) if not donations.empty else 0
    total_collected = float(pickups["actual_quantity"].sum()) if not pickups.empty else 0
    available = int((donations["status"] == "Available").sum()) if not donations.empty else 0
    pending = int((requests_df["status"] == "Pending").sum()) if not requests_df.empty else 0
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Food listed", f"{total_listed:,.1f}")
    c2.metric("Food collected", f"{total_collected:,.1f}")
    c3.metric("Available listings", available)
    c4.metric("Pending requests", pending)
    if not donations.empty:
        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            st.markdown("#### Donations by category")
            by_cat = donations.groupby("category", as_index=False)["quantity"].sum()
            st.plotly_chart(px.bar(by_cat, x="category", y="quantity", color="category",
                                   labels={"quantity":"Quantity"}, title="Listed quantity by category"),
                            use_container_width=True)
        with chart_col2:
            st.markdown("#### Donation status")
            status_counts = donations["status"].value_counts().rename_axis("status").reset_index(name="count")
            st.plotly_chart(px.pie(status_counts, names="status", values="count", hole=.45,
                                   title="Listings by status"), use_container_width=True)
    if not pickups.empty:
        st.markdown("#### Pickup trend")
        pickups["picked_up_at"] = pd.to_datetime(pickups["picked_up_at"], errors="coerce")
        trend = pickups.dropna(subset=["picked_up_at"]).assign(day=lambda x: x["picked_up_at"].dt.date).groupby("day", as_index=False)["actual_quantity"].sum()
        if not trend.empty:
            st.plotly_chart(px.line(trend, x="day", y="actual_quantity", markers=True,
                                    labels={"day":"Date","actual_quantity":"Collected quantity"}),
                            use_container_width=True)
    if user["role"] == "Admin":
        st.markdown("#### 🧭 Admin overview")
        users_df = query_df("SELECT role,verified FROM users")
        pending_ngos = int(((users_df["role"] == "NGO") & (users_df["verified"] == 0)).sum()) if not users_df.empty else 0
        completed_pickups = len(pickups)
        recent_donations = query_df("""SELECT d.food_name,d.category,d.quantity,d.unit,d.status,d.location,
                                              u.organization AS donor
                                       FROM donations d JOIN users u ON u.id=d.donor_id
                                       ORDER BY d.created_at DESC LIMIT 5""")
        m1,m2,m3 = st.columns(3)
        m1.metric("Registered accounts", len(users_df))
        m2.metric("NGOs awaiting verification", pending_ngos)
        m3.metric("Completed pickups", completed_pickups)
        st.markdown("#### 🕘 Latest donation listings")
        show_donation_table(recent_donations)
        admin_export_button(donations, "foodbridge_donations.csv", "⬇️ Export all donations")
    st.caption("Quantities are displayed in the units selected by donors; use a consistent unit (for example, meals) for meaningful totals.")

# ----------------------------- Donor: add donation -------------------------
elif page == "Add donation":
    st.subheader("🍱 Add a food donation")
    st.write("List food that can be collected safely before the deadline.")
    with st.form("add_donation_form"):
        a,b = st.columns(2)
        with a:
            food_name = st.text_input("Food name *", placeholder="e.g. Packed vegetarian meals")
            category = st.selectbox("Category *", ["Prepared meals", "Bakery", "Fruits", "Vegetables", "Dairy", "Packaged food", "Grains", "Other"])
            quantity = st.number_input("Quantity *", min_value=0.1, value=10.0, step=1.0)
            unit = st.selectbox("Unit", ["meals", "kg", "boxes", "litres", "packets", "items"])
            location = st.text_input("Collection location *", value=user["location"] or "", placeholder="Area, city")
        with b:
            today = date.today()
            prepared_date = st.date_input("Prepared / packed date", value=today)
            prepared_time = st.time_input("Prepared / packed time", value=datetime.now().time().replace(second=0, microsecond=0))
            expiry_date = st.date_input("Use-by date", value=today)
            expiry_time = st.time_input("Use-by time", value=(datetime.now()+timedelta(hours=6)).time().replace(second=0, microsecond=0))
            deadline_date = st.date_input("Collection deadline", value=today)
            deadline_time = st.time_input("Collection time", value=(datetime.now()+timedelta(hours=3)).time().replace(second=0, microsecond=0))
        description = st.text_area("Food safety / handling notes", placeholder="Ingredients, storage conditions, allergens, packaging...")
        submit = st.form_submit_button("Publish donation", type="primary")
    if submit:
        prepared = datetime.combine(prepared_date, prepared_time)
        expiry = datetime.combine(expiry_date, expiry_time)
        deadline = datetime.combine(deadline_date, deadline_time)
        if not food_name.strip() or not location.strip():
            st.error("Food name and collection location are required.")
        elif prepared > datetime.now() + timedelta(minutes=5):
            st.error("Prepared / packed time cannot be in the future.")
        elif expiry <= datetime.now():
            st.error("Use-by date/time must be in the future.")
        elif deadline <= datetime.now():
            st.error("Collection deadline must be in the future.")
        elif deadline > expiry:
            st.error("Collection deadline must be on or before the use-by time.")
        else:
            execute("""INSERT INTO donations(donor_id,food_name,category,quantity,unit,location,description,
                        prepared_at,expiry_at,deadline,status,created_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (user["id"], food_name.strip(), category, quantity, unit, location.strip(),
                     description.strip(), prepared.strftime("%Y-%m-%d %H:%M:%S"),
                     expiry.strftime("%Y-%m-%d %H:%M:%S"), deadline.strftime("%Y-%m-%d %H:%M:%S"),
                     "Available", now_str()))
            st.success("Donation published successfully.")
            st.rerun()

# ----------------------------- Donor: own listings -------------------------
elif page == "My donations":
    st.subheader("📦 My donations")
    df = query_df("""SELECT id,food_name,category,quantity,unit,location,deadline,status,created_at
                     FROM donations WHERE donor_id=? ORDER BY created_at DESC""", (user["id"],))
    show_donation_table(df)
    if not df.empty:
        options = {f"#{r.id} · {r.food_name} ({r.status})": int(r.id) for r in df.itertuples()}
        selected_label = st.selectbox("Select a listing to manage", list(options))
        donation_id = options[selected_label]
        selected = df[df["id"] == donation_id].iloc[0]
        if selected["status"] == "Available":
            if st.button("Remove this listing", type="secondary"):
                execute("UPDATE donations SET status='Removed' WHERE id=? AND donor_id=?", (donation_id, user["id"]))
                st.success("Listing removed.")
                st.rerun()

# ----------------------------- Donor: requests -----------------------------
elif page == "Donation requests":
    st.subheader("🤝 Requests for my donations")
    df = query_df("""SELECT r.id AS request_id, d.food_name, r.requested_quantity, d.unit,
                            u.name AS ngo_name, u.organization, u.location AS ngo_location,
                            r.message, r.status, r.created_at
                     FROM requests r JOIN donations d ON d.id=r.donation_id
                     JOIN users u ON u.id=r.ngo_id
                     WHERE d.donor_id=? ORDER BY r.created_at DESC""", (user["id"],))
    show_donation_table(df)
    actionable = df[df["status"] == "Pending"] if not df.empty else df
    if not actionable.empty:
        opts = {f"Request #{int(r.request_id)} · {r.food_name} · {r.ngo_name}": int(r.request_id) for r in actionable.itertuples()}
        choice = st.selectbox("Choose a pending request", list(opts))
        rid = opts[choice]
        c1,c2 = st.columns(2)
        with c1:
            if st.button("Accept request", type="primary", use_container_width=True):
                with get_conn() as conn:
                    req = conn.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()
                    don = conn.execute("SELECT * FROM donations WHERE id=?", (req["donation_id"],)).fetchone()
                    if don["status"] != "Available":
                        st.error("This donation is no longer available.")
                    elif req["requested_quantity"] > don["quantity"]:
                        st.error("Requested quantity exceeds the listed quantity.")
                    else:
                        conn.execute("UPDATE requests SET status='Accepted',updated_at=? WHERE id=?", (now_str(),rid))
                        conn.execute("UPDATE donations SET status='Reserved' WHERE id=?", (don["id"],))
                        conn.execute("UPDATE requests SET status='Declined',updated_at=? WHERE donation_id=? AND id<>? AND status='Pending'",
                                     (now_str(),don["id"],rid))
                        conn.commit()
                        st.success("Request accepted. Other pending requests for this listing were declined.")
                        st.rerun()
        with c2:
            if st.button("Decline request", use_container_width=True):
                execute("UPDATE requests SET status='Declined',updated_at=? WHERE id=? AND status='Pending'", (now_str(),rid))
                st.success("Request declined.")
                st.rerun()

# ----------------------------- NGO: find food ------------------------------
elif page == "Find food":
    st.subheader("🔎 Find suitable food")
    if not user["verified"]:
        st.warning("Your NGO account is awaiting administrator verification. You can browse listings, but you cannot submit requests yet.")
    available_df = query_df("""SELECT d.id,d.food_name,d.category,d.quantity,d.unit,d.location,d.description,
                                      d.prepared_at,d.expiry_at,d.deadline,u.name AS donor_name,
                                      u.organization AS donor_organization
                               FROM donations d JOIN users u ON u.id=d.donor_id
                               WHERE d.status='Available' AND d.deadline>=? AND d.expiry_at>=?
                               ORDER BY d.deadline ASC""", (now_str(), now_str()))
    f1,f2,f3 = st.columns(3)
    with f1:
        categories = ["All"] + sorted(available_df["category"].dropna().unique().tolist()) if not available_df.empty else ["All"]
        cat_filter = st.selectbox("Category", categories)
    with f2:
        location_filter = st.text_input("Location contains", value=user["location"] or "")
    with f3:
        max_days = st.selectbox("Deadline within", ["Any time", "6 hours", "24 hours", "3 days"])
    filtered = available_df.copy()
    if cat_filter != "All" and not filtered.empty:
        filtered = filtered[filtered["category"] == cat_filter]
    if location_filter.strip() and not filtered.empty:
        filtered = filtered[filtered["location"].str.contains(location_filter.strip(), case=False, na=False)]
    if not filtered.empty and max_days != "Any time":
        hours = {"6 hours":6, "24 hours":24, "3 days":72}[max_days]
        cutoff = datetime.now() + timedelta(hours=hours)
        filtered = filtered[pd.to_datetime(filtered["deadline"]) <= cutoff]
    # Transparent rules-based recommendation score: nearby text match + urgency + freshness.
    if not filtered.empty:
        now_dt = pd.Timestamp.now()
        deadline_series = pd.to_datetime(filtered["deadline"], errors="coerce")
        hours_left = (deadline_series - now_dt).dt.total_seconds() / 3600
        location_match = filtered["location"].str.contains((user["location"] or "").strip(), case=False, na=False) if (user["location"] or "").strip() else pd.Series(False, index=filtered.index)
        filtered["match_score"] = (50 + location_match.astype(int) * 25 + (hours_left.clip(lower=0, upper=72).fillna(72).rsub(72) / 72 * 25)).round().astype(int).clip(0,100)
        filtered = filtered.sort_values(["match_score", "deadline"], ascending=[False, True])
        filtered["recommendation"] = filtered["match_score"].apply(lambda score: "⭐ Strong match" if score >= 75 else ("👍 Good match" if score >= 60 else "Available"))
    st.caption(f"{len(filtered)} matching listing(s) · ranked by location similarity and collection urgency")
    show_donation_table(filtered)
    if not filtered.empty:
        labels = {f"#{int(r.id)} · {r.food_name} · {r.quantity:g} {r.unit} · {r.location}": int(r.id) for r in filtered.itertuples()}
        with st.form("request_food_form"):
            chosen = st.selectbox("Choose a donation", list(labels))
            donation_id = labels[chosen]
            donation = filtered[filtered["id"] == donation_id].iloc[0]
            requested_quantity = st.number_input("Quantity requested", min_value=0.1, max_value=float(donation["quantity"]), value=float(donation["quantity"]), step=0.5)
            message = st.text_area("Message to donor (optional)", placeholder="Tell the donor who the food will serve or any pickup details.")
            send = st.form_submit_button("Request donation", type="primary", disabled=not bool(user["verified"]))
        if send:
            existing = query_df("SELECT id FROM requests WHERE donation_id=? AND ngo_id=? AND status IN ('Pending','Accepted')", (donation_id,user["id"]))
            if not existing.empty:
                st.error("You already have an active request for this donation.")
            else:
                execute("""INSERT INTO requests(donation_id,ngo_id,requested_quantity,message,status,created_at,updated_at)
                           VALUES(?,?,?,?,?,?,?)""",
                        (donation_id,user["id"],requested_quantity,message.strip(),"Pending",now_str(),now_str()))
                st.success("Request sent to the donor.")
                st.rerun()

# ----------------------------- NGO: requests -------------------------------
elif page == "My requests":
    st.subheader("📨 My donation requests")
    df = query_df("""SELECT r.id AS request_id,d.food_name,d.category,r.requested_quantity,d.unit,
                            d.location,d.deadline,u.name AS donor_name,r.message,r.status,r.created_at,r.updated_at
                     FROM requests r JOIN donations d ON d.id=r.donation_id
                     JOIN users u ON u.id=d.donor_id
                     WHERE r.ngo_id=? ORDER BY r.created_at DESC""", (user["id"],))
    show_donation_table(df)
    if not df.empty:
        accepted = df[df["status"] == "Accepted"]
        if not accepted.empty:
            st.markdown("#### Record a completed pickup")
            accepted_opts = {f"Request #{int(r.request_id)} · {r.food_name} · {r.requested_quantity:g} {r.unit}": int(r.request_id) for r in accepted.itertuples()}
            with st.form("pickup_form"):
                selected = st.selectbox("Accepted request", list(accepted_opts))
                rid = accepted_opts[selected]
                req_row = accepted[accepted["request_id"] == rid].iloc[0]
                actual = st.number_input("Actual quantity collected", min_value=0.1, max_value=float(req_row["requested_quantity"]), value=float(req_row["requested_quantity"]), step=0.5)
                notes = st.text_area("Pickup notes (optional)")
                confirm = st.form_submit_button("Confirm pickup", type="primary")
            if confirm:
                with get_conn() as conn:
                    req = conn.execute("SELECT * FROM requests WHERE id=? AND ngo_id=? AND status='Accepted'", (rid,user["id"])).fetchone()
                    if not req:
                        st.error("This request is no longer eligible for pickup.")
                    else:
                        conn.execute("INSERT INTO pickups(request_id,actual_quantity,picked_up_at,notes) VALUES(?,?,?,?)",
                                     (rid,actual,now_str(),notes.strip()))
                        conn.execute("UPDATE requests SET status='Collected',updated_at=? WHERE id=?", (now_str(),rid))
                        conn.execute("UPDATE donations SET status='Collected' WHERE id=?", (req["donation_id"],))
                        conn.commit()
                        st.success("Pickup recorded. Thank you for reducing food waste!")
                        st.rerun()

# ----------------------------- NGO: pickup history -------------------------
elif page == "Pickup history":
    st.subheader("🚚 My pickup history")
    df = query_df("""SELECT p.id AS pickup_id,d.food_name,d.category,p.actual_quantity,d.unit,
                            d.location,p.picked_up_at,p.notes,u.name AS donor_name
                     FROM pickups p JOIN requests r ON p.request_id=r.id
                     JOIN donations d ON r.donation_id=d.id JOIN users u ON d.donor_id=u.id
                     WHERE r.ngo_id=? ORDER BY p.picked_up_at DESC""", (user["id"],))
    show_donation_table(df)
    if not df.empty:
        st.metric("Total quantity collected", f"{df['actual_quantity'].sum():,.1f}")

# ----------------------------- Admin: verify -------------------------------
elif page == "Admin verification":
    st.subheader("🛡️ NGO verification center")
    df = query_df("SELECT id,name,email,organization,location,verified,created_at FROM users WHERE role='NGO' ORDER BY verified,created_at")
    pending_count = int((df["verified"] == 0).sum()) if not df.empty else 0
    verified_count = int((df["verified"] == 1).sum()) if not df.empty else 0
    a,b,c = st.columns(3)
    a.metric("Total NGOs", len(df))
    b.metric("Awaiting review", pending_count)
    c.metric("Verified", verified_count)
    search = st.text_input("🔎 Search NGO name, email, organization or location")
    status_filter = st.selectbox("Verification status", ["All", "Pending", "Verified"])
    filtered = df.copy()
    if search.strip() and not filtered.empty:
        mask = filtered[["name","email","organization","location"]].fillna("").astype(str).apply(
            lambda col: col.str.contains(search.strip(), case=False, na=False)
        ).any(axis=1)
        filtered = filtered[mask]
    if status_filter == "Pending" and not filtered.empty:
        filtered = filtered[filtered["verified"] == 0]
    elif status_filter == "Verified" and not filtered.empty:
        filtered = filtered[filtered["verified"] == 1]
    show_donation_table(filtered)
    admin_export_button(filtered, "foodbridge_ngo_verification.csv")
    pending = filtered[filtered["verified"] == 0] if not filtered.empty else filtered
    if not pending.empty:
        opts = {f"#{int(r.id)} · {r.organization or r.name} · {r.email}": int(r.id) for r in pending.itertuples()}
        selected = st.selectbox("Select an NGO to review", list(opts))
        uid = opts[selected]
        x,y = st.columns(2)
        with x:
            if st.button("✅ Verify organization", type="primary", use_container_width=True):
                execute("UPDATE users SET verified=1 WHERE id=? AND role='NGO'", (uid,))
                st.success("NGO verified. It can now submit donation requests.")
                st.rerun()
        with y:
            if st.button("⏸️ Keep pending", use_container_width=True):
                st.info("The NGO remains pending. You can verify it after reviewing its details.")
    else:
        st.success("No pending NGOs match the current filters.")
    if not df.empty:
        chart = df.assign(verification=df["verified"].map({0:"Pending",1:"Verified"})).groupby("verification", as_index=False).size()
        st.plotly_chart(px.pie(chart, names="verification", values="size", hole=.5, title="NGO verification status"), use_container_width=True)

# ----------------------------- Admin: donations -----------------------------
elif page == "Manage donations":
    st.subheader("📋 Donation management")
    df = query_df("""SELECT d.id,d.food_name,d.category,d.quantity,d.unit,d.location,d.deadline,d.status,d.created_at,
                            u.name AS donor_name,u.organization AS donor_organization,u.email AS donor_email
                     FROM donations d JOIN users u ON u.id=d.donor_id ORDER BY d.created_at DESC""")
    a,b,c,d = st.columns(4)
    a.metric("Total listings", len(df))
    b.metric("Available", int((df["status"] == "Available").sum()) if not df.empty else 0)
    c.metric("Reserved", int((df["status"] == "Reserved").sum()) if not df.empty else 0)
    d.metric("Collected", int((df["status"] == "Collected").sum()) if not df.empty else 0)
    f1,f2,f3 = st.columns(3)
    with f1:
        search = st.text_input("🔎 Search food, donor or location")
    with f2:
        categories = ["All"] + sorted(df["category"].dropna().unique().tolist()) if not df.empty else ["All"]
        category_filter = st.selectbox("Category", categories)
    with f3:
        status_filter = st.selectbox("Status", ["All","Available","Reserved","Collected","Expired","Removed"])
    filtered = df.copy()
    if search.strip() and not filtered.empty:
        mask = filtered[["food_name","donor_name","donor_organization","location"]].fillna("").astype(str).apply(
            lambda col: col.str.contains(search.strip(), case=False, na=False)
        ).any(axis=1)
        filtered = filtered[mask]
    if category_filter != "All" and not filtered.empty:
        filtered = filtered[filtered["category"] == category_filter]
    if status_filter != "All" and not filtered.empty:
        filtered = filtered[filtered["status"] == status_filter]
    show_donation_table(filtered)
    admin_export_button(filtered, "foodbridge_donations_filtered.csv")
    if not filtered.empty:
        opts = {f"#{int(r.id)} · {r.food_name} · {r.status}": int(r.id) for r in filtered.itertuples()}
        choice = st.selectbox("Select listing to moderate", list(opts))
        did = opts[choice]
        current_status = str(filtered.loc[filtered["id"] == did, "status"].iloc[0])
        statuses = ["Available","Reserved","Collected","Expired","Removed"]
        status = st.selectbox("Set listing status", statuses, index=statuses.index(current_status) if current_status in statuses else 0)
        if st.button("Update listing status", type="primary"):
            execute("UPDATE donations SET status=? WHERE id=?", (status,did))
            st.success("Listing status updated.")
            st.rerun()
    if not df.empty:
        chart = df.groupby("status", as_index=False).size()
        st.plotly_chart(px.bar(chart, x="status", y="size", color="status", title="Listings by status"), use_container_width=True)

# ----------------------------- Admin: requests ------------------------------
elif page == "All requests":
    st.subheader("🤝 Request monitoring")
    df = query_df("""SELECT r.id AS request_id,d.food_name,d.category,du.name AS donor_name,du.organization AS donor_organization,
                            nu.name AS ngo_name,nu.organization AS ngo_organization,r.requested_quantity,d.unit,
                            r.status,r.message,r.created_at,r.updated_at
                     FROM requests r JOIN donations d ON r.donation_id=d.id
                     JOIN users du ON d.donor_id=du.id JOIN users nu ON r.ngo_id=nu.id
                     ORDER BY r.created_at DESC""")
    a,b,c,d = st.columns(4)
    a.metric("Total requests", len(df))
    for col, status, label in [(b,"Pending","Pending"),(c,"Accepted","Accepted"),(d,"Collected","Collected")]:
        col.metric(label, int((df["status"] == status).sum()) if not df.empty else 0)
    f1,f2 = st.columns(2)
    with f1:
        status_filter = st.selectbox("Request status", ["All","Pending","Accepted","Declined","Collected"])
    with f2:
        search = st.text_input("🔎 Search food, donor or NGO")
    filtered = df.copy()
    if status_filter != "All" and not filtered.empty:
        filtered = filtered[filtered["status"] == status_filter]
    if search.strip() and not filtered.empty:
        mask = filtered[["food_name","donor_name","donor_organization","ngo_name","ngo_organization"]].fillna("").astype(str).apply(
            lambda col: col.str.contains(search.strip(), case=False, na=False)
        ).any(axis=1)
        filtered = filtered[mask]
    show_donation_table(filtered)
    admin_export_button(filtered, "foodbridge_requests_filtered.csv")
    if not df.empty:
        chart = df.groupby("status", as_index=False).size()
        st.plotly_chart(px.pie(chart, names="status", values="size", hole=.48, title="Request status mix"), use_container_width=True)

# ----------------------------- Admin: pickups ------------------------------
elif page == "Pickup records":
    st.subheader("🚚 Pickup operations")
    df = query_df("""SELECT p.id AS pickup_id,d.food_name,d.category,nu.name AS ngo_name,p.actual_quantity,d.unit,
                            p.picked_up_at,p.notes,du.name AS donor_name,du.organization AS donor_organization
                     FROM pickups p JOIN requests r ON p.request_id=r.id
                     JOIN donations d ON r.donation_id=d.id JOIN users nu ON r.ngo_id=nu.id
                     JOIN users du ON d.donor_id=du.id ORDER BY p.picked_up_at DESC""")
    total_qty = float(df["actual_quantity"].sum()) if not df.empty else 0.0
    a,b,c = st.columns(3)
    a.metric("Completed pickups", len(df))
    b.metric("Total quantity recorded", f"{total_qty:,.1f}")
    c.metric("Food categories", int(df["category"].nunique()) if not df.empty else 0)
    f1,f2 = st.columns(2)
    with f1:
        search = st.text_input("🔎 Search food, donor or NGO")
    with f2:
        categories = ["All"] + sorted(df["category"].dropna().unique().tolist()) if not df.empty else ["All"]
        category_filter = st.selectbox("Food category", categories)
    filtered = df.copy()
    if search.strip() and not filtered.empty:
        mask = filtered[["food_name","donor_name","donor_organization","ngo_name"]].fillna("").astype(str).apply(
            lambda col: col.str.contains(search.strip(), case=False, na=False)
        ).any(axis=1)
        filtered = filtered[mask]
    if category_filter != "All" and not filtered.empty:
        filtered = filtered[filtered["category"] == category_filter]
    show_donation_table(filtered)
    admin_export_button(filtered, "foodbridge_pickup_records.csv")
    if not df.empty:
        chart = df.groupby("category", as_index=False)["actual_quantity"].sum()
        st.plotly_chart(px.bar(chart, x="category", y="actual_quantity", color="category", title="Collected quantity by category"), use_container_width=True)

# ----------------------------- Admin: users --------------------------------
elif page == "Users":
    st.subheader("👥 User directory")
    df = query_df("SELECT id,name,email,role,organization,location,verified,created_at FROM users ORDER BY created_at DESC")
    a,b,c,d = st.columns(4)
    a.metric("Total accounts", len(df))
    b.metric("Donors", int((df["role"] == "Donor").sum()) if not df.empty else 0)
    c.metric("NGOs", int((df["role"] == "NGO").sum()) if not df.empty else 0)
    d.metric("Admins", int((df["role"] == "Admin").sum()) if not df.empty else 0)
    f1,f2 = st.columns(2)
    with f1:
        role_filter = st.selectbox("Account type", ["All","Donor","NGO","Admin"])
    with f2:
        search = st.text_input("🔎 Search name, email, organization or location")
    filtered = df.copy()
    if role_filter != "All" and not filtered.empty:
        filtered = filtered[filtered["role"] == role_filter]
    if search.strip() and not filtered.empty:
        mask = filtered[["name","email","organization","location"]].fillna("").astype(str).apply(
            lambda col: col.str.contains(search.strip(), case=False, na=False)
        ).any(axis=1)
        filtered = filtered[mask]
    show_donation_table(filtered)
    admin_export_button(filtered, "foodbridge_users.csv")
    st.caption("Passwords are hashed and never displayed. Sample demo accounts are seeded with a shared demo password for local testing.")
    editable_ngos = filtered[filtered["role"] == "NGO"] if not filtered.empty else filtered
    if not editable_ngos.empty:
        opts = {f"#{int(r.id)} · {r.organization or r.name} · {'Verified' if r.verified else 'Pending'}": int(r.id) for r in editable_ngos.itertuples()}
        selected = st.selectbox("Manage NGO verification", list(opts))
        uid = opts[selected]
        current = int(editable_ngos.loc[editable_ngos["id"] == uid, "verified"].iloc[0])
        action = st.selectbox("Verification setting", ["Verified","Pending"], index=0 if current else 1)
        if st.button("Save NGO verification", type="primary"):
            execute("UPDATE users SET verified=? WHERE id=? AND role='NGO'", (1 if action == "Verified" else 0, uid))
            st.success("NGO verification setting saved.")
            st.rerun()

st.divider()
st.caption("FoodBridge · Academic prototype · SDG 2 Zero Hunger · SDG 12 Responsible Consumption and Production")
