# ✅ Advanced PDF Tool by Dr. Alomari (UI + Email + Telegram + QR Code + Preview + Logo)
import streamlit as st
import tempfile
import os
import pandas as pd
import re
import requests
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
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
import qrcode
from reportlab.lib.utils import ImageReader
import arabic_reshaper
from bidi.algorithm import get_display

st.set_page_config(page_title="🔐 Alomari PDF Protector", layout="wide")
st.title("🔐 نظام الحماية الذكي - د. محمد العمري")

ACCESS_KEY = os.environ["ACCESS_KEY"]
code = st.text_input("🔑 أدخل رمز الدخول:", type="password")
if code != ACCESS_KEY:
    st.warning("⚠️ رمز الدخول غير صحيح")
    st.stop()

custom_message = st.text_area("📝 رسالة إضافية تظهر في الإيميل (اختياري)", placeholder="اكتب رسالة شكر أو تعليمات للطالب هنا...")

FONT_PATH = "Cairo-Regular.ttf"
pdfmetrics.registerFont(TTFont("Cairo", FONT_PATH))

FOLDER_ID = os.environ["FOLDER_ID"]
SHEET_ID = os.environ["SHEET_ID"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
EMAIL_SENDER = os.environ["EMAIL_SENDER"]
EMAIL_PASSWORD = os.environ["EMAIL_PASSWORD"]

service_info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT"])
creds = service_account.Credentials.from_service_account_info(service_info, scopes=["https://www.googleapis.com/auth/drive"])
drive_service = build("drive", "v3", credentials=creds)
gc = gspread.service_account_from_dict(service_info)
sheet = gc.open_by_key(SHEET_ID).worksheet("PDF Tracking Log")

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        requests.post(url, data=data)
    except Exception as e:
        st.warning(f"📛 فشل إرسال تيليجرام: {e}")

def send_email_to_student(name, email, password, link, extra_message=""):
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_SENDER
        msg["To"] = email
        msg["Subject"] = "🔐 ملفك من فريق د. محمد العمري"
        body = f"""مرحبًا {name},

📎 روابط الملفات:
{link}

🔑 كلمة المرور: {password}

⚠️ الملفات خاصة بك فقط. لا تشاركها مع الآخرين.
"""
        if extra_message.strip():
            body += f"\n📩 ملاحظة من الدكتور:\n{extra_message.strip()}"

        msg.attach(MIMEText(body, "plain"))
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        st.warning(f"📛 فشل إرسال الإيميل إلى {email}: {e}")

def generate_qr_code(link):
    qr = qrcode.make(link)
    output = BytesIO()
    qr.save(output, format="PNG")
    output.seek(0)
    return ImageReader(output)

def upload_and_share(filename, filepath, email, allow_download):
    file_metadata = {"name": filename, "parents": [FOLDER_ID]}
    media = MediaFileUpload(filepath, mimetype="application/pdf")
    try:
        uploaded_file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id"
        ).execute()
    except Exception as e:
        st.error(f"📛 فشل في رفع الملف إلى Google Drive: {e}")
        return ""

    file_id = uploaded_file.get("id")
    link = f"https://drive.google.com/file/d/{file_id}/view"

    if email and re.match(r"[^@]+@[^@]+\.[^@]+", email):
        try:
            drive_service.permissions().create(
                fileId=file_id,
                body={"type": "user", "role": "reader", "emailAddress": email.strip()},
                fields='id',
                sendNotificationEmail=True
            ).execute()
            drive_service.files().update(
                fileId=file_id,
                body={
                    "copyRequiresWriterPermission": True,
                    "viewersCanCopyContent": allow_download
                }
            ).execute()
        except Exception as e:
            st.warning(f"📛 مشاركة فشلت مع {email}: {e}")
            return ""

    return link


