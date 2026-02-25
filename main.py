from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, HTTPException
import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel
from urllib.parse import quote


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.client = httpx.AsyncClient(
        follow_redirects=True,
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        timeout=30.0,
    )
    yield
    await app.state.client.aclose()


app = FastAPI(
    title="Lex.uz Search Proxy",
    description="Proxy API for searching documents on lex.uz",
    version="1.0.0",
    lifespan=lifespan,
)


class Document(BaseModel):
    number: int | None
    title: str
    url: str
    badge: str | None
    status: str


class SearchResponse(BaseModel):
    documents: list[Document]
    current_page: int
    total_pages: int


def extract_asp_fields(soup: BeautifulSoup) -> dict:
    """Extract ASP.NET hidden form fields needed for postback."""
    fields = {}
    for field_name in ["__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"]:
        field = soup.find("input", {"name": field_name})
        if field:
            fields[field_name] = field.get("value", "")
    return fields


def get_total_pages(soup: BeautifulSoup) -> int:
    """Extract total number of pages from pagination."""
    pagination_table = soup.find("table", {"id": "ucFoundActsControl_rptPaging"})
    if not pagination_table:
        return 1

    page_links = pagination_table.find_all("a", class_="btn_pgn_extend")
    if not page_links:
        return 1

    # Get the highest page number from visible pagination
    max_page = 1
    for link in page_links:
        try:
            page_num = int(link.get_text(strip=True))
            max_page = max(max_page, page_num)
        except ValueError:
            pass

    return max_page


def parse_documents(soup: BeautifulSoup) -> list[Document]:
    """Parse document rows from the HTML response."""
    documents = []

    table_container = soup.find("div", class_="refind__table")
    if not table_container:
        return documents

    table = table_container.find("table")
    if not table:
        return documents

    rows = table.find_all("tr", class_="dd-table__main-item")

    for row in rows:
        # Extract number
        number_span = row.find("span", class_="dd-table__main-item_number")
        number = None
        if number_span:
            try:
                number = int(number_span.get_text(strip=True))
            except ValueError:
                pass

        # Extract title and URL
        link = row.find("a", class_="lx_link")
        title = link.get_text(strip=True) if link else ""
        doc_url = link.get("href", "") if link else ""

        # Extract badge
        badge_span = row.find("span", class_="badge")
        badge = badge_span.get_text(strip=True) if badge_span else None

        # Determine status from icon class
        status = "inactive"
        icon = row.find("i", class_="fa")
        if icon:
            icon_classes = icon.get("class", [])
            if "status_code_y" in icon_classes:
                status = "active"

        documents.append(Document(
            number=number,
            title=title,
            url=doc_url,
            badge=badge,
            status=status
        ))

    return documents


@app.get("/search", response_model=SearchResponse)
async def search(
    searchtitle: str = Query(..., description="Search query for document title"),
    page: int = Query(1, ge=1, description="Page number (starting from 1)")
):
    """
    Search for documents on lex.uz by title with pagination support.

    Returns a list of documents matching the search query along with pagination info.
    """
    base_url = f"https://lex.uz/ru/search/nat?searchtitle={quote(searchtitle)}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    client: httpx.AsyncClient = app.state.client

    try:
        # First, get the initial page to obtain ASP.NET form fields
        initial_response = await client.get(base_url, headers=headers)
        initial_response.raise_for_status()

        soup = BeautifulSoup(initial_response.text, "lxml")

        # If requesting page 1, just return the initial response
        if page == 1:
            documents = parse_documents(soup)
            total_pages = get_total_pages(soup)
            return SearchResponse(
                documents=documents,
                current_page=1,
                total_pages=total_pages
            )

        # For other pages, we need to do a POST with ViewState
        asp_fields = extract_asp_fields(soup)
        del soup  # free memory before second request

        if not asp_fields.get("__VIEWSTATE"):
            raise HTTPException(status_code=500, detail="Could not extract ViewState from lex.uz")

        # Build the POST data for pagination
        # The EVENTTARGET format is: ucFoundActsControl$rptPaging$ctl{XX}$lbPaging
        # where XX is the 0-padded page index (page 2 = ctl01, page 3 = ctl02, etc.)
        page_index = str(page - 1).zfill(2)
        event_target = f"ucFoundActsControl$rptPaging$ctl{page_index}$lbPaging"

        post_data = {
            "__EVENTTARGET": event_target,
            "__EVENTARGUMENT": "",
            "__VIEWSTATE": asp_fields.get("__VIEWSTATE", ""),
            "__VIEWSTATEGENERATOR": asp_fields.get("__VIEWSTATEGENERATOR", ""),
            "__EVENTVALIDATION": asp_fields.get("__EVENTVALIDATION", ""),
        }
        del asp_fields

        # Make the POST request
        response = await client.post(
            base_url,
            data=post_data,
            headers=headers,
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")
        documents = parse_documents(soup)
        total_pages = get_total_pages(soup)

        return SearchResponse(
            documents=documents,
            current_page=page,
            total_pages=total_pages
        )

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail="Error fetching data from lex.uz")
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Connection error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=19780)
