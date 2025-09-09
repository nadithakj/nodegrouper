from fastapi import FastAPI, UploadFile, File, Request, Form
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from lxml import etree
from collections import defaultdict
import io
import pandas as pd
import json

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


# ---------------- XML Schedule Import Cleaner ----------------
@app.get("/meal_cleanup", response_class=HTMLResponse)
async def meal_cleanup(request: Request):
    return templates.TemplateResponse("meal_cleanup.html", {"request": request})


# ---------------- Excel Compare ----------------
@app.get("/excel_compare", response_class=HTMLResponse)
async def excel_compare(request: Request):
    return templates.TemplateResponse(
        "excel_compare.html",
        {"request": request, "columns1": None, "columns2": None, "file1": None, "file2": None, "diffs": None}
    )


@app.post("/upload_excel_files", response_class=HTMLResponse)
async def upload_excel_files(
    request: Request,
    file1: UploadFile = File(...),
    file2: UploadFile = File(...)
):
    # Read both Excel files into DataFrames
    df1 = pd.read_excel(io.BytesIO(await file1.read()))
    df2 = pd.read_excel(io.BytesIO(await file2.read()))

    # Pass column names for mapping
    return templates.TemplateResponse(
        "excel_compare.html",
        {
            "request": request,
            "columns1": df1.columns.tolist(),
            "columns2": df2.columns.tolist(),
            "file1": df1.to_json(orient="records"),
            "file2": df2.to_json(orient="records"),
            "diffs": None
        }
    )


@app.post("/map_fields", response_class=HTMLResponse)
async def map_fields(
    request: Request,
    file1: str = Form(...),
    file2: str = Form(...),
    key_field1: str = Form(...),
    key_field2: str = Form(...),
    other_mappings: str = Form(None)
):
    # Convert JSON back to DataFrames
    df1 = pd.DataFrame.from_records(json.loads(file1))
    df2 = pd.DataFrame.from_records(json.loads(file2))

    # Parse the JSON string from the new mapping UI
    mappings = {}
    if other_mappings and other_mappings != '[]':
        try:
            mapped_pairs = json.loads(other_mappings)
            for pair in mapped_pairs:
                mappings[pair['template']] = pair['report']
        except json.JSONDecodeError:
            # Handle malformed JSON gracefully
            return templates.TemplateResponse(
                "excel_compare.html",
                {
                    "request": request,
                    "error": "Error parsing field mappings. Please try again.",
                    "columns1": df1.columns.tolist(),
                    "columns2": df2.columns.tolist(),
                    "file1": file1,
                    "file2": file2,
                    "diffs": None,
                    "selected_key1": key_field1,
                    "selected_key2": key_field2,
                    "mapped_pairs": []
                }
            )
    else:
        mapped_pairs = []

    # Ensure key fields exist
    if key_field1 not in df1.columns or key_field2 not in df2.columns:
        return templates.TemplateResponse(
            "excel_compare.html",
            {
                "request": request,
                "error": "Key field not found in one of the files.",
                "columns1": df1.columns.tolist(),
                "columns2": df2.columns.tolist(),
                "file1": file1,
                "file2": file2,
                "diffs": None,
                "selected_key1": key_field1,
                "selected_key2": key_field2,
                "mapped_pairs": mapped_pairs
            }
        )

    # Merge on key fields
    merged = df1.merge(df2, left_on=key_field1, right_on=key_field2, suffixes=("_file1", "_file2"))

    # Compare mapped fields
    diffs = []
    # Loop through the mappings and perform the comparison
    for f1, f2 in mappings.items():
        # This check is crucial to prevent the KeyError
        if f1 in df1.columns and f2 in df2.columns:
            # Check for differences, stripping whitespace for robustness
            diff_rows = merged[merged[f"{f1}_file1"].astype(str).str.strip() != merged[f"{f2}_file2"].astype(str).str.strip()]
            if not diff_rows.empty:
                diffs.append({
                    "field1": f1,
                    "field2": f2,
                    # Access columns correctly, using the key field's original name
                    "differences": diff_rows[[key_field1, f"{f1}_file1", f"{f2}_file2"]].to_dict(orient="records")
                })
    
    return templates.TemplateResponse(
        "excel_compare.html",
        {
            "request": request,
            "columns1": df1.columns.tolist(),
            "columns2": df2.columns.tolist(),
            "file1": file1,
            "file2": file2,
            "diffs": diffs,
            "selected_key1": key_field1,
            "selected_key2": key_field2
        }
    )

# ---------------- Helper Functions ----------------
# The rest of your helper functions are not changed and can be kept as-is.
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
                    for tag in merge_tags:
                        for sub in other.findall(tag):
                            base.append(sub)
                    parent.remove(other)

    return etree.tostring(
        root, pretty_print=True, xml_declaration=True, encoding="UTF-8"
    ).decode("utf-8")


