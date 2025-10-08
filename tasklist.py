"""
Paathshala Tasks (Assignments) Lister - CSV with rich fields and Auto-Login
Fields:
  Task Name, Module ID, Due Date, Time Remaining, Late Policy, Max Grade, Submission Status,
  Grading Status, Last Modified, Submission Comments, Participants, Drafts, Submitted,
  Needs Grading, URL

Usage:
  python paatshala_tasks_csv.py <course_id>
  python paatshala_tasks_csv.py <course_id> --cookie <MoodleSession>
  python paatshala_tasks_csv.py <course_id> --threads 8
  or set MOODLE_SESSION_ID
  or create .config with username/password
"""

import os, re, csv, sys, argparse, time, threading
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = "https://paatshala.ictkerala.org"
PAATSHALA_HOST = "paatshala.ictkerala.org"
CONFIG_FILE = ".config"

# Thread-local storage for sessions
thread_local = threading.local()

def read_config(config_path=CONFIG_FILE):
    """Read username and password from config file"""
    if not os.path.exists(config_path):
        return None, None
    
    username, password = None, None
    try:
        with open(config_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip().lower()
                    value = value.strip().strip('"').strip("'")
                    if key == 'username':
                        username = value
                    elif key == 'password':
                        password = value
        print(f"[Config] Read credentials from {config_path}")
        return username, password
    except Exception as e:
        print(f"[Config] Error reading {config_path}: {e}")
        return None, None

def login_and_get_cookie(username, password):
    """Login to Paathshala and extract session cookie"""
    print(f"[Login] Attempting login as {username}...")
    
    try:
        response = requests.post(
            f"https://{PAATSHALA_HOST}/login/index.php",
            data={
                'username': username,
                'password': password
            },
            allow_redirects=False,
            timeout=10
        )
        
        # Extract MoodleSession cookie
        if 'MoodleSession' in response.cookies:
            session_cookie = response.cookies['MoodleSession']
            print(f"[Login] ✓ Successfully logged in!")
            return session_cookie
        else:
            print(f"[Login] ✗ Login failed - no session cookie received")
            print(f"[Login]   Status: {response.status_code}")
            if response.status_code == 200:
                print(f"[Login]   Hint: Check username/password in {CONFIG_FILE}")
            return None
            
    except Exception as e:
        print(f"[Login] ✗ Login error: {e}")
        return None

def setup_session(session_id):
    s = requests.Session()
    s.cookies.set("MoodleSession", session_id, domain=PAATSHALA_HOST)
    s.headers.update({'User-Agent': 'Mozilla/5.0'})
    return s

def get_thread_session(session_id: str) -> requests.Session:
    """Get or create a session for the current thread"""
    if not hasattr(thread_local, 'session'):
        thread_local.session = requests.Session()
        thread_local.session.cookies.set("MoodleSession", session_id, domain=PAATSHALA_HOST)
        thread_local.session.headers.update({'User-Agent': 'Mozilla/5.0'})
        tid = threading.get_ident()
        print(f"[T{tid}] Created new session for this thread")
    return thread_local.session

def logout_session(session):
    """Logout from Moodle to clean up the session"""
    try:
        logout_url = f"{BASE}/login/logout.php?sesskey="
        # Try to get sesskey from a page first
        resp = session.get(f"{BASE}/my/", timeout=10)
        if resp.ok:
            soup = BeautifulSoup(resp.text, "html.parser")
            # Look for sesskey in any form or link
            sesskey_input = soup.find("input", {"name": "sesskey"})
            if sesskey_input:
                sesskey = sesskey_input.get("value", "")
                logout_url = f"{BASE}/login/logout.php?sesskey={sesskey}"
        
        session.get(logout_url, timeout=10)
        print("[Logout] ✓ Session closed")
    except Exception as e:
        print(f"[Logout] ⚠ Could not logout cleanly: {e}")

def text_or_none(node):
    return node.get_text(" ", strip=True) if node else ""

def find_table_label_value(soup, wanted_labels):
    """
    Scan all tables with class 'generaltable' (and others) for rows where <th> is a label
    and <td> is the value. Return dict of lower(label)->value.
    """
    out = {}
    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            th = tr.find("th")
            td = tr.find("td")
            if not th or not td:
                continue
            label = text_or_none(th).strip().lower()
            value = text_or_none(td).strip()
            for key in wanted_labels:
                if key in label and value:
                    out[key] = value
    return out

def parse_assign_view(html):
    """
    Extract assignment details from the view page HTML.
    """
    soup = BeautifulSoup(html, "html.parser")

    # 1) Admin/overview stats table (Participants, Drafts, Submitted, Needs grading, Due date, Time remaining, Late submissions)
    overview_labels = {
        "hidden from students": "hidden",
        "participants": "participants",
        "drafts": "drafts",
        "submitted": "submitted",
        "needs grading": "needs_grading",
        "due date": "due_date_overview",
        "time remaining": "time_remaining_overview",
        "late submissions": "late_policy",
    }
    overview = find_table_label_value(soup, overview_labels.keys())
    mapped_overview = { overview_labels[k]: v for k, v in overview.items() }

    # 2) Submission status table (Submission status, Grading status, Due date, Time remaining, Last modified, Submission comments)
    status_labels = {
        "submission status": "submission_status",
        "grading status": "grading_status",
        "due date": "due_date_status",
        "time remaining": "time_remaining_status",
        "last modified": "last_modified",
        "submission comments": "submission_comments",
    }
    status = find_table_label_value(soup, status_labels.keys())
    mapped_status = { status_labels[k]: v for k, v in status.items() }

    # 3) Max Grade (prefer labels with 'maximum grade' or 'max grade' or 'grade to pass')
    grade_info = find_table_label_value(soup, ["maximum grade", "max grade", "grade to pass", "grade"])
    max_grade = grade_info.get("maximum grade") or grade_info.get("max grade") or ""

    # Submission comments count: try to parse "Comments (0)" etc from link text if present
    comments_count = ""
    # Look for something like "Comments (N)"
    for a in soup.find_all("a"):
        txt = a.get_text(" ", strip=True)
        m = re.search(r"Comments\s*\((\d+)\)", txt, flags=re.I)
        if m:
            comments_count = m.group(1)
            break
    if not comments_count and "submission_comments" in mapped_status:
        m = re.search(r"\((\d+)\)", mapped_status["submission_comments"])
        if m:
            comments_count = m.group(1)

    # Consolidate: prefer values from status table; fall back to overview table
    due_date = mapped_status.get("due_date_status") or mapped_overview.get("due_date_overview") or ""
    time_remaining = mapped_status.get("time_remaining_status") or mapped_overview.get("time_remaining_overview") or ""

    return {
        "participants": mapped_overview.get("participants", ""),
        "drafts": mapped_overview.get("drafts", ""),
        "submitted": mapped_overview.get("submitted", ""),
        "needs_grading": mapped_overview.get("needs_grading", ""),
        "late_policy": mapped_overview.get("late_policy", ""),
        "due_date": due_date,
        "time_remaining": time_remaining,
        "submission_status": mapped_status.get("submission_status", ""),
        "grading_status": mapped_status.get("grading_status", ""),
        "last_modified": mapped_status.get("last_modified", ""),
        "submission_comments": comments_count,
        "max_grade": max_grade,
    }

def get_tasks(session, course_id):
    url = f"{BASE}/course/view.php?id={course_id}"
    resp = session.get(url)
    if not resp.ok:
        print(f"✗ Failed to load course page: {resp.status_code}")
        return []
    soup = BeautifulSoup(resp.text, "html.parser")

    items = soup.find_all("li", class_=lambda c: c and "modtype_assign" in c)
    tasks = []
    for item in items:
        link = item.find("a", href=re.compile(r"mod/assign/view\.php\?id=\d+"))
        if not link:
            link = item.find("a", href=re.compile(r"/mod/assign/"))
        if link:
            name = link.get_text(strip=True)
            href = link.get("href", "")
            m = re.search(r"[?&]id=(\d+)", href)
            module_id = m.group(1) if m else ""
            if href.startswith("/"):
                href = BASE + href
            elif href.startswith("http") is False:
                href = BASE + "/" + href.lstrip("/")
            tasks.append((name, module_id, href))
    return tasks

def fetch_task_details(session_id, name, mid, url, index, total):
    """Fetch task details using thread-local session"""
    tid = threading.get_ident()
    
    # Get the thread's reusable session
    s = get_thread_session(session_id)
    
    print(f"[T{tid}] [{index}/{total}] → {name[:50]}...")
    t0 = time.perf_counter()
    
    try:
        resp = s.get(url, timeout=30)
        elapsed = time.perf_counter() - t0
        
        if not resp.ok:
            print(f"[T{tid}] ✗ HTTP {resp.status_code} ({elapsed:.2f}s)")
            return name, mid, url, {}
        
        info = parse_assign_view(resp.text)
        status_str = info.get('submission_status', '-')
        grading_str = info.get('grading_status', '-')
        print(f"[T{tid}] ✓ Status: {status_str} | Grading: {grading_str} ({elapsed:.2f}s)")
        
        return name, mid, url, info
        
    except requests.RequestException as e:
        elapsed = time.perf_counter() - t0
        print(f"[T{tid}] ✗ Network error ({elapsed:.2f}s): {e}", file=sys.stderr)
        return name, mid, url, {}
    except Exception as e:
        elapsed = time.perf_counter() - t0
        print(f"[T{tid}] ✗ Unexpected error ({elapsed:.2f}s): {e}", file=sys.stderr)
        return name, mid, url, {}

def main():
    parser = argparse.ArgumentParser(
        description="List assignments with rich fields to CSV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Authentication (in order of priority):
  1. --cookie flag
  2. MOODLE_SESSION_ID environment variable
  3. .config file with username/password

Config file format (.config):
  username=your_username
  password=your_password

Examples:
  python paatshala_tasks_csv.py 450
  python paatshala_tasks_csv.py 450 --threads 8
  python paatshala_tasks_csv.py 450 --cookie "abc123..."
  python paatshala_tasks_csv.py 450 --config my_credentials.txt
        """
    )
    parser.add_argument("course_id", type=int, help="Course ID to scrape")
    parser.add_argument("--cookie", "-c", help="Moodle session cookie (overrides other auth methods)")
    parser.add_argument("--threads", "-t", type=int, default=4, help="Number of parallel threads (default: 4)")
    parser.add_argument("--config", type=str, default=CONFIG_FILE, help=f"Config file path (default: {CONFIG_FILE})")
    parser.add_argument("--output", "-o", help="Output CSV filename (default: tasks_<course_id>.csv)")
    args = parser.parse_args()

    print("=" * 70)
    print(f"Paathshala Tasks Lister - Course {args.course_id}")
    print(f"Threads: {args.threads}")
    print("=" * 70)

    # Try to get session cookie from multiple sources
    SESSION_ID = None
    
    # 1. Command line argument
    if args.cookie:
        SESSION_ID = args.cookie
        print("[Auth] Using cookie from command line")
    
    # 2. Environment variable
    elif os.environ.get("MOODLE_SESSION_ID"):
        SESSION_ID = os.environ.get("MOODLE_SESSION_ID")
        print("[Auth] Using cookie from MOODLE_SESSION_ID environment variable")
    
    # 3. Config file with username/password
    else:
        username, password = read_config(args.config)
        if username and password:
            SESSION_ID = login_and_get_cookie(username, password)
            if not SESSION_ID:
                print("\n[Auth] ✗ Auto-login failed. Please check credentials.")
                sys.exit(1)
        else:
            print(f"\n[Auth] ✗ No authentication provided.")
            print(f"\nProvide authentication via:")
            print(f"  1. Command line: --cookie 'your_cookie'")
            print(f"  2. Environment:  export MOODLE_SESSION_ID='your_cookie'")
            print(f"  3. Config file:  Create {args.config} with username/password")
            print(f"\nConfig file format:")
            print(f"  username=your_username")
            print(f"  password=your_password")
            sys.exit(1)

    # Create main session for initial course fetch
    main_session = setup_session(SESSION_ID)
    tasks = get_tasks(main_session, args.course_id)
    if not tasks:
        print("✗ No tasks (assignments) found.")
        logout_session(main_session)
        sys.exit(1)

    print(f"\n[Main] Found {len(tasks)} tasks")
    print(f"[Main] Starting parallel fetch with {args.threads} threads...\n")

    start_time = time.perf_counter()
    
    # Fetch task details in parallel
    rows = []
    task_results = {}
    
    with ThreadPoolExecutor(max_workers=max(1, args.threads)) as executor:
        futures = {
            executor.submit(fetch_task_details, SESSION_ID, name, mid, url, i, len(tasks)): (name, mid, url)
            for i, (name, mid, url) in enumerate(tasks, 1)
        }
        
        for fut in as_completed(futures):
            name, mid, url = futures[fut]
            try:
                returned_name, returned_mid, returned_url, info = fut.result()
                task_results[(returned_name, returned_mid)] = (returned_url, info)
            except Exception as e:
                print(f"[Main] ✗ Error processing {name}: {e}")
                continue
    
    # Build rows in original order
    for name, mid, url in tasks:
        if (name, mid) in task_results:
            url, info = task_results[(name, mid)]
            rows.append([
                name, mid,
                info.get("due_date",""),
                info.get("time_remaining",""),
                info.get("late_policy",""),
                info.get("max_grade",""),
                info.get("submission_status",""),
                info.get("grading_status",""),
                info.get("last_modified",""),
                info.get("submission_comments",""),
                info.get("participants",""),
                info.get("drafts",""),
                info.get("submitted",""),
                info.get("needs_grading",""),
                url
            ])
    
    elapsed = time.perf_counter() - start_time

    out = args.output or f"tasks_{args.course_id}.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Task Name","Module ID","Due Date","Time Remaining","Late Policy","Max Grade",
            "Submission Status","Grading Status","Last Modified","Submission Comments",
            "Participants","Drafts","Submitted","Needs Grading","URL"
        ])
        writer.writerows(rows)

    print("\n" + "=" * 70)
    print(f"✓ Success! Wrote {len(rows)} tasks to {out}")
    print(f"  Total time: {elapsed:.2f}s")
    print(f"  Avg per task: {elapsed/len(rows):.2f}s")
    print("=" * 70)
    
    logout_session(main_session)

if __name__ == "__main__":
    main()
