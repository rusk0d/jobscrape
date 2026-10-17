import json
import feedparser
import re
import boto3
from datetime import datetime, timezone
import time
import requests
import html as htmllib
import calendar
import os
from dotenv import load_dotenv

load_dotenv()


SEARCHES = [
    "https://www.profession.hu/allasok/budapest/1,0,23,cloud%401%401?keywordsearch&rss",
    "https://www.profession.hu/allasok/budapest/1,0,23,devops%401%401?keywordsearch&rss",
    "https://www.profession.hu/allasok/budapest/1,0,23,sysadmin%401%401?keywordsearch&rss",
    "https://www.profession.hu/allasok/budapest/1,0,23,terraform%401%401?keywordsearch&rss",
    "https://www.profession.hu/allasok/budapest/1,0,23,aws%401%401?keywordsearch&rss",
    "https://www.profession.hu/allasok/budapest/1,0,23,rendszergazda%401%401?keywordsearch&rss",
    "https://www.profession.hu/allasok/budapest/1,0,23,linux%401%401?keywordsearch&rss",
    "https://www.profession.hu/allasok/budapest/1,0,23,infrastruktúra%401%401?keywordsearch&rss",
    "https://www.profession.hu/allasok/budapest/1,0,23,docker%401%401?keywordsearch&rss",	
    "https://www.profession.hu/allasok/budapest/1,0,23,automatizálás%401%401?keywordsearch&rss",
    "https://www.profession.hu/allasok/budapest/1,0,23,uzemelteto%401%401?keywordsearch&rss",
	
]

INCLUDE = ["cloud", "aws", "sysadmin", "system administrator", "devops", "terraform", "rendszergazda", "rendszeruzemelte", "alkalmazas tamogat", "it administrator", "it support"]
EXCLUDE = ["Sales & Guest Relations Representative","Breakfast","german", "német", "deutsch", "francia", "french", "pénztáros", "recepciós"]

def get_users():
    region = os.environ.get("AWS_REGION", "eu-central-1")
    table_name = os.environ.get("USERS_TABLE", "users")
    table = boto3.resource("dynamodb", region_name=region).Table(table_name)
    resp = table.scan()
    return resp["Items"]


def all_searches(users):
    urls = set()
    for u in users:
        urls.update(u.get("searches", []))
    return list(urls)

def entry_date(entry):
    parsed = getattr(entry, "published_parsed", None)
    if not parsed:
        return ""
    return datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc).isoformat()

def html_to_lines(raw):
    if not raw:
        return []
    text = re.sub(r'<br\s*/?>', '\n', raw)
    text = re.sub(r'</(p|li|div|h\d|ul|ol)\s*>', '\n', text)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = htmllib.unescape(text)                 # &nbsp; &amp; etc
    text = re.sub(r'[ \t]+', ' ', text)
    return [line.strip() for line in text.split('\n') if line.strip()]

def fetch_profession(searches):

    jobs = []
    seen = set()

    for url in searches:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            title_lower = entry.title.lower()
            if any(word in title_lower for word in EXCLUDE):
                continue

            if entry.id not in seen:
                seen.add(entry.id)

                jobs.append({"id": entry.id,"title": entry.title,"link": entry.link.strip(),"published": entry.published, "description": [], "location": "Budapest", "salary": "", "source":"Profession","employer": "", "posted_at": entry_date(entry) })
    return jobs
    
    
def fetch_randstad():
    jobs = []
    xml = requests.get(
        "https://www.randstad.hu/sitemaps/jobs/hu/sitemap-jobdetails.xml",
        timeout=15,
        headers={"User-Agent": "Mozilla/5.0"},
    ).text
    urls = re.findall(r"<loc>(.*?)</loc>", xml)
    for url in urls:
        slug = url.rstrip("/").split("/")[-1]
        parts = slug.split("_")

        name = slug.replace("-", " ")
        if not any(word in name.lower() for word in INCLUDE):
            continue
        title = parts[0].replace("-", " ").title()
        location = parts[1].title() if len(parts) > 1 else ""
        if location.lower() not in ("budapest", "remote", "tavmunka"):
            continue
        jobs.append({
            "id": url,
            "link": url,
            "title": title,
            "location": location,
            "source": "Randstad",
            "description": [],
            "salary": "",
            "employer": "",
            "posted_at": "",
            "published": "",
        })
    return jobs

def fetch_nofluffjobs():
    jobs = []
    
    feed = feedparser.parse("https://nofluffjobs.com/rss")
    for entry in feed.entries:

            
        loc = re.search(r"Location:</b>\s*([^<]+)", entry.summary)
        sal = re.search(r"Salary:</b>\s*([^<]+)", entry.summary)
        location = loc.group(1).strip() if loc else ""
        salary = sal.group(1).strip() if sal else ""            
        desc_lower = entry.summary.lower()
        if ("hungary" in desc_lower or "budapest" in desc_lower):
            
            jobs.append({"id": entry.id,"title": entry.title,"link": entry.link,"published": entry.published, "location": location, "salary": salary, "description": [], "source": "No Fluff Jobs", "employer": "", "posted_at": entry_date(entry)})
    return jobs

