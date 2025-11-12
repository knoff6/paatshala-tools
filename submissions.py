"""
Paathshala Assignment Submissions Scraper - Get grading details for assignments
Fetches the grading table from assignment "View all submissions" page

User-friendly options:
  --task N      : Select Nth task (e.g., --task 1 for first, --task 2 for second)
  --group N     : Select Nth group (e.g., --group 1 for first, --group 2 for second)
  --group-id ID : Select group by exact ID (e.g., --group-id 3345)

Usage:
  python paatshala_submissions.py <course_id> --tasks-csv tasks.csv --task 1 --group 2
  or set MOODLE_SESSION_ID
  or use .config with username/password
"""

import os, re, csv, sys, argparse, getpass
import requests
from bs4 import BeautifulSoup

BASE = "https://paatshala.ictkerala.org"
PAATSHALA_HOST = "paatshala.ictkerala.org"
CONFIG_FILE = ".config"

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

def prompt_for_credentials():
    """Interactively prompt user for username and password"""
    print("\n[Auth] Cookie appears to be invalid or expired.")
    print("[Auth] Please enter your credentials to continue:\n")
    
    try:
        username = input("Username: ").strip()
        if not username:
            return None, None
        
        password = getpass.getpass("Password: ").strip()
        if not password:
            return None, None
        
        return username, password
    except (KeyboardInterrupt, EOFError):
        print("\n[Auth] Login cancelled by user")
        return None, None

def setup_session(session_id):
    s = requests.Session()
    s.cookies.set("MoodleSession", session_id, domain=PAATSHALA_HOST)
    s.headers.update({'User-Agent': 'Mozilla/5.0'})
    return s

def text_or_none(node):
    return node.get_text(" ", strip=True) if node else ""

def parse_grading_table(html):
    """
    Parse the grading table from assignment view page.
    Extract: Name, Status, Last modified, Submission, Feedback comments, Final Grade
    """
    soup = BeautifulSoup(html, "html.parser")
    
    # Find the grading table
    table = soup.find("table", class_="flexible generaltable generalbox")
    if not table:
        print("✗ No grading table found")
        return []
    
    rows = []
    tbody = table.find("tbody")
    if not tbody:
        print("✗ No tbody in table")
        return []
    
    for tr in tbody.find_all("tr"):
        # Skip empty rows
        if "emptyrow" in tr.get("class", []):
            continue
            
        cells = tr.find_all(["th", "td"])
        if len(cells) < 14:  # Make sure we have enough columns
            continue
        
        # Extract the required columns
        # c2: Name
        name_cell = cells[2]
        name_link = name_cell.find("a")
        name = name_link.get_text(strip=True) if name_link else ""
        
        # c4: Status
        status_cell = cells[4]
        status_divs = status_cell.find_all("div")
        status = " | ".join([div.get_text(strip=True) for div in status_divs])
        
        # c7: Last modified (submission)
        last_modified = text_or_none(cells[7])
        
        # c8: File submissions OR Online text - improved parsing
        submission_cell = cells[8]
        
        # Look for fileuploadsubmission divs (file uploads)
        file_divs = submission_cell.find_all("div", class_="fileuploadsubmission")
        file_links = ""
        if file_divs:
            # Extract filenames and links from file submission divs
            submissions = []
            links = []
            for div in file_divs:
                file_link = div.find("a", href=lambda h: h and "pluginfile.php" in h)
                if file_link:
                    filename = file_link.get_text(strip=True)
                    submissions.append(filename)
                    # Extract the full URL
                    href = file_link.get("href", "")
                    links.append(href)
            submissions = ", ".join(submissions)
            file_links = ", ".join(links)
        else:
            # Check for online text submissions (with no-overflow div)
            no_overflow_div = submission_cell.find("div", class_="no-overflow")
            if no_overflow_div:
                # Extract text content (usually contains URLs)
                submissions = no_overflow_div.get_text(" ", strip=True)
            else:
                # Fallback: extract all text content from the cell
                submissions = text_or_none(submission_cell)
        
        # c11: Feedback comments
        feedback = text_or_none(cells[11])
        
        # c13: Final grade
        final_grade = text_or_none(cells[13])
        
        rows.append({
            "Name": name,
            "Status": status,
            "Last Modified": last_modified,
            "Submission": submissions,
            "Feedback Comments": feedback,
            "Final Grade": final_grade
        })
    
    return rows

