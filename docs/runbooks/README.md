# Runbooks

Short, step-by-step guides for things that go wrong or need care. Written for the Product Owner and
on-call engineer: plain English first, commands second. Each runbook states how to tell it worked.

| Runbook | When to use |
|---|---|
| [Try the API on your own computer](local-development.md) | Running and testing locally with test tokens |
| [Database migrations](database-migrations.md) | Applying or rolling back a schema change |
| [Security incident](security-incident.md) | Suspected leak, breach, or authentication/tenant defect |

Planned (written as the matching feature lands): connector outage, LLM outage, stuck research jobs,
backup restore, secret rotation, hotfix.
