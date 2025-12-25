# Multi-Athlete Authentication Plan

## Problem Statement

Strava's API requires OAuth2 authentication, meaning each user must explicitly authorize the application to access their data. Currently, mykrok supports only a single authenticated athlete.

To back up activities from multiple athletes (friends, family, training partners), we need a solution that:
1. Allows multiple users to authenticate with the same Strava API application
2. Stores tokens securely for each authenticated athlete
3. Makes the authentication process turnkey (minimal friction for friends)
4. Works with the existing data layout (`athl={username}/`)

## Strava API Constraints

- **Per-user OAuth**: Each user must complete OAuth flow individually
- **Rate limits**: 200 requests/15min, 2000/day per application (shared across all users)
- **Token storage**: Access tokens expire, refresh tokens are long-lived
- **Scope**: We need `activity:read_all` for full activity access

## Solution Options

### Option A: Local Multi-Token Storage (Recommended for Start)

Store multiple OAuth tokens locally, one per athlete.

**Token storage structure**:
```
.mykrok/
├── config.toml          # Shared app credentials
└── tokens/
    ├── alice.json       # Alice's OAuth tokens
    ├── bob.json         # Bob's OAuth tokens
    └── carol.json       # Carol's OAuth tokens
```

**CLI flow**:
```bash
# Initial setup (shared credentials)
mykrok auth --client-id XXXX --client-secret YYYY

# Alice authenticates
mykrok auth --athlete alice
# Opens browser, Alice logs in, token saved to tokens/alice.json

# Bob authenticates (on same machine or share config)
mykrok auth --athlete bob
# Opens browser, Bob logs in, token saved to tokens/bob.json

# Sync all athletes
mykrok sync --all-athletes

# Sync specific athlete
mykrok sync --athlete alice
```

**Pros**:
- Simple implementation
- Works offline after initial auth
- No server infrastructure needed

**Cons**:
- Friends must have physical access to the machine OR
- You must handle token file transfer securely

---

### Option B: Web-Based OAuth Callback Service

Deploy a simple web service that handles OAuth callbacks and returns tokens.

**Architecture**:
```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│  Friend's       │      │  OAuth Callback │      │  Strava API     │
│  Browser        │─────►│  Service        │◄────►│                 │
└─────────────────┘      └────────┬────────┘      └─────────────────┘
                                  │
                                  ▼
                         Token displayed to friend
                         (copy/paste to CLI or QR code)
```

**Implementation options**:

1. **GitHub Pages + Serverless Function**:
   - Static page with OAuth redirect
   - Cloudflare Worker / Vercel Function for token exchange
   - Friend clicks link, authorizes, gets token to paste

2. **Self-Hosted Flask App**:
   - Simple Flask app with OAuth flow
   - Deploy on any VPS or home server
   - Friend visits URL, authorizes, you get the token

**Example GitHub Actions Workflow** (store tokens as secrets):
```yaml
name: Add Friend Token
on:
  workflow_dispatch:
    inputs:
      athlete_name:
        description: 'Friend username'
        required: true
      refresh_token:
        description: 'OAuth refresh token'
        required: true

jobs:
  add-token:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Store token
        run: |
          echo '${{ secrets.STRAVA_TOKENS }}' | jq \
            '. + {"${{ inputs.athlete_name }}": "${{ inputs.refresh_token }}"}' \
            > /tmp/tokens.json
          # Use gh secret set to update
```

**Pros**:
- Friends can authenticate remotely
- Turnkey experience once deployed
- Can be fully automated with CI

**Cons**:
- Requires hosting (even if minimal)
- Token transfer adds security considerations
- More complex setup

---

### Option C: Shared OAuth App with Manual Token Exchange

Share your Strava API app credentials with friends, who run `mykrok auth` locally and send you the token file.

**Flow**:
1. You share `client_id` and `client_secret` with friend (securely)
2. Friend runs: `mykrok auth --export-token friend_token.json`
3. Friend sends you `friend_token.json` (encrypted email, Signal, etc.)
4. You import: `mykrok import-token friend_token.json --athlete friend`

