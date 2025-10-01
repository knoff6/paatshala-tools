"""
Minimal Paathshala Quiz Scraper - CSV output
Usage: 
  python scraper.py <course_id>
  python scraper.py <course_id> --cookie <session_cookie>
  
Examples:
  python scraper.py 450
  python scraper.py 450 --cookie "abc123xyz..."
"""
import os, re, csv, sys, argparse
from collections import defaultdict
import requests
from bs4 import BeautifulSoup

def setup_session(session_id):
    s = requests.Session()
    s.cookies.set("MoodleSession", session_id, domain="paatshala.ictkerala.org")
    s.headers.update({'User-Agent': 'Mozilla/5.0'})
    return s

def get_quizzes(session, course_id):
    url = f"https://paatshala.ictkerala.org/course/view.php?id={course_id}"
    print(f"Fetching course page: {url}")
    
    resp = session.get(url)
    if not resp.ok:
        print(f"✗ Failed to load course page: {resp.status_code}")
        return []
    
    soup = BeautifulSoup(resp.text, "html.parser")
    items = soup.find_all("li", class_="modtype_quiz")
    print(f"Found {len(items)} quiz items")
    
    quizzes = []
    for item in items:
        link = item.find("a", href=re.compile(r"mod/quiz/view\.php\?id=\d+"))
        if link:
            name = link.get_text(strip=True)
            name = re.sub(r'\s+(Quiz)$', '', name)
            if "practice quiz" in name.lower():
                module_id = re.search(r"id=(\d+)", link.get("href", "")).group(1)
                quizzes.append((name, module_id))
                print(f"  ✓ Found: {name} (module {module_id})")
    
    return quizzes

def get_scores(session, module_id):
    # Visit quiz page first
    view_url = f"https://paatshala.ictkerala.org/mod/quiz/view.php?id={module_id}"
    view_resp = session.get(view_url)
    if not view_resp.ok:
        print(f"  ✗ Could not open quiz view (status {view_resp.status_code})")
        return {}
    
    # Get report
    report_url = f"https://paatshala.ictkerala.org/mod/quiz/report.php?id={module_id}&mode=overview"
    report_resp = session.get(report_url)
    if not report_resp.ok:
        print(f"  ✗ Could not open quiz report (status {report_resp.status_code})")
        return {}
    
    soup = BeautifulSoup(report_resp.text, "html.parser")
    table = soup.find("table", class_="generaltable")
    if not table:
        print(f"  ✗ No attempts table found")
        return {}
    
    scores = defaultdict(float)
    attempt_count = 0
    
    for row in table.find_all("tr")[1:]:
        if "emptyrow" in row.get("class", []):
            continue
        
        cols = row.find_all(["th", "td"])
        if len(cols) < 9:
            continue
        
        # Column 2 = name, Column 8 = grade
        name_link = cols[2].find("a", href=re.compile(r"user/view\.php"))
        if name_link:
            name = name_link.get_text(strip=True)
            grade_text = cols[8].get_text(strip=True)
            grade_match = re.search(r'(\d+\.?\d*)', grade_text)
            if grade_match:
                grade = float(grade_match.group(1))
                scores[name] = max(scores[name], grade)
                attempt_count += 1
    
    print(f"  ✓ Found {len(scores)} unique students with {attempt_count} total attempts")
    return scores

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Scrape practice quiz scores from Paathshala',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scraper.py 450
  python scraper.py 450 --cookie "abc123xyz..."
  
  export MOODLE_SESSION_ID="abc123xyz..."
  python scraper.py 450
        """
    )
    parser.add_argument('course_id', type=int, help='Course ID to scrape')
    parser.add_argument('--cookie', '-c', help='Moodle session cookie (overrides MOODLE_SESSION_ID env var)')
    
    args = parser.parse_args()
    
    # Get session ID from argument or environment
    SESSION_ID = args.cookie or os.environ.get("MOODLE_SESSION_ID")
    
    if not SESSION_ID:
        print("Error: No session cookie provided.")
        print("\nProvide cookie via:")
        print("  1. Command line: python scraper.py 450 --cookie 'your_cookie'")
        print("  2. Environment:  export MOODLE_SESSION_ID='your_cookie'")
        exit(1)
    
    print("=" * 70)
    print(f"Paathshala Practice Quiz Scraper - Course {args.course_id}")
    print("=" * 70)
    print()
    
    session = setup_session(SESSION_ID)
    quizzes = get_quizzes(session, args.course_id)
    
    if not quizzes:
        print("\n✗ No practice quizzes found in course.")
        exit(1)
    
    print(f"\nFound {len(quizzes)} practice quizzes\n")
    
    all_scores = defaultdict(dict)
    for name, mid in quizzes:
        print(f"Processing: {name} (module {mid})")
        for student, grade in get_scores(session, mid).items():
            all_scores[student][name] = grade
    
    if not all_scores:
        print("\n✗ No student data found. Check permissions and quiz attempts.")
        exit(1)
    
    # Write CSV
    students = sorted(all_scores.keys())
    quiz_names = [name for name, _ in quizzes]
    
    output_file = f"quiz_scores_{args.course_id}.csv"
    with open(output_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Student Name"] + quiz_names)
        for student in students:
            writer.writerow([student] + [all_scores[student].get(q, "") for q in quiz_names])
    
    print("\n" + "=" * 70)
    print(f"✓ Success!")
    print(f"  Students: {len(students)}")
    print(f"  Quizzes: {len(quiz_names)}")
    print(f"  Output: {output_file}")
    print("=" * 70)