"""Add a job posting by hand (e.g. found on LinkedIn) and score it.

Edit the block below, then run:  python3 add_job.py
"""
from dotenv import load_dotenv
load_dotenv()
import boto3
import os
from datetime import datetime, timezone

import scrap  # reuse score_job and get_users

# ---------------------------------------------------------------- edit me

USER_EMAIL = os.environ.get("USER_EMAIL", "rusko.david@gmail.com")      # which user this is for
STATUS     = "new"                     # new / interested / applied / ...

JOB = {
    "id":       "https://karrier.nisz.hu/alkalmazasuzemelteto-webes",
    "link":     "https://karrier.nisz.hu/alkalmazasuzemelteto-webes",
    "title":    "Junior alkalmazásüzemeltető (webes)",
    "employer": "NISZ Zrt.",
    "location": "Budapest",
    "salary":   "",
    "source":   "LinkedIn",
}

DESCRIPTION = """
Feladatok

Webes portálok és alkalmazások napi szintű üzemeltetése, rendelkezésre állásuk biztosítása
Alkalmazások monitorozása és felügyelete (ELK stack, Grafana)
Incidenskezelés: hibák diagnosztizálása, egyeztetés fejlesztőkkel, javítás koordinálása és végrehajtása
Verziófrissítések, patch-ek telepítése, változáskezelési folyamatok végrehajtása
CMS-alapú rendszerek (Drupal, WordPress) üzemeltetése
CI/CD pipeline-ok kialakításában és működtetésében való részvétel (GitLab CI)
Automatizált tesztek és üzemeltetési szkriptek kidolgozásában közreműködés
Üzemeltetési és rendszerdokumentáció készítése, karbantartása
Projektek szakmai támogatása, együttműködés fejlesztői csapatokkal
Elvárások

Legalább 1-2 éves hasonló munkakörben szerzett tapasztalat
Linux rendszerek magabiztos kezelése (CLI, shell scripting)
LAMP stack (Linux, Apache, MySQL/MariaDB, PHP) üzemeltetési tapasztalat
CMS rendszerek (Drupal, WordPress) üzemeltetési ismerete
Monitoring eszközök használata (ELK stack, Grafana)
Angol nyelvű technikai dokumentáció értése
Előny

Kubernetes ismerete
Docker konténerek napi szintű használatában szerzett gyakorlat
CI/CD pipeline-ok kialakításában szerzett tapasztalat (GitLab CI, Jenkins)
Modern JavaScript keretrendszerek ismerete (React, Angular, Node.js)
Infrastruktúra, mint kód (IaC) eszközök ismerete (Ansible, Terraform)
Monitoring és log-menedzsment rendszerek mélyebb ismerete (Prometheus, Kibana)
Ticket- és verziókezelő rendszerek használata (Jira, GitLab)
ITIL alapismeretek
Nagyvállalati vagy közigazgatási IT környezetben szerzett tapasztalat
"""

# ---------------------------------------------------------------- run


def main():
    region = os.environ.get("AWS_REGION", "eu-central-1")
    db = boto3.resource("dynamodb", region_name=region)
    jobs_t = db.Table("jobs")
    uj_t = db.Table("user_jobs")

    now = datetime.now(timezone.utc).isoformat()
    lines = [l.strip() for l in DESCRIPTION.strip().split("\n") if l.strip()]

    user = next(u for u in scrap.get_users() if u.get("email") == USER_EMAIL)

    job = {
        **JOB,
        "description": lines,
        "published": "",
        "posted_at": now,
        "first_seen": now,
        "last_seen": now,
    }
    jobs_t.put_item(Item=job)
    print("saved to jobs:", job["title"])

    match = scrap.score_job(job, user.get("profile", ""))
    print("score:", match.get("score"), "-", match.get("reason"))

    uj_t.put_item(Item={
        "user_id": user["user_id"],
        "job_id": job["id"],
        "status": STATUS,
        "score": match.get("score", 0),
        "reason": match.get("reason", ""),
        "first_seen": now,
    })
    print("saved to user_jobs as:", STATUS)


if __name__ == "__main__":
    main()