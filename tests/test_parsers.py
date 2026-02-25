from bs4 import BeautifulSoup

from main import extract_asp_fields, get_total_pages, parse_documents
from tests.conftest import (
    ASP_FIELDS_HTML,
    ASP_PARTIAL_HTML,
    ASP_NONE_HTML,
    PAGINATION_HTML,
    PAGINATION_SINGLE_HTML,
    NO_PAGINATION_HTML,
    DOCUMENTS_HTML,
    DOCUMENT_NO_NUMBER_HTML,
    DOCUMENT_NO_BADGE_HTML,
    EMPTY_TABLE_HTML,
    NO_TABLE_CONTAINER_HTML,
    VIEWSTATE_VALUE,
    VIEWSTATEGENERATOR_VALUE,
    EVENTVALIDATION_VALUE,
)


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


# ── extract_asp_fields ─────────────────────────────────────────────────────

class TestExtractAspFields:
    def test_all_fields_present(self):
        result = extract_asp_fields(_soup(ASP_FIELDS_HTML))
        assert result == {
            "__VIEWSTATE": VIEWSTATE_VALUE,
            "__VIEWSTATEGENERATOR": VIEWSTATEGENERATOR_VALUE,
            "__EVENTVALIDATION": EVENTVALIDATION_VALUE,
        }

    def test_partial_fields(self):
        result = extract_asp_fields(_soup(ASP_PARTIAL_HTML))
        assert result == {"__VIEWSTATE": VIEWSTATE_VALUE}
        assert "__VIEWSTATEGENERATOR" not in result
        assert "__EVENTVALIDATION" not in result

    def test_no_fields(self):
        result = extract_asp_fields(_soup(ASP_NONE_HTML))
        assert result == {}


# ── get_total_pages ────────────────────────────────────────────────────────

class TestGetTotalPages:
    def test_multiple_pages(self):
        # "..." is non-numeric and should be skipped; max numeric is 5
        assert get_total_pages(_soup(PAGINATION_HTML)) == 5

    def test_single_page(self):
        assert get_total_pages(_soup(PAGINATION_SINGLE_HTML)) == 1

    def test_no_pagination_table(self):
        assert get_total_pages(_soup(NO_PAGINATION_HTML)) == 1

    def test_non_numeric_links_skipped(self):
        html = """
        <table id="ucFoundActsControl_rptPaging">
          <tr>
            <td><a class="btn_pgn_extend" href="#">...</a></td>
            <td><a class="btn_pgn_extend" href="#">>></a></td>
          </tr>
        </table>
        """
        assert get_total_pages(_soup(html)) == 1


# ── parse_documents ────────────────────────────────────────────────────────

class TestParseDocuments:
    def test_multiple_rows(self):
        docs = parse_documents(_soup(DOCUMENTS_HTML))
        assert len(docs) == 2

        assert docs[0].number == 42
        assert docs[0].title == "O nalogovom kodekse"
        assert docs[0].url == "https://lex.uz/docs/123456"
        assert docs[0].badge == "Zakon"
        assert docs[0].status == "active"

        assert docs[1].number == 7
        assert docs[1].title == "Ob obrazovanii"
        assert docs[1].url == "https://lex.uz/docs/654321"
        assert docs[1].badge is None
        assert docs[1].status == "inactive"

    def test_active_status(self):
        docs = parse_documents(_soup(DOCUMENTS_HTML))
        assert docs[0].status == "active"

    def test_inactive_status(self):
        docs = parse_documents(_soup(DOCUMENTS_HTML))
        assert docs[1].status == "inactive"

    def test_relative_href_becomes_absolute(self):
        docs = parse_documents(_soup(DOCUMENTS_HTML))
        assert docs[0].url.startswith("https://lex.uz/")

    def test_missing_number(self):
        docs = parse_documents(_soup(DOCUMENT_NO_NUMBER_HTML))
        assert len(docs) == 1
        assert docs[0].number is None

    def test_missing_badge(self):
        docs = parse_documents(_soup(DOCUMENT_NO_BADGE_HTML))
        assert len(docs) == 1
        assert docs[0].badge is None

    def test_empty_table(self):
        docs = parse_documents(_soup(EMPTY_TABLE_HTML))
        assert docs == []

    def test_no_table_container(self):
        docs = parse_documents(_soup(NO_TABLE_CONTAINER_HTML))
        assert docs == []