def get_available_groups(session, module_id):
    """Get list of available groups for an assignment"""
    url = f"{BASE}/mod/assign/view.php?id={module_id}&action=grading"
    
    try:
        resp = session.get(url, timeout=30)
        if not resp.ok:
            return []
        
        soup = BeautifulSoup(resp.text, "html.parser")
        group_select = soup.find("select", {"name": "group"})
        
        if not group_select:
            return []
        
        groups = []
        for option in group_select.find_all("option"):
            group_id = option.get("value", "")
            group_name = option.get_text(strip=True)
            if group_id and group_name:
                groups.append((group_id, group_name))
        
        return groups
    except Exception as e:
        print(f"✗ Error fetching groups: {e}")
        return []

def fetch_assignment_grading(session, module_id, group_id=None):
    """Fetch grading table for a specific assignment module, optionally filtered by group"""
    url = f"{BASE}/mod/assign/view.php?id={module_id}&action=grading"
    if group_id:
        url += f"&group={group_id}"
    
    print(f"\n[Fetch] Getting grading table for module {module_id}")
    if group_id:
        print(f"[Fetch] Filtering by group: {group_id}")
    print(f"[Fetch] URL: {url}")
    
    try:
        resp = session.get(url, timeout=30)
        if not resp.ok:
            print(f"✗ Failed to fetch grading page: HTTP {resp.status_code}")
            return []
        
        return parse_grading_table(resp.text)
    except requests.RequestException as e:
        print(f"✗ Network error: {e}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"✗ Unexpected error: {e}", file=sys.stderr)
        return []

def get_tasks_list(csv_file):
    """Read the tasks CSV file and return list of (name, module_id)"""
    tasks = []
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("Task Name", "")
                module_id = row.get("Module ID", "")
                if name and module_id:
                    tasks.append((name, module_id))
        return tasks
    except Exception as e:
        print(f"✗ Error reading tasks CSV: {e}")
        return []

def main():
    parser = argparse.ArgumentParser(
        description="Fetch assignment grading details",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Authentication (in order of priority):
  1. --cookie flag
  2. --username and --password flags (generates and saves cookie to .config)
  3. MOODLE_SESSION_ID environment variable
  4. cookie from .config file
  5. username/password from .config file (generates and saves cookie)

Config file format (.config):
  Option 1 (reusable cookie - fastest):
    cookie=your_cookie_value
  
  Option 2 (credentials - will auto-generate and save cookie):
    username=your_username
    password=your_password

Examples:
  # List available groups for first assignment
  python submissions.py 450 --tasks-csv tasks_450.csv --list-groups

  # First time with username/password (generates and saves cookie)
  python submissions.py 450 --tasks-csv tasks_450.csv --task 1 --username myuser --password mypass

  # Subsequent runs (reuses saved cookie - much faster!)
  python submissions.py 450 --tasks-csv tasks_450.csv --task 1
  python submissions.py 450 --tasks-csv tasks_450.csv --first  # same as above

  # Fetch second task
  python submissions.py 450 --tasks-csv tasks_450.csv --task 2

  # Fetch first task filtered by second group (user-friendly)
  python submissions.py 450 --tasks-csv tasks_450.csv --task 1 --group 2
  # Output: submissions_450_mod28922_grp3345.csv

  # Fetch first task filtered by specific group ID (exact)
  python submissions.py 450 --tasks-csv tasks_450.csv --task 1 --group-id 3345

  # Fetch specific module by ID
  python submissions.py 450 --module-id 28922
  # Output: submissions_450_mod28922.csv

  # Fetch specific module filtered by second group
  python submissions.py 450 --module-id 28922 --group 2
  # Output: submissions_450_mod28922_grp3345.csv

  # Process all tasks for second group
  python submissions.py 450 --tasks-csv tasks_450.csv --group 2
  # Output: submissions_450_grp3345.csv (multiple tasks)
        """
    )
    parser.add_argument("course_id", type=int, help="Course ID")
    parser.add_argument("--module-id", "-m", type=int, help="Specific module ID to fetch")
    parser.add_argument("--tasks-csv", help="Path to tasks CSV file (to get module IDs)")
    parser.add_argument("--task", "-t", type=int, help="Task number to process (e.g., --task 1 for first task, --task 2 for second)")
    parser.add_argument("--first", action="store_true", help="Only process first task (same as --task 1)")
    parser.add_argument("--group", "-g", type=int, help="Group number to filter by (e.g., --group 1 for first group, --group 2 for second)")
    parser.add_argument("--group-id", help="Exact Group ID to filter by (e.g., --group-id 3345)")
    parser.add_argument("--list-groups", action="store_true", help="List available groups for the first/specified assignment and exit")
    parser.add_argument("--cookie", "-c", help="Moodle session cookie")
    parser.add_argument("--username", "-u", help="Username for login (will generate and save cookie)")
    parser.add_argument("--password", "-p", help="Password for login (will generate and save cookie)")
    parser.add_argument("--config", type=str, default=CONFIG_FILE, help=f"Config file path (default: {CONFIG_FILE})")
    parser.add_argument("--output", "-o", help="Output CSV filename")
    args = parser.parse_args()

    print("=" * 70)
    print(f"Paathshala Submissions Scraper - Course {args.course_id}")
    print("=" * 70)

    # Get session cookie
    SESSION_ID = None
    
    # 1. Command line cookie argument
    if args.cookie:
        SESSION_ID = args.cookie
        print("[Auth] Using cookie from command line")
    
    # 2. Command line username/password arguments
    elif args.username and args.password:
        print("[Auth] Using username/password from command line")
        SESSION_ID = login_and_get_cookie(args.username, args.password)
        if SESSION_ID:
            # Save cookie to config for future use
            write_config(args.config, cookie=SESSION_ID)
        else:
            print("\n[Auth] ✗ Login failed. Please check credentials.")
            sys.exit(1)
    
    # 3. Environment variable
    elif os.environ.get("MOODLE_SESSION_ID"):
        SESSION_ID = os.environ.get("MOODLE_SESSION_ID")
        print("[Auth] Using cookie from MOODLE_SESSION_ID environment variable")
    
    # 4. Config file (cookie or username/password)
    else:
        cookie, username, password = read_config(args.config)
        
        # 4a. Try cookie from config first
        if cookie:
            SESSION_ID = cookie
            print("[Auth] Using saved cookie from config")
        
        # 4b. Try username/password from config
        elif username and password:
            print("[Auth] Using credentials from config")
            SESSION_ID = login_and_get_cookie(username, password)
            if SESSION_ID:
                # Save cookie to config for future use
                write_config(args.config, cookie=SESSION_ID)
            else:
                print("\n[Auth] ✗ Auto-login failed. Please check credentials.")
                sys.exit(1)
        
        # No authentication found
        else:
            print(f"\n[Auth] ✗ No authentication provided.")
            print(f"\nProvide authentication via:")
            print(f"  1. Command line: --cookie 'your_cookie'")
            print(f"  2. Command line: --username 'user' --password 'pass'")
            print(f"  3. Environment:  export MOODLE_SESSION_ID='your_cookie'")
            print(f"  4. Config file:  Create {args.config} with cookie or username/password")
            print(f"\nConfig file format (option 1 - reusable cookie):")
            print(f"  cookie=your_cookie_value")
            print(f"\nConfig file format (option 2 - will generate and save cookie):")
            print(f"  username=your_username")
            print(f"  password=your_password")
            sys.exit(1)

    # Validate the session cookie and prompt for credentials if invalid
    if SESSION_ID:
        print("[Auth] Validating session...")
        if not validate_session(SESSION_ID):
            print("[Auth] ✗ Cookie is invalid or expired")
            
            # Prompt for credentials interactively
            username, password = prompt_for_credentials()
            
            if username and password:
                SESSION_ID = login_and_get_cookie(username, password)
                if SESSION_ID:
                    # Save the new cookie
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

    s = setup_session(SESSION_ID)
    
    # Validate conflicting options
    if args.group and args.group_id:
        print("✗ Cannot use both --group and --group-id. Choose one.")
        sys.exit(1)
    
    if args.task and args.first:
        print("✗ Cannot use both --task and --first. Choose one (--first is same as --task 1).")
        sys.exit(1)
    
    # Validate --task requires --tasks-csv
    if args.task and not args.tasks_csv:
        print("✗ --task requires --tasks-csv to be provided.")
        print("   Example: python script.py 450 --tasks-csv tasks_450.csv --task 2")
        sys.exit(1)
    
    # Handle list-groups command
    if args.list_groups:
        if args.module_id:
            module_id = args.module_id
            task_name = "Manual Module"
        elif args.tasks_csv:
            tasks = get_tasks_list(args.tasks_csv)
            if not tasks:
                print("✗ No tasks found in CSV")
                sys.exit(1)
            
            # If --task is specified, use that task for listing groups
            if args.task:
                if args.task < 1 or args.task > len(tasks):
                    print(f"✗ Task number {args.task} is out of range (1-{len(tasks)})")
                    sys.exit(1)
                task_name, module_id = tasks[args.task - 1]  # Convert to 0-indexed
                print(f"[Task] Selected task #{args.task}: {task_name}")
            else:
                task_name, module_id = tasks[0]
        else:
            print("✗ Please provide either --module-id or --tasks-csv")
            sys.exit(1)
        
        print(f"\n[Groups] Fetching available groups for: {task_name} (Module: {module_id})\n")
        groups = get_available_groups(s, module_id)
        
        if groups:
            print(f"Found {len(groups)} group(s):\n")
            for idx, (group_id, group_name) in enumerate(groups, 1):
                if group_id == "0":
                    print(f"  Group {idx}: ID={group_id:>6} - {group_name} (all participants)")
                else:
                    print(f"  Group {idx}: ID={group_id:>6} - {group_name}")
            print(f"\nUse --group <number> to filter by group number (e.g., --group 2 for second group)")
            print(f"Or use --group-id <ID> to filter by exact group ID (e.g., --group-id {groups[1][0] if len(groups) > 1 else groups[0][0]})")
        else:
            print("✗ No groups found or assignment has no group mode")
        
        sys.exit(0)
    
    # Determine which module(s) to fetch
    modules_to_fetch = []
    
    if args.module_id:
        modules_to_fetch = [("Manual Module", str(args.module_id))]
    elif args.tasks_csv:
        tasks = get_tasks_list(args.tasks_csv)
        if not tasks:
            print("✗ No tasks found in CSV")
            sys.exit(1)
        
        # Handle task selection
        if args.task:
            if args.task < 1 or args.task > len(tasks):
                print(f"✗ Task number {args.task} is out of range (1-{len(tasks)})")
                sys.exit(1)
            modules_to_fetch = [tasks[args.task - 1]]  # Convert to 0-indexed
            print(f"\n[Mode] Fetching task #{args.task}")
        elif args.first:
            modules_to_fetch = [tasks[0]]
            print(f"\n[Mode] Fetching FIRST task (task #1)")
        else:
            modules_to_fetch = tasks
    else:
        print("✗ Please provide either --module-id or --tasks-csv")
        sys.exit(1)
    
    # Determine group filter
    group_id_to_use = None
    group_description = None
    
    if args.group_id:
        group_id_to_use = args.group_id
        group_description = f"Group ID {group_id_to_use}"
    elif args.group:
        # Need to fetch groups to get the Nth group
        # Use first module to determine available groups
        first_module_id = modules_to_fetch[0][1]
        groups = get_available_groups(s, first_module_id)
        
        if not groups:
            print("✗ No groups found for this assignment")
            sys.exit(1)
        
        if args.group < 1 or args.group > len(groups):
            print(f"✗ Group number {args.group} is out of range (1-{len(groups)})")
            print(f"   Available groups: {len(groups)}")
            print(f"   Use --list-groups to see all available groups")
            sys.exit(1)
        
        group_id_to_use, group_name = groups[args.group - 1]  # Convert to 0-indexed
        group_description = f"Group #{args.group}: {group_name} (ID: {group_id_to_use})"
        print(f"\n[Group] Selected {group_description}")
    
    # Show filter info if applied
    if group_id_to_use:
        print(f"\n[Filter] Applying group filter: {group_description}")
    
    print(f"\n[Tasks] Found {len(modules_to_fetch)} assignment(s) to process\n")
    
    # Fetch grading data for each module
    all_results = []
    
    for task_name, module_id in modules_to_fetch:
        print(f"[Task] {task_name} (Module: {module_id})")
        
        grading_data = fetch_assignment_grading(s, module_id, group_id_to_use)
        
        if grading_data:
            print(f"✓ Found {len(grading_data)} student submissions")
            
            # Add task name to each row
            for row in grading_data:
                row["Task Name"] = task_name
                row["Module ID"] = module_id
                if group_id_to_use:
                    row["Group ID"] = group_id_to_use
                all_results.append(row)
        else:
            print(f"✗ No grading data found")
        
        print()
    
    if not all_results:
        print("✗ No data collected")
        sys.exit(1)
    
    # Generate output filename with module_id and group_id
    if args.output:
        output_file = args.output
    else:
        # Build filename based on what was processed
        filename_parts = [f"submissions_{args.course_id}"]
        
        # Add module info if single module
        if len(modules_to_fetch) == 1:
            filename_parts.append(f"mod{modules_to_fetch[0][1]}")
        
        # Add group info if filtered
        if group_id_to_use:
            filename_parts.append(f"grp{group_id_to_use}")
        
        output_file = "_".join(filename_parts) + ".csv"
    
    fieldnames = ["Task Name", "Module ID"]
    if group_id_to_use:
        fieldnames.append("Group ID")
    fieldnames.extend(["Name", "Status", "Last Modified", 
                       "Submission", "Feedback Comments", "Final Grade"])
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_results)
    
    print("=" * 70)
    print(f"✓ Success! Wrote {len(all_results)} submission records to {output_file}")
    print(f"  Tasks processed: {len(modules_to_fetch)}")
    if group_id_to_use:
        print(f"  Group filter: {group_description}")
    print("=" * 70)

if __name__ == "__main__":
    main()