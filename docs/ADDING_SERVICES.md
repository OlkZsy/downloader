# How to add a new service

The plugin architecture makes a new service = **one file** in the
`mediagrab/services/` folder. On startup the application discovers all
files in that folder and adds the services to the sidebar — no
registration needed anywhere.

## Step 1. Copy the template

Take `mediagrab/services/_template.py` and save it under a new name,
e.g. `soundcloud.py`. The file name must **not** start with `_`
(such files are ignored) and must not be `base.py`.

## Step 2. Fill in the fields

```python
from .base import ServicePlugin


class SoundCloud(ServicePlugin):
    id = "soundcloud"                    # unique id, latin letters
    name = "SoundCloud"                  # name shown in the sidebar
    url_patterns = [r"soundcloud\.com/"] # regexes for the service's links
    supported_formats = ("mp3",)         # ("mp3",), ("mp4",) or both
    order = 50                           # position in the list (lower = higher)


PLUGIN = SoundCloud()
```

The `PLUGIN` variable at the end of the file is mandatory — that is
what the registry looks for.

This alone is enough: the downloading is done by yt-dlp, which supports
more than 1000 sites out of the box
([full list](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md)).
The plugin's job is to show the service in the panel, detect it from
links and, when needed, add special logic.

## Step 3 (optional). Special logic

The `ServicePlugin` base class (`base.py`) has two methods to override:

### `prepare(self, url) -> str`

Called before the download in a background thread — network requests
are fine here. Must return what should actually be downloaded: usually
the same URL, but a yt-dlp search query works too.

Example — the Spotify plugin (`spotify.py`): it resolves a Spotify link
into the track title via the public oEmbed API and returns
`"ytsearch1:<title>"`, so yt-dlp finds and downloads the track from
YouTube.

### `tweak_options(self, options, fmt) -> dict`

Lets you adjust the
[yt-dlp options](https://github.com/yt-dlp/yt-dlp#usage-and-options)
for the service's quirks:

```python
def tweak_options(self, options, fmt):
    options["http_headers"] = {"Referer": "https://example.com/"}
    return options
```

### `retry_variants(self) -> list`

Returns option dicts to try in turn while a download keeps failing with
an error that looks temporary (HTTP 403, broken fragments and the
like). The first entry is empty — the normal attempt. `youtube.py` uses
this to re-ask as a different player client, which is the standard cure
for "HTTP Error 403: Forbidden":

```python
def retry_variants(self):
    return [{}, {"extractor_args": {"youtube": {"player_client": ["tv"]}}}]
```

There is also an `error_hint` attribute — a text appended to error
messages for this service (e.g. a reminder that private content needs
cookies).

## Step 4. Verify

Restart the application (`start.bat` / `./start.sh`) — the new service
appears in the sidebar. Paste one of the service's links and check that
the "Auto" mode detects it (the "Service" column in the history).

## Mini-checklist for a pull request

- [ ] the file is named after the service, no leading `_`;
- [ ] the `id` is unique (does not clash with existing plugins);
- [ ] the `url_patterns` do not capture other services' links;
- [ ] the file ends with `PLUGIN = ClassName()`;
- [ ] the download was tested on at least one real link.