def fetch_smartrecruiters(company):
    jobs = []
    r = requests.get(
        f"https://api.smartrecruiters.com/v1/companies/{company}/postings",
        params={"limit": 100},
        timeout=15,
    ).json()
    for p in r.get("content", []):
        city = p['location']['city'].lower()
        if "budapest" not in city and not p['location'].get('remote'):
            continue
        if not any(word in p['name'].lower() for word in INCLUDE):
            continue
        if any(word in p['name'].lower() for word in EXCLUDE):
            continue
        url = f"https://jobs.smartrecruiters.com/{company}/{p['id']}"
        jobs.append({
            "id": url,
            "link": url,
            "title": p['name'],
            "location": p['location']['city'],
            "source": "SmartRecruiters",
            "description": [],
            "salary": "",
            "employer": p["company"]["name"],
            "posted_at": p['releasedDate'],
            "published": "",
            "experience": p.get("experienceLevel", {}).get("label", "")
        })
    return jobs




def fetch_jsonld_details(url):
    time.sleep(1)
    try:
        html = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"}).text
    except Exception as e:
        print("FETCH FAILED:", e)
        return {}
    for m in re.finditer(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html, re.S):
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        nodes = data.get("@graph", [data]) if isinstance(data, dict) else data
        for node in nodes:
            if node.get("@type") == "JobPosting":
                return {
                    "description": html_to_lines(node.get("description", "")),
                    "employer": node.get("hiringOrganization", {}).get("name", ""),
                    "skills": node.get("skills", ""),
                }
    return {}


def save_jobs(jobs):
    now = datetime.now(timezone.utc).isoformat()
    region = os.environ.get("AWS_REGION", "eu-central-1")
    table_name = os.environ.get("JOBS_TABLE", "jobs")
    dynamodb = boto3.resource('dynamodb', region_name=region)
    table = dynamodb.Table(table_name)
    new_jobs = []
    for job in jobs:
        response = table.get_item(Key={"id": job["id"]})
        if "Item" in response:
            table.update_item(Key={"id": job["id"]},
                              UpdateExpression='SET #ts = :val1',
                              ExpressionAttributeNames={'#ts': 'last_seen'},
                              ExpressionAttributeValues={':val1': datetime.now(timezone.utc).isoformat()})
        else:
            newjob = {**job, "status": "new", "first_seen": now, "last_seen": now}
            new_jobs.append(newjob)


            table.put_item(Item=newjob)
    return new_jobs



def score_job(job, profile):
    desc = job.get("description", [])
    description = " ".join(desc)[:4000] if isinstance(desc, list) else str(desc)[:4000]
    region = os.environ.get("AWS_REGION", "eu-central-1")
    client = boto3.client("bedrock-runtime", region_name=region)
    prompt = f"""You are screening job postings for a candidate. Score how well this posting fits.

             Weight these heavily:
             - Seniority match. The candidate is junior to medior. Senior, lead, architect and principal roles should score low.
             - Real infrastructure/cloud work versus level 1 helpdesk or service desk with a technical-sounding title.
             - Language requirements. Any requirement for German or a language other than Hungarian and English is disqualifying.
             - Whether the required tech overlaps what the candidate actually knows.

            Score low for: senior roles, pure development roles, helpdesk, shift work, roles needing a driving licence.
            Score high for: junior/medior cloud, DevOps, infrastructure, systems administration with a cloud component.

            Respond with JSON only. No preamble, no markdown fences.
            {{"score": <integer 0-100>, "reason": "<one short sentence>"}}

            CANDIDATE:
            {profile}

            JOB POSTING:
            Title: {job.get('title', '')}
            Employer: {job.get('employer', '')}
            Location: {job.get('location', '')}
            Seniority: {job.get('experience', '')}
            Description: {description}
            """
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 300,
        "messages": [{"role": "user", "content": prompt}]
    })
    try:
        response = client.invoke_model(
        modelId="eu.anthropic.claude-haiku-4-5-20251001-v1:0",
        body=body,
        )
    except Exception as e:
        print("BEDROCK FAILED:", e)
        return {}

    result = json.loads(response["body"].read())
    text = result["content"][0]["text"].strip()
    if text.startswith("```"):
        text = text.split("```")[1].removeprefix("json").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        print("PARSE FAILED:", repr(text))
        return {}

