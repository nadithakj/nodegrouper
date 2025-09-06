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

# ---------------- Meal Cleanup ----------------
@app.get("/meal_cleanup", response_class=HTMLResponse)
async def meal_cleanup(request: Request):
    return templates.TemplateResponse("meal_cleanup.html", {"request": request})

@app.post("/meal_cleanup_upload", response_class=HTMLResponse)
async def meal_cleanup_upload(request: Request, file: UploadFile = File(...)):
    content = await file.read()
    xml_str = content.decode("utf-8")
    parser = etree.XMLParser(remove_blank_text=True)
    root = etree.fromstring(xml_str.encode("utf-8"), parser=parser)

    # Find empty tags
    empty_tags = set()
    for elem in root.iter():
        if elem.text is None or elem.text.strip() == "":
            empty_tags.add(elem.tag)

    return templates.TemplateResponse(
        "meal_cleanup.html",
        {"request": request, "xml_preview": xml_str, "empty_tags": list(empty_tags)}
    )

@app.post("/meal_cleanup_clean", response_class=HTMLResponse)
async def meal_cleanup_clean(request: Request, xml_content: str = Form(...), tags_to_remove: list[str] = Form(...)):
    parser = etree.XMLParser(remove_blank_text=True)
    root = etree.fromstring(xml_content.encode("utf-8"), parser=parser)

    # Remove selected empty tags
    for elem in root.xpath("//*"):
        if elem.tag in tags_to_remove and (elem.text is None or elem.text.strip() == ""):
            parent = elem.getparent()
            if parent is not None:
                parent.remove(elem)

    cleaned_xml = etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8").decode("utf-8")
    return templates.TemplateResponse(
        "meal_cleanup.html",
        {"request": request, "cleaned_xml": cleaned_xml}
    )

# ---------------- Download XML ----------------
@app.post("/download")
async def download_xml(file_content: str = Form(...)):
    xml_file = io.BytesIO(file_content.encode("utf-8"))
    return StreamingResponse(
        xml_file,
        media_type="application/xml",
        headers={"Content-Disposition": "attachment; filename=cleaned.xml"}
    )
