# ✅ Advanced PDF Tool by Dr. Alomari (UI + Email + Telegram + QR Code + Preview + Logo)
import os
import re
import csv
import json
import time
import pickle
import secrets
import tempfile
from io import BytesIO
from zipfile import ZipFile
from datetime import datetime

import streamlit as st
import pandas as pd
import requests
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from PyPDF2 import PdfReader, PdfWriter

from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader

import qrcode
import arabic_reshaper
from bidi.algorithm import get_display

import gspread

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request


# =========================
# إعدادات الواجهة والدخول
# =========================
st.set_page_config(page_title="🔐 Alomari PDF Protector", layout="wide")
st.title("🔐 نظام الحماية الذكي - د. محمد العمري")

ACCESS_KEY = st.secrets["ACCESS_KEY"]
code = st.text_input("🔑 أدخل رمز الدخول:", type="password")
if code != ACCESS_KEY:
    st.warning("⚠️ رمز الدخول غير صحيح")
    st.stop()

# =========================
# رسائل جاهزة + مخصصة
# =========================
messages_options = {
    "مكمل": {"color": "blue", "message": "📘 عزيزي الطالب، هذه الرسالة خاصة بالمكمل وتشمل جميع التعليمات الهامة."},
    "فيرست": {"color": "orange", "message": "🟠 مرحبًا، هذه مواد الفيرست فقط، نرجو مراجعتها بعناية."},
    "فيرست + سكند": {"color": "red", "message": "🔴 الملفات التالية تحتوي مواد الفيرست والسكند كاملة."},
    "سكند": {"color": "green", "message": "✅ هذه الملفات خاصة بالسكند فقط."},
    "ميد": {"color": "purple", "message": "🟣 مرحبًا، هذه ملفات الميد الخاصة بك."},
    "فاينل": {"color": "cyan", "message": "🔵 هذه الملفات خاصة بالفينال النهائي."},
    "كامل المادة": {"color": "pink", "message": "🌸 الملفات التالية تحتوي كامل المادة من البداية للنهاية."},
    "✏️ كتابة رسالة مخصصة...": {"color": "gray", "message": ""}
}

selected_option = st.selectbox("📩 اختر رسالة جاهزة:", list(messages_options.keys()))
selected_color = messages_options[selected_option]["color"]
default_message = messages_options[selected_option]["message"]

st.markdown(
    f"""
    <div style="display:flex;align-items:center;margin-bottom:10px;">
        <div style="width:20px;height:20px;background:{selected_color};border-radius:50%;margin-right:10px;"></div>
        <span style="font-size:16px;">الخيار الحالي: <b>{selected_option}</b></span>
    </div>
    """,
    unsafe_allow_html=True
)

if selected_option == "✏️ كتابة رسالة مخصصة...":
    custom_message = st.text_area("📝 اكتب رسالتك الخاصة:", placeholder="اكتب رسالة شكر أو تعليمات...")
else:
    custom_message = st.text_area("📝 الرسالة المختارة (يمكنك تعديلها):", value=default_message)

st.write("✅ الرسالة النهائية التي سيتم إرسالها:")
st.info(custom_message)

# =========================
# الخط العربي (Cairo)
# =========================
FONT_PATH = "Cairo-Regular.ttf"
try:
    pdfmetrics.registerFont(TTFont("Cairo", FONT_PATH))
except Exception as e:
    st.warning(f"⚠️ تعذر تسجيل الخط '{FONT_PATH}'. تأكد من وجود الملف. التفاصيل: {e}")

# =========================
# أسرار التطبيق (secrets)
# =========================
FOLDER_ID = st.secrets["FOLDER_ID"]
SHEET_ID = st.secrets["SHEET_ID"]
TELEGRAM_BOT_TOKEN = st.secrets["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]
EMAIL_SENDER = st.secrets["EMAIL_SENDER"]
EMAIL_PASSWORD = st.secrets["EMAIL_PASSWORD"]

# =========================
# Google Auth (OAuth)
# =========================
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets"
]

