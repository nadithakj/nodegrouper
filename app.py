from fastapi import FastAPI, UploadFile, File, Request, Form
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from lxml import etree
from collections import defaultdict
import io

app = FastAPI()
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "xml_preview": None, "tags": [], "keys": []})


def get_groupable_tags(xml_content: str):
    """
    Return a list of tags that repeat under the same parent.
    """
    parser = etree.XMLParser(remove_blank_text=True)
    root = etree.fromstring(xml_content.encode("utf-8"), parser=parser)
    candidates = set()
    for parent in root.xpath("//*"):
        counts = defaultdict(int)
        for child in parent:
            counts[child.tag] += 1
        for tag, count in counts.items():
            if count > 1:
                candidates.add(tag)
    return list(candidates)


def get_child_keys(xml_content: str, tag_to_group: str):
    """
    Return list of child element tags under tag_to_group to use as key.
    """
    parser = etree.XMLParser(remove_blank_text=True)
    root = etree.fromstring(xml_content.encode("utf-8"), parser=parser)
    elem = root.find(f".//{tag_to_group}")
    if elem is not None:
        return [child.tag for child in elem]
    return []


def group_xml_by_tag_and_key(xml_content: str, tag_to_group: str, key_tag: str):
    """
    Merge elements with the same key_tag value under the same parent.
    Preserves all repeating children (like multiple <Job>).
    """
    parser = etree.XMLParser(remove_blank_text=True)
    root = etree.fromstring(xml_content.encode("utf-8"), parser=parser)

    for parent in root.xpath(f".//{tag_to_group}/.."):
        children = parent.findall(tag_to_group)
        if len(children) <= 1:
            continue

        key_map = defaultdict(list)
        for c in children:
            key_elem = c.find(key_tag)
            key = key_elem.text.strip() if key_elem is not None and key_elem.text else id(c)
            key_map[key].append(c)

        for key, group in key_map.items():
            if len(group) > 1:
                base = group[0]
                for other in group[1:]:
                    for sub in other:
                        base.append(sub)
                    parent.remove(other)

    return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8").decode("utf-8")


@app.post("/upload", response_class=HTMLResponse)
async def upload_xml(request: Request, file: UploadFile = File(...)):
    content = await file.read()
    xml_str = content.decode("utf-8")
    tags = get_groupable_tags(xml_str)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "xml_preview": xml_str,
            "tags": tags,
            "keys": [],
            "selected_tag": None,
            "selected_key": None
        }
    )


@app.post("/select_key", response_class=HTMLResponse)
async def select_key(request: Request, xml_content: str = Form(...), selected_tag: str = Form(...)):
    keys = get_child_keys(xml_content, selected_tag)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "xml_preview": xml_content,
            "tags": [selected_tag],
            "keys": keys,
            "selected_tag": selected_tag,
            "selected_key": None
        }
    )


@app.post("/group", response_class=HTMLResponse)
async def group_xml(request: Request, xml_content: str = Form(...), selected_tag: str = Form(...), selected_key: str = Form(...)):
    grouped_xml = group_xml_by_tag_and_key(xml_content, selected_tag, selected_key)
    tags = get_groupable_tags(grouped_xml)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "xml_preview": grouped_xml,
            "tags": tags,
            "keys": [selected_key],
            "selected_tag": selected_tag,
            "selected_key": selected_key
        }
    )


@app.post("/download")
async def download_xml(file_content: str = Form(...)):
    xml_file = io.BytesIO(file_content.encode("utf-8"))
    return StreamingResponse(
        xml_file,
        media_type="application/xml",
        headers={"Content-Disposition": "attachment; filename=grouped.xml"}
    )
