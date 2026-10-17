# jobscrape

A Python-based job scraping and matching system that aggregates job postings from multiple Hungarian job boards and uses AI to match them against user profiles.

## Features

- **Multi-source job aggregation**: Fetches jobs from:
  - Profession.hu (RSS feeds)
  - No Fluff Jobs (RSS)
  - Randstad (sitemap scraping)
  - SmartRecruiters API
  
- **Intelligent job matching**: Uses Claude AI (via AWS Bedrock) to score job postings against user profiles
  
- **User preferences**: Customizable search keywords, inclusion/exclusion filters, and alert thresholds
  
- **Email notifications**: AWS SES integration to send matching jobs to users
  
- **Web interface**: Flask-based dashboard with Cognito authentication to track job status
  
- **Database persistence**: DynamoDB for job storage and user tracking

## Setup

### Prerequisites
- Python 3.9+
- AWS account with:
  - DynamoDB tables (`jobs`, `users`, `user_jobs`)
  - Bedrock access (Claude model)
  - SES (for email)
  - Cognito (for web auth)
- AWS CLI configured with credentials

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/rusk0d/jobscrape.git
   cd jobscrape
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your AWS credentials and Cognito settings
   ```

4. **Set up user profile**
   ```bash
   cp user.py.example user.py
   # Edit user.py with your user ID, email, search queries, and preferences
   # Create profile.txt with your CV or profile text
   python user.py  # Run to save user to DynamoDB
   ```

## Usage

### Run the job scraper
```bash
python scrap.py
```
This fetches jobs from all sources, saves new jobs to DynamoDB, enriches them with details, and sends alerts to matching users.

### Run as Lambda
The `lambda_handler()` function in `scrap.py` is designed to run as an AWS Lambda function (e.g., on a schedule via EventBridge).

### Web Dashboard
```bash
python -m flask --app app run
```
Visit `http://localhost:4999` to browse jobs and track status.

### Add Jobs Manually
```bash
# Edit add_job.py with job details, then:
python add_job.py
```

## Configuration

### Environment Variables
- `AWS_REGION`: AWS region (default: `eu-central-1`)
- `JOBS_TABLE`: DynamoDB table for job postings
- `USER_JOBS_TABLE`: DynamoDB table for user-job associations
- `USERS_TABLE`: DynamoDB table for user profiles
- `COMPANY_NAME`: SmartRecruiters company slug
- `SES_SOURCE_EMAIL`: Email address for sending alerts
- `COGNITO_*`: Cognito configuration for web auth
- `FLASK_SECRET_KEY`: Flask session secret

### User Configuration (user.py)
- `user_id`: Unique user identifier (UUID)
- `email`: User email for alerts
- `profile`: CV or profile text (loaded from `profile.txt`)
- `searches`: List of RSS feed URLs to monitor
- `include`: Keywords to prioritize in job titles
- `exclude`: Keywords to filter out
- `alert`: Score threshold for sending alerts (0-100)

## Architecture

```
scrap.py
├── fetch_*() functions: Download job postings from various sources
├── save_jobs(): Deduplicate and store jobs in DynamoDB
├── enrich(): Fetch detailed job descriptions
├── score_job(): Use Claude to score job fit
├── score_for_user(): Score all jobs for a user
├── send_alerts(): Email matching jobs to user
└── lambda_handler()/main(): Orchestrate the pipeline

app.py
├── Flask web app with Cognito OAuth
├── Display user's jobs with filtering and status tracking
└── Update job status (new → interested → applied → etc.)

add_job.py
└── Manual job entry for found-on-LinkedIn-style additions
```

## DynamoDB Schema

### jobs table
```
- id (PK): Unique job posting ID (URL or hash)
- title, link, location, salary, employer
- source: Where the job came from (Profession, No Fluff Jobs, etc.)
- description: Array of description lines
- posted_at, first_seen, last_seen: Timestamps
```

### user_jobs table
```
- user_id (PK), job_id (SK): Composite key
- status: Job status (new, interested, applied, interviewing, rejected, dismissed)
- score: AI match score (0-100)
- reason: Why Claude scored it this way
- first_seen: When job was first seen
```

### users table
```
- user_id (PK): User UUID
- email: User email
- profile: CV/profile text
- searches: List of RSS URLs to monitor
- include/exclude: Filter keywords
- alert: Score threshold
```

## Roadmap

- [ ] Support more job sources (LinkedIn, Indeed, Stack Overflow)
- [ ] Implement job de-duplication across sources
- [ ] Add job description caching to reduce API calls
- [ ] Create admin dashboard for managing users and sources
- [ ] Add Slack notifications as alternative to email
- [ ] Implement job trending and market analysis
- [ ] Support other languages beyond Hungarian

## Contributing

Contributions welcome! Please note:
- Never commit `.env`, `user.py`, or `profile.txt`
- Use `.env.example` and `user.py.example` for templates
- Test with real AWS resources (no mocks for database integration)

## License

MIT

## Support

For issues, feature requests, or questions, please open a GitHub issue.