creds = None

# زر إعادة تسجيل الدخول
if st.button("🔁 إعادة تسجيل الدخول من جديد"):
    if os.path.exists("token.pickle"):
        os.remove("token.pickle")
    st.rerun()

# تحميل التوكن إن وجد
if os.path.exists("token.pickle"):
    with open("token.pickle", "rb") as token:
        creds = pickle.load(token)

# بدء المصادقة إذا التوكن غير موجود/غير صالح
if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception as e:
            st.error(f"📛 فشل تحديث التوكن: {e}")
            if os.path.exists("token.pickle"):
                os.remove("token.pickle")
            st.stop()
    else:
        try:
            flow = Flow.from_client_secrets_file(
                "client_secret.json",
                scopes=SCOPES,
                redirect_uri="https://advancedapp-version2.streamlit.app/"
            )
        except Exception as e:
            st.error(f"📛 تعذر قراءة client_secret.json: {e}")
            st.stop()

        auth_url, _ = flow.authorization_url(prompt='consent', include_granted_scopes='true')
        st.markdown(f"[🔐 اضغط هنا لتسجيل الدخول باستخدام Google]({auth_url})")

        auth_code = st.text_input("🔑 أدخل كود المصادقة (auth code) بعد تسجيل الدخول:")

        if auth_code:
            try:
                flow.fetch_token(code=auth_code)
                creds = flow.credentials
                with open("token.pickle", "wb") as token:
                    pickle.dump(creds, token)
                st.success("✅ تم الحصول على التوكن بنجاح. جاري المتابعة...")
                time.sleep(1.5)
                st.rerun()
            except Exception as e:
                st.error(f"📛 فشل الحصول على التوكن: {e}")
                st.stop()
        else:
            st.stop()

# إنشاء الخدمات بعد التأكد من التوكن
try:
    drive_service = build("drive", "v3", credentials=creds)
    gc = gspread.authorize(creds)
    sheet = gc.open_by_key(SHEET_ID).worksheet("PDF Tracking Log")
except Exception as e:
    st.error(f"📛 فشل إنشاء خدمات Google: {e}")
    st.stop()

# =========================
# رفع لوجو اختياري لدمجه في كل صفحة
# =========================
logo_file = st.file_uploader("🖼️ اختياري: ارفع لوجو ليظهر على كل الصفحات", type=["png", "jpg", "jpeg"], key="logo")
logo_reader = None
if logo_file:
    try:
        logo_bytes = logo_file.read()
        logo_reader = ImageReader(BytesIO(logo_bytes))
    except Exception as e:
        st.warning(f"⚠️ تعذر قراءة اللوجو: {e}")

# =========================
# رفع ملفات المادة وترتيبها
# =========================
uploaded_files = st.file_uploader("📄 ارفع كل ملفات المادة (PDFs)", type=["pdf"], accept_multiple_files=True, key="file_upload_main")

sorted_file_copies = []
if uploaded_files:
    st.markdown("### 🔃 ترتيب الملفات")
    sort_mode = st.radio("اختر طريقة الترتيب:", ["تلقائي", "يدوي"])

    file_names = [f.name for f in uploaded_files]
    if sort_mode == "تلقائي":
        sorted_files = sorted(uploaded_files, key=lambda f: f.name)
        st.success("✅ تم الترتيب تلقائيًا حسب اسم الملف.")
    else:
        custom_order = st.multiselect("🔀 رتب الملفات يدويًا:", file_names, default=file_names)
        if set(custom_order) == set(file_names):
            sorted_files = sorted(uploaded_files, key=lambda f: custom_order.index(f.name))
            st.success("✅ تم تطبيق الترتيب اليدوي بنجاح.")
        else:
            st.warning("⚠️ الرجاء التأكد من ترتيب جميع الملفات.")
            sorted_files = uploaded_files

    # خزّن نسخة bytes لأن Streamlit يغلق الملف بعد القراءة
    sorted_file_copies = [(file.name, file.read()) for file in sorted_files]

