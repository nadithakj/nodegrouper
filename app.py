from fastapi import FastAPI, UploadFile, File, Request, Form
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
import xml.etree.ElementTree as ET
from collections import defaultdict
import io

app = FastAPI()
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "xml_preview": None})


def group_xml(content: bytes) -> bytes:
    """Parse and group the XML by XRefCode."""
    root = ET.fromstring(content)

    grouped = defaultdict(list)
    for emp in root.findall("Employee"):
        xref = emp.find("XRefCode").text
        grouped[xref].append(emp)

    new_root = ET.Element("EmployeeImport", root.attrib)
    for xref, employees in grouped.items():
        base_emp = employees[0]
        emp_node = ET.SubElement(new_root, "Employee")
        for tag in ["XRefCode", "EmployeeNumber", "FirstName", "LastName"]:
            elem = base_emp.find(tag)
            if elem is not None:
                ET.SubElement(emp_node, tag).text = elem.text

        for emp in employees:
            for job in emp.findall("Job"):
                emp_node.append(job)

    return ET.tostring(new_root, encoding="utf-8", xml_declaration=True)


@app.post("/upload", response_class=HTMLResponse)
async def upload_xml(request: Request, file: UploadFile = File(...)):
    try:
        content = await file.read()
        xml_bytes = group_xml(content)
        xml_preview = xml_bytes.decode("utf-8")
    except Exception as e:
        return HTMLResponse(f"<h2>Error parsing XML:</h2><pre>{e}</pre>")

    # Render preview with download form
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
