from nobu.providers.contacts import emails_on_pages
from nobu.providers.fetch import FakeFetcher, html_to_page
from nobu.providers.search import FakeSearch, SearchResult


def test_html_to_page_strips_scripts_and_keeps_title() -> None:
    html = (
        "<html><head><title>Acme</title><script>x=1</script></head>"
        "<body><p>We build APIs</p></body></html>"
    )
    page = html_to_page("https://acme.dev", html)
    assert page.title == "Acme"
    assert page.text == "We build APIs"


def test_fake_fetcher_unknown_url_is_none() -> None:
    f = FakeFetcher({"https://a.dev": "<p>hi</p>"})
    assert f.fetch("https://b.dev") is None
    page = f.fetch("https://a.dev")
    assert page is not None and page.text == "hi"


def test_emails_on_pages_filters_domain_and_noreply() -> None:
    page = html_to_page(
        "https://acme.dev/careers",
        "<p>Write to careers@acme.dev or priya@acme.dev. Not noreply@acme.dev or x@gmail.com</p>",
    )
    found = {c.email: c for c in emails_on_pages([page], "www.acme.dev")}
    assert set(found) == {"careers@acme.dev", "priya@acme.dev"}
    assert found["priya@acme.dev"].source == "https://acme.dev/careers"
    assert found["careers@acme.dev"].confidence < found["priya@acme.dev"].confidence


def test_fake_search_matches_by_key() -> None:
    s = FakeSearch({"acme": [SearchResult("News", "https://n.com/acme", "raised seed")]})
    assert s.search("Acme funding")[0].url == "https://n.com/acme"
    assert s.search("other") == []
