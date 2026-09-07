from pathlib import Path

import pytest
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {".git", ".venv", "venv", "env", "ENV", "node_modules", "__pycache__"}
EXPECTED_NAV_LABELS = [
    "Home",
    "Content",
    "Community",
    "Leadership",
    "Developer Relations",
    "AI Enablement",
    "Music",
]
EXPECTED_SAMPLE_CARD_TITLES = [
    "Blogs",
    "Community Content",
    "Video Content",
    "Tech Docs",
    "Public GitHub",
]
REMOVED_GITHUB_REPO_LINKS = [
    "https://github.com/paulzim/pedalboard_extractor",
    "https://github.com/paulzim/music_scout",
    "https://github.com/paulzim/nttv_chatbot_ext",
]
MUSIC_SCOUT_SENTENCE = (
    "I also put together a short demo of the Music Scout AI Agent to show how "
    "memory makes an AI agent more useful from one run to the next."
)


def html_files() -> list[Path]:
    files = []
    for path in ROOT.glob("*.html"):
        if not any(part in EXCLUDED_DIRS for part in path.parts):
            files.append(path)
    return sorted(files)


def soup_for(path: Path) -> BeautifulSoup:
    return BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")


def stylesheet_text(path: Path) -> str:
    soup = soup_for(path)
    return "\n".join(style.get_text() for style in soup.find_all("style"))


def is_external_href(href: str) -> bool:
    return href.startswith(("http://", "https://"))


def find_section_by_heading(soup: BeautifulSoup, heading_text: str):
    heading = soup.find(lambda tag: tag.name in {"h1", "h2", "h3"} and tag.get_text(strip=True) == heading_text)
    assert heading is not None, f"Expected heading '{heading_text}' to exist"
    return heading.find_parent(class_="section") or heading.parent


def test_discovers_top_level_html_files():
    names = {path.name for path in html_files()}
    assert names == {
        "index.html",
        "content.html",
        "community.html",
        "leadership.html",
        "developer-relations.html",
        "ai.html",
        "music.html",
    }


@pytest.mark.parametrize("path", html_files(), ids=lambda path: path.name)
def test_navbar_labels_are_consistent(path: Path):
    soup = soup_for(path)
    navbar = soup.select_one(".navbar")
    assert navbar is not None, f"{path.name} should have a navbar"

    links = navbar.find_all("a", recursive=False)
    labels = [link.get_text(strip=True) for link in links]
    assert labels == EXPECTED_NAV_LABELS, f"{path.name} has inconsistent navbar labels"

    ai_links = [link for link in links if link.get("href") == "ai.html"]
    assert len(ai_links) == 1, f"{path.name} should have exactly one ai.html navbar link"
    assert ai_links[0].get_text(strip=True) == "AI Enablement"
    assert "AI Work" not in labels, f"{path.name} navbar should not use 'AI Work'"


@pytest.mark.parametrize("path", html_files(), ids=lambda path: path.name)
def test_internal_navbar_links_point_to_existing_pages(path: Path):
    soup = soup_for(path)
    navbar = soup.select_one(".navbar")
    existing_pages = {html_path.name for html_path in html_files()}

    for link in navbar.find_all("a", href=True):
        href = link["href"]
        if href.endswith(".html") and not is_external_href(href):
            assert href in existing_pages, f"{path.name} navbar links to missing page: {href}"


@pytest.mark.parametrize("path", html_files(), ids=lambda path: path.name)
def test_external_blank_links_include_noopener_noreferrer(path: Path):
    soup = soup_for(path)
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if is_external_href(href) and link.get("target") == "_blank":
            rel = set(link.get("rel") or [])
            assert {"noopener", "noreferrer"}.issubset(rel), (
                f"{path.name} external target=_blank link must include "
                f'rel="noopener noreferrer": {href}'
            )


