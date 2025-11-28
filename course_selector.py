"""
Paathshala Course Selector - Interactive Course ID Finder

This script fetches all your enrolled courses from Paathshala and lets you
interactively select a course to get its ID for use with other scripts.

Usage:
  python course_selector.py
  python course_selector.py --cookie <MoodleSession>
  or set MOODLE_SESSION_ID
  or create .config with username/password
"""

import os, re, sys, argparse, getpass
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
        
        # Extract MoodleSession cookie
        if 'MoodleSession' in response.cookies:
            session_cookie = response.cookies['MoodleSession']
            print(f"[Login] ✓ Successfully logged in!")
            return session_cookie
        else:
            print(f"[Login] ✗ Login failed - no session cookie received")
            print(f"[Login]   Status: {response.status_code}")
            if response.status_code == 200:
                print(f"[Login]   Hint: Check username/password")
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
    if not save_option:
        print("\n[Auth] Cookie appears to be invalid or expired.")
    print("[Auth] Please enter your credentials:\n")
    
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
        return None, None, False

def setup_session(session_id):
    s = requests.Session()
    s.cookies.set("MoodleSession", session_id, domain=PAATSHALA_HOST)
    s.headers.update({'User-Agent': 'Mozilla/5.0'})
    return s

def get_courses(session):
    """Fetch all courses using Moodle's AJAX APIs"""
    print(f"[Fetch] Getting your courses from Moodle APIs...")
    
    # Use a dict to deduplicate courses
    courses_dict = {}
    
    try:
        # First, we need to get the sesskey from the main page
        print("[Debug] Getting session key...")
        resp = session.get(f"{BASE}/my/", timeout=15)
        if not resp.ok:
            print(f"[Fetch] ✗ Failed to load dashboard: {resp.status_code}")
            return []
        
        # Extract sesskey from HTML
        import re
        sesskey_match = re.search(r'"sesskey":"([^"]+)"', resp.text)
        if not sesskey_match:
            print("[Debug] Could not find sesskey, trying without it...")
            sesskey = ""
        else:
            sesskey = sesskey_match.group(1)
            print(f"[Debug] Found sesskey: {sesskey[:10]}...")
        
        # API 1: Get enrolled courses by timeline
        print("[Debug] API 1: Fetching enrolled courses...")
        api_url = f"{BASE}/lib/ajax/service.php?sesskey={sesskey}&info=core_course_get_enrolled_courses_by_timeline_classification"
        
        payload = [{
            "index": 0,
            "methodname": "core_course_get_enrolled_courses_by_timeline_classification",
            "args": {
                "offset": 0,
                "limit": 0,
                "classification": "all",
                "sort": "fullname",
                "customfieldname": "",
                "customfieldvalue": ""
            }
        }]
        
        api_resp = session.post(api_url, json=payload, timeout=15)
        if api_resp.ok:
            try:
                data = api_resp.json()
                if data and len(data) > 0 and not data[0].get("error"):
                    courses_data = data[0].get("data", {}).get("courses", [])
                    print(f"[Debug] API 1: Found {len(courses_data)} courses")
                    
                    for course in courses_data:
                        course_id = str(course.get("id", ""))
                        if course_id and course_id not in courses_dict:
                            courses_dict[course_id] = {
                                'id': course_id,
                                'name': course.get("fullname", ""),
                                'category': course.get("coursecategory", ""),
                                'starred': course.get("isfavourite", False)
                            }
                else:
                    print(f"[Debug] API 1: No courses or error in response")
            except Exception as e:
                print(f"[Debug] API 1: Error parsing response: {e}")
        
        # API 2: Get recent courses
        print("[Debug] API 2: Fetching recent courses...")
        api_url2 = f"{BASE}/lib/ajax/service.php?sesskey={sesskey}&info=core_course_get_recent_courses"
        
        payload2 = [{
            "index": 0,
            "methodname": "core_course_get_recent_courses",
            "args": {
                "userid": 0,
                "limit": 0,
                "offset": 0,
                "sort": "fullname"
            }
        }]
        
        api_resp2 = session.post(api_url2, json=payload2, timeout=15)
        if api_resp2.ok:
            try:
                data2 = api_resp2.json()
                if data2 and len(data2) > 0 and not data2[0].get("error"):
                    courses_data2 = data2[0].get("data", [])
                    print(f"[Debug] API 2: Found {len(courses_data2)} courses")
                    
                    for course in courses_data2:
                        course_id = str(course.get("id", ""))
                        if course_id and course_id not in courses_dict:
                            courses_dict[course_id] = {
                                'id': course_id,
                                'name': course.get("fullname", ""),
                                'category': course.get("coursecategory", ""),
                                'starred': course.get("isfavourite", False)
                            }
            except Exception as e:
                print(f"[Debug] API 2: Error parsing response: {e}")
        
        # API 3: Get courses from calendar data
        print("[Debug] API 3: Fetching courses from calendar...")
        api_url3 = f"{BASE}/lib/ajax/service.php?sesskey={sesskey}&info=core_calendar_get_calendar_monthly_view"
        
        import time
        current_timestamp = int(time.time())
        
        payload3 = [{
            "index": 0,
            "methodname": "core_calendar_get_calendar_monthly_view",
            "args": {
                "year": 2025,
                "month": 11,
                "courseid": 1,
                "categoryid": 0,
                "includenavigation": True,
                "mini": False,
                "day": 1,
                "view": "month"
            }
        }]
        
        api_resp3 = session.post(api_url3, json=payload3, timeout=15)
        if api_resp3.ok:
            try:
                data3 = api_resp3.json()
                if data3 and len(data3) > 0 and not data3[0].get("error"):
                    calendar_data = data3[0].get("data", {})
                    # Extract course info from calendar events
                    weeks = calendar_data.get("weeks", [])
                    for week in weeks:
                        for day in week.get("days", []):
                            for event in day.get("events", []):
                                course_info = event.get("course", {})
                                course_id = str(course_info.get("id", ""))
                                if course_id and course_id not in courses_dict:
                                    courses_dict[course_id] = {
                                        'id': course_id,
                                        'name': course_info.get("fullname", ""),
                                        'category': course_info.get("coursecategory", ""),
                                        'starred': course_info.get("isfavourite", False)
                                    }
                    
                    print(f"[Debug] API 3: Extracted courses from calendar events")
            except Exception as e:
                print(f"[Debug] API 3: Error parsing response: {e}")
        
        # Fallback: Parse navigation menu from HTML
        if not courses_dict:
            print("[Debug] Fallback: Parsing navigation menu from HTML...")
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "html.parser")
            course_links = soup.find_all("a", href=lambda x: x and "/course/view.php?id=" in x)
            
            for link in course_links:
                course_id = link.get("data-key")
                if not course_id:
                    href = link.get("href", "")
                    if "?id=" in href:
                        course_id = href.split("?id=")[-1].split("&")[0]
                
                if not course_id or not course_id.isdigit() or course_id in courses_dict:
                    continue
                
                course_name = None
                for elem in link.children:
                    if isinstance(elem, str):
                        text = elem.strip()
                        if text:
                            course_name = text
                            break
                
                if not course_name:
                    course_name = link.get_text(strip=True)
                
                if course_name:
                    courses_dict[course_id] = {
                        'id': course_id,
                        'name': course_name,
                        'category': '',
                        'starred': False
                    }
            
            print(f"[Debug] Fallback: Found {len(courses_dict)} courses from navigation")
        
        courses = list(courses_dict.values())
        
        if not courses:
            print("[Fetch] ✗ Could not extract any courses")
        else:
            print(f"[Fetch] ✓ Successfully fetched {len(courses)} unique courses total")
        
        return courses
        
    except Exception as e:
        print(f"[Fetch] ✗ Error fetching courses: {e}")
        import traceback
        traceback.print_exc()
        return []