**Pros**:
- No infrastructure needed
- Friends control their own auth process
- Works with existing CLI

**Cons**:
- Requires manual coordination
- Security depends on token transfer method
- Not truly "turnkey"

---

## Recommended Implementation Path

### Phase 1: Local Multi-Token (MVP)

1. **Extend token storage** to support multiple athletes:
   ```python
   # config.py changes
   def get_token_path(athlete: str | None = None) -> Path:
       if athlete:
           return config_dir / "tokens" / f"{athlete}.json"
       return config_dir / "token.json"  # default/legacy
   ```

2. **Update `auth` command**:
   ```bash
   mykrok auth [--athlete NAME]
   ```

3. **Update `sync` command**:
   ```bash
   mykrok sync [--athlete NAME | --all-athletes]
   ```

4. **Rate limit awareness**: Track API usage across all athletes to avoid hitting limits.

### Phase 2: Token Import/Export

1. **Add `auth --export`** to create shareable token file
2. **Add `import-token` command** to import friend's token
3. **Document secure sharing methods** (GPG, Signal, etc.)

### Phase 3: Web OAuth Service (Optional)

1. **Create minimal OAuth callback service**:
   - Vercel/Cloudflare Worker (free tier)
   - Returns refresh token to user (display or QR code)

2. **Add `auth --remote`** mode:
   - Generates unique auth URL
   - Polls for token completion or uses webhook

3. **GitHub Actions integration**:
   - Workflow to add tokens as repository secrets
   - Scheduled sync using stored tokens

---

## Security Considerations

1. **Token storage**:
   - Tokens should be file-permission protected (600)
   - Consider optional encryption with user passphrase

2. **Token transfer**:
   - Never send tokens via unencrypted email
   - Use encrypted messaging or in-person transfer

3. **Shared credentials**:
   - `client_secret` should only be shared with trusted friends
   - Consider separate Strava API apps for untrusted users

4. **CI/CD secrets**:
   - Use GitHub encrypted secrets for token storage
   - Limit workflow permissions appropriately

---

## Data Model Changes

### athletes.tsv Extension

Add columns for multi-athlete management:
```
username  id        auth_status  last_sync           token_expires
alice     12345     active       2025-12-22T10:00:00 2025-12-23T10:00:00
bob       67890     active       2025-12-22T09:30:00 2025-12-24T08:00:00
carol     11111     expired      2025-12-20T15:00:00 2025-12-21T15:00:00
```

### Config Changes

```toml
[strava]
client_id = "12345"
client_secret = "secret"

[athletes]
# Optional: specify which athletes to sync by default
default = ["alice", "bob"]
# Or sync all authenticated athletes
sync_all = true
```

---

## Tasks

- [ ] T088 [US8] Implement multi-token storage in config.py
- [ ] T089 [US8] Add `--athlete` option to `auth` command
- [ ] T090 [US8] Add `--athlete` and `--all-athletes` to `sync` command
- [ ] T091 [US8] Update rate limiter to track cross-athlete usage
- [ ] T092 [US8] Add `auth --export` for token export
- [ ] T093 [US8] Add `import-token` command
- [ ] T094 [US8] Document multi-athlete setup in quickstart.md
- [ ] T095 [US8] (Optional) Create web OAuth callback service
- [ ] T096 [US8] (Optional) Add GitHub Actions workflow for token management

---

## Open Questions

1. **Token encryption**: Should we encrypt tokens at rest? If so, what key management?

2. **Rate limit strategy**: With multiple athletes, how do we fairly distribute API calls?
   - Round-robin per athlete?
   - Priority for recently active athletes?
   - Backoff when approaching limits?

3. **Strava app sharing**: Is it acceptable under Strava ToS to share app credentials with friends for personal use?

4. **Conflict resolution**: What if two athletes have the same session datetime (group activity)?
   - Already handled by `related_sessions` field
   - Consider adding `same_activity_id` detection

---

## References

- [Strava OAuth Documentation](https://developers.strava.com/docs/authentication/)
- [Strava API Rate Limits](https://developers.strava.com/docs/rate-limits/)
- [GitHub Actions Secrets](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
