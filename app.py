from flask import Flask, jsonify
import pandas as pd

app = Flask(__name__)

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

if __name__ == "__main__":
    app.run()