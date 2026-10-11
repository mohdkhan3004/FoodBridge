# FoodBridge — AI-Based Food Waste Management System

**Prepared by:** Mohammed Irfan Khan  
**Institution:** Muffakham Jah College of Engineering and Technology  
**SDGs:** SDG 2 — Zero Hunger; SDG 12 — Responsible Consumption and Production

FoodBridge is a working Streamlit + Python + SQLite academic prototype for connecting surplus-food donors with verified NGOs.

## Features
- Separate Donor, NGO, and Admin roles
- Registration/login with salted PBKDF2 password hashes
- Food donation listings with category, quantity, location, use-by time, and pickup deadline
- Rules-based food matching by category, location text, and deadline
- Donation requests that donors can accept or decline
- Pickup records with actual collected quantity
- Animated responsive styling, hover effects, and reduced-motion accessibility support
- Interactive dashboard with Plotly charts and summary metrics
- Impact Center with milestones, pickup completion progress, and configurable community goals
- Activity feed with status filters and request timelines
- Transparent rules-based match score based on location similarity and collection urgency
- Admin NGO verification and listing moderation
- SQLite persistence in `data/foodbridge.db`

> Matching is currently rules-based, not a trained AI/ML model. This keeps the project fully runnable without external APIs or model downloads. You can later add a recommendation model using historical pickup data.

## Project structure
```text
FoodBridge/
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
└── data/
    └── .gitkeep
```
The SQLite database is created automatically in `data/foodbridge.db` on first run.

## Requirements
- Python 3.10 or newer recommended
- Internet access for installing the Python packages the first time

## Run on Windows
Open Command Prompt or PowerShell in the `FoodBridge` folder:

```powershell
py -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

## Run on macOS / Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

Streamlit will show a local URL, usually `http://localhost:8501`.

## Administrator account
An administrator account is initialized automatically when the database is first created. For security, demo login credentials are not displayed in the app interface or in this README. Before public deployment, configure a secure administrator password and review the authentication settings in `app.py`.

## Suggested demo flow
1. Sign in as admin and keep the session open in one browser.
2. Register a Donor account, then add a donation with a future use-by time and pickup deadline.
3. Register an NGO account.
4. Sign back in as admin and verify the NGO under **Admin verification**.
5. Sign in as the NGO, filter listings and request food.
6. Sign in as the donor and accept the request.
7. Sign in as the NGO and record the pickup.
8. View the updated dashboard and pickup history.

## Important prototype notes
- Use consistent units when comparing quantities. A `kg` value and a `meals` value are not directly comparable.
- This is a demonstration project, not a food-safety certification system. Donors must ensure food is safe, properly stored, labelled for allergens, and legally eligible for donation.
- SQLite is suitable for a local academic prototype. For a multi-user production deployment, consider PostgreSQL, secure secret management, audit logging, rate limiting, and deployment behind HTTPS.
- Do not expose the demo admin credentials or database file in a public repository.


## Demo data and admin tools
On a fresh database, FoodBridge seeds sample donors, NGOs, food listings, requests, and pickup records so the dashboard, Impact Center, activity feed, and admin pages are populated immediately. Seeded records are only added when the donations table is empty; they are not added repeatedly on every launch.

Sample Donor/NGO accounts use the shared local-testing password `FoodBridgeDemo@123`. These are fictional accounts for a local academic demonstration only. Do not use demo credentials or seeded data in a public deployment.

Admin tools include search and status filters, summary metrics, category/status charts, CSV export, NGO verification controls, and donation status moderation.
