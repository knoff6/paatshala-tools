# Paathshala Tools

A comprehensive toolkit for extracting data from Paathshala (ICT Kerala's Moodle-based Learning Management System). This suite of Python scripts enables educators to efficiently gather practice quiz scores, assignment metadata, and grading information.

[![Python Version](https://img.shields.io/badge/python-3.6%2B-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Moodle](https://img.shields.io/badge/platform-Moodle-orange)](https://paatshala.ictkerala.org)

## 📋 Table of Contents

- [Features](#-features)
- [Scripts Overview](#-scripts-overview)
- [Installation](#-installation)
- [Quick Start](#-quick-start)
- [Authentication](#-authentication)
- [Usage Examples](#-usage-examples)
- [Configuration](#-configuration)
- [Advanced Features](#-advanced-features)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)
- [License](#-license)

## ✨ Features

- 🔐 **Unified Authentication** - Login once, use across all scripts
- 🍪 **Cookie Persistence** - Automatic cookie saving and reuse
- 🔄 **Auto-Recovery** - Interactive credential prompting on expired cookies
- ⚡ **Multi-Threading** - Fast parallel data fetching
- 📊 **CSV Export** - Clean, structured data output
- 🛡️ **Secure** - Password masking and secure credential storage
- 🔧 **Flexible** - Multiple authentication methods
- 📝 **Well-Documented** - Comprehensive guides and examples

## 📦 Scripts Overview

### 1. quiz.py - Practice Quiz Scores
Extracts student scores from practice quizzes with multi-threaded fetching.

**Output:** `quiz_scores_<course_id>.csv`

**Features:**
- Fetches highest scores per student
- Parallel processing with configurable threads
- Automatic quiz discovery

### 2. tasklist.py - Assignment Metadata
Lists all assignments with comprehensive metadata.

**Output:** `tasks_<course_id>.csv`

**Features:**
- Due dates, time remaining, late policies
- Submission status, grading status
- Participant counts, draft/submitted counts
- Direct links to assignments

### 3. submissions.py - Grading Tables
Retrieves detailed grading information for assignments.

**Output:** `submissions_<course_id>_mod<module_id>.csv`

**Features:**
- Student submission status
- File uploads and online text submissions
- Feedback comments and final grades
- Group filtering support

## 🚀 Installation

### Prerequisites

- Python 3.6 or higher
- Active Paathshala account
- Internet connection

### Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/paathshala-scraper.git
   cd paathshala-scraper
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Verify installation**
   ```bash
   python quiz.py --help
   python tasklist.py --help
   python submissions.py --help
   ```

## ⚡ Quick Start

### First Time Setup

**Option 1: Command Line (Recommended)**
```bash
# Login with any script - cookie saved for all
python quiz.py 450 --username your_username --password your_password
```

**Option 2: Config File**
```bash
# Create .config file
cat > .config << EOF
username=your_username
password=your_password
EOF

# Make it secure
chmod 600 .config

# Run any script
python quiz.py 450
```

### Daily Usage

After initial setup, just run scripts normally:

```bash
# Get practice quiz scores
python quiz.py 450

# Get assignment list
python tasklist.py 450

# Get grading data for first assignment
python submissions.py 450 --tasks-csv tasks_450.csv --task 1
```

## 🔐 Authentication

### Authentication Methods (Priority Order)

1. **Command-line cookie**
   ```bash
   python quiz.py 450 --cookie "your_session_cookie"
   ```

2. **Command-line credentials** (generates and saves cookie)
   ```bash
   python quiz.py 450 --username teacher --password secret
   ```

3. **Environment variable**
   ```bash
   export MOODLE_SESSION_ID="your_session_cookie"
   python quiz.py 450
   ```

4. **Config file cookie** (fastest - auto-saved)
   ```
   cookie=abc123xyz456...
   ```

5. **Config file credentials** (auto-generates cookie)
   ```
   username=your_username
   password=your_password
   ```

### Config File Format

Create a `.config` file in the script directory:

```ini
# Option 1: Cookie (fastest - auto-saved after first login)
cookie=your_cookie_value

# Option 2: Credentials (generates and saves cookie automatically)
username=your_username
password=your_password

# Both can coexist - cookie takes priority
```

**Security:** Always set proper permissions
```bash
chmod 600 .config
```

### Interactive Recovery

When a cookie expires, scripts automatically prompt for credentials:

```bash
$ python quiz.py 450

[Auth] Validating session...
[Auth] ✗ Cookie is invalid or expired
[Auth] Please enter your credentials to continue:

Username: teacher
Password: ******* (hidden)

[Auth] ✓ Successfully logged in with new credentials
# Script continues automatically!
```

## 📖 Usage Examples

### quiz.py Examples

**Basic usage:**
```bash
python quiz.py 450
```

**With more threads for faster execution:**
```bash
python quiz.py 450 --threads 8
```

**With custom config file:**
```bash
python quiz.py 450 --config .config.teacher
```

**Output columns:**
- Student Name
- Practice Quiz 1, Practice Quiz 2, Practice Quiz 3... (highest scores)

---

### tasklist.py Examples

**Basic usage:**
```bash
python tasklist.py 450
```

**With custom output filename:**
```bash
python tasklist.py 450 --output my_assignments.csv
```

**With more threads:**
```bash
python tasklist.py 450 --threads 8
```

**Output columns:**
- Task Name, Module ID, Due Date, Time Remaining
- Late Policy, Max Grade, Submission Status, Grading Status
- Last Modified, Comments, Participants, Drafts, Submitted
- Needs Grading, URL

---

### submissions.py Examples

**List available groups:**
```bash
python submissions.py 450 --tasks-csv tasks_450.csv --list-groups
```

**Get first assignment:**
```bash
python submissions.py 450 --tasks-csv tasks_450.csv --task 1
# OR
python submissions.py 450 --tasks-csv tasks_450.csv --first
```

**Get second assignment:**
```bash
python submissions.py 450 --tasks-csv tasks_450.csv --task 2
```

**Filter by group:**
```bash
python submissions.py 450 --tasks-csv tasks_450.csv --task 1 --group 2
```

**Direct module ID access:**
```bash
python submissions.py 450 --module-id 28922
```

**All assignments:**
```bash
python submissions.py 450 --tasks-csv tasks_450.csv
```

**Output columns:**
- Name, Status, Last Modified, Submission
- Feedback Comments, Final Grade

---

### Complete Workflow

```bash
#!/bin/bash
# Complete data collection for a course

COURSE_ID=450

# Step 1: Get practice quiz scores
echo "Fetching quiz scores..."
python quiz.py $COURSE_ID

# Step 2: Get assignment metadata  
echo "Fetching assignment list..."
python tasklist.py $COURSE_ID

# Step 3: Get grading data for first assignment
echo "Fetching grading data..."
python submissions.py $COURSE_ID --tasks-csv tasks_${COURSE_ID}.csv --task 1

echo "✓ All data collected!"
ls -lh *.csv
```

## ⚙️ Configuration

### Command-Line Options

#### quiz.py
| Option | Description | Default |
|--------|-------------|---------|
| `course_id` | Course ID (required) | - |
| `--cookie, -c` | Session cookie | - |
| `--username, -u` | Username for login | - |
| `--password, -p` | Password for login | - |
| `--threads, -t` | Number of threads | 4 |
| `--config` | Config file path | .config |

#### tasklist.py
| Option | Description | Default |
|--------|-------------|---------|
| `course_id` | Course ID (required) | - |
| `--cookie, -c` | Session cookie | - |
| `--username, -u` | Username for login | - |
| `--password, -p` | Password for login | - |
| `--threads, -t` | Number of threads | 4 |
| `--config` | Config file path | .config |
| `--output, -o` | Output filename | tasks_<id>.csv |

#### submissions.py
| Option | Description | Default |
|--------|-------------|---------|
| `course_id` | Course ID (required) | - |
| `--tasks-csv` | Path to tasks CSV | - |
| `--task, -t` | Task number (1, 2, 3...) | - |
| `--first` | First task (same as --task 1) | - |
| `--module-id, -m` | Direct module ID | - |
| `--group, -g` | Group number (1, 2, 3...) | - |
| `--group-id` | Exact group ID | - |
| `--list-groups` | List available groups | - |
| `--cookie, -c` | Session cookie | - |
| `--username, -u` | Username for login | - |
| `--password, -p` | Password for login | - |
| `--config` | Config file path | .config |
| `--output, -o` | Output filename | auto-generated |

### Environment Variables

```bash
# Set session cookie via environment variable
export MOODLE_SESSION_ID="your_session_cookie"

# Now all scripts use this cookie
python quiz.py 450
python tasklist.py 450
python submissions.py 450 --tasks-csv tasks_450.csv --task 1
```

## 🎯 Advanced Features

### Multi-Course Processing

```bash
#!/bin/bash
# Process multiple courses

for course in 450 451 452; do
  echo "Processing course $course..."
  python quiz.py $course
  python tasklist.py $course
done
```

### Group-Specific Reports

```bash
#!/bin/bash
# Generate reports for each group

COURSE=450

# First get the task list
python tasklist.py $COURSE

# Then process each group
for group in 1 2 3; do
  python submissions.py $COURSE \
    --tasks-csv tasks_${COURSE}.csv \
    --task 1 \
    --group $group \
    --output group${group}_submissions.csv
done
```

### Automated Cron Job

```bash
# Add to crontab (crontab -e)
# Run every Monday at 9 AM
0 9 * * 1 cd /path/to/paathshala-scraper && ./weekly_report.sh > log.txt 2>&1
```

**weekly_report.sh:**
```bash
#!/bin/bash
export MOODLE_SESSION_ID="your_cookie"  # Or use .config

python quiz.py 450
python tasklist.py 450
python submissions.py 450 --tasks-csv tasks_450.csv --task 1

echo "Report generated: $(date)"
```

### Using Different Accounts

```bash
# Use separate config files for different accounts

# Teacher account
python quiz.py 450 --config .config.teacher

# Admin account
python quiz.py 450 --config .config.admin

# Guest account
python quiz.py 450 --config .config.guest
```

## 🔧 Troubleshooting

### Common Issues

#### "No authentication provided"
**Solution:** Provide credentials via command line or create `.config` file
```bash
python quiz.py 450 --username your_username --password your_password
```

#### "Login failed"
**Solution:** Check your username and password
```bash
# Verify credentials in .config
cat .config

# Try logging in manually via command line
python quiz.py 450 --username teacher --password pass
```

#### "Cookie is invalid or expired"
**Solution:** Script will automatically prompt for credentials. Just enter them when asked.
```bash
# Script handles this automatically!
# Just follow the prompts
```

#### "No tasks CSV file" (for submissions.py)
**Solution:** Generate it first with tasklist.py
```bash
python tasklist.py 450
# Creates tasks_450.csv

# Now use it
python submissions.py 450 --tasks-csv tasks_450.csv --task 1
```

#### "ModuleNotFoundError: No module named 'requests'"
**Solution:** Install dependencies
```bash
pip install -r requirements.txt
```

#### Scripts running slow
**Solution:** Increase thread count
```bash
python quiz.py 450 --threads 8
python tasklist.py 450 --threads 8
```

#### Permission denied on .config
**Solution:** Set proper permissions
```bash
chmod 600 .config
```

### Debug Mode

For more verbose output, check the console messages. All scripts provide detailed status messages:

```bash
python quiz.py 450
# Shows:
# [Auth] Using saved cookie from config
# [Auth] Validating session...
# [Auth] ✓ Session is valid
# [Main] Fetching course page...
# [Main] Found 5 quiz items total
# etc.
```

### Getting Help

```bash
# View all options for any script
python quiz.py --help
python tasklist.py --help
python submissions.py --help
```

## 🔒 Security Best Practices

1. **Protect your .config file**
   ```bash
   chmod 600 .config
   ```

2. **Add .config to .gitignore**
   ```bash
   echo ".config" >> .gitignore
   echo "*.csv" >> .gitignore
   ```

3. **Never commit credentials**
   ```bash
   git update-index --assume-unchanged .config
   ```

4. **Use environment variables for CI/CD**
   ```bash
   export MOODLE_SESSION_ID="cookie_from_secure_storage"
   ```

5. **Rotate cookies periodically**
   ```bash
   # Delete old cookie to force fresh login
   sed -i '/^cookie=/d' .config
   python quiz.py 450 --username teacher --password pass
   ```

## 📊 Output File Formats

### quiz_scores_450.csv
```csv
Student Name,Practice Quiz 1,Practice Quiz 2,Practice Quiz 3
Alice Johnson,10.00,9.50,10.00
Bob Smith,8.00,9.00,8.50
Charlie Brown,9.00,10.00,9.50
```

### tasks_450.csv
```csv
Task Name,Module ID,Due Date,Time Remaining,Late Policy,Max Grade,Submission Status,Grading Status,Last Modified,Submission Comments,Participants,Drafts,Submitted,Needs Grading,URL
Assignment 1,28922,2025-11-15,2 days,Accepted,10,Submitted,Graded,2025-11-14 10:30,0,30,2,25,0,https://...
Assignment 2,28923,2025-11-22,9 days,Not accepted,15,Draft,Not graded,2025-11-10 14:20,0,30,5,20,5,https://...
```

### submissions_450_mod28922.csv
```csv
Name,Status,Last Modified,Submission,Feedback Comments,Final Grade
Alice Johnson,Submitted,2025-11-14 10:30,assignment1.pdf,,9.5
Bob Smith,Submitted,2025-11-14 11:15,assignment1.docx,,8.0
Charlie Brown,Not submitted,-,No submission,,0.0
```

## 🤝 Contributing

Contributions are welcome! Here's how you can help:

1. **Report bugs** - Open an issue describing the problem
2. **Suggest features** - Open an issue with your idea
3. **Submit pull requests** - Fork, create a branch, and submit PR
4. **Improve documentation** - Help make docs clearer

### Development Setup

```bash
# Clone the repo
git clone https://github.com/yourusername/paathshala-scraper.git
cd paathshala-scraper

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run tests (if you add them)
python -m pytest tests/
```

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built for educators using Paathshala (ICT Kerala's Moodle LMS)
- Inspired by the need for efficient data extraction from legacy systems
- Thanks to all contributors and users

## 📧 Support

- **Documentation:** Check the `/docs` folder for detailed guides
- **Issues:** [GitHub Issues](https://github.com/yourusername/paathshala-scraper/issues)
- **Discussions:** [GitHub Discussions](https://github.com/yourusername/paathshala-scraper/discussions)

## 🗺️ Roadmap

- [ ] Add GUI interface
- [ ] Support for more Moodle LMS instances
- [ ] Export to Excel format
- [ ] Automated report generation
- [ ] Email notifications on completion
- [ ] Docker containerization

## 📚 Additional Resources

- [Paathshala Platform](https://paatshala.ictkerala.org)
- [Moodle Documentation](https://docs.moodle.org)
- [Python Requests](https://docs.python-requests.org)
- [BeautifulSoup Documentation](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)

---

**Version:** 2.1  
**Last Updated:** November 2025  
**Maintainer:** [knoff6](https://github.com/knoff6)

Made with ❤️ for educators