def create_watermark_page(name, link, font_size=20, spacing=200, rotation=35, alpha=0.12):
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
            c.drawString(0, 0, f"خاص بـ ـ {name}")
            c.restoreState()
    c.setFillAlpha(1)
    c.setFont("Cairo", 8)
    reshaped_text = arabic_reshaper.reshape(" هذا الملف محمي ولا يجوز تداوله او طباعته إلا باذن خطي")
    bidi_text = get_display(reshaped_text)
    c.drawString(30, 30, bidi_text)
    qr_img = generate_qr_code(link)
    c.drawImage(qr_img, width - 80, 15, width=50, height=50)
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
def process_students(file_copies, students, mode, allow_download):
    temp_dir = tempfile.mkdtemp()
    password_file_path = os.path.join(temp_dir, "passwords_and_links.csv")
    pdf_paths = []

    with open(password_file_path, mode="w", newline="", encoding="utf-8") as pw_file:
        writer_csv = csv.writer(pw_file)
        writer_csv.writerow(["Student Name", "Email", "Password", "Drive Links"])

        for idx, (name, email) in enumerate(students):
            with st.spinner(f"🔄 جاري المعالجة: {name} ({idx+1}/{len(students)})"):
                safe_name = name.replace(" ", "_").replace("+", "plus")
                password = name.replace(" ", "") + "@alomari"
                student_links = []

                for file_name, file_bytes in file_copies:
                    temp_input = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
                    temp_input.write(file_bytes)
                    temp_input.close()

                    base_filename = os.path.splitext(file_name)[0]
                    raw_path = os.path.join(temp_dir, f"{safe_name}_{base_filename}_raw.pdf")
                    protected_path = os.path.join(temp_dir, f"{safe_name}_{base_filename}.pdf")

                    drive_link = "https://pdf.alomari.com/placeholder"
                    if mode == "Drive":
                        drive_link = "https://placeholder"

                    reader = PdfReader(temp_input.name)
                    writer = PdfWriter()
                    watermark_page = create_watermark_page(name, drive_link)

                    for page in reader.pages:
                        page.merge_page(watermark_page)
                        writer.add_page(page)

                    with open(raw_path, "wb") as f_out:
                        writer.write(f_out)

                    apply_pdf_protection(raw_path, protected_path, password)

                    if mode == "Drive":
                        final_name = f"{safe_name}_{base_filename}.pdf"
                        drive_link = upload_and_share(final_name, protected_path, email, allow_download)
                        student_links.append(drive_link)

                    pdf_paths.append(protected_path)

                if mode == "Drive":
                    links_msg = "\n".join([f"{i+1}. {link}" for i, link in enumerate(student_links)])
                    message = f"📥 الملفات الخاصة بـ {name}:\n🔑 الباسورد: {password}\n{links_msg}"
                    send_telegram_message(message)
                    send_email_to_student(name, email, password, links_msg, custom_message)

                writer_csv.writerow([name, email, password, " | ".join(student_links)])
                sheet.append_row([name, email, password, " | ".join(student_links), datetime.now().strftime("%Y-%m-%d %H:%M:%S")])

    return pdf_paths, password_file_path, temp_dir

# === واجهة الاستخدام ===
uploaded_files = st.file_uploader("📄 ارفع كل ملفات المادة (PDFs)", type=["pdf"], accept_multiple_files=True)
input_method = st.radio("📋 إدخال الأسماء:", ["📁 رفع ملف Excel (A: الاسم، B: الإيميل)", "✍️ إدخال يدوي"])

students = []
if input_method.startswith("📁"):
    excel_file = st.file_uploader("📄 ملف Excel", type=["xlsx"])
    if excel_file:
        df = pd.read_excel(excel_file)
        students = df.iloc[:, :2].dropna().values.tolist()
else:
    raw = st.text_area("✏️ أدخل الأسماء بهذا الشكل: الاسم | الايميل")
    if raw:
        for line in raw.splitlines():
            parts = [p.strip() for p in line.split("|")]
            if len(parts) == 2:
                students.append(parts)

option = st.radio("اختيار طريقة الإخراج:", ["📦 تحميل ZIP", "☁️ رفع إلى Google Drive + مشاركة تلقائية"])
allow_download = st.checkbox("✅ السماح بتنزيل الملف من Google Drive", value=False)

if students:
    st.markdown("---")
    st.subheader("👁️‍🗨️ معاينة البيانات")
    st.dataframe(pd.DataFrame(students, columns=["الاسم", "الإيميل"]))
    st.markdown("---")
    st.subheader("📊 عدد الطلاب: " + str(len(students)))

if uploaded_files and students:
    if st.button("🚀 بدء العملية"):
        with st.spinner("⏳ جاري تنفيذ العملية..."):
            mode = "Drive" if option.startswith("☁️") else "ZIP"
            file_copies = [(file.name, file.read()) for file in uploaded_files]
            pdf_paths, password_file_path, temp_dir = process_students(file_copies, students, mode, allow_download)

            if mode == "ZIP":
                zip_path = os.path.join(temp_dir, "protected_students.zip")
                with ZipFile(zip_path, "w") as zipf:
                    for file_path in pdf_paths:
                        zipf.write(file_path, arcname=os.path.basename(file_path))
                    zipf.write(password_file_path, arcname="passwords_and_links.csv")
                with open(zip_path, "rb") as f:
                    st.download_button("📦 تحميل ZIP مع كلمات السر والروابط", f.read(), file_name="students_files.zip")
            else:
                with open(password_file_path, "rb") as f:
                    st.download_button("📄 تحميل ملف كلمات السر والروابط", f.read(), file_name="passwords_and_links.csv")

st.markdown("---")
st.caption("🛡️ تم تطوير هذا النظام بواسطة د. محمد العمري - جميع الحقوق محفوظة")
