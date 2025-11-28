"""
Paathshala Practice Quiz Scraper - Optimized Threading with Auto-Login
"""
import os, re, csv, sys, argparse, time, threading, getpass
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

BASE = "https://paatshala.ictkerala.org"
PAATSHALA_HOST = "paatshala.ictkerala.org"
CONFIG_FILE = ".config"

# Thread-local storage for sessions
thread_local = threading.local()

def read_config(config_path=CONFIG_FILE):
    """Read cookie, username, and password from config file"""
    if not os.path.exists(config_path):
        return None, None, None
    
    cookie, username, password = None, None, None
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
                    if key == 'cookie':
                        cookie = value
                    elif key == 'username':
                        username = value
                    elif key == 'password':
                        password = value
        if cookie:
            print(f"[Config] Read cookie from {config_path}")
        elif username and password:
            print(f"[Config] Read credentials from {config_path}")
        return cookie, username, password
    except Exception as e:
        print(f"[Config] Error reading {config_path}: {e}")
        return None, None, None

def write_config(config_path, cookie=None, username=None, password=None):
    """Write cookie or credentials to config file"""
    try:
        lines = []
        existing_keys = set()
        
        # Read existing config if it exists
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                for line in f:
                    line_stripped = line.strip()
                    # Keep comments and empty lines
                    if not line_stripped or line_stripped.startswith('#'):
                        lines.append(line)
                        continue
                    # Parse key=value
                    if '=' in line_stripped:
                        key = line_stripped.split('=', 1)[0].strip().lower()
                        existing_keys.add(key)
                        # Skip lines we're updating
                        if cookie and key == 'cookie':
                            continue
                        if username and key == 'username':
                            continue
                        if password and key == 'password':
                            continue
                        lines.append(line)
                    else:
                        lines.append(line)
        
        # Add new values
        if cookie and 'cookie' not in existing_keys:
            lines.append(f"cookie={cookie}\n")
        elif cookie:
            # Insert at beginning if updating
            lines.insert(0, f"cookie={cookie}\n")
        
        if username and 'username' not in existing_keys:
            lines.append(f"username={username}\n")
        
        if password and 'password' not in existing_keys:
            lines.append(f"password={password}\n")
        
        # Write back to file
        with open(config_path, 'w') as f:
            f.writelines(lines)
        
        if cookie:
            print(f"[Config] Saved cookie to {config_path}")
        elif username and password:
            print(f"[Config] Saved credentials to {config_path}")
        return True
    except Exception as e:
        print(f"[Config] Error writing to {config_path}: {e}")
        return False

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

def validate_session(session_id):
    """Check if a session cookie is valid by making a test request"""
    try:
        s = requests.Session()
        s.cookies.set("MoodleSession", session_id, domain=PAATSHALA_HOST)
        s.headers.update({'User-Agent': 'Mozilla/5.0'})
        
        # Try to access the main page
        resp = s.get(f"{BASE}/my/", timeout=10)
        
        # Check if we're redirected to login page or get a valid response
        if resp.ok and 'login' not in resp.url.lower():
            return True
        return False
    except Exception:
        return False

def prompt_for_credentials(save_option=False):
    """Interactively prompt user for username and password"""
    print("\n[Auth] Cookie appears to be invalid or expired.")
    print("[Auth] Please enter your credentials to continue:\n")
    
    try:
        username = input("Username: ").strip()
        if not username:
            return None, None, False
        
        password = getpass.getpass("Password: ").strip()
        if not password:
            return None, None, False
        
        
        # Ask if user wants to save credentials
        if save_option:
            save_creds = input("\nSave credentials to config file? (y/n): ").strip().lower()
            should_save = save_creds in ['y', 'yes']
        else:
            should_save = False
        
        return username, password, should_save
    except (KeyboardInterrupt, EOFError):
        print("\n[Auth] Login cancelled by user")
        return None, None

def get_thread_session(session_id: str) -> requests.Session:
    """Get or create a session for the current thread"""
    if not hasattr(thread_local, 'session'):
        thread_local.session = requests.Session()
        thread_local.session.cookies.set("MoodleSession", session_id, domain=PAATSHALA_HOST)
        thread_local.session.headers.update({'User-Agent': 'Mozilla/5.0'})
        tid = threading.get_ident()
        print(f"[T{tid}] Created new session for this thread")
    return thread_local.session

