#!/usr/bin/env python3
"""
Витягує дані з GA4 і зберігає в google_data.json
Запускається автоматично через GitHub Actions щодня.
"""
import json
import os
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunReportRequest, DateRange, Dimension, Metric,
    FilterExpression, Filter, OrderBy
)

PROPERTY_ID = "309925981"
TOKEN_FILE = "google_token.json"

def get_credentials():
    token_json = os.environ.get("GOOGLE_TOKEN_JSON")
    if token_json:
        data = json.loads(token_json)
    else:
        with open(TOKEN_FILE) as f:
            data = json.load(f)

    creds = Credentials(
        token=None,
        refresh_token=data["refresh_token"],
        client_id=data["client_id"],
        client_secret=data["client_secret"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/analytics.readonly"]
    )
    creds.refresh(Request())
    return creds

def fetch_data(creds, start_date, end_date):
    client = BetaAnalyticsDataClient(credentials=creds)

    request = RunReportRequest(
        property=f"properties/{PROPERTY_ID}",
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
        dimensions=[
            Dimension(name="sessionCampaignName"),
            Dimension(name="sessionDefaultChannelGroup"),
        ],
        metrics=[
            Metric(name="sessions"),
            Metric(name="screenPageViews"),
            Metric(name="conversions"),
            Metric(name="totalUsers"),
            Metric(name="advertiserAdCost"),
            Metric(name="advertiserAdClicks"),
            Metric(name="advertiserAdImpressions"),
        ],
        dimension_filter=FilterExpression(
            filter=Filter(
                field_name="sessionDefaultChannelGroup",
                string_filter=Filter.StringFilter(
                    match_type=Filter.StringFilter.MatchType.CONTAINS,
                    value="Paid Search"
                )
            )
        ),
        limit=100
    )
    response = client.run_report(request)

    rows = []
    for row in response.rows:
        campaign = row.dimension_values[0].value
        channel  = row.dimension_values[1].value
        if campaign in ("(not set)", "(direct)", ""):
            continue
        sessions = int(row.metric_values[0].value or 0)
        views    = int(row.metric_values[1].value or 0)
        conv     = int(float(row.metric_values[2].value or 0))
        users    = int(row.metric_values[3].value or 0)
        cost     = round(float(row.metric_values[4].value or 0), 2)
        clicks   = int(row.metric_values[5].value or 0)
        impr     = int(row.metric_values[6].value or 0)
        rows.append({
            "name": campaign, "channel": channel,
            "sessions": sessions, "views": views,
            "conversions": conv, "users": users,
            "cost": cost, "clicks": clicks, "impressions": impr,
            "adgroups": []
        })
    rows.sort(key=lambda x: x["cost"], reverse=True)
    return rows

def main():
    print("🔄 Pobieranie danych z GA4...")
    creds = get_credentials()

    today = datetime.today()
    first_day = today.replace(day=1).strftime("%Y-%m-%d")
    yesterday = (today - timedelta(days=1)).strftime("%Y-%m-%d")

    rows_month = fetch_data(creds, first_day, yesterday)
    rows_30d   = fetch_data(creds, (today - timedelta(days=30)).strftime("%Y-%m-%d"), yesterday)
    rows_7d    = fetch_data(creds, (today - timedelta(days=7)).strftime("%Y-%m-%d"), yesterday)

    output = {
        "updated": datetime.utcnow().isoformat() + "Z",
        "this_month": rows_month,
        "last_30d":   rows_30d,
        "last_7d":    rows_7d
    }

    with open("google_data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    total_cost = sum(r["cost"] for r in rows_month)
    print(f"✅ Zapisano {len(rows_month)} kampanii | Łączny koszt: {total_cost:.2f} zł")

if __name__ == "__main__":
    main()
