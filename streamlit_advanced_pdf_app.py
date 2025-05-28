import streamlit as st
st.set_page_config(page_title="🔐 PDF Tool by Alomari")

import tempfile
import os
import pandas as pd
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import letter
from io import BytesIO
from zipfile import ZipFile
import json
import csv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import gspread
from datetime import datetime

# إعداد الخط
FONT_PATH = "Cairo-Regular.ttf"
pdfmetrics.registerFont(TTFont("Cairo", FONT_PATH))

# إعداد Google Drive
FOLDER_ID = "1D5gu4vO_YLjVHObfaRZc_XJEIPhlc_k4"
service_info = json.loads(st.secrets["GOOGLE_SERVICE_ACCOUNT"])
creds = service_account.Credentials.from_service_account_info(
    service_info,
    scopes=["https://www.googleapis.com/auth/drive"]
)
drive_service = build("drive", "v3", credentials=creds)

# ربط Google Sheets
SHEET_ID = "1o_bx5KszHuU1ur-vYF7AdLH8ypvUmm7HXmxMOTzbhXg"
gc = gspread.service_account_from_dict(service_info)
sheet = gc.open_by_key(SHEET_ID).worksheet("PDF Tracking Log")

def upload_and_share(filename, filepath, email):
    file_metadata = {"name": filename, "parents": [FOLDER_ID]}
    media = MediaFileUpload(filepath, mimetype="application/pdf")
    uploaded_file = drive_service.files().create(body=file_metadata, media_body=media, fields="id").execute()
    file_id = uploaded_file.get("id")
    drive_service.permissions().create(
        fileId=file_id,
        body={
            'type': 'user',
            'role': 'reader',
            'emailAddress': email
        },
        fields='id',
        sendNotificationEmail=True
    ).execute()
    drive_service.files().update(
        fileId=file_id,
        body={
            'copyRequiresWriterPermission': True,
            'viewersCanCopyContent': False
        }
    ).execute()
    return f"https://drive.google.com/file/d/{file_id}/view"

def create_watermark_page(text, font_size=20, spacing=200, rotation=35, alpha=0.12):
    packet = BytesIO()
    c = canvas.Canvas(packet, pagesize=letter)
    c.setFont("Cairo", font_size)
    c.setFillAlpha(alpha)
    width, height = letter
    for x in range(0, int(width), spacing):
        for y in range(0, int(height), spacing):
            c.saveState()
            c.translate(x, y)
            c.rotate(rotation)
            c.drawString(0, 0, f"خاص بـ {text}")
            c.restoreState()
    c.save()
    packet.seek(0)
    return PdfReader(packet).pages[0]

def apply_pdf_protection(input_path, output_path, password):
    reader = PdfReader(input_path)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt(user_password=password, owner_password=None, permissions_flag=4)
    with open(output_path, "wb") as f:
        writer.write(f)

def process_students(base_pdf, students, mode):
    base_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    base_temp.write(base_pdf.read())
    base_temp.close()

    temp_dir = tempfile.mkdtemp()
    password_file_path = os.path.join(temp_dir, "passwords_and_links.csv")
    pdf_paths = []

    with open(password_file_path, mode="w", newline="", encoding="utf-8") as pw_file:
        writer_csv = csv.writer(pw_file)
        writer_csv.writerow(["Student Name", "Email", "Password", "Drive Link"])

        for name, email in students:
            st.write(f"🔄 جاري المعالجة: {name}")
            safe_name = name.replace(" ", "_").replace("+", "plus")
            raw_path = os.path.join(temp_dir, f"{safe_name}_raw.pdf")
            protected_path = os.path.join(temp_dir, f"{safe_name}.pdf")
            password = name.replace(" ", "") + "@alomari"

            reader = PdfReader(base_temp.name)
            writer = PdfWriter()
            watermark_page = create_watermark_page(name)

            for page in reader.pages:
                page.merge_page(watermark_page)
                writer.add_page(page)

            with open(raw_path, "wb") as f_out:
                writer.write(f_out)

            apply_pdf_protection(raw_path, protected_path, password)

            drive_link = ""
            if mode == "Drive":
                drive_link = upload_and_share(f"{name}.pdf", protected_path, email)

            writer_csv.writerow([name, email, password, drive_link])

            sheet.append_row([
                name,
                email,
                password,
                drive_link,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ])

            pdf_paths.append(protected_path)

    return pdf_paths, password_file_path, temp_dir

# واجهة التطبيق
st.title("🔐 إضافة علامة مائية + حماية + مشاركة Google Drive")
pdf_file = st.file_uploader("📄 تحميل ملف PDF الأساسي", type=["pdf"])

input_method = st.radio("📋 إدخال الأسماء:", ["رفع ملف Excel (A: الاسم، B: الإيميل)", "✍️ إدخال يدوي"])

students = []
if input_method.startswith("رفع"):
    excel_file = st.file_uploader("📄 ملف Excel", type=["xlsx"])
    if excel_file:
        df = pd.read_excel(excel_file)
        students = df.iloc[:, :2].dropna().values.tolist()
else:
    raw = st.text_area("أدخل الأسماء بهذا الشكل: الاسم | الايميل")
    if raw:
        for line in raw.splitlines():
            parts = [p.strip() for p in line.split("|")]
            if len(parts) == 2:
                students.append(parts)

option = st.radio("اختيار طريقة الإخراج:", ["📆 تحميل ZIP", "☁️ رفع إلى Google Drive + مشاركة تلقائية"])

if pdf_file and students:
    if st.button("🚀 بدء العملية"):
        with st.spinner("⏳ جاري تنفيذ العملية..."):
            mode = "Drive" if option.startswith("☁️") else "ZIP"
            pdf_paths, password_file_path, temp_dir = process_students(pdf_file, students, mode)

            if mode == "ZIP":
                zip_path = os.path.join(temp_dir, "protected_students.zip")
                with ZipFile(zip_path, "w") as zipf:
                    for file_path in pdf_paths:
                        zipf.write(file_path, arcname=os.path.basename(file_path))
                    zipf.write(password_file_path, arcname="passwords_and_links.csv")
                with open(zip_path, "rb") as f:
                    st.download_button("📆 تحميل ZIP مع كلمات السر والروابط", f.read(), file_name="students_files.zip")
            else:
                with open(password_file_path, "rb") as f:
                    st.download_button("📄 تحميل ملف كلمات السر والروابط", f.read(), file_name="passwords_and_links.csv")