def find_empty_tags(xml_content: str):
    """Find tags that are empty (<Tag></Tag> or <Tag/>)"""
    parser = etree.XMLParser(remove_blank_text=True)
    root = etree.fromstring(xml_content.encode("utf-8"), parser=parser)
    empty_tags = set()

    for elem in root.xpath("//*"):
        if (elem.text is None or elem.text.strip() == "") and len(elem) == 0:
            empty_tags.add(elem.tag)

    return list(empty_tags)


def remove_selected_empty_tags(xml_content: str, tags_to_remove: list):
    parser = etree.XMLParser(remove_blank_text=True)
    root = etree.fromstring(xml_content.encode("utf-8"), parser=parser)
    removed_count = 0

    for tag in tags_to_remove:
        for elem in root.xpath(f"//{tag}"):
            if (elem.text is None or elem.text.strip() == "") and len(elem) == 0:
                parent = elem.getparent()
                parent.remove(elem)
                removed_count += 1

    return (
        etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8").decode("utf-8"),
        removed_count
    )


# ---------------- Upload XML ----------------
@app.post("/upload", response_class=HTMLResponse)
async def upload_xml(request: Request, file: UploadFile = File(...)):
    content = await file.read()
    xml_str = content.decode("utf-8")
    tags = get_groupable_tags(xml_str)

    return templates.TemplateResponse(
        "index.html",
        {"request": request, "xml_preview": xml_str, "tags": tags, "keys": [], "child_tags": []}
    )


# ---------------- Select Key ----------------
@app.post("/select_key", response_class=HTMLResponse)
async def select_key(request: Request, xml_content: str = Form(...), selected_tag: str = Form(...)):
    keys = get_child_keys(xml_content, selected_tag)
    child_tags = get_child_tags(xml_content, selected_tag)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "xml_preview": xml_content,
            "tags": [selected_tag],
            "keys": keys,
            "child_tags": child_tags,
            "selected_tag": selected_tag,
            "selected_key": None,
            "selected_child_tags": []
        }
    )


# ---------------- Group XML ----------------
@app.post("/group", response_class=HTMLResponse)
async def group_xml(
    request: Request,
    xml_content: str = Form(...),
    selected_tag: str = Form(...),
    selected_key: str = Form(...),
    selected_child_tags: str = Form(...)
):
    merge_tags = [tag.strip() for tag in selected_child_tags.split(",") if tag.strip()]
    grouped_xml = group_xml_by_tag_and_key(xml_content, selected_tag, selected_key, merge_tags)

    tags = get_groupable_tags(grouped_xml)
    child_tags = get_child_tags(grouped_xml, selected_tag)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "xml_preview": grouped_xml,
            "tags": tags,
            "keys": [selected_key],
            "child_tags": child_tags,
            "selected_tag": selected_tag,
            "selected_key": selected_key,
            "selected_child_tags": merge_tags
        }
    )


# ---------------- Download for Grouper ----------------
@app.post("/download")
async def download_xml(file_content: str = Form(...)):
    xml_file = io.BytesIO(file_content.encode("utf-8"))
    return StreamingResponse(
        xml_file,
        media_type="application/xml",
        headers={"Content-Disposition": "attachment; filename=grouped.xml"}
    )


# ---------------- Upload for Meal Cleanup ----------------
@app.post("/meal_cleanup", response_class=HTMLResponse)
async def meal_cleanup_upload(request: Request, file: UploadFile = File(...)):
    content = await file.read()
    xml_str = content.decode("utf-8")
    empty_tags = find_empty_tags(xml_str)

    return templates.TemplateResponse(
        "meal_cleanup.html",
        {"request": request, "xml_preview": xml_str, "empty_tags": empty_tags, "cleaned_xml": None, "removed_count": None}
    )


# ---------------- Clean Meal Cleanup ----------------
@app.post("/meal_cleanup_clean", response_class=HTMLResponse)
async def meal_cleanup_clean(
    request: Request,
    xml_content: str = Form(...),
    tags_to_remove: list = Form([])
):
    cleaned_xml, removed_count = remove_selected_empty_tags(xml_content, tags_to_remove)

    return templates.TemplateResponse(
        "meal_cleanup.html",
        {
            "request": request,
            "xml_preview": xml_content,
            "empty_tags": None,   # prevent "No Empty Records" message after cleaning
            "cleaned_xml": cleaned_xml,
            "removed_count": removed_count
        }
    )


# ---------------- Download for Meal Cleanup ----------------
@app.post("/meal_download")
async def meal_download(file_content: str = Form(...)):
    xml_file = io.BytesIO(file_content.encode("utf-8"))
    return StreamingResponse(
        xml_file,
        media_type="application/xml",
        headers={"Content-Disposition": "attachment; filename=cleaned_meal_break.xml"}
    )
