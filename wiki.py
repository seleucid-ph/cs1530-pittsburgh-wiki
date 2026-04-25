from flask import Flask, render_template, session, redirect
from backend.map_routes import map_bp
from backend.auth_routes import auth_bp

app = Flask(__name__, static_folder="frontend/static")
app.secret_key = "secret-key"

@app.route("/")
def welcome_page():
    print("NEW NEW")#for debugging
    return render_template("welcome-page.html")

@app.route("/login")
def login_page():
    return render_template("login.html")

@app.route("/signup")
def signup_page():
    return render_template("signup.html")

@app.route("/home")
def home():
    if "user_id" not in session:
        return redirect("/")
    return render_template("home.html")

app.register_blueprint(auth_bp)
app.register_blueprint(map_bp)
