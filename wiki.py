from flask import Flask, render_template
from backend.map_routes import map_bp
from backend.auth_routes import auth_bp

app = Flask(__name__, static_folder="frontend/static")
app.secret_key = "secret-key"

@app.route("/")
def welcome_page():
    return render_template("welcome-page.html")

app.register_blueprint(auth_bp)
app.register_blueprint(map_bp)
