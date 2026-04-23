from flask import Flask, jsonify
from flask_cors import CORS
import pandas as pd

app = Flask(__name__)
CORS(app)

def load(file):
    try:
        return pd.read_csv(file).to_dict("records")
    except:
        return []

@app.route("/")
def home():
    return "API is running"

@app.route("/api/stocks")
def stocks():
    return jsonify({
        "trend": load("data/trend.csv"),
        "setup": load("data/setup.csv"),
        "reversal": load("data/reversal.csv")
    })

@app.route("/api/funds")
def funds():
    return jsonify({
        "foreign": [],
        "invest": []
    })

if __name__ == "__main__":
    app.run()