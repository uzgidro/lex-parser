import pytest
import httpx
import respx
from fastapi.testclient import TestClient

from main import app, SearchCache


# ---------------------------------------------------------------------------
# HTML fixture fragments (realistic lex.uz structure)
# ---------------------------------------------------------------------------

VIEWSTATE_VALUE = "dDwxNTc2OTg0MDk7Oz4="
VIEWSTATEGENERATOR_VALUE = "CA0B0334"
EVENTVALIDATION_VALUE = "/wEdAAIJAM6bBQk="

ASP_FIELDS_HTML = f"""
<html><body>
<form>
  <input type="hidden" name="__VIEWSTATE" value="{VIEWSTATE_VALUE}" />
  <input type="hidden" name="__VIEWSTATEGENERATOR" value="{VIEWSTATEGENERATOR_VALUE}" />
  <input type="hidden" name="__EVENTVALIDATION" value="{EVENTVALIDATION_VALUE}" />
</form>
</body></html>
"""

ASP_PARTIAL_HTML = f"""
<html><body>
<form>
  <input type="hidden" name="__VIEWSTATE" value="{VIEWSTATE_VALUE}" />
</form>
</body></html>
"""

ASP_NONE_HTML = "<html><body><form></form></body></html>"

PAGINATION_HTML = """
<html><body>
<table id="ucFoundActsControl_rptPaging">
  <tr>
    <td><a class="btn_pgn_extend" href="#">1</a></td>
    <td><a class="btn_pgn_extend" href="#">2</a></td>
    <td><a class="btn_pgn_extend" href="#">3</a></td>
    <td><a class="btn_pgn_extend" href="#">...</a></td>
    <td><a class="btn_pgn_extend" href="#">5</a></td>
  </tr>
</table>
</body></html>
"""

PAGINATION_SINGLE_HTML = """
<html><body>
<table id="ucFoundActsControl_rptPaging">
  <tr>
    <td><a class="btn_pgn_extend" href="#">1</a></td>
  </tr>
</table>
</body></html>
"""

NO_PAGINATION_HTML = "<html><body><div>No pages here</div></body></html>"

DOCUMENTS_HTML = """
<html><body>
<div class="refind__table">
  <table>
    <tr class="dd-table__main-item">
      <td><span class="dd-table__main-item_number">42</span></td>
      <td>
        <a class="lx_link" href="/docs/123456">O nalogovom kodekse</a>
        <span class="badge">Zakon</span>
      </td>
      <td><i class="fa status_code_y"></i></td>
    </tr>
    <tr class="dd-table__main-item">
      <td><span class="dd-table__main-item_number">7</span></td>
      <td>
        <a class="lx_link" href="/docs/654321">Ob obrazovanii</a>
      </td>
      <td><i class="fa status_code_n"></i></td>
    </tr>
  </table>
</div>
</body></html>
"""

DOCUMENT_NO_NUMBER_HTML = """
<html><body>
<div class="refind__table">
  <table>
    <tr class="dd-table__main-item">
      <td></td>
      <td>
        <a class="lx_link" href="/docs/99">Some doc</a>
        <span class="badge">Ukaz</span>
      </td>
      <td><i class="fa status_code_y"></i></td>
    </tr>
  </table>
</div>
</body></html>
"""

DOCUMENT_NO_BADGE_HTML = """
<html><body>
<div class="refind__table">
  <table>
    <tr class="dd-table__main-item">
      <td><span class="dd-table__main-item_number">1</span></td>
      <td>
        <a class="lx_link" href="/docs/11">Title only</a>
      </td>
      <td><i class="fa status_code_y"></i></td>
    </tr>
  </table>
</div>
</body></html>
"""

EMPTY_TABLE_HTML = """
<html><body>
<div class="refind__table">
  <table></table>
</div>
</body></html>
"""

NO_TABLE_CONTAINER_HTML = "<html><body><div>nothing</div></body></html>"


def _build_full_page_html(
    documents_html: str = "",
    pagination_html: str = "",
    asp_fields: bool = True,
) -> str:
    """Build a full lex.uz-style page combining fragments."""
    asp = ""
    if asp_fields:
        asp = f"""
        <input type="hidden" name="__VIEWSTATE" value="{VIEWSTATE_VALUE}" />
        <input type="hidden" name="__VIEWSTATEGENERATOR" value="{VIEWSTATEGENERATOR_VALUE}" />
        <input type="hidden" name="__EVENTVALIDATION" value="{EVENTVALIDATION_VALUE}" />
        """
    return f"<html><body><form>{asp}</form>{documents_html}{pagination_html}</body></html>"


FULL_PAGE_HTML = _build_full_page_html(
    documents_html="""
    <div class="refind__table">
      <table>
        <tr class="dd-table__main-item">
          <td><span class="dd-table__main-item_number">1</span></td>
          <td>
            <a class="lx_link" href="/docs/100">Test Document</a>
            <span class="badge">Zakon</span>
          </td>
          <td><i class="fa status_code_y"></i></td>
        </tr>
      </table>
    </div>
    """,
    pagination_html="""
    <table id="ucFoundActsControl_rptPaging">
      <tr>
        <td><a class="btn_pgn_extend" href="#">1</a></td>
        <td><a class="btn_pgn_extend" href="#">2</a></td>
        <td><a class="btn_pgn_extend" href="#">3</a></td>
      </tr>
    </table>
    """,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def cache():
    """Fresh SearchCache with short TTL for tests."""
    return SearchCache(ttl=60, max_size=4)


@pytest.fixture()
def client():
    """FastAPI TestClient with mocked upstream HTTP via respx."""
    with respx.mock(assert_all_mocked=False) as respx_mock:
        with TestClient(app, raise_server_exceptions=False) as tc:
            tc.respx_mock = respx_mock  # type: ignore[attr-defined]
            yield tc
