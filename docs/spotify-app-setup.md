# Spotify App Setup Guide

This guide walks through creating and configuring a Spotify Developer application so
that Spotify Curator can authenticate users via OAuth 2.0.

---

## 1. Create a Spotify Developer App

1. Go to <https://developer.spotify.com/dashboard> and log in with your Spotify account.
2. Click **Create app**.
3. Fill in the form:
   - **App name** — any name, e.g. _Spotify Curator_.
   - **App description** — a short description.
   - **Website** — optional; leave blank or use your domain.
   - **Redirect URI** — add the URI(s) described in [section 3](#3-redirect-uris) below.
   - **Which API/SDKs are you planning to use?** — check **Web API**.
4. Accept the Terms of Service and click **Save**.

After saving you land on the app overview page. Keep this page open — you need the
**Client ID** and **Client secret** in the next step.

---

## 2. Copy Credentials into `.env`

Open `backend/.env` (copy from `backend/.env.example` if it does not exist yet) and
set these values:

```env
SPOTIFY_CLIENT_ID=<your Client ID>
SPOTIFY_CLIENT_SECRET=<your Client secret>
```

The client secret is revealed by clicking **View client secret** on the app overview
page. Treat it like a password — never commit it to version control.

---

## 3. Redirect URIs

Spotify validates the `redirect_uri` parameter on every authorization request against
the allow-list you configure. The URI must match **exactly** (scheme, host, port, path,
and trailing slash all matter).

Add each URI you need in **Settings → Redirect URIs** on the app overview page and
click **Save**.

### Development (local, self-signed TLS)

The backend runs HTTPS on `127.0.0.1:8000` (required by Spotify's redirect policy).
Add **both** of these URIs so either host alias works:

```text
https://localhost:8000/auth/callback
https://127.0.0.1:8000/auth/callback
```

Set the matching value in `backend/.env`:

```env
SPOTIFY_REDIRECT_URI=https://localhost:8000/auth/callback
```

> **TLS certificates** — Spotify requires HTTPS even for local development.
> Generate a self-signed certificate with:
>
> ```bash
> mkdir -p backend/certs
> openssl req -x509 -newkey rsa:2048 -nodes \
>   -keyout backend/certs/key.pem \
>   -out  backend/certs/cert.pem \
>   -days 825 -subj "/CN=localhost" \
>   -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
> ```
>
> If `mkcert` is available (macOS/Linux) you can also run
> `./backend/scripts/dev-certs.sh`, which produces a browser-trusted cert.
> The Vite dev server proxies to the backend with `secure: false`, so an
> untrusted self-signed cert works fine during development.

### Production (real domain via Caddy)

When deploying behind a [Caddy](https://caddyserver.com/) reverse proxy add the
public-facing URI:

```text
https://your-domain.com/auth/callback
```

Set the matching value in `backend/.env` on your server:

```env
SPOTIFY_REDIRECT_URI=https://your-domain.com/auth/callback
FRONTEND_URL=https://your-domain.com
```

A minimal Caddyfile that handles TLS automatically and proxies to the backend:

```caddyfile
your-domain.com {
    reverse_proxy /auth/* localhost:8000
    reverse_proxy /playlists/* localhost:8000
    reverse_proxy /cleanup/* localhost:8000
    reverse_proxy /curate/* localhost:8000
    reverse_proxy /discover/* localhost:8000
    reverse_proxy /* localhost:5173
}
```

Caddy provisions a Let's Encrypt certificate automatically — no manual cert management
required.

---

## 4. OAuth Scopes

Spotify Curator requests the following scopes. They are defined in
`backend/app/config.py` (`spotify_scopes`) and cannot be reduced without disabling
features.

| Scope | Why it is needed |
| --- | --- |
| `user-read-recently-played` | Fetches the last 50 played tracks to seed the taste profile and improve discovery recommendations. |
| `user-top-read` | Reads long-term and medium-term top tracks and artists for the taste profile. |
| `user-library-read` | Reads saved (liked) tracks and albums; used in taste scoring and cleanup analysis. |
| `playlist-read-private` | Lists all playlists, including private ones, in the playlist browser and cleanup tool. |
| `playlist-modify-private` | Creates and updates private playlists for Curate and Discover results, and applies cleanup actions to private playlists. |
| `playlist-modify-public` | Creates and updates public playlists (same features as above for public playlists). |
| `user-read-email` | Reads the account email address; displayed on the Account page and used to identify the connected user. |
| `user-read-private` | Reads the subscription tier and country; required to determine feature availability (e.g. some Spotify API endpoints are unavailable on free-tier accounts). |

---

## 5. Development Mode and the 25-User Cap

New Spotify Developer apps start in **Development mode**. In this mode:

- Only Spotify accounts explicitly added to the app's **User Management** allow-list
  can authenticate.
- The allow-list is capped at **25 users**.

For a self-hosted personal instance this is not a limitation — add your own account to
the list and you are done.

To add a user:

1. Open the app's **User Management** page in the Spotify Developer Dashboard.
2. Click **Add new user** and enter the user's Spotify display name and email address.
3. Click **Save**.

> The user must have an active Spotify account. The email address must match the
> account's primary email, not an alias.

---

## 6. Quota Extension (Extended Quota Mode)

If you need more than 25 users, Spotify requires a **quota extension** request.
This involves a manual review by Spotify and typically requires demonstrating a
production deployment with a real domain.

For most self-hosted use cases the 25-user cap is sufficient. Do not apply for
quota extension unless you genuinely need it — Spotify rejects applications that
do not meet their review criteria.

More information: <https://developer.spotify.com/documentation/web-api/concepts/quota-modes>

---

## 7. Troubleshooting

### `INVALID_CLIENT: Invalid redirect URI`

The `redirect_uri` in the authorization request does not match any URI registered
in the Spotify Developer Dashboard.

**Fix:** Verify that `SPOTIFY_REDIRECT_URI` in `backend/.env` is listed **verbatim**
in the dashboard under **Settings → Redirect URIs** and that you clicked **Save**
after adding it.

Common mismatches:

- `http://` vs `https://`
- `localhost` vs `127.0.0.1`
- missing or extra trailing slash
- wrong port (e.g. `8000` vs `8080`)

### `User not registered in the Developer Dashboard`

The Spotify account trying to log in is not in the app's user allow-list (Development
mode only).

**Fix:** Add the account's email address in **User Management** in the Spotify
Developer Dashboard, then try logging in again.

### `401 Unauthorized` after a successful login

The `SPOTIFY_CLIENT_ID` or `SPOTIFY_CLIENT_SECRET` in `backend/.env` does not match
the credentials in the Spotify Developer Dashboard.

**Fix:** Copy the Client ID and reveal the Client secret again from the dashboard to
confirm you have the correct values.
