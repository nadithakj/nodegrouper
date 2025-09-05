from fastapi import FastAPI, UploadFile, File, Request, Form
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
import xml.etree.ElementTree as ET
from collections import defaultdict
import io
import xml.dom.minidom

app = FastAPI()
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "xml_preview": None, "tags": []})


def get_groupable_tags(root: ET.Element):
    """
    Return a list of tags that repeat under the same parent.
    """
    candidates = set()
    for parent in root.iter():
        tag_count = defaultdict(int)
        for child in parent:
            tag_count[child.tag] += 1
        for tag, count in tag_count.items():
            if count > 1:
                candidates.add(tag)
    return list(candidates)


def group_xml_by_tag(root: ET.Element, tag_to_group: str) -> ET.Element:
    """
    Group elements with tag `tag_to_group` by first child text.
    """
    for parent in root.iter():
        # Find all children with the selected tag
        children = [c for c in parent if c.tag == tag_to_group]
        if len(children) > 1:
            # Group by first child text
            key_map = defaultdict(list)
            for c in children:
                key = None
                for sub in c:
                    if sub.text and sub.text.strip():
                        key = sub.text.strip()
                        break
                if key is None:
                    key = id(c)
                key_map[key].append(c)

            # Merge children with same key
            for key, group in key_map.items():
                if len(group) > 1:
                    base = group[0]
                    for other in group[1:]:
                        for sub in other:
                            if base.find(sub.tag) is None:
                                base.append(sub)
                        parent.remove(other)
    return root


def pretty_xml(root: ET.Element) -> str:
    xml_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    parsed = xml.dom.minidom.parseString(xml_bytes)
    return parsed.toprettyxml(indent="    ")


@app.post("/upload", response_class=HTMLResponse)
async def upload_xml(request: Request, file: UploadFile = File(...)):
    try:
        content = await file.read()
        root = ET.fromstring(content)
        tags = get_groupable_tags(root)
        xml_preview = pretty_xml(root)
    except Exception as e:
        return HTMLResponse(f"<h2>Error parsing XML:</h2><pre>{e}</pre>")

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "xml_preview": xml_preview,
            "tags": tags,
            "filename": file.filename
        }
    )


@app.post("/group", response_class=HTMLResponse)
async def group_xml(request: Request, xml_content: str = Form(...), selected_tag: str = Form(...)):
    try:
        root = ET.fromstring(xml_content.encode("utf-8"))
        grouped_root = group_xml_by_tag(root, selected_tag)
        xml_preview = pretty_xml(grouped_root)
        tags = get_groupable_tags(grouped_root)
    except Exception as e:
        return HTMLResponse(f"<h2>Error processing XML:</h2><pre>{e}</pre>")

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "xml_preview": xml_preview,
            "tags": tags,
            "selected_tag": selected_tag
        }
    )


@app.post("/download")
async def download_xml(file_content: str = Form(...)):
    """Download XML from preview."""
    xml_file = io.BytesIO(file_content.encode("utf-8"))
    return StreamingResponse(
        xml_file,
        media_type="application/xml",
        headers={"Content-Disposition": "attachment; filename=grouped.xml"}
    )
