from flask import Flask, render_template
from backend.map_routes import map_bp
from backend.submission_routes import submission_bp

app = Flask(__name__, static_folder="frontend/static")

@app.route("/")
def welcome_page():
    return render_template("welcome-page.html")

app.register_blueprint(map_bp)
app.register_blueprint(submission_bp)