def get_quizzes(session: requests.Session, course_id: int):
    url = f"https://{PAATSHALA_HOST}/course/view.php?id={course_id}"
    print(f"[Main] Fetching course page: {url}")
    resp = session.get(url)
    if not resp.ok:
        print(f"[Main] ✗ Failed to load course page: {resp.status_code}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    items = soup.find_all("li", class_="modtype_quiz")
    print(f"[Main] Found {len(items)} quiz items total")

    quizzes = []
    for item in items:
        link = item.find("a", href=re.compile(r"mod/quiz/view\.php\?id=\d+"))
        if not link:
            continue
        name = link.get_text(strip=True)
        name = re.sub(r'\s+(Quiz)$', '', name)
        if "practice quiz" in name.lower():
            m = re.search(r"id=(\d+)", link.get("href", ""))
            if m:
                module_id = m.group(1)
                quizzes.append((name, module_id))
                print(f"[Main]  ✓ Found: {name} (module {module_id})")
    return quizzes

def fetch_scores_for_module(session_id: str, module_id: str):
    """Fetch scores using thread-local session"""
    tid = threading.get_ident()
    
    # Get the thread's reusable session
    s = get_thread_session(session_id)

    view_url = f"https://{PAATSHALA_HOST}/mod/quiz/view.php?id={module_id}"
    print(f"[T{tid}] → GET view (module {module_id})")
    t0 = time.perf_counter()
    view_resp = s.get(view_url)
    print(f"[T{tid}] ← {view_resp.status_code} ({time.perf_counter()-t0:.2f}s)")
    if not view_resp.ok:
        return module_id, {}, 0

    report_url = f"https://{PAATSHALA_HOST}/mod/quiz/report.php?id={module_id}&mode=overview"
    print(f"[T{tid}] → GET report (module {module_id})")
    t0 = time.perf_counter()
    report_resp = s.get(report_url)
    print(f"[T{tid}] ← {report_resp.status_code} ({time.perf_counter()-t0:.2f}s)")
    if not report_resp.ok:
        return module_id, {}, 0

    soup = BeautifulSoup(report_resp.text, "html.parser")
    table = soup.find("table", class_="generaltable")
    if not table:
        print(f"[T{tid}] ✗ No attempts table in module {module_id}")
        return module_id, {}, 0

    scores = defaultdict(float)
    attempt_count = 0
    for row in table.find_all("tr")[1:]:
        if "emptyrow" in row.get("class", []):
            continue
        cols = row.find_all(["th", "td"])
        if len(cols) < 9:
            continue
        name_link = cols[2].find("a", href=re.compile(r"user/view\.php"))
        if name_link:
            name = name_link.get_text(strip=True)
            grade_text = cols[8].get_text(strip=True)
            grade_match = re.search(r'(\d+\.?\d*)', grade_text)
            if grade_match:
                grade = float(grade_match.group(1))
                scores[name] = max(scores[name], grade)
                attempt_count += 1

    print(f"[T{tid}] ✓ Module {module_id} – {len(scores)} students, {attempt_count} attempts")
    return module_id, scores, attempt_count

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Scrape practice quiz scores from Paathshala',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Authentication (in order of priority):
  1. --cookie flag
  2. MOODLE_SESSION_ID environment variable
  3. cookie from .config file
  4. username/password from .config file (generates and saves cookie)
  5. Interactive prompt (safer than command line)

Config file format (.config):
  Option 1 (reusable cookie - fastest):
    cookie=your_cookie_value
  
  Option 2 (credentials - will auto-generate and save cookie):
    username=your_username
    password=your_password

Examples:
  # Subsequent runs (reuses saved cookie - much faster!)
  python script.py 450
  
  # With custom thread count
  python script.py 450 --threads 8
  
  # With direct cookie
  python script.py 450 --cookie "abc123..."
        """
    )
    parser.add_argument('course_id', type=int, help='Course ID to scrape')
    parser.add_argument('--cookie', '-c', help='Moodle session cookie')
    parser.add_argument('--threads', '-t', type=int, default=4, help='Number of threads (default: 4)')
    parser.add_argument('--config', type=str, default=CONFIG_FILE, help=f'Config file path (default: {CONFIG_FILE})')
    args = parser.parse_args()

    print("=" * 70)
    print(f"Paathshala Practice Quiz Scraper - Course {args.course_id}")
    print(f"Threads: {args.threads}")
    print("=" * 70)

    # Try to get session cookie from multiple sources
    SESSION_ID = None
    
    # 1. Command line cookie argument
    if args.cookie:
        SESSION_ID = args.cookie
        print("[Auth] Using cookie from command line")
    
    # 2. Environment variable
    elif os.environ.get("MOODLE_SESSION_ID"):
        SESSION_ID = os.environ.get("MOODLE_SESSION_ID")
        print("[Auth] Using cookie from MOODLE_SESSION_ID environment variable")
    
    # 3. Config file (cookie or username/password)
    else:
        cookie, username, password = read_config(args.config)
        
        # 3a. Try cookie from config first
        if cookie:
            SESSION_ID = cookie
            print("[Auth] Using saved cookie from config")
        
        # 3b. Try username/password from config
        elif username and password:
            print("[Auth] Using credentials from config")
            SESSION_ID = login_and_get_cookie(username, password)
            if SESSION_ID:
                # Save cookie to config for future use
                write_config(args.config, cookie=SESSION_ID)
            else:
                print("\n[Auth] ✗ Auto-login failed. Please check credentials.")
                sys.exit(1)
        
        # No authentication found - prompt user
        else:
            print(f"\n[Auth] No authentication configured.")
            username, password, should_save = prompt_for_credentials(save_option=True)
            
            if username and password:
                SESSION_ID = login_and_get_cookie(username, password)
                if SESSION_ID:
                    # Always save the cookie
                    if should_save:
                        write_config(args.config, cookie=SESSION_ID, username=username, password=password)
                    else:
                        write_config(args.config, cookie=SESSION_ID)
                    print("[Auth] ✓ Successfully logged in")
                else:
                    print("\n[Auth] ✗ Login failed. Please check credentials and try again.")
                sys.exit(1)
            else:
                print("\n[Auth] ✗ No credentials provided. Exiting.")
                sys.exit(1)

    # Validate the session cookie and prompt for credentials if invalid
    if SESSION_ID:
        print("[Auth] Validating session...")
        if not validate_session(SESSION_ID):
            print("[Auth] ✗ Cookie is invalid or expired")
            
            # Prompt for credentials interactively
            username, password, should_save = prompt_for_credentials()
            
            if username and password:
                SESSION_ID = login_and_get_cookie(username, password)
                if SESSION_ID:
                    # Always save the cookie, optionally save credentials
                    if should_save:
                        write_config(args.config, cookie=SESSION_ID, username=username, password=password)
                    else:
                        write_config(args.config, cookie=SESSION_ID)
                    print("[Auth] ✓ Successfully logged in with new credentials")
                else:
                    print("\n[Auth] ✗ Login failed. Please check credentials and try again.")
                sys.exit(1)
            else:
                print("\n[Auth] ✗ No credentials provided. Exiting.")
                sys.exit(1)
        else:
            print("[Auth] ✓ Session is valid")

    start_all = time.perf_counter()

    # Create main session for initial course fetch
    main_session = requests.Session()
    main_session.cookies.set("MoodleSession", SESSION_ID, domain=PAATSHALA_HOST)
    main_session.headers.update({'User-Agent': 'Mozilla/5.0'})
    
    quizzes = get_quizzes(main_session, args.course_id)
    if not quizzes:
        print("[Main] ✗ No practice quizzes found.")
        sys.exit(1)

    print(f"[Main] Found {len(quizzes)} practice quizzes\n")

    all_scores = defaultdict(dict)
    quiz_names_ordered = [name for name, _ in quizzes]
    mid_to_name = {mid: name for name, mid in quizzes}
    attempts_total = 0

    print(f"[Main] Starting parallel fetch with {args.threads} threads...\n")
    
    with ThreadPoolExecutor(max_workers=max(1, args.threads)) as executor:
        futures = {executor.submit(fetch_scores_for_module, SESSION_ID, mid): mid for _, mid in quizzes}
        for fut in as_completed(futures):
            mid = futures[fut]
            try:
                _mid, scores, attempt_count = fut.result()
            except Exception as e:
                print(f"[Main] ✗ Error on module {mid}: {e}")
                continue
            attempts_total += attempt_count
            quiz_name = mid_to_name.get(_mid, f"module_{_mid}")
            for student, grade in scores.items():
                all_scores[student][quiz_name] = grade

    if not all_scores:
        print("[Main] ✗ No student data found.")
        sys.exit(1)

    students = sorted(all_scores.keys())
    output_file = f"quiz_scores_{args.course_id}.csv"
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Student Name"] + quiz_names_ordered)
        for student in students:
            writer.writerow([student] + [all_scores[student].get(q, "") for q in quiz_names_ordered])

    elapsed = time.perf_counter() - start_all
    print("\n" + "=" * 70)
    print(f"[Main] ✓ Success!")
    print(f"[Main]  Students: {len(students)}")
    print(f"[Main]  Quizzes: {len(quiz_names_ordered)}")
    print(f"[Main]  Attempts counted: {attempts_total}")
    print(f"[Main]  Output: {output_file}")
    print(f"[Main]  Total time: {elapsed:.2f}s")
    print(f"[Main]  Avg per quiz: {elapsed/len(quiz_names_ordered):.2f}s")
    print("=" * 70)