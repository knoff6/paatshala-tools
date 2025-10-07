"""
Paathshala Practice Quiz Scraper - Optimized Threading with Session Reuse
"""
import os, re, csv, sys, argparse, time, threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

PAATSHALA_HOST = "paatshala.ictkerala.org"

# Thread-local storage for sessions
thread_local = threading.local()

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

    print(f"[T{tid}] ✓ Module {module_id} — {len(scores)} students, {attempt_count} attempts")
    return module_id, scores, attempt_count

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('course_id', type=int)
    parser.add_argument('--cookie', '-c', help='Moodle session cookie')
    parser.add_argument('--threads', '-t', type=int, default=4, help='Number of threads (default: 4)')
    args = parser.parse_args()

    SESSION_ID = args.cookie or os.environ.get("MOODLE_SESSION_ID")
    if not SESSION_ID:
        print("Error: No session cookie provided.")
        sys.exit(1)

    start_all = time.perf_counter()

    print("=" * 70)
    print(f"Paathshala Practice Quiz Scraper - Course {args.course_id}")
    print(f"Threads: {args.threads}")
    print("=" * 70)

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
