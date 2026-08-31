# Create an Atlassian API token

The goat talks to Jira Cloud with **email + API token** basic auth. Copilot never sees the token.

Keep the site URL and email in `.env`. Store the API token in the **OS keychain** (macOS Keychain or Windows Credential Manager). The CLI reads it in-process when it talks to Jira.

## 1. Create the token

1. Sign in to [id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens).
2. Prefer **Create API token with scopes**. Classic tokens work, but scoped tokens are tighter.
3. Name it something obvious, for example `goat`.
4. Set an expiry (Atlassian caps this at one year).
5. If you are creating a scoped token, choose **Jira** and the least privilege you need:
   - **Planning profile (default):** read issue, search, and comment scopes. Enough for `prepare`, `jira get/search/mine`, and `/jira-ticket`.
   - **Write profile (later):** add comment / transition scopes only after `harness jira comment` exists. Do not mint write scopes "just in case."
6. Click **Create**, then **Copy**. You cannot view the value again.

If your company uses SSO, you can still create a token for your own Atlassian account. Service-account tokens are an admin concern; this goat is meant for personal tokens.

## 2. Put the site URL and email in `.env`

From the goat repo:

```bash
cp .env.example .env
```

Set only the non-secret values:

```bash
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_EMAIL=you@company.com
```

Leave `JIRA_API_TOKEN` empty. `JIRA_EMAIL` must be the Atlassian account email that owns the token, not a Slack handle.

These three names are rows in `catalog/env.yaml`. Add other env vars and secrets there (not on generated `.code-workspace` files). `uv run goat env list` shows what is missing without printing values.

## 3. Store the token in the OS keychain

Preferred: run this in **your own terminal** (not Copilot Chat). Input is hidden.

```bash
uv run goat jira login
```

`init --interactive` does the same thing on first run. If the token is already in `.env`, move it:

```bash
uv run goat jira login --from-env
```

That writes the token to the OS store, then blanks `JIRA_API_TOKEN` in `.env`.

| OS | Store | How the CLI finds it |
| --- | --- | --- |
| macOS | Keychain | service `goat`, account `jira-api-token` |
| Windows | Credential Manager | generic credential `goat` / `jira-api-token` |
| Linux desktop | Secret Service (GNOME Keyring / KWallet) | same service and account |
| Headless / CI | `.env` fallback | `JIRA_API_TOKEN=...` |

### macOS Keychain Access (manual)

1. Open **Keychain Access**.
2. File > New Password Item.
3. Keychain Item Name: `goat`
4. Account Name: `jira-api-token`
5. Password: the Atlassian API token (not your account password).
6. Click **Add**.

Or in Terminal:

```bash
security add-generic-password -a jira-api-token -s goat -w
```

### Windows Credential Manager (manual)

1. Open **Credential Manager** (Control Panel > User Accounts > Credential Manager).
2. Select **Windows Credentials**.
3. Click **Add a generic credential**.
4. Internet or network address: `goat`
5. User name: `jira-api-token`
6. Password: the Atlassian API token.
7. Click **OK**.

Do **not**:

- Paste the token into Copilot Chat
- Export it in your shell profile
- Commit `.env` with a filled `JIRA_API_TOKEN`
- Check it into screenshots or PR descriptions

`.env` remains a fallback when no OS store is available. The CLI still prefers an environment variable if one is set, so blank `JIRA_API_TOKEN` after a successful `jira login`.

## 4. Confirm it works

```bash
uv run goat init
uv run goat doctor --ping-jira
uv run goat jira whoami
```

`whoami` should return a display name only. If you ever see a token in that output, stop and treat it as a leak.

## 5. Rotate or revoke

Tokens expire. When `doctor --ping-jira` or `jira whoami` returns 401/403:

1. Revoke the old token on the same Atlassian page.
2. Create a new one.
3. Run `uv run goat jira login` again (or `jira login --from-env` if you temporarily put the new value in `.env`).

To forget the stored token:

```bash
uv run goat jira logout
```

If you accidentally pasted a token into chat, revoke it immediately and create a new one.