def display_courses(courses, show_all=False):
    """Display courses in a formatted table"""
    if not courses:
        print("\n✗ No courses to display")
        return
    
    print("\n" + "=" * 80)
    print(f"{'#':<4} {'★':<2} {'ID':<6} {'Course Name':<45} {'Category':<20}")
    print("=" * 80)
    
    for idx, course in enumerate(courses, 1):
        star = "★" if course['starred'] else " "
        name = course['name'][:43] + ".." if len(course['name']) > 45 else course['name']
        category = course['category'][:18] + ".." if len(course['category']) > 20 else course['category']
        
        print(f"{idx:<4} {star:<2} {course['id']:<6} {name:<45} {category:<20}")
    
    print("=" * 80)
    print(f"Total courses: {len(courses)}")
    print("=" * 80)

def interactive_selection(courses):
    """Interactive course selection"""
    while True:
        print("\nOptions:")
        print("  - Enter a number (1-{}) to select a course".format(len(courses)))
        print("  - Enter 's' to search by name")
        print("  - Enter 'q' to quit")
        
        try:
            choice = input("\nYour choice: ").strip().lower()
            
            if choice == 'q':
                print("Exiting...")
                return None
            
            elif choice == 's':
                search_term = input("Enter search term: ").strip().lower()
                if not search_term:
                    print("✗ Empty search term")
                    continue
                
                # Filter courses by search term
                filtered = [c for c in courses if search_term in c['name'].lower() or search_term in c['category'].lower()]
                
                if not filtered:
                    print(f"✗ No courses found matching '{search_term}'")
                    continue
                
                print(f"\n✓ Found {len(filtered)} matching course(s):")
                display_courses(filtered)
                
                if len(filtered) == 1:
                    use_it = input(f"\nUse this course (ID: {filtered[0]['id']})? (y/n): ").strip().lower()
                    if use_it in ['y', 'yes']:
                        return filtered[0]
                
            else:
                try:
                    num = int(choice)
                    if 1 <= num <= len(courses):
                        selected = courses[num - 1]
                        print(f"\n✓ Selected: {selected['name']} (ID: {selected['id']})")
                        return selected
                    else:
                        print(f"✗ Please enter a number between 1 and {len(courses)}")
                except ValueError:
                    print("✗ Invalid input. Please enter a number, 's' to search, or 'q' to quit")
        
        except (KeyboardInterrupt, EOFError):
            print("\n\nExiting...")
            return None

