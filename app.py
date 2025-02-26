import os
import logging
from flask import Flask, redirect, url_for, session, render_template
from flask_sqlalchemy import SQLAlchemy
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
import sys
# Load environment variables
load_dotenv()

app = Flask(__name__)

# Logging setup (logs to app.log + console)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("app.log", encoding="utf-8"),  # Ensure UTF-8 encoding
        logging.StreamHandler(sys.stdout)  # Use sys.stdout for console logs
    ]
)
logger = logging.getLogger(__name__)

# Database Configuration (Using SQLite, can be switched to PostgreSQL/MySQL)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///users.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = os.getenv("SECRET_KEY")

# Initialize database
db = SQLAlchemy(app)

# User Model (Updated to store Google ID)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(100), unique=True, nullable=False)  # Stores Google ID
    email = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    picture = db.Column(db.String(300))

    def __init__(self, google_id, email, name, picture):
        self.google_id = google_id
        self.email = email
        self.name = name
        self.picture = picture

# OAuth configuration for Google login
oauth = OAuth(app)
google = oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    access_token_url="https://oauth2.googleapis.com/token",
    authorize_url="https://accounts.google.com/o/oauth2/auth",
    api_base_url="https://www.googleapis.com/oauth2/v1/",
    userinfo_endpoint="https://www.googleapis.com/oauth2/v1/userinfo",
    client_kwargs={"scope": "email profile"},
)

@app.before_first_request
def create_tables():
    """Ensures database tables are created before the app runs."""
    db.create_all()

@app.route("/")
def home():
    """Homepage"""
    user = session.get("user")
    if user:
        logger.info(f"User logged in: {user['email']}")
    else:
        logger.info("User is not logged in.")
    return render_template("index.html")

@app.route("/login")
def login():
    """Redirect to Google login"""
    logger.info("Redirecting to Google login...")
    return google.authorize_redirect(url_for("authorize", _external=True))

@app.route("/login/callback")
def authorize():
    """Google OAuth Callback: Authenticate user and store in DB"""
    try:
        token = google.authorize_access_token()
        user_info = google.get("userinfo").json()

        if not user_info:
            logger.error("Failed to retrieve user info from Google!")
            return redirect(url_for("home"))

        google_id = user_info.get("id")  # Get Google ID
        email = user_info.get("email")
        name = user_info.get("name")
        picture = user_info.get("picture")

        # Store user session
        session["user"] = user_info
        logger.info(f"✅ User logged in successfully: {email} (Google ID: {google_id})")

        # Check if user exists in the database
        user = User.query.filter_by(email=email).first()

        if user:
            logger.info(f"🔄 Updating user: {email}")
            user.google_id = google_id  # Update Google ID if missing
            user.name = name
            user.picture = picture
        else:
            logger.info(f"🆕 New user detected: {email}. Adding to database.")
            user = User(google_id=google_id, email=email, name=name, picture=picture)
            db.session.add(user)

        db.session.commit()

        return redirect(url_for("chatbot"))

    except Exception as e:
        logger.exception("❌ Error during Google login:")
        return redirect(url_for("home"))
    
@app.route("/chatbot")
def chatbot():
    """Chatbot Page: Requires Authentication"""
    logging.info(f"📌 DEBUG: Session Data - {dict(session)}")

    email = session.get("user", {}).get("email")

    if not email:
        logging.warning("🚫 No user session found! Redirecting to login.")
        return redirect(url_for("login"))

    # Check if user exists in the database
    user = User.query.filter_by(email=email).first()
    if not user:
        logging.error(f"🚫 User {email} not found in database! Clearing session & redirecting.")
        session.clear()
        return redirect(url_for("login"))

    return render_template("chatbot.html", name=user.name, email=user.email, picture=user.picture)



















@app.route("/logout")
def logout():
    """Logout User"""
    user = session.get("user")
    if user:
        logger.info(f"User logged out: {user['email']}")
    else:
        logger.info("Logout attempted with no active session.")

    session.pop("user", None)
    return redirect(url_for("home"))

if __name__ == "__main__":
    logger.info("🚀 Starting Flask app on port 8000")
    app.run(debug=True, host="127.0.0.1", port=8000)
