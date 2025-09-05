from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
import xml.etree.ElementTree as ET
from collections import defaultdict
import io

app = FastAPI()
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/upload")
async def upload_xml(file: UploadFile = File(...)):
    try:
        content = await file.read()
        root = ET.fromstring(content)
    except Exception as e:
        return HTMLResponse(f"<h2>Error parsing XML:</h2><pre>{e}</pre>")

    # Step 1: Group Employees by XRefCode
    grouped = defaultdict(list)
    for emp in root.findall("Employee"):
        xref = emp.find("XRefCode").text
        grouped[xref].append(emp)

    # Step 2: Build new XML with grouped Jobs
    new_root = ET.Element("EmployeeImport", root.attrib)
    for xref, employees in grouped.items():
        base_emp = employees[0]
        emp_node = ET.SubElement(new_root, "Employee")
        for tag in ["XRefCode", "EmployeeNumber", "FirstName", "LastName"]:
            elem = base_emp.find(tag)
            if elem is not None:
                ET.SubElement(emp_node, tag).text = elem.text

        # Append all Job nodes
        for emp in employees:
            for job in emp.findall("Job"):
                emp_node.append(job)

    # Step 3: Convert XML to bytes for download
    xml_bytes = ET.tostring(new_root, encoding="utf-8", xml_declaration=True)
    xml_file = io.BytesIO(xml_bytes)

    # Return as downloadable XML file
    return StreamingResponse(
        xml_file,
        media_type="application/xml",
        headers={"Content-Disposition": "attachment; filename=grouped.xml"}
    )
