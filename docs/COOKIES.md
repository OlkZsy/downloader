# Signing in to accounts via cookies (X, Facebook and others)

Some services only serve part of their content to signed-in users:
on X (Twitter) that is 18+ posts and private accounts, on Facebook —
group videos, on YouTube — age-restricted videos.

## Why not a login and password?

Putting a login and password into a text file would not work, for two
reasons:

1. Services (X especially) block sign-ins from programs: they demand a
   captcha, an e-mail code or two-factor authentication. The program
   simply cannot pass that.
2. Storing a password in plain text is unsafe.

The standard solution is a **cookies file**: also a plain text file,
but instead of your password it holds the "pass" your browser received
after you signed in. The program attaches it to its requests and the
service treats them as yours. Your password is never stored anywhere.

## Step by step: connecting an X account

1. **Install a cookies-export extension** in your browser:
   - Chrome / Edge / Opera: [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
   - Firefox: [cookies.txt](https://addons.mozilla.org/firefox/addon/cookies-txt/)
2. **Sign in to your account** at [x.com](https://x.com) in that
   browser.
3. While on the x.com page, **click the extension icon** in the browser
   toolbar and press **Export** (in "Get cookies.txt LOCALLY" —
   "Export As ⇩"). A file like `x.com_cookies.txt` is downloaded.
4. **Rename the file to `x.txt`** and put it into the application's
   cookies folder:
   - in MediaGrab press the **👤** button (to the right of "…") →
     **«Папка cookies»** — the folder opens by itself
     (it is `C:\Users\YOUR_NAME\.mediagrab\cookies`, on macOS/Linux —
     `~/.mediagrab/cookies`);
   - drop `x.txt` in there.
5. **Retry the download** in MediaGrab — the file is picked up
   automatically, no restart needed.

## File names for other services

The file is named after the service id:

| Service | File name |
| --- | --- |
| X (Twitter) | `x.txt` |
| Facebook | `facebook.txt` |
| YouTube | `youtube.txt` |
| YouTube Music | `youtube_music.txt` |
| TikTok | `tiktok.txt` |
| all services at once | `all.txt` |

If both `x.txt` and `all.txt` exist, `x.txt` wins for X.

## Security notes

- **A cookies file grants full access to your account.** Never send it
  to anyone, never publish it and never commit it to git.
- Cookies expire over time (or reset when you sign out in the
  browser). If account downloads stop working — just export the file
  again (steps 2–4).
- To disconnect the account, delete the file from the cookies folder.
