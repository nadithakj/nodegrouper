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
    return templates.TemplateResponse("index.html", {"request": request, "xml_preview": None, "tags": [], "keys": []})


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


def get_child_keys(root: ET.Element, tag_to_group: str):
    """
    Return list of child element tags under tag_to_group to use as key.
    """
    for elem in root.iter(tag_to_group):
        return [child.tag for child in elem]
    return []


def group_xml_by_tag_and_key(root: ET.Element, tag_to_group: str, key_tag: str) -> ET.Element:
    """
    Group elements with tag `tag_to_group` using `key_tag` as the key.
    """
    for parent in root.iter():
        children = [c for c in parent if c.tag == tag_to_group]
        if len(children) > 1:
            key_map = defaultdict(list)
            for c in children:
                key_elem = c.find(key_tag)
                key = key_elem.text.strip() if key_elem is not None and key_elem.text else id(c)
                key_map[key].append(c)

            # Merge children with same key
            for key, group in key_map.items():
                if len(group) > 1:
                    base = group[0]
                    for other in group[1:]:
                        for sub in other:
                            base.append(sub)  # always append, preserve repeating children
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
            "keys": [],
            "selected_tag": None,
            "selected_key": None
        }
    )


@app.post("/select_key", response_class=HTMLResponse)
async def select_key(request: Request, xml_content: str = Form(...), selected_tag: str = Form(...)):
    try:
        root = ET.fromstring(xml_content.encode("utf-8"))
        keys = get_child_keys(root, selected_tag)
        xml_preview = pretty_xml(root)
    except Exception as e:
        return HTMLResponse(f"<h2>Error processing XML:</h2><pre>{e}</pre>")

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "xml_preview": xml_preview,
            "tags": [selected_tag],
            "keys": keys,
            "selected_tag": selected_tag,
            "selected_key": None
        }
    )


@app.post("/group", response_class=HTMLResponse)
async def group_xml(request: Request, xml_content: str = Form(...), selected_tag: str = Form(...), selected_key: str = Form(...)):
    try:
        root = ET.fromstring(xml_content.encode("utf-8"))
        grouped_root = group_xml_by_tag_and_key(root, selected_tag, selected_key)
        xml_preview = pretty_xml(grouped_root)
        tags = get_groupable_tags(grouped_root)
    except Exception as e:
        return HTMLResponse(f"<h2>Error grouping XML:</h2><pre>{e}</pre>")

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "xml_preview": xml_preview,
            "tags": tags,
            "keys": [selected_key],
            "selected_tag": selected_tag,
            "selected_key": selected_key
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