def fetch_sr_details(company, job_id):
    time.sleep(1)
    try:
        r = requests.get(
            f"https://api.smartrecruiters.com/v1/companies/{company}/postings/{job_id}",
            timeout=10,
        ).json()
    except Exception as e:
        print("SR FETCH FAILED:", e)
        return {}
    lines = []
    for key, sec in r.get("jobAd", {}).get("sections", {}).items():
        text = sec.get("text", "")
        if text:
            lines.extend(html_to_lines(text))
    return {
        "description": lines,
        "experience": r.get("experienceLevel", {}).get("label", ""),
    }

def enrich(new_jobs):
    region = os.environ.get("AWS_REGION", "eu-central-1")
    table_name = os.environ.get("JOBS_TABLE", "jobs")
    table = boto3.resource("dynamodb", region_name=region).Table(table_name)
    enriched = []
    for i, job in enumerate(new_jobs, 1):
        print(f"{i}/{len(new_jobs)} {job['title'][:40]}")
        company_name = os.environ.get("COMPANY_NAME", "DeutscheTelekomITSolutions")
        if job.get("source") == "SmartRecruiters":
            details = fetch_sr_details(company_name, job["id"].split("/")[-1])
        else:
            details = fetch_jsonld_details(job["link"])

        if not details:
            continue
        table.update_item(
            Key={"id": job["id"]},
            UpdateExpression="SET #d = :d, employer = :e, skills = :s, experience = :x",
            ExpressionAttributeNames={"#d": "description"},
            ExpressionAttributeValues={
                ":d": details.get("description", []),
                ":e": details.get("employer") or job.get("employer", ""),
                ":s": details.get("skills") or job.get("skills", ""),
				":x": details.get("experience") or job.get("experience", ""),
            },
        )
        enriched.append({**job, **details})
    return enriched

def score_for_user(user, jobs):
    region = os.environ.get("AWS_REGION", "eu-central-1")
    table_name = os.environ.get("USER_JOBS_TABLE", "user_jobs")
    table = boto3.resource("dynamodb", region_name=region).Table(table_name)
    now = datetime.now(timezone.utc).isoformat()
    include = [w.lower() for w in user.get("include", [])]
    exclude = [w.lower() for w in user.get("exclude", [])]
    threshold = int(user.get("alert", 75))
    alerts = []

    for job in jobs:
        title = job.get("title", "").lower()

        if exclude and any(w in title for w in exclude):
            continue


        match = score_job(job, user.get("profile", ""))

        table.put_item(Item={
            "user_id": user["user_id"],
            "job_id": job["id"],
            "status": "new",
            "score": match.get("score", 0),
            "reason": match.get("reason", ""),
            "first_seen": now,
        })

        if match.get("score", 0) >= threshold:
            alerts.append({**job, **match})

    return alerts


def send_alerts(alerts, email):
    if not alerts:
        return

    region = os.environ.get("AWS_REGION", "eu-central-1")
    source_email = os.environ.get("SES_SOURCE_EMAIL", "noreply@example.com")
    client = boto3.client("ses", region_name=region)
    lines = []
    for job in alerts:
        lines.append(f"{job.get('score')}  {job.get('title')}")
        lines.append(f"  {job.get('employer', '')}  {job.get('location', '')}")
        lines.append(f"  {job.get('reason', '')}")
        lines.append(f"  {job.get('link')}")
        lines.append("")
    body = "\n".join(lines)
    response = client.send_email(
        Destination={
            'ToAddresses': [email],
        },
        Message={
            'Body': {
                'Text': {
                    'Charset': 'UTF-8',
                    'Data': body
                },
            },
            'Subject': {
                'Charset': 'UTF-8',
                'Data': f"{len(alerts)} new job match(es)",
            },
        },
        Source=source_email,
    )

def lambda_handler(event, context):
    company_name = os.environ.get("COMPANY_NAME", "DeutscheTelekomITSolutions")
    users = get_users()
    jobs = fetch_nofluffjobs() + fetch_profession(all_searches(users)) + fetch_randstad() + fetch_smartrecruiters(company_name)
    new_jobs = save_jobs(jobs)
    print(f"found {len(jobs)}, new {len(new_jobs)}")
    enriched = enrich(new_jobs)
    for user in users:
        alerts = score_for_user(user, enriched)
        send_alerts(alerts, user["email"])
    return {"found": len(jobs), "new": len(new_jobs)}


if __name__ == "__main__":
    company_name = os.environ.get("COMPANY_NAME", "DeutscheTelekomITSolutions")
    users = get_users()
    jobs = fetch_nofluffjobs() + fetch_profession(all_searches(users)) + fetch_randstad() + fetch_smartrecruiters(company_name)
    new_jobs = save_jobs(jobs)
    enriched = enrich(new_jobs)
    for user in users:
        alerts = score_for_user(user, enriched)
        send_alerts(alerts, user["email"])