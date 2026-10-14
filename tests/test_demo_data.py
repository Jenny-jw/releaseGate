import re
from datetime import date
from pathlib import Path

import pytest
import yaml

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
FICTION_MARKER = "演示用虛構資料"
ISRC_PATTERN = re.compile(r"^[A-Z]{2}[A-Z0-9]{3}\d{7}$")
CLAUSE_HEADING = re.compile(r"^#{2,3} (§\d+(?:\.\d+)?) \S")
REQUIRED_TRACK_FIELDS = {"title", "artist", "album", "isrc", "release_date", "is_public"}

DATA_FILES = sorted(path for path in DATA_DIR.rglob("*") if path.is_file())
LICENSE_FILES = sorted((DATA_DIR / "licenses").glob("*.md"))


def load_yaml(relative_path: str) -> dict:
    return yaml.safe_load((DATA_DIR / relative_path).read_text(encoding="utf-8"))


def load_tracks() -> list[dict]:
    return load_yaml("catalog/releases.yaml")["tracks"]


@pytest.mark.parametrize("path", DATA_FILES, ids=lambda p: str(p.relative_to(DATA_DIR)))
def test_every_data_file_is_marked_fictional(path):
    first_line = path.read_text(encoding="utf-8").splitlines()[0]
    assert FICTION_MARKER in first_line


def test_tracks_have_required_fields_and_unique_valid_isrc():
    tracks = load_tracks()

    for track in tracks:
        assert REQUIRED_TRACK_FIELDS <= track.keys(), track
        assert ISRC_PATTERN.match(track["isrc"]), track["isrc"]

    isrcs = [track["isrc"] for track in tracks]
    assert len(isrcs) == len(set(isrcs))


def test_public_catalog_has_3_to_5_tracks():
    public = [track for track in load_tracks() if track["is_public"]]
    assert 3 <= len(public) <= 5


def test_unreleased_album_is_four_pomme_tracks_after_today():
    unreleased = [track for track in load_tracks() if not track["is_public"]]

    assert len(unreleased) == 4
    assert {track["album"] for track in unreleased} == {"Entre deux marées"}
    assert {track["artist"] for track in unreleased} == {"Pomme"}
    for track in unreleased:
        assert track["release_date"] > date.today(), (
            f"{track['title']} 的發行日 {track['release_date']} 已過，請更新 releases.yaml"
        )


def test_lyrics_belong_to_unreleased_tracks_and_have_8_to_12_lines():
    tracks_with_lyrics = [track for track in load_tracks() if "lyrics" in track]
    assert tracks_with_lyrics

    for track in tracks_with_lyrics:
        assert not track["is_public"], track["title"]
        text = (DATA_DIR / "catalog" / track["lyrics"]).read_text(encoding="utf-8")
        lines = [line for line in text.splitlines() if line.strip() and not line.startswith("#")]
        assert 8 <= len(lines) <= 12, (track["title"], len(lines))


def test_every_lyrics_file_is_listed_in_catalog():
    listed = {track["lyrics"] for track in load_tracks() if "lyrics" in track}
    on_disk = {f"lyrics/{path.name}" for path in (DATA_DIR / "catalog" / "lyrics").iterdir()}
    assert on_disk == listed


def test_license_files_match_roadmap():
    assert {path.name for path in LICENSE_FILES} == {
        "sync-license-tidal.md",
        "streaming-promo.md",
        "catalog-general-terms.md",
    }


@pytest.mark.parametrize("path", LICENSE_FILES, ids=lambda p: p.name)
def test_every_clause_heading_has_a_unique_section_number(path):
    headings = [
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith(("## ", "### "))
    ]
    numbers = []
    for heading in headings:
        match = CLAUSE_HEADING.match(heading)
        assert match, f"條款標題缺少條號：{heading}"
        numbers.append(match.group(1))

    assert numbers
    assert len(numbers) == len(set(numbers))


def test_general_terms_has_sections_cited_by_other_licenses():
    general_terms = (DATA_DIR / "licenses" / "catalog-general-terms.md").read_text(encoding="utf-8")
    citation = re.compile(r"《一般授權條款》(§\d+(?:\.\d+)?)")
    cited = set()
    for path in LICENSE_FILES:
        cited |= set(citation.findall(path.read_text(encoding="utf-8")))

    assert cited
    for section in cited:
        assert re.search(rf"^#{{2,3}} {re.escape(section)} ", general_terms, re.MULTILINE), section


def test_customer_assets_reference_known_customers():
    data = load_yaml("customers/media_assets.yaml")
    codes = {customer["code"] for customer in data["customers"]}

    for asset in data["assets"]:
        assert asset["customer"] in codes
        assert asset["customer"] in asset["storage_url"]
        assert asset["customer"] in asset["playback_url"]
