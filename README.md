# dict

German–English dictionary at https://dict.darmok.link, behind the devauth login.
The web version of the Android app Wörterbuch (`jamescrg/dict-android`): same
database, same lookup, same colours. Django 5.2 on gunicorn; a sibling of
`~/mindlog` and `~/fitlog`, laid out the same way.

- Type in either language; results appear as you type. Inflected German forms
  ("ging", "Häusern", "fing an") lead to their dictionary form: the line at the
  top names it, and clicking it looks it up.
- Clicking an entry shows the whole Ding line it belongs to, that sub-entry in
  bold. ✕ or Esc clears; ⓘ shows the sources and their licences.
- The address follows the query, so `https://dict.darmok.link/?q=Haus` opens a
  lookup directly.
- Gruvbox colours, light or dark to match the system setting.
- No admin, no login of its own and nothing stored: devauth is the only gate,
  and the dictionary is read-only.

## Layout

- `config/`: settings and URLs.
- `lookup/`: `dict.py` is the lookup (a port of `Dict.kt`), `text.py` the word
  normalisation, `views.py` the page and the JSON it calls (`/api/search?q=`,
  `/api/line?id=`, `/api/about`), `templates/lookup/index.html` the page.
- `tools/build_db.py`: builds the database; the same script as in dict-android.
  `tools/make_icons.py` draws the home-screen icons.
- `data/`: the downloads, `dict.db` and the secret key; not committed.
- Tests: `.venv/bin/python manage.py test lookup` (they build a small database
  of their own).

`lookup/dict.py` and `Dict.kt`, and `lookup/text.py`, `Text.kt` and the
normalisation in `build_db.py`, must stay in step: change them together.

## Data

`data/dict.db` (about 83 MB) is built from:

- **Ding** German–English dictionary, © Frank Richter, GPL version 2 or later.
- **Wiktionary** inflection tables by way of Kaikki.org, CC BY-SA 4.0.

To build or refresh it (each download in its own folder; about a minute):

    mkdir -p data/ding data/kaikki
    curl -L -o data/ding/de-en.txt.gz https://ftp.tu-chemnitz.de/pub/Local/urz/ding/de-en-devel/de-en.txt.gz
    curl -L -o data/kaikki/German.jsonl.gz https://kaikki.org/dictionary/German/kaikki.org-dictionary-German.jsonl.gz
    python3 -I tools/build_db.py data/ding/de-en.txt.gz data/kaikki/German.jsonl.gz data/dict.db
    systemctl --user restart dict

The restart matters: the service holds the old file open.

## Running

    uv sync
    .venv/bin/python manage.py collectstatic --noinput
    systemctl --user restart dict

- User service: `deploy/dict.service` (gunicorn on 127.0.0.1:8793), symlinked
  into `~/.config/systemd/user/`. Restart after code changes.
- nginx and certificate: `sudo deploy/setup-site.sh` installs
  `deploy/nginx-dict` and gets the certificate (DNS-01 through DigitalOcean).
- The landing page card and status dot are in `~/darmok` (`index.html`,
  `gen-status.sh`).

## Licence

The code is licensed under the GNU General Public License, version 3 (see
`LICENSE`). The dictionary data keeps its own licences, listed under Data; the
ⓘ screen shows the attribution.