# =========================
# أدوات إرسال
# =========================
def send_telegram_message(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        requests.post(url, data=data, timeout=15)
    except Exception as e:
        st.warning(f"📛 فشل إرسال تيليجرام: {e}")

def send_email_to_student(name, email, password, link_block_text, extra_message=""):
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_SENDER
        msg["To"] = email
        msg["Subject"] = "🔐 ملفك من فريق د. محمد العمري"

        body = f"""مرحبًا {name},

📎 روابط الملفات:
{link_block_text}

🔑 كلمة المرور: {password}

⚠️ الملفات خاصة بك فقط. لا تشاركها مع الآخرين.
"""
        if extra_message.strip():
            body += f"\n📩 ملاحظة من الدكتور:\n{extra_message.strip()}"

        msg.attach(MIMEText(body, "plain"))
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        st.warning(f"📛 فشل إرسال الإيميل إلى {email}: {e}")

# =========================
# QR + PDF Utilities
# =========================
def generate_qr_code(link: str) -> ImageReader:
    qr = qrcode.make(link)
    output = BytesIO()
    qr.save(output, format="PNG")
    output.seek(0)
    return ImageReader(output)

def create_placeholder_pdf(tmp_path, text="Preparing your protected file..."):
    c = canvas.Canvas(tmp_path, pagesize=letter)
    c.setFont("Cairo", 16)
    c.drawString(72, 720, text)
    c.showPage()
    c.save()

def precreate_drive_pdf(filename: str, email: str):
    """يرفع PDF بسيط مؤقتًا فقط للحصول على fileId النهائي قبل توليد QR."""
    temp_placeholder = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    create_placeholder_pdf(temp_placeholder.name)
    file_metadata = {
        "name": filename,
        "parents": [FOLDER_ID],
        "mimeType": "application/pdf",
    }
    media = MediaFileUpload(temp_placeholder.name, mimetype="application/pdf", resumable=False)
    try:
        created = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id",
            supportsAllDrives=True
        ).execute()
        file_id = created["id"]
        link = f"https://drive.google.com/file/d/{file_id}/view"

        # شارك مع الطالب مباشرة (إن وجد إيميل صالح)
        if email and re.match(r"[^@]+@[^@]+\.[^@]+", email.strip()):
            try:
                drive_service.permissions().create(
                    fileId=file_id,
                    body={"type": "user", "role": "reader", "emailAddress": email.strip()},
                    sendNotificationEmail=True,
                    supportsAllDrives=True
                ).execute()
            except HttpError as pe:
                st.warning(f"⚠️ لم تتم مشاركة الملف مع {email}: {pe}")

        return file_id, link
    except HttpError as e:
        st.error(f"📛 فشل إنشاء الملف المؤقت على Google Drive: {e}")
        return None, ""
    finally:
        try:
            os.unlink(temp_placeholder.name)
        except Exception:
            pass

def finalize_drive_pdf(file_id: str, final_path: str, allow_download: bool) -> str:
    """يستبدل محتوى الملف المؤقت بالمحتوى النهائي ويطبق إعدادات التحميل/النسخ."""
    if not file_id:
        return ""
    try:
        media = MediaFileUpload(final_path, mimetype="application/pdf", resumable=False)
        drive_service.files().update(
            fileId=file_id,
            media_body=media,
            supportsAllDrives=True
        ).execute()

        # ضبط سياسات النسخ/التحميل
        drive_service.files().update(
            fileId=file_id,
            body={
                # إن أردت منع التحميل/النسخ غيّر إلى False
                "viewersCanCopyContent": bool(allow_download),
                "copyRequiresWriterPermission": (not allow_download),
            },
            supportsAllDrives=True
        ).execute()

        return f"https://drive.google.com/file/d/{file_id}/view"
    except HttpError as e:
        st.warning(f"⚠️ فشل تحديث الملف النهائي على Drive: {e}")
        return ""

