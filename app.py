from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
import xml.etree.ElementTree as ET
from collections import defaultdict

app = FastAPI()
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/upload", response_class=HTMLResponse)
async def upload_xml(request: Request, file: UploadFile = File(...)):
    content = await file.read()
    root = ET.fromstring(content)

    # Step 1: Group Employees by XRefCode
    grouped = defaultdict(list)
    for emp in root.findall("Employee"):
        xref = emp.find("XRefCode").text
        grouped[xref].append(emp)

    # Step 2: Build new XML with grouped Jobs
    new_root = ET.Element("EmployeeImport", root.attrib)
    for xref, employees in grouped.items():
        # take data from first employee node
        base_emp = employees[0]
        emp_node = ET.SubElement(new_root, "Employee")
        for tag in ["XRefCode", "EmployeeNumber", "FirstName", "LastName"]:
            elem = base_emp.find(tag)
            if elem is not None:
                ET.SubElement(emp_node, tag).text = elem.text

        # add all Job nodes
        for emp in employees:
            for job in emp.findall("Job"):
                emp_node.append(job)

    # Step 3: Convert XML back to string
    new_xml = ET.tostring(new_root, encoding="utf-8").decode("utf-8")

    return HTMLResponse(f"<h2>Grouped XML</h2><pre>{new_xml}</pre>")
