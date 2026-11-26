"""Lookup against a small database built by tools/build_db.py from sample data."""

import gzip
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, override_settings

from . import dict as dictionary

DING = """# Version: test
gehen {vi} | gehend | gegangen | er/sie geht | ich/er/sie ging :: to go {went; gone} | going | gone | he/she goes | I/he/she went
Haus {n} | Häuser {pl} :: house | houses
anfangen {vt}; beginnen {vt} | anfangend :: to begin; to start | beginning
schon {adv} :: already
schön {adj} :: beautiful; nice
über {prp} :: over; above
Hausaufgabe {f} :: homework
nach Hause gehen :: to go home
fangen {vt} :: to catch
"""

KAIKKI = [
    {"word": "gehen", "pos": "verb", "forms": [
        {"form": "ging", "tags": ["preterite"]}, {"form": "gegangen", "tags": ["participle", "past"]}]},
    {"word": "Haus", "pos": "noun", "forms": [{"form": "Häusern", "tags": ["dative", "plural"]}]},
    {"word": "fangen", "pos": "verb", "forms": [{"form": "fing", "tags": ["preterite"]}]},
]


class LookupTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls.tmp.name)
        with gzip.open(tmp / "ding.gz", "wt", encoding="utf-8") as f:
            f.write(DING)
        with gzip.open(tmp / "kaikki.gz", "wt", encoding="utf-8") as f:
            f.writelines(json.dumps(e) + "\n" for e in KAIKKI)
        subprocess.run([sys.executable, "-I", str(settings.BASE_DIR / "tools/build_db.py"),
                        str(tmp / "ding.gz"), str(tmp / "kaikki.gz"), str(tmp / "dict.db")],
                       check=True, capture_output=True)
        cls.override = override_settings(DICT_DB=tmp / "dict.db")
        cls.override.enable()
        dictionary._local.__dict__.clear()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        dictionary._local.db.close()
        dictionary._local.__dict__.clear()
        cls.override.disable()
        cls.tmp.cleanup()

    def search(self, q):
        r = self.client.get("/api/search", {"q": q})
        self.assertEqual(r.status_code, 200)
        return r.json()

    def test_page_and_manifest_load(self):
        self.assertContains(self.client.get("/"), "Deutsch or English")
        self.assertEqual(self.client.get("/manifest.webmanifest").json()["name"], "Wörterbuch")

    def test_headword_first_either_language(self):
        self.assertEqual(self.search("Haus")["hits"][0]["de"], "Haus {n}")
        self.assertEqual(self.search("house")["hits"][0]["en"], "house")
        self.assertEqual(self.search("  ")["hits"], [])

    def test_completions_follow(self):
        self.assertIn("Hausaufgabe {f}", [h["de"] for h in self.search("Hau")["hits"]])

    def test_inflected_form_names_its_lemma(self):
        found = self.search("Häusern")
        self.assertEqual(found["hints"], [{"lemma": "Haus", "kind": "plural"}])
        self.assertEqual(found["hits"][0]["de"], "Haus {n}")
        found = self.search("ging")
        self.assertEqual(found["hints"], [{"lemma": "gehen", "kind": "past tense"}])
        self.assertIn("gehen {vi}", [h["de"] for h in found["hits"]])

    def test_typed_umlaut_wins_among_equals(self):
        self.assertEqual(self.search("schön")["hits"][0]["de"], "schön {adj}")
        self.assertEqual(self.search("schon")["hits"][0]["de"], "schon {adv}")

    def test_ue_is_read_as_umlaut(self):
        self.assertEqual(self.search("ueber")["hits"][0]["de"], "über {prp}")

    def test_phrase_and_separable_verb(self):
        self.assertEqual(self.search("nach Hause")["hits"][0]["de"], "nach Hause gehen")
        found = self.search("fing an")
        self.assertEqual(found["hints"], [{"lemma": "anfangen", "kind": "past tense"}])
        self.assertEqual(found["hits"][0]["de"], "anfangen {vt}; beginnen {vt}")

    def test_filler_words_are_ignored(self):
        self.assertEqual(self.search("to begin")["hits"][0]["de"], "anfangen {vt}; beginnen {vt}")

    def test_line_and_about(self):
        hit = self.search("Häuser")["hits"][0]
        pairs = self.client.get("/api/line", {"id": hit["line"]}).json()["pairs"]
        self.assertEqual(pairs, [["Haus {n}", "house"], ["Häuser {pl}", "houses"]])
        self.assertEqual(self.client.get("/api/line", {"id": "x"}).status_code, 400)
        self.assertEqual(self.client.get("/api/line", {"id": 99999}).json(), {"pairs": []})
        self.assertEqual(self.client.get("/api/about").json(), {"ding_version": "test", "lines": "9", "forms": "4"})
