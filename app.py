import os
from datetime import datetime, timezone
from authlib.integrations.flask_client import OAuth
import boto3
from boto3.dynamodb.conditions import Key
from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, url_for, session

load_dotenv()



app = Flask(__name__)
app.secret_key = os.environ["FLASK_SECRET_KEY"]
oauth = OAuth(app)
oauth.register(
    name="cognito",
    client_id=os.environ["COGNITO_CLIENT_ID"],
    client_secret=os.environ["COGNITO_CLIENT_SECRET"],
    server_metadata_url=f"https://cognito-idp.eu-central-1.amazonaws.com/{os.environ['COGNITO_POOL_ID']}/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

@app.route("/logout")
def logout():
    session.clear()
    domain = os.environ["COGNITO_DOMAIN"]
    client_id = os.environ["COGNITO_CLIENT_ID"]
    return redirect(
        f"{domain}/logout?client_id={client_id}&logout_uri=https://jobs.ruskodavid.hu/logout"
    )







@app.before_request
def require_login():
    if request.endpoint in ("login", "callback", "static"):
        return
    if "user_id" not in session:
        return redirect(url_for("login"))




@app.route("/callback")
def callback():
    if "user_id" in session:
        return redirect(url_for("index"))
    try:
        token = oauth.cognito.authorize_access_token()
    except Exception:
        return redirect(url_for("login"))
    user = token.get("userinfo")
    session["user_id"] = user["sub"]
    session["email"] = user.get("email", "")
    return redirect(url_for("index"))










STATUSES = ["new", "interested", "applied", "interviewing", "rejected", "dismissed"]


def get_table(name):
    region = os.environ.get("AWS_REGION", "eu-central-1")
    return boto3.resource("dynamodb", region_name=region).Table(os.environ[name])


def age(iso):
    """Turn an ISO timestamp into 'today' / '3 days ago'."""
    if not iso:
        return ""
    try:
        seen = datetime.fromisoformat(iso)
    except ValueError:
        return ""
    days = (datetime.now(timezone.utc) - seen).days
    if days <= 0:
        return "today"
    if days == 1:
        return "yesterday"
    return f"{days} days ago"


@app.route("/login")
def login():
    return oauth.cognito.authorize_redirect("https://jobs.ruskodavid.hu/callback")

@app.route("/")
def index():
    uid = session["user_id"]

    # 1. this user's rows
    table = get_table("USER_JOBS_TABLE")
    resp = table.query(KeyConditionExpression=Key("user_id").eq(uid))
    user_jobs = resp["Items"]
    while "LastEvaluatedKey" in resp:
        resp = table.query(
            KeyConditionExpression=Key("user_id").eq(uid),
            ExclusiveStartKey=resp["LastEvaluatedKey"],
        )
        user_jobs.extend(resp["Items"])

    # 2. the shared job data, 100 keys at a time
    region = os.environ.get("AWS_REGION", "eu-central-1")
    db = boto3.resource("dynamodb", region_name=region)
    job_ids = [uj["job_id"] for uj in user_jobs]
    items = []
    for i in range(0, len(job_ids), 100):
        chunk = job_ids[i:i + 100]
        r = db.batch_get_item(
            RequestItems={os.environ["JOBS_TABLE"]: {"Keys": [{"id": j} for j in chunk]}}
        )
        items.extend(r["Responses"][os.environ["JOBS_TABLE"]])

    # 3. merge
    by_id = {j["id"]: j for j in items}
    jobs = []
    for uj in user_jobs:
        job = by_id.get(uj["job_id"])
        if job:
            jobs.append({**job, **uj})

    # 4. everything below is your original code, unchanged
    for job in jobs:
        job["age"] = age(job.get("posted_at") or job.get("first_seen"))
        job.setdefault("status", "new")
        job["score"] = int(job.get("score") or 0)
        job["band"] = "high" if job["score"] >= 70 else "mid" if job["score"] >= 45 else "low"
        desc = job.get("description")
        lines = desc if isinstance(desc, list) else []
        job["lines"] = [
            {"text": l, "heading": l.rstrip().endswith(":") and len(l) < 60}
            for l in lines
        ]
        last = job.get("last_seen")
        job["stale"] = bool(last) and (datetime.now(timezone.utc) - datetime.fromisoformat(last)).days > 7

    counts = {s: 0 for s in STATUSES}
    for job in jobs:
        counts[job["status"]] = counts.get(job["status"], 0) + 1
    counts["all"] = len(jobs)

    active = request.args.get("status", "new")
    if active != "all":
        jobs = [j for j in jobs if j["status"] == active]

    jobs.sort(key=lambda j: (j["score"], j.get("first_seen", "")), reverse=True)

    return render_template("index.html", jobs=jobs, counts=counts,
                           active=active, statuses=STATUSES)




@app.route("/status", methods=["POST"])
def set_status():
    get_table("USER_JOBS_TABLE").update_item(
        Key={"user_id": session["user_id"], "job_id": request.form["id"]},
        UpdateExpression="SET #s = :v",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":v": request.form["status"]},
    )
    return redirect(request.referrer or url_for("index"))


if __name__ == "__main__":
    # debug=False: the Flask debugger is remote code execution on a public IP
    app.run(host="127.0.0.1", port=4999)
