#!/usr/bin/env python3
"""Stock Screener Dashboard — Flask web application."""

import os
import requests as http_requests
from flask import Flask, render_template, jsonify, request, Response
from screener.data_service import StockDataService

app = Flask(__name__)
service = StockDataService(edgar_email=os.environ.get("EDGAR_EMAIL", "andrew@sailingcircus.com"))

# Register API v1 blueprint
from screener.api_v1 import api_v1
app.register_blueprint(api_v1)

# Initialize database if DATABASE_URL is set
if os.environ.get("DATABASE_URL"):
    from screener.db import init_db
    with app.app_context():
        init_db()


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
    periods = int(request.args.get("periods", "5"))
    return jsonify(service.get_financials(ticker, stmt_type, freq, periods))


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


@app.route("/api/filing-proxy")
def api_filing_proxy():
    """Proxy SEC EDGAR documents to bypass X-Frame-Options."""
    url = request.args.get("url", "")
    if not url or not url.startswith("https://www.sec.gov/"):
        return "Invalid URL", 400
    try:
        resp = http_requests.get(url, headers={
            "User-Agent": "StockScreener andrew@sailingcircus.com",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }, timeout=30)
        # Inject <base> tag so relative links resolve against SEC
        content = resp.text
        base_url = url.rsplit("/", 1)[0] + "/"
        content = content.replace("<head>", f'<head><base href="{base_url}">', 1)
        if "<head>" not in content.lower():
            content = content.replace("<HEAD>", f'<HEAD><base href="{base_url}">', 1)
        return Response(content, content_type=resp.headers.get("Content-Type", "text/html"))
    except Exception as e:
        return f"Error fetching filing: {e}", 502


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", debug=False, port=port)
