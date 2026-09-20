# YouTube OAuth setup

The uploader reads `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET` and `YOUTUBE_REFRESH_TOKEN` from the server environment or local `.env`. They must belong to the same OAuth client. Never commit their actual values.

1. Select your project in [Google Cloud Console](https://console.cloud.google.com/) and enable **YouTube Data API v3**.
2. Configure **Google Auth Platform → Branding and Audience**. If an external app is in Testing, add the Google account managing your channel as a test user.
3. In **Clients**, create or reuse a **Web application** OAuth client for this Playground flow. Register `https://developers.google.com/oauthplayground` as the exact authorized redirect URI, without a trailing slash. Desktop clients use a different authorization flow; keep any existing desktop client if it is still in use.
4. Open [OAuth Playground](https://developers.google.com/oauthplayground/). In settings choose **Server-side**, **Google**, **Offline** and **Consent Screen**. Check **Use your own OAuth credentials** and enter that web client's ID and secret.
5. In Step 1 enter `https://www.googleapis.com/auth/youtube.upload`, click **Authorize APIs**, sign in to the intended channel's account and approve upload access.
6. In Step 2 click **Exchange authorization code for tokens**. Copy **Refresh token**, not Access token or Authorization code.
7. Save the matching three values in `.env`, restart the server and refresh the browser. Retry publishing the existing video.

Playground default credentials revoke refresh tokens after 24 hours; use your own credentials. Separately, external apps in Testing issue tokens that expire after seven days for YouTube scopes. For ongoing operation, review production publishing and applicable verification requirements, then authorize again. Production tokens can still be revoked.

If a new token works in a separate process but not in the server, check inherited terminal variables: `.env` does not overwrite existing environment values. In CMD, clear only the three variables with `set "YOUTUBE_CLIENT_ID="`, `set "YOUTUBE_CLIENT_SECRET="` and `set "YOUTUBE_REFRESH_TOKEN="`, then relaunch the server to load the file.

OAuth verification and YouTube API audits are separate. Videos from unverified API projects created after July 28, 2020 can be restricted to private visibility. Custom thumbnail permissions may also be restricted. The Studio records cover failure separately from video upload success.

References: [OAuth authorization](https://developers.google.com/youtube/v3/guides/auth/server-side-web-apps), [token expiration](https://developers.google.com/identity/protocols/oauth2#expiration), [video upload restrictions](https://developers.google.com/youtube/v3/docs/videos/insert), [thumbnail API](https://developers.google.com/youtube/v3/docs/thumbnails/set).
