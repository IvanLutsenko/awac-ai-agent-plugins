#!/usr/bin/env python3
"""Fetch crash data from Firebase Crashlytics REST API.

Usage: python3 fetch-crash-data.py <APP_ID> <ISSUE_ID> [PROJECT_ID]

Output format:
  ISSUE_DATA:{json}   - issue details
  EVENTS_DATA:{json}  - sample events
  API_NOT_ENABLED     - API needs to be enabled
  REST_FALLBACK_FAILED - all attempts failed

Stderr diagnostics:
  AUTH_FAILED:<reason> - token refresh failed
  FETCH_FAILED:<reason> - API request failed

Note: client_id and client_secret are public OAuth credentials from Firebase CLI
(embedded in firebase-tools source code, this is an installed app OAuth flow).
The access token stays internal - never printed or logged.
"""
import glob
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

TIMEOUT = 15


def get_access_token():
    config_path = os.path.expanduser("~/.config/configstore/firebase-tools.json")
    with open(config_path) as f:
        config = json.load(f)
    refresh_token = config.get("tokens", {}).get("refresh_token")
    if not refresh_token:
        raise ValueError("no refresh_token in firebase config")
    token_data = urllib.parse.urlencode({
        "client_id": "563584335869-fgrhgmd47bqnekij5i8b5pr03ho849e6.apps.googleusercontent.com",
        "client_secret": "j9iVZfS8kkCEFUPaAeJV0sAi",
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }).encode()
    resp = urllib.request.urlopen(
        urllib.request.Request("https://oauth2.googleapis.com/token", data=token_data),
        timeout=TIMEOUT,
    )
    return json.loads(resp.read())["access_token"]


def urlopen_with_retry(req, retries=1):
    """urlopen with retry on transient URLError (not HTTP errors)."""
    for attempt in range(retries + 1):
        try:
            return urllib.request.urlopen(req, timeout=TIMEOUT)
        except urllib.error.HTTPError:
            raise  # HTTP errors are not transient — propagate immediately
        except urllib.error.URLError as e:
            if attempt < retries:
                print("WARN: transient error, retrying in 2s: {}".format(e.reason), file=sys.stderr)
                time.sleep(2)
            else:
                raise


def main():
    if len(sys.argv) < 3:
        print("Usage: fetch-crash-data.py <APP_ID> <ISSUE_ID> [PROJECT_ID]", file=sys.stderr)
        sys.exit(1)

    app_id = sys.argv[1]
    issue_id = sys.argv[2]
    project_id = sys.argv[3] if len(sys.argv) > 3 else None

    # Extract numeric project number from APP_ID format "1:PROJECT_NUM:android:hash"
    project_num = app_id.split(":")[1] if ":" in app_id else project_id

    try:
        token = get_access_token()
    except Exception as e:
        print("AUTH_FAILED:{}".format(e), file=sys.stderr)
        print("REST_FALLBACK_FAILED")
        sys.exit(0)

    headers = {"Authorization": "Bearer " + token}

    base_urls = [
        "https://firebasecrashlytics.googleapis.com/v1alpha/projects/{}/apps/{}".format(project_num, app_id),
    ]
    if project_id and project_id != project_num:
        base_urls.append(
            "https://firebasecrashlytics.googleapis.com/v1alpha/projects/{}/apps/{}".format(project_id, app_id)
        )

    issue_data = None
    for base in base_urls:
        try:
            req = urllib.request.Request("{}/issues/{}".format(base, issue_id), headers=headers)
            issue_data = json.loads(urlopen_with_retry(req).read())
            print("ISSUE_DATA:" + json.dumps(issue_data, indent=2))
            try:
                ereq = urllib.request.Request(
                    "{}/events?filter.issue.id={}&page_size=3".format(base, issue_id), headers=headers
                )
                events = json.loads(urlopen_with_retry(ereq).read())
                print("EVENTS_DATA:" + json.dumps(events, indent=2))
            except Exception as e:
                print("FETCH_FAILED:events:{}".format(e), file=sys.stderr)
            break
        except urllib.error.HTTPError as e:
            err_body = e.read().decode() if hasattr(e, "read") else ""
            print("FETCH_FAILED:{}/issues/{} HTTP {}".format(base, issue_id, e.code), file=sys.stderr)
            if e.code == 403 and "not been used" in err_body:
                print("API_NOT_ENABLED")
            continue
        except Exception as e:
            print("FETCH_FAILED:{} {}".format(base, e), file=sys.stderr)
            continue

    if issue_data:
        save_app_id_to_config(app_id, project_id)
    else:
        print("REST_FALLBACK_FAILED")


def save_app_id_to_config(app_id, project_id):
    """Save discovered app_id/project_id back to crashlytics.local.md if empty."""
    config_path = find_config_file()
    if not config_path:
        return
    try:
        with open(config_path) as f:
            content = f.read()
        changed = False
        platform = "android" if ":android:" in app_id else "ios"
        field = "firebase_app_id_{}".format(platform)
        pattern = r'({}:\s*)""\s*$'.format(re.escape(field))
        replacement = r'\g<1>"{}"\n'.format(app_id)
        new_content, n = re.subn(pattern, replacement, content, flags=re.MULTILINE)
        if n:
            changed = True
            content = new_content
        if project_id:
            pattern = r'(firebase_project_id:\s*)""\s*$'
            replacement = r'\g<1>"{}"\n'.format(project_id)
            new_content, n = re.subn(pattern, replacement, content, flags=re.MULTILINE)
            if n:
                changed = True
                content = new_content
        if changed:
            with open(config_path, "w") as f:
                f.write(content)
            print("CONFIG_UPDATED:{}".format(config_path), file=sys.stderr)
    except Exception as e:
        print("CONFIG_SAVE_FAILED:{}".format(e), file=sys.stderr)


def find_config_file():
    """Find crashlytics.local.md in current dir or parent dirs."""
    cwd = os.getcwd()
    for _ in range(5):
        candidate = os.path.join(cwd, ".claude", "crashlytics.local.md")
        if os.path.isfile(candidate):
            return candidate
        parent = os.path.dirname(cwd)
        if parent == cwd:
            break
        cwd = parent
    return None


if __name__ == "__main__":
    main()
