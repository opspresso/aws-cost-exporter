import atexit
import boto3
import os
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timedelta
from flask import Flask, Response
from prometheus_client import Gauge, generate_latest, CONTENT_TYPE_LATEST


QUERY_PERIOD = os.getenv("QUERY_PERIOD", "1800")

METRIC_MONTHLY_COSTS = os.getenv("METRIC_MONTHLY_COSTS", None)
METRIC_TODAY_DAILY_COSTS = os.getenv("METRIC_TODAY_DAILY_COSTS", None)
METRIC_YESTERDAY_DAILY_COSTS = os.getenv("METRIC_YESTERDAY_DAILY_COSTS", None)
METRIC_TODAY_DAILY_USAGE = os.getenv("METRIC_TODAY_DAILY_USAGE", None)
METRIC_TODAY_DAILY_USAGE_NORM = os.getenv("METRIC_TODAY_DAILY_USAGE_NORM", None)


app = Flask(__name__)

client = boto3.client("ce")

scheduler = BackgroundScheduler()

if METRIC_MONTHLY_COSTS is not None:
    g_monthly = Gauge("aws_monyhly_costs", "Today monthly costs from AWS")
if METRIC_TODAY_DAILY_COSTS is not None:
    g_today = Gauge("aws_today_daily_costs", "Today daily costs from AWS")
if METRIC_YESTERDAY_DAILY_COSTS is not None:
    g_yesterday = Gauge("aws_yesterday_daily_costs", "Yesterday daily costs from AWS")
if METRIC_TODAY_DAILY_USAGE is not None:
    g_usage = Gauge("aws_today_daily_usage", "Today daily usage from AWS")
if METRIC_TODAY_DAILY_USAGE_NORM is not None:
    g_usage_norm = Gauge("aws_today_daily_usage_norm", "Today daily usage normalized from AWS")


def aws_query():
    print("Calculating costs...")

    now = datetime.now()
    yesterday = datetime.today() - timedelta(days=1)
    two_days_ago = datetime.today() - timedelta(days=2)
    first_day = datetime.today().replace(day=1)

    if METRIC_MONTHLY_COSTS is not None:
        r = client.get_cost_and_usage(
            TimePeriod={
                "Start": first_day.strftime("%Y-%m-%d"),
                "End":  now.strftime("%Y-%m-%d")
            },
            Granularity="MONTHLY",
            Metrics=["BlendedCost"]
        )
        cost = r["ResultsByTime"][0]["Total"]["BlendedCost"]["Amount"]
        print("aws_monyhly_costs: %s" %(cost))
        g_monthly.set(float(cost))

    if METRIC_TODAY_DAILY_COSTS is not None:
        r = client.get_cost_and_usage(
            TimePeriod={
                "Start": yesterday.strftime("%Y-%m-%d"),
                "End":  now.strftime("%Y-%m-%d")
            },
            Granularity="DAILY",
            Metrics=["BlendedCost"]
        )
        cost = r["ResultsByTime"][0]["Total"]["BlendedCost"]["Amount"]
        print("aws_today_daily_costs: %s" %(cost))
        g_today.set(float(cost))

    if METRIC_YESTERDAY_DAILY_COSTS is not None:
        r = client.get_cost_and_usage(
            TimePeriod={
                "Start": two_days_ago.strftime("%Y-%m-%d"),
                "End":  yesterday.strftime("%Y-%m-%d")
            },
            Granularity="DAILY",
            Metrics=["BlendedCost"]
        )
        cost = r["ResultsByTime"][0]["Total"]["BlendedCost"]["Amount"]
        print("aws_yesterday_daily_costs: %s" %(cost))
        g_yesterday.set(float(cost))

    if METRIC_TODAY_DAILY_USAGE is not None:
        r = client.get_cost_and_usage(
            TimePeriod={
                "Start": yesterday.strftime("%Y-%m-%d"),
                "End":  now.strftime("%Y-%m-%d")
            },
            Granularity="DAILY",
            Metrics=["UsageQuantity"]
        )
        usage = r["ResultsByTime"][0]["Total"]["UsageQuantity"]["Amount"]
        print("aws_today_daily_usage: %s" %(usage))
        g_usage.set(float(usage))

    if METRIC_TODAY_DAILY_USAGE_NORM is not None:
        r = client.get_cost_and_usage(
            TimePeriod={
                "Start": yesterday.strftime("%Y-%m-%d"),
                "End":  now.strftime("%Y-%m-%d")
            },
            Granularity="DAILY",
            Metrics=["NormalizedUsageAmount"]
        )
        usage = r["ResultsByTime"][0]["Total"]["NormalizedUsageAmount"]["Amount"]
        print("aws_today_daily_usage_norm: %s" %(usage))
        g_usage_norm.set(float(usage))

    print("Finished calculating costs.")

    return 0


@app.route("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


@app.route("/health")
def health():
    return "OK"


scheduler.start()
scheduler.add_job(
    func=aws_query,
    trigger=IntervalTrigger(seconds=int(QUERY_PERIOD),start_date=(datetime.now() + timedelta(seconds=5))),
    id="aws_query",
    name="Run AWS Query",
    replace_existing=True
    )
# Shut down the scheduler when exiting the app
atexit.register(lambda: scheduler.shutdown())