def main():
    parser = argparse.ArgumentParser(
        description='Interactive course selector for Paathshala',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Authentication (in order of priority):
  1. --cookie flag
  2. MOODLE_SESSION_ID environment variable
  3. cookie from .config file
  4. username/password from .config file (generates and saves cookie)
  5. Interactive prompt (safer than command line)

Examples:
  # Interactive selection
  python course_selector.py
  
  # With direct cookie
  python course_selector.py --cookie "abc123..."
  
  # List all courses and exit
  python course_selector.py --list
        """
    )
    parser.add_argument("--cookie", "-c", help="Moodle session cookie (overrides other auth methods)")
    parser.add_argument("--config", type=str, default=CONFIG_FILE, help=f"Config file path (default: {CONFIG_FILE})")
    parser.add_argument("--list", "-l", action="store_true", help="List all courses and exit (no interaction)")
    parser.add_argument("--starred", "-s", action="store_true", help="Show only starred courses")
    parser.add_argument("--json", action="store_true", help="Output in JSON format")
    args = parser.parse_args()

    print("=" * 80)
    print("Paathshala Course Selector")
    print("=" * 80)

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
                print("\n[Auth] ✗ Auto-login failed. Will prompt for credentials.")
                SESSION_ID = None
        
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

    # Create session
    session = setup_session(SESSION_ID)
    
    # Fetch courses
    print("\n[Fetch] Loading your courses...")
    courses = get_courses(session)
    
    if not courses:
        print("\n✗ No courses found or failed to fetch courses")
        sys.exit(1)
    
    # Filter starred courses if requested
    if args.starred:
        courses = [c for c in courses if c['starred']]
        if not courses:
            print("\n✗ No starred courses found")
            sys.exit(1)
        print(f"\n[Filter] Showing {len(courses)} starred course(s)")
    
    # Sort courses: starred first, then alphabetically
    courses.sort(key=lambda x: (not x['starred'], x['name'].lower()))
    
    # JSON output
    if args.json:
        import json
        print(json.dumps(courses, indent=2))
        sys.exit(0)
    
    # List mode - just display and exit
    if args.list:
        display_courses(courses)
        sys.exit(0)
    
    # Interactive mode
    display_courses(courses)
    selected = interactive_selection(courses)
    
    if selected:
        print("\n" + "=" * 80)
        print("SELECTED COURSE DETAILS")
        print("=" * 80)
        print(f"Course Name: {selected['name']}")
        print(f"Course ID:   {selected['id']}")
        print(f"Category:    {selected['category']}")
        print(f"Starred:     {'Yes' if selected['starred'] else 'No'}")
        print("=" * 80)
        print(f"\nUse this ID with other scripts:")
        print(f"  python tasklist.py {selected['id']}")
        print(f"  python submissions.py {selected['id']} --tasks-csv tasks_{selected['id']}.csv")
        print(f"  python quiz.py {selected['id']}")
        print("=" * 80)

if __name__ == "__main__":
    main()