def test_index_content_samples_cards_are_structured():
    path = ROOT / "index.html"
    soup = soup_for(path)
    section = find_section_by_heading(soup, "Content Samples")
    sample_grid = section.select_one(".sample-grid")
    assert sample_grid is not None, "index.html Content Samples should include .sample-grid"

    cards = sample_grid.select(".sample-card")
    titles = [card.find("h3").get_text(strip=True) for card in cards if card.find("h3")]
    assert titles == EXPECTED_SAMPLE_CARD_TITLES

    for card in cards:
        title = card.find("h3").get_text(strip=True)
        assert len(card.find_all("h3", recursive=False)) == 1, f"{title} should have one h3"
        assert len(card.find_all("p", recursive=False)) == 1, f"{title} should have one p"
        assert card.find("a", recursive=False) is not None, f"{title} should have at least one direct link"

    public_github = next(card for card in cards if card.find("h3").get_text(strip=True) == "Public GitHub")
    public_links = [link["href"] for link in public_github.find_all("a", href=True)]
    assert public_links == ["https://github.com/paulzim"]

    html = path.read_text(encoding="utf-8")
    for removed_link in REMOVED_GITHUB_REPO_LINKS:
        assert removed_link not in html, f"index.html should not include old repo link: {removed_link}"


def test_ai_page_project_links_and_video_embed():
    path = ROOT / "ai.html"
    soup = soup_for(path)
    html = path.read_text(encoding="utf-8")

    assert soup.find("h2", string="Post-Cisco AI Enablement & Consulting") is not None
    for href in REMOVED_GITHUB_REPO_LINKS:
        assert soup.find("a", href=href) is not None, f"ai.html should link to {href}"

    assert MUSIC_SCOUT_SENTENCE in soup.get_text(" ", strip=True)

    video_demo = soup.select_one(".video-demo")
    assert video_demo is not None, "Music Scout video should be wrapped in .video-demo"
    video_wrapper = video_demo.select_one(".video-wrapper")
    assert video_wrapper is not None, "Music Scout video iframe should be wrapped in .video-wrapper"

    iframe = video_wrapper.find("iframe")
    assert iframe is not None, "Music Scout video wrapper should contain an iframe"
    assert iframe.get("src") == "https://www.youtube-nocookie.com/embed/ALyKcje6JNI"
    assert iframe.get("title", "").strip(), "Music Scout iframe should have a non-empty title"
    assert "https://www.youtube.com/watch?v=ALyKcje6JNI" not in html


def test_modern_layout_guardrails():
    index_css = stylesheet_text(ROOT / "index.html")
    assert ".sample-grid" in index_css
    assert "display: grid" in index_css
    assert "repeat(auto-fit" in index_css or "repeat(auto-fill" in index_css
    assert "minmax" in index_css
    assert ".sample-card" in index_css

    ai_css = stylesheet_text(ROOT / "ai.html")
    assert ".video-wrapper" in ai_css
    assert "aspect-ratio" in ai_css or "padding-bottom" in ai_css


@pytest.mark.parametrize("path", html_files(), ids=lambda path: path.name)
def test_no_loose_list_items_in_cards(path: Path):
    soup = soup_for(path)
    for card in soup.select(".card, .sample-card"):
        for child in card.find_all("li", recursive=False):
            assert child.parent.name in {"ul", "ol"}, (
                f"{path.name} has a loose li directly inside a card: {child.get_text(strip=True)}"
            )


@pytest.mark.parametrize("path", html_files(), ids=lambda path: path.name)
def test_images_have_alt_text(path: Path):
    soup = soup_for(path)
    for image in soup.find_all("img"):
        assert image.get("alt", "").strip(), f"{path.name} has an image without alt text: {image}"


@pytest.mark.parametrize("path", html_files(), ids=lambda path: path.name)
def test_iframes_have_title_text(path: Path):
    soup = soup_for(path)
    for iframe in soup.find_all("iframe"):
        assert iframe.get("title", "").strip(), f"{path.name} has an iframe without title: {iframe}"


@pytest.mark.parametrize("path", html_files(), ids=lambda path: path.name)
def test_youtube_embeds_include_referrer_policy(path: Path):
    soup = soup_for(path)
    for iframe in soup.find_all("iframe", src=True):
        src = iframe["src"]
        if "youtube.com/embed/" in src or "youtube-nocookie.com/embed/" in src:
            assert iframe.get("referrerpolicy") == "strict-origin-when-cross-origin", (
                f"{path.name} YouTube iframe should include "
                f'referrerpolicy="strict-origin-when-cross-origin": {src}'
            )