def create_watermark_page(name: str, link: str, logo_reader=None, font_size=20, spacing=200, rotation=35, alpha=0.12):
    packet = BytesIO()
    c = canvas.Canvas(packet, pagesize=letter)
    width, height = letter

    # النص العربي (اسم الطالب) مع reshape + Bidi
    raw_text = f"خاص بـ {name}"
    bidi_text = get_display(arabic_reshaper.reshape(raw_text))

    # شفافية أو لون فاتح كـ fallback
    try:
        c.setFillAlpha(alpha)
        alpha_supported = True
    except Exception:
        alpha_supported = False

    c.setFont("Cairo", font_size)
    if not alpha_supported:
        # fallback بسيط: لون رمادي فاتح (بدون شفافية)
        from reportlab.lib.colors import Color
        c.setFillColor(Color(0.6, 0.6, 0.6))

    # شبكة الوترمارك
    for x in range(0, int(width), spacing):
        for y in range(0, int(height), spacing):
            c.saveState()
            c.translate(x, y)
            c.rotate(rotation)
            c.drawString(0, 0, bidi_text)
            c.restoreState()

    # رجّع الإعدادات للكتابة العادية
    if alpha_supported:
        c.setFillAlpha(1)

    # سطر تحذيري سفلي
    small_raw = "هذا الملف محمي ولا يجوز تداوله أو طباعته إلا بإذن خطي"
    small_bidi = get_display(arabic_reshaper.reshape(small_raw))
    c.setFont("Cairo", 8)
    c.drawString(30, 30, small_bidi)

    # QR للرابط النهائي
    try:
        qr_img = generate_qr_code(link)
        c.drawImage(qr_img, width - 80, 15, width=50, height=50)
    except Exception as e:
        # لو صار خطأ، فقط تجاهله واستمر
        pass

    # لوجو اختياري أعلى اليسار
    if logo_reader:
        try:
            c.drawImage(logo_reader, 20, height - 90, width=70, height=70, mask='auto')
        except Exception:
            pass

    c.save()
    packet.seek(0)
    return PdfReader(packet).pages[0]

def apply_pdf_protection(input_path: str, output_path: str, password: str):
    reader = PdfReader(input_path)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)

    owner_password = secrets.token_urlsafe(16)  # لا تشاركها مع أحد
    try:
        writer.encrypt(user_password=password, owner_password=owner_password, use_128bit=True)
    except TypeError:
        # توافقية مع بعض إصدارات PyPDF2
        writer.encrypt(password, owner_password)

    with open(output_path, "wb") as f:
        writer.write(f)

