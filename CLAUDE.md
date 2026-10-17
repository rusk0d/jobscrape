# Working with Claude Code on jobscrape

This document describes how Claude Code should approach this project.

## Project Context

**jobscrape** is a job scraping and matching system for Hungarian job boards. It aggregates jobs from multiple sources, uses Claude AI (Bedrock) to score matches against user profiles, and sends email alerts via AWS SES.

- **Primary language**: Python 3.9+
- **Infrastructure**: AWS (DynamoDB, Bedrock, SES, Cognito, Lambda)
- **Deployment**: Lambda function + Flask web app
- **Users**: Job seekers in Budapest looking for cloud/DevOps/infrastructure roles

## Code Quality Standards

### Testing
- **Integration tests required**: All database operations must test against real DynamoDB, not mocks.
- **Test failures are real**: If tests pass locally, they work. Mocks hide problems.
- **No pytest mocks for AWS**: Use LocalStack or real AWS resources for integration tests.

### Secrets & Security
- **Never commit secrets**: `.env`, `user.py`, `profile.txt` are in `.gitignore` for a reason.
- **Use environment variables**: All AWS credentials, API keys, emails go in `.env`.
- **Review before pushing**: Check `git diff` before commits—watch for accidentally hardcoded credentials.
- **Validate at boundaries**: Validate user input (web forms, API payloads). Trust internal code.

### Error Handling
- **Be specific**: Catch exceptions for known failure modes (network timeouts, JSON parse errors).
- **Log failures**: Print to stdout for Lambda logs. Include the actual error message.
- **Don't silence errors**: Except where explicitly expected (e.g., missing job descriptions).

### AWS & DynamoDB
- **Batch operations**: Use `batch_get_item()` and `batch_write_item()` for multiple records.
- **Region consistency**: All boto3 calls use `AWS_REGION` env var. No hardcoding.
- **Table names**: Use env vars (`JOBS_TABLE`, `USERS_TABLE`, `USER_JOBS_TABLE`).
- **Pagination**: Respect `LastEvaluatedKey` when querying large result sets.

## Code Organization

### scrap.py
**Role**: Core scraper and job matching logic

- `fetch_*()` functions: Fetch and parse job postings
- `save_jobs()`: Dedup and store jobs in DynamoDB
- `enrich()`: Fetch detailed job descriptions from job sites
- `score_job()`: Call Claude Bedrock to score a job against a user's profile
- `send_alerts()`: Email matching jobs to users
- `lambda_handler()`: Entry point for AWS Lambda
- `main()`: Entry point for local CLI

**Standards**:
- Each `fetch_*()` should return list of dicts with consistent schema
- All boto3 calls should use env vars for region and table names
- Error handling should log but not crash (resilient to individual job failures)

### app.py
**Role**: Flask web dashboard for job browsing and status tracking

- OAuth/Cognito authentication required
- Session-based user identity
- Display user's jobs, filter by status, update status
- Query DynamoDB using composite keys

**Standards**:
- All routes require `@require_login` or equivalent
- Database queries should use `get_table()` helper
- No hardcoded credentials or user IDs

### add_job.py
**Role**: Utility for manually adding found jobs

- Load user from DynamoDB
- Score job using `scrap.py` functions
- Save to DynamoDB

**Standards**:
- Reuse `scrap.score_job()` and `scrap.get_users()`
- User customization goes in `user.py` (not in script)

## Commit Guidelines

- **Small commits**: One logical change per commit (feature, fix, refactor, test, docs).
- **Descriptive messages**: Explain the *why*, not just the *what*.
- **Test before pushing**: Verify syntax and that logic changes work.
- **No force-push to main**: Use PRs for review; rebase/squash locally before merging.

## When to Ask for Clarification

- **Scope ambiguity**: "Add XYZ feature"—ask if it blocks on infrastructure (new AWS table?) or data migrations.
- **Trade-offs**: Backwards compatibility vs. simplification; ask which matters.
- **Performance**: If a change affects query patterns or Lambda timeout, discuss impact.
- **Security**: Any hardcoding, input handling, or data exposure—always ask before assuming.

## Collaboration

- **Use github.com issues** for tracking bugs and features.
- **Link commits** to issues (e.g., "Fixes #42" in commit message).
- **Tag with `reviewed` label** once a PR is code-reviewed and working.
- **Prefer PRs over direct commits** for visibility, especially for security changes.

## Common Patterns

### Adding a new job source
1. Write `fetch_newsite()` that returns `[{"id": ..., "title": ..., "link": ..., ...}, ...]`
2. Add filtering logic (INCLUDE/EXCLUDE keywords) if needed
3. Add to `lambda_handler()` and `main()` orchestration
4. Test with real site (not mocked)

### Changing DynamoDB schema
1. **Backward compatible**: Add new fields with defaults, don't remove old ones.
2. **Migration script**: If old data needs updating, write a one-off script.
3. **Update docstring**: Document new fields in comments.

### Debugging Lambda failures
1. Check CloudWatch logs (Lambda execution)
2. Check Step Functions if used (timing, errors between steps)
3. Test locally with `.env` file and real AWS credentials
4. Print intermediate values for investigation

## What NOT to Do

- ❌ Use mock databases (test against real DynamoDB or LocalStack)
- ❌ Hardcode AWS credentials, emails, company names, UUIDs
- ❌ Commit `.env`, `user.py`, or `profile.txt`
- ❌ Silently catch and ignore exceptions
- ❌ Add features without understanding the surrounding architecture
- ❌ Refactor without tests—this isn't legacy cleanup, it's a working system
- ❌ Add dependencies without checking compatibility with Lambda runtime

## Questions?

If unclear about project direction, code style, or infrastructure, ask before implementing.
