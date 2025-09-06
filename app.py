from fastapi import FastAPI, UploadFile, File, Request, Form
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from lxml import etree
import io

app = FastAPI()
templates = Jinja2Templates(directory="templates")


# ---------------- Landing Page ----------------
@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    return templates.TemplateResponse("landing.html", {"request": request})


# ---------------- XML Node Grouper App ----------------
@app.get("/app", response_class=HTMLResponse)
async def xml_app(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "xml_preview": None, "tags": [], "keys": [], "child_tags": []}
    )


# ---------------- Meal Break Cleanup ----------------
@app.get("/meal_cleanup", response_class=HTMLResponse)
async def meal_cleanup(request: Request):
    return templates.TemplateResponse("meal_cleanup.html", {"request": request})


@app.post("/meal_cleanup", response_class=HTMLResponse)
async def meal_cleanup_upload(request: Request, file: UploadFile = File(...)):
    content = await file.read()
    xml_str = content.decode("utf-8")

    empty_tags = find_empty_tags(xml_str)

    return templates.TemplateResponse(
        "meal_cleanup.html",
        {
            "request": request,
            "xml_preview": xml_str,
            "empty_tags": empty_tags,
            "cleaned_xml": None
        }
    )


@app.post("/meal_cleanup_clean", response_class=HTMLResponse)
async def meal_cleanup_clean(
    request: Request,
    xml_content: str = Form(...),
    tags_to_remove: list[str] = Form(...)
):
    cleaned_xml = remove_empty_tags(xml_content, tags_to_remove)

    return templates.TemplateResponse(
        "meal_cleanup.html",
        {
            "request": request,
            "xml_preview": xml_content,
            "cleaned_xml": cleaned_xml,
            "empty_tags": []
        }
    )


# ---------------- Helper Functions ----------------
def find_empty_tags(xml_content: str):
    """Return a list of tags that have empty values"""
    parser = etree.XMLParser(remove_blank_text=True)
    root = etree.fromstring(xml_content.encode("utf-8"), parser=parser)
    empty_tags = set()

    for elem in root.iter():
        if (elem.text is None or not elem.text.strip()) and len(elem) == 0:
            empty_tags.add(elem.tag)

    return list(empty_tags)


def remove_empty_tags(xml_content: str, tags_to_remove: list[str]):
    """Remove selected empty tags from XML"""
    parser = etree.XMLParser(remove_blank_text=True)
    root = etree.fromstring(xml_content.encode("utf-8"), parser=parser)

    for tag in tags_to_remove:
        for elem in root.findall(f".//{tag}"):
            if (elem.text is None or not elem.text.strip()) and len(elem) == 0:
                parent = elem.getparent()
                if parent is not None:
                    parent.remove(elem)

    return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8").decode("utf-8")


# ---------------- Download XML ----------------
@app.post("/download")
async def download_xml(file_content: str = Form(...)):
    xml_file = io.BytesIO(file_content.encode("utf-8"))
    return StreamingResponse(
        xml_file,
        media_type="application/xml",
        headers={"Content-Disposition": "attachment; filename=cleaned.xml"}
    )
