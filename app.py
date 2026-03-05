#!/usr/bin/env python3
"""Stock Screener Dashboard — Flask web application."""

import os
from flask import Flask, render_template, jsonify, request
from screener.data_service import StockDataService

app = Flask(__name__)
service = StockDataService(edgar_email=os.environ.get("EDGAR_EMAIL", "andrew@sailingcircus.com"))


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/quote/<ticker>")
def api_quote(ticker):
    try:
        return jsonify(service.get_quote(ticker))
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/profile/<ticker>")
def api_profile(ticker):
    return jsonify(service.get_profile(ticker))


@app.route("/api/metrics/<ticker>")
def api_metrics(ticker):
    return jsonify(service.get_metrics(ticker))


@app.route("/api/history/<ticker>")
def api_history(ticker):
    period = request.args.get("period", "1y")
    return jsonify(service.get_history(ticker, period))


@app.route("/api/financials/<ticker>")
def api_financials(ticker):
    stmt_type = request.args.get("type", "income")
    freq = request.args.get("freq", "annual")
    return jsonify(service.get_financials(ticker, stmt_type, freq))


@app.route("/api/recommendations/<ticker>")
def api_recommendations(ticker):
    return jsonify(service.get_recommendations(ticker))


@app.route("/api/analyst_targets/<ticker>")
def api_analyst_targets(ticker):
    return jsonify(service.get_analyst_targets(ticker))


@app.route("/api/news/<ticker>")
def api_news(ticker):
    return jsonify(service.get_news(ticker))


@app.route("/api/upgrades/<ticker>")
def api_upgrades(ticker):
    return jsonify(service.get_upgrades(ticker))


@app.route("/api/holders/<ticker>")
def api_holders(ticker):
    return jsonify(service.get_holders(ticker))


@app.route("/api/filings/<ticker>")
def api_filings(ticker):
    return jsonify(service.get_filings(ticker))


@app.route("/api/fetch/<ticker>", methods=["POST"])
def api_fetch(ticker):
    results = service.fetch_all(ticker)
    return jsonify(results)


if __name__ == "__main__":
    app.run(debug=False, port=5000)
