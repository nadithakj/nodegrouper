from fastapi import FastAPI, UploadFile, File, Request, Form
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from lxml import etree
from collections import defaultdict
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
        {
            "request": request,
            "xml_preview": None,
            "tags": [],
            "keys": [],
            "child_tags": []
        }
    )


# ---------------- XML Schedule Import Cleaner ----------------
@app.get("/meal_cleanup", response_class=HTMLResponse)
async def meal_cleanup(request: Request):
    # render a new page templates/meal_cleanup.html
    return templates.TemplateResponse(
        "meal_cleanup.html",
        {"request": request}
    )


# ---------------- Helper Functions ----------------
def get_groupable_tags(xml_content: str):
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
    parser = etree.XMLParser(remove_blank_text=True)
    root = etree.fromstring(xml_content.encode("utf-8"), parser=parser)
    elem = root.find(f".//{tag_to_group}")
    if elem is not None:
        return [child.tag for child in elem]
    return []


def get_child_tags(xml_content: str, tag_to_group: str):
    parser = etree.XMLParser(remove_blank_text=True)
    root = etree.fromstring(xml_content.encode("utf-8"), parser=parser)
    tags = set()
    for elem in root.findall(f".//{tag_to_group}"):
        for child in elem:
            tags.add(child.tag)
    return list(tags)


def group_xml_by_tag_and_key(xml_content: str, tag_to_group: str, key_tag: str, merge_tags: list):
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
                    # Append only the selected child tags to merge
                    for tag in merge_tags:
