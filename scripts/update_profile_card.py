#!/usr/bin/env python3
"""Refresh the profile-card SVGs with current public GitHub data."""
import json
import os
import re
import urllib.request
from datetime import datetime, timezone
from html import escape

USER = "MayanKiz"
API = "https://api.github.com"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "MayanKiz-profile-card-updater",
}
token = os.getenv("GITHUB_TOKEN")
if token:
    HEADERS["Authorization"] = f"Bearer {token}"


def get_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.load(response)


def fetch_all_repos():
    repos = []
    for page in range(1, 4):
        batch = get_json(f"{API}/users/{USER}/repos?per_page=100&page={page}&type=owner&sort=updated")
        repos.extend(batch)
        if len(batch) < 100:
            break
    return repos


def replace_line(svg, marker, inner):
    pattern = re.compile(r'(<text\\b[^>]*>)(.*?)(</text>)', re.DOTALL)
    found = False

    def swap(match):
        nonlocal found
        if not found and marker in match.group(2):
            found = True
            return match.group(1) + inner + match.group(3)
        return match.group(0)

    result = pattern.sub(swap, svg)
    if not found:
        raise RuntimeError(f"Could not find SVG line containing: {marker}")
    return result


def stat_line(label1, value1, label2, value2, palette):
    label, muted, value, separator = palette
    return (
        f'<tspan fill="{label}">. {escape(label1)}: </tspan>'
        f'<tspan fill="{muted}">{"." * max(3, 27 - len(label1))}</tspan>'
        f'<tspan fill="{value}"> {escape(str(value1))}</tspan>'
        f'<tspan fill="{separator}"> | </tspan>'
        f'<tspan fill="{label}">. {escape(label2)}: </tspan>'
        f'<tspan fill="{muted}">{"." * max(3, 27 - len(label2))}</tspan>'
        f'<tspan fill="{value}"> {escape(str(value2))}</tspan>'
    )


def update_svg(path, stats, dark):
    with open(path, "r", encoding="utf-8") as file:
        svg = file.read()

    if dark:
        palette = ("#ffa657", "#484f58", "#79c0ff", "#3d444d")
        section = "#58a6ff"
        separator = "#3d444d"
        updated_color = "#79c0ff"
    else:
        palette = ("#953800", "#8c959f", "#0550ae", "#d0d7de")
        section = "#0969da"
        separator = "#d0d7de"
        updated_color = "#0550ae"

    svg = replace_line(
        svg, ". Repos:",
        stat_line("Repos", stats["repos"], "Stars", stats["stars"], palette)
    )
    svg = replace_line(
        svg, ". Forks:",
        stat_line("Forks", stats["forks"], "Followers", stats["followers"], palette)
    )
    svg = replace_line(
        svg, ". Commits:",
        stat_line("Commits (90d)", stats["commits_90d"], "Active repos", stats["active_repos_90d"], palette)
    )
    svg = replace_line(
        svg, ". PRs:",
        stat_line("PR events (90d)", stats["prs_90d"], "Issue events (90d)", stats["issues_90d"], palette)
    )
    top_inner = (
        f'<tspan fill="{palette[0]}">. Top repo: </tspan>'
        f'<tspan fill="{palette[1]}">{"." * 26}</tspan>'
        f'<tspan fill="{palette[2]}"> {escape(stats["top_repo"])} ({stats["top_repo_stars"]} ★)</tspan>'
    )
    svg = replace_line(svg, ". Top repo:", top_inner)

    section_inner = (
        f'<tspan fill="{separator}">─</tspan>'
        f'<tspan fill="{section}"> Auto-updated daily · public GitHub data </tspan>'
        f'<tspan fill="{separator}">────────────────────</tspan>'
    )
    svg = replace_line(svg, "Last 12 Months", section_inner)

    activity_inner = stat_line(
        "Public commits (90d)", stats["commits_90d"],
        "PR events (90d)", stats["prs_90d"], palette
    )
    svg = replace_line(svg, ". Contributions:", activity_inner)

    updated_inner = (
        f'<tspan fill="{palette[0]}">. Updated (UTC): </tspan>'
        f'<tspan fill="{palette[1]}">{"." * 23}</tspan>'
        f'<tspan fill="{updated_color}"> {stats["updated"]}</tspan>'
    )
    svg = replace_line(svg, ". Private:", updated_inner)

    with open(path, "w", encoding="utf-8") as file:
        file.write(svg)


def main():
    profile = get_json(f"{API}/users/{USER}")
    repos = fetch_all_repos()
    public_repos = [repo for repo in repos if not repo.get("fork")]
    stars = sum(repo.get("stargazers_count", 0) for repo in repos)
    forks = sum(repo.get("forks_count", 0) for repo in repos)
    top_repo = max(repos, key=lambda repo: repo.get("stargazers_count", 0), default={})

    events = []
    for page in range(1, 4):
        batch = get_json(f"{API}/users/{USER}/events?per_page=100&page={page}")
        events.extend(batch)
        if len(batch) < 100:
            break

    now = datetime.now(timezone.utc)
    recent = []
    for event in events:
        created = event.get("created_at")
        if not created:
            continue
        try:
            event_date = datetime.fromisoformat(created.replace("Z", "+00:00"))
        except ValueError:
            continue
        if (now - event_date).days <= 90:
            recent.append(event)

    commits = sum(
        len(event.get("payload", {}).get("commits", []))
        for event in recent if event.get("type") == "PushEvent"
    )
    prs = sum(1 for event in recent if event.get("type") == "PullRequestEvent")
    issues = sum(1 for event in recent if event.get("type") == "IssuesEvent")
    active_repos = len({
        event.get("repo", {}).get("name")
        for event in recent if event.get("repo", {}).get("name")
    })

    stats = {
        "repos": profile.get("public_repos", len(repos)),
        "stars": stars,
        "forks": forks,
        "followers": profile.get("followers", 0),
        "commits_90d": commits,
        "active_repos_90d": active_repos,
        "prs_90d": prs,
        "issues_90d": issues,
        "top_repo": top_repo.get("name", "No public repos"),
        "top_repo_stars": top_repo.get("stargazers_count", 0),
        "updated": now.strftime("%Y-%m-%d"),
    }

    update_svg("dark_mode-1.svg", stats, True)
    update_svg("light_mode.svg", stats, False)
    print("Updated profile cards:", json.dumps(stats, sort_keys=True))


if __name__ == "__main__":
    main()
