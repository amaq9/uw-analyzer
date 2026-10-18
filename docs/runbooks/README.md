# Runbooks

Short, step-by-step guides for things that go wrong or need care. Written for the Product Owner and
on-call engineer: plain English first, commands second. Each runbook states how to tell it worked.

| Runbook | When to use |
|---|---|
| [Try the API on your own computer](local-development.md) | Running and testing locally with test tokens |
| [Test run script (plain English)](test-run.md) | Testing the whole product step by step |
| [Assisted mode: analyse a case with Claude Code](assisted-mode.md) | Getting a draft recommendation before the research pipeline exists |
| [Recording published credit ratings](published-ratings.md) | Adding Moody's, S&P or Fitch ratings, with their source, to a case |
| [Reading the notes and auditor's report](notes-review.md) | Why Step 1 says the printed 10-K was not read, and how an analyst session adds to it |
| [Database migrations](database-migrations.md) | Applying or rolling back a schema change |
| [Security incident](security-incident.md) | Suspected leak, breach, or authentication/tenant defect |

Planned (written as the matching feature lands): connector outage, LLM outage, stuck research jobs,
backup restore, secret rotation, hotfix.
