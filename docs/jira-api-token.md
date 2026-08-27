# Create an Atlassian API token

The harness talks to Jira Cloud with **email + API token** basic auth. Copilot never sees the token. You create it in the browser, put it in `.env`, and the CLI loads that file in-process.

## 1. Create the token

1. Sign in to [id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens).
2. Prefer **Create API token with scopes**. Classic tokens work, but scoped tokens are tighter.
3. Name it something obvious, for example `copilot-harness`.
4. Set an expiry (Atlassian caps this at one year).
5. If you are creating a scoped token, choose **Jira** and the least privilege you need:
   - **Planning profile (default):** read issue, search, and comment scopes. Enough for `prepare`, `jira get/search/mine`, and `/jira-ticket`.
   - **Write profile (later):** add comment / transition scopes only after `harness jira comment` exists. Do not mint write scopes "just in case."
6. Click **Create**, then **Copy**. You cannot view the value again.

If your company uses SSO, you can still create a token for your own Atlassian account. Service-account tokens are an admin concern; this harness is meant for personal tokens.

## 2. Put it in `.env`

From the harness repo:

```bash
cp .env.example .env
```

Set:

```bash
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_EMAIL=you@company.com
JIRA_API_TOKEN=the-token-you-just-copied
```

`JIRA_EMAIL` must be the Atlassian account email that owns the token, not a Slack handle.

Do **not**:

- Paste the token into Copilot Chat
- Export it in your shell profile
- Commit `.env`
- Check it into screenshots or PR descriptions

## 3. Confirm it works

```bash
uv run harness init
uv run harness doctor --ping-jira
uv run harness jira whoami
```

`whoami` should return a display name only. If you ever see a token in that output, stop and treat it as a leak.

## 4. Rotate or revoke

Tokens expire. When `doctor --ping-jira` or `jira whoami` returns 401/403:

1. Revoke the old token on the same Atlassian page.
2. Create a new one.
3. Replace `JIRA_API_TOKEN` in `.env` yourself.

If you accidentally pasted a token into chat, revoke it immediately and create a new one.
