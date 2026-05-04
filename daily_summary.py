#!/usr/bin/env python3
"""
Daily summary email script.
Collects GitHub activity and sends an HTML email summary.

Usage:
    python daily_summary.py

Environment variables:
    GITHUB_TOKEN   - GitHub personal access token
    GITHUB_OWNER   - Repository owner (e.g. yuvaliko)
    GITHUB_REPO    - Repository name (e.g. AI)
    EMAIL_FROM     - Sender email address
    EMAIL_TO       - Recipient email address
    SMTP_HOST      - SMTP server hostname (default: smtp.gmail.com)
    SMTP_PORT      - SMTP server port (default: 587)
    SMTP_USER      - SMTP username
    SMTP_PASSWORD  - SMTP password / app password
"""

import os
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests


def get_env(key: str, default: str = "") -> str:
    value = os.environ.get(key, default)
    if not value and not default:
        raise EnvironmentError(f"Missing required environment variable: {key}")
    return value


def github_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def fetch_today_items(url: str, token: str, since: str) -> list:
    params = {"since": since, "per_page": 100, "state": "all"}
    resp = requests.get(url, headers=github_headers(token), params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def fetch_commits(owner: str, repo: str, token: str, since: str) -> list:
    url = f"https://api.github.com/repos/{owner}/{repo}/commits"
    params = {"since": since, "per_page": 100}
    resp = requests.get(url, headers=github_headers(token), params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def section_html(title: str, items: list, row_fn) -> str:
    if not items:
        return f"<h2>{title}</h2><p style='color:#888'>אין פעילות היום.</p>"
    rows = "".join(row_fn(item) for item in items)
    return f"""
    <h2 style='border-bottom:2px solid #e1e4e8;padding-bottom:6px'>{title} ({len(items)})</h2>
    <ul style='list-style:none;padding:0'>{rows}</ul>
    """


def issue_row(issue: dict) -> str:
    state_color = "#2da44e" if issue["state"] == "open" else "#8250df"
    state_label = "פתוח" if issue["state"] == "open" else "סגור"
    return (
        f"<li style='margin-bottom:8px'>"
        f"<span style='background:{state_color};color:#fff;border-radius:12px;"
        f"padding:2px 8px;font-size:12px'>{state_label}</span> "
        f"<a href='{issue['html_url']}' style='color:#0969da;text-decoration:none'>"
        f"#{issue['number']} {issue['title']}</a>"
        f"</li>"
    )


def pr_row(pr: dict) -> str:
    state_color = "#2da44e" if pr["state"] == "open" else "#6e40c9"
    state_label = "פתוח" if pr["state"] == "open" else "מוזג/סגור"
    return (
        f"<li style='margin-bottom:8px'>"
        f"<span style='background:{state_color};color:#fff;border-radius:12px;"
        f"padding:2px 8px;font-size:12px'>{state_label}</span> "
        f"<a href='{pr['html_url']}' style='color:#0969da;text-decoration:none'>"
        f"#{pr['number']} {pr['title']}</a>"
        f"</li>"
    )


def commit_row(commit: dict) -> str:
    msg = commit["commit"]["message"].splitlines()[0]
    sha = commit["sha"][:7]
    url = commit["html_url"]
    author = commit["commit"]["author"]["name"]
    return (
        f"<li style='margin-bottom:8px'>"
        f"<code style='background:#f6f8fa;padding:2px 5px;border-radius:4px'>{sha}</code> "
        f"<a href='{url}' style='color:#0969da;text-decoration:none'>{msg}</a> "
        f"<span style='color:#888;font-size:12px'>— {author}</span>"
        f"</li>"
    )


def build_html(owner: str, repo: str, issues: list, prs: list, commits: list, date_str: str) -> str:
    issues_html = section_html("Issues", issues, issue_row)
    prs_html = section_html("Pull Requests", prs, pr_row)
    commits_html = section_html("Commits", commits, commit_row)
    repo_url = f"https://github.com/{owner}/{repo}"

    return f"""
    <!DOCTYPE html>
    <html lang="he" dir="rtl">
    <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
    <body style='font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
                 max-width:700px;margin:0 auto;padding:20px;color:#24292f;direction:rtl'>
        <div style='background:#0969da;color:#fff;padding:16px 24px;border-radius:8px 8px 0 0'>
            <h1 style='margin:0;font-size:20px'>סיכום יומי — {date_str}</h1>
            <p style='margin:4px 0 0;opacity:0.85'>
                <a href='{repo_url}' style='color:#fff'>{owner}/{repo}</a>
            </p>
        </div>
        <div style='border:1px solid #d0d7de;border-top:none;padding:20px;border-radius:0 0 8px 8px'>
            {issues_html}
            {prs_html}
            {commits_html}
        </div>
        <p style='color:#888;font-size:12px;text-align:center;margin-top:16px'>
            נשלח אוטומטית על ידי daily_summary.py
        </p>
    </body>
    </html>
    """


def send_email(subject: str, html_body: str, cfg: dict) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg["from"]
    msg["To"] = cfg["to"]
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(cfg["host"], int(cfg["port"])) as server:
        server.ehlo()
        server.starttls()
        server.login(cfg["user"], cfg["password"])
        server.sendmail(cfg["from"], cfg["to"], msg.as_string())


def main():
    token = get_env("GITHUB_TOKEN")
    owner = get_env("GITHUB_OWNER")
    repo = get_env("GITHUB_REPO")

    smtp_cfg = {
        "from":     get_env("EMAIL_FROM"),
        "to":       get_env("EMAIL_TO"),
        "host":     get_env("SMTP_HOST", "smtp.gmail.com"),
        "port":     get_env("SMTP_PORT", "587"),
        "user":     get_env("SMTP_USER"),
        "password": get_env("SMTP_PASSWORD"),
    }

    now = datetime.now(timezone.utc)
    since = (now - timedelta(hours=24)).isoformat().replace("+00:00", "Z")
    date_str = now.strftime("%d/%m/%Y")

    base = f"https://api.github.com/repos/{owner}/{repo}"

    print("מאסף נתוני GitHub...")
    issues  = fetch_today_items(f"{base}/issues",       token, since)
    prs     = fetch_today_items(f"{base}/pulls",        token, since)
    commits = fetch_commits(owner, repo, token, since)

    html = build_html(owner, repo, issues, prs, commits, date_str)
    subject = f"סיכום יומי — {owner}/{repo} — {date_str}"

    print(f"שולח מייל ל-{smtp_cfg['to']}...")
    send_email(subject, html, smtp_cfg)
    print("הסיכום היומי נשלח בהצלחה.")


if __name__ == "__main__":
    main()
