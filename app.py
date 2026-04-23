from flask import Flask, jsonify
from flask_cors import CORS
import pandas as pd
from funds import get_funds_rank, get_funds_debug

app = Flask(__name__)
CORS(app)


def load(file):
    try:
        return pd.read_csv(file).to_dict("records")
    except Exception:
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
    return jsonify(get_funds_rank(top_n=20))


@app.route("/api/funds/debug")
def funds_debug():
    return jsonify(get_funds_debug())


if __name__ == "__main__":
    app.run()