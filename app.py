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
    return templates.TemplateResponse("index.html", {"request": request, "xml_preview": None})


def generic_group_xml(root: ET.Element) -> ET.Element:
    """
    Recursively group repeating child elements by shared key values.
    For children with the same tag under the same parent, tries to group
    by the first text child found. Falls back to unique id if no key.
    """
    for parent in root.iter():
        children = list(parent)
        tag_count = defaultdict(list)

        # Group children by tag
        for child in children:
            tag_count[child.tag].append(child)

        for tag, elems in tag_count.items():
            if len(elems) > 1:
                # Attempt to group by common key
                key_map = defaultdict(list)
                for e in elems:
                    key = None
                    # Pick first child with text as key
                    for sub in e:
                        if sub.text and sub.text.strip():
                            key = sub.text.strip()
                            break
                    if key is None:
                        key = id(e)  # fallback unique id
                    key_map[key].append(e)

                # Merge elements with same key
                for key, group in key_map.items():
                    if len(group) > 1:
                        base = group[0]
                        for other in group[1:]:
                            for sub in other:
                                # Avoid overwriting existing tags
                                if base.find(sub.tag) is None:
                                    base.append(sub)
                            parent.remove(other)
    return root


def process_xml(content: bytes) -> str:
    """Parse, group, and pretty-print XML."""
    root = ET.fromstring(content)
    grouped_root = generic_group_xml(root)
    xml_bytes = ET.tostring(grouped_root, encoding="utf-8", xml_declaration=True)
    pretty_xml = xml.dom.minidom.parseString(xml_bytes).toprettyxml(indent="    ")
    return pretty_xml


@app.post("/upload", response_class=HTMLResponse)
async def upload_xml(request: Request, file: UploadFile = File(...)):
    try:
        content = await file.read()
        xml_preview = process_xml(content)
    except Exception as e:
        return HTMLResponse(f"<h2>Error parsing XML:</h2><pre>{e}</pre>")

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "xml_preview": xml_preview,
            "filename": file.filename
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