# =========================
# المعالجة الرئيسية للطلاب
# =========================
def process_students(file_copies, students, mode, allow_download, logo_reader=None):
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
                    base_filename = os.path.splitext(file_name)[0]
                    final_name = f"{idx+1:02d} - {safe_name} - {base_filename}.pdf"

                    # 1) في وضع Drive: إنشاء ملف مؤقت على Drive للحصول على fileId + رابط نهائي للـ QR
                    file_id = None
                    drive_link = "https://pdf.alomari.com/placeholder"
                    if mode == "Drive":
                        file_id, drive_link = precreate_drive_pdf(final_name, email)
                        if not file_id:
                            continue  # انتقل للملف التالي إذا فشل الإنشاء

                    # 2) تجهيز الملفات المؤقتة
                    temp_input = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
                    temp_input.write(file_bytes)
                    temp_input.close()

                    raw_path = os.path.join(temp_dir, f"{safe_name}_{base_filename}_raw.pdf")
                    protected_path = os.path.join(temp_dir, f"{safe_name}_{base_filename}.pdf")

                    # 3) الوترمارك الآن يستخدم الرابط النهائي الصحيح (drive_link)
                    reader = PdfReader(temp_input.name)
                    writer = PdfWriter()
                    watermark_page = create_watermark_page(name, drive_link, logo_reader=logo_reader)

                    for page in reader.pages:
                        page.merge_page(watermark_page)
                        writer.add_page(page)

                    with open(raw_path, "wb") as f_out:
                        writer.write(f_out)

                    # 4) حماية
                    apply_pdf_protection(raw_path, protected_path, password)
                    pdf_paths.append(protected_path)

                    # 5) في وضع Drive: حدث الملف نفسه (نفس fileId) بالمحتوى النهائي
                    if mode == "Drive":
                        final_link = finalize_drive_pdf(file_id, protected_path, allow_download)
                        student_links.append(final_link)

                # إرسال تيليجرام وإيميل
                if mode == "Drive" and student_links:
                    links_msg = "\n".join([
                        f"{i+1}. {os.path.basename(fc[0])}\n🔗 {lnk}"
                        for i, (fc, lnk) in enumerate(zip(file_copies, student_links))
                    ])
                    message = f"📥 الملفات الخاصة بـ {name}:\n🔑 الباسورد: {password}\n{links_msg}"
                    send_telegram_message(message)
                    send_email_to_student(name, email, password, links_msg, custom_message)

                writer_csv.writerow([name, email, password, " | ".join(student_links)])

                # لوج إلى Google Sheet
                try:
                    sheet.append_row([name, email, password, " | ".join(student_links), datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
                except Exception as e:
                    st.warning(f"⚠️ فشل إضافة صف إلى Google Sheet: {e}")

    return pdf_paths, password_file_path, temp_dir

# =========================
# واجهة إدخال الطلاب
# =========================
input_method = st.radio("📋 إدخال الأسماء:", ["📁 رفع ملف Excel (A: الاسم، B: الإيميل)", "✍️ إدخال يدوي"])

students = []
if input_method.startswith("📁"):
    excel_file = st.file_uploader("📄 ملف Excel", type=["xlsx"])
    if excel_file:
        try:
            df = pd.read_excel(excel_file)
            students = df.iloc[:, :2].dropna().values.tolist()
        except Exception as e:
            st.error(f"📛 تعذر قراءة ملف Excel: {e}")
else:
    raw = st.text_area("✏️ أدخل الأسماء بهذا الشكل: الاسم | الايميل")
    if raw:
        for line in raw.splitlines():
            parts = [p.strip() for p in line.split("|")]
            if len(parts) == 2 and parts[0] and parts[1]:
                students.append(parts)

option = st.radio("اختيار طريقة الإخراج:", ["📦 تحميل ZIP", "☁️ رفع إلى Google Drive + مشاركة تلقائية"])
allow_download = st.checkbox("✅ السماح بتنزيل الملف من Google Drive", value=False)

if students:
    st.markdown("---")
    st.subheader("👁️‍🗨️ معاينة البيانات")
    st.dataframe(pd.DataFrame(students, columns=["الاسم", "الإيميل"]))
    st.markdown("---")
    st.subheader("📊 عدد الطلاب: " + str(len(students)))

# =========================
# زر التشغيل
# =========================
if uploaded_files and students:
    if st.button("🚀 بدء العملية"):
        with st.spinner("⏳ جاري تنفيذ العملية..."):
            mode = "Drive" if option.startswith("☁️") else "ZIP"
            file_copies = sorted_file_copies
            pdf_paths, password_file_path, temp_dir = process_students(
                file_copies, students, mode, allow_download, logo_reader=logo_reader
            )

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

        # علامة ريفرش لمرة واحدة
        st.session_state["refresh_needed"] = True

# ريفرش بعد الإرسال
if "refresh_needed" in st.session_state and st.session_state["refresh_needed"]:
    st.success("✅ تم إرسال الملفات بنجاح! سيتم تحديث الصفحة...")
    time.sleep(3)
    st.session_state["refresh_needed"] = False
    st.rerun()

st.markdown("---")
st.caption("🛡️ تم تطوير هذا النظام بواسطة د. محمد العمري - جميع الحقوق محفوظة")
