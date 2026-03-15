# ✅ Advanced PDF Tool by eLite Acadimea (UI + HTML Email + Telegram + QR Code + Preview + Logo)
# — جاهز مع متصفح Google Drive (مجلدات + ملفات + Breadcrumbs) واختيار متعدد —
# — يستخدم QR و watermark بالرابط النهائي (precreate + finalize) —
# — يدعم ZIP أو رفع مباشر إلى Drive + مشاركة تلقائية (بدون إشعار جوجل المزعج) —

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

from pypdf import PdfReader, PdfWriter

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
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
import io

# =========================
# إعدادات الواجهة والدخول
# =========================
st.set_page_config(page_title="🔐 eLite Acadimea PDF Protector", layout="wide")
st.title("🔐 نظام الحماية الذكي - eLite Acadimea")

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
LIB_FOLDER_ID = st.secrets.get("LIB_FOLDER_ID", FOLDER_ID)

# =========================
# Google Auth (OAuth)
# =========================
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets"
]

creds = None
OAUTH_STATE_FILE = "oauth_state.json"
TOKEN_FILE = "token.pickle"

if st.button("🔁 إعادة تسجيل الدخول من جديد"):
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)
    if os.path.exists(OAUTH_STATE_FILE):
        os.remove(OAUTH_STATE_FILE)
    st.query_params.clear()
    st.rerun()

if os.path.exists(TOKEN_FILE):
    with open(TOKEN_FILE, "rb") as token:
        creds = pickle.load(token)

if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception as e:
            st.error(f"📛 فشل تحديث التوكن: {e}")
            if os.path.exists(TOKEN_FILE):
                os.remove(TOKEN_FILE)
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

        query_params = st.query_params

        if "code" in query_params:
            auth_code = query_params["code"]
            try:
                if os.path.exists(OAUTH_STATE_FILE):
                    with open(OAUTH_STATE_FILE, "r") as f:
                        state_data = json.load(f)
                        flow.code_verifier = state_data.get("code_verifier")

                flow.fetch_token(code=auth_code)
                creds = flow.credentials
                
                with open(TOKEN_FILE, "wb") as token:
                    pickle.dump(creds, token)
                
                st.query_params.clear()
                if os.path.exists(OAUTH_STATE_FILE):
                    os.remove(OAUTH_STATE_FILE)
                
                st.success("✅ تم تسجيل الدخول بنجاح! جاري إعداد بيئة العمل...")
                time.sleep(1.5)
                st.rerun()
            except Exception as e:
                st.error(f"📛 فشل الحصول على التوكن: {e}")
                st.stop()
        else:
            auth_url, _ = flow.authorization_url(prompt='consent', include_granted_scopes='true')
            
            with open(OAUTH_STATE_FILE, "w") as f:
                json.dump({"code_verifier": flow.code_verifier}, f)

            st.markdown(f"### [🔐 اضغط هنا لتسجيل الدخول والمصادقة باستخدام حساب Google]({auth_url})")
            st.info("بعد تسجيل الدخول، سيتم توجيهك تلقائياً إلى التطبيق ولن تحتاج لإدخال أي كود يدوياً.")
            st.stop()

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
# دوال Google Drive (مجلدات + ملفات + تنزيل)
# =========================
def drive_get_name(drive_service, file_id: str) -> str:
    try:
        meta = drive_service.files().get(
            fileId=file_id,
            fields="name",
            supportsAllDrives=True
        ).execute()
        return meta.get("name", "Root")
    except Exception:
        return "Root"

def drive_list_children(drive_service, folder_id, query_text="", page_token=None, page_size=50, kind_filter="All"):
    base = [f"'{folder_id}' in parents", "trashed=false"]

    if kind_filter == "PDF":
        base.append("mimeType='application/pdf'")
    elif kind_filter == "Images":
        base.append("(mimeType contains 'image/')")

    if query_text:
        safe_q = query_text.replace("'", "\\'")
        base.append(f"name contains '{safe_q}'")

    q = " and ".join(base)

    res = drive_service.files().list(
        q=q,
        fields="files(id,name,mimeType,size,modifiedTime),nextPageToken",
        pageToken=page_token,
        pageSize=page_size,
        orderBy="folder,name,modifiedTime desc",
        includeItemsFromAllDrives=True,
        supportsAllDrives=True
    ).execute()

    items = res.get("files", [])
    folders = [it for it in items if it["mimeType"] == "application/vnd.google-apps.folder"]
    files   = [it for it in items if it["mimeType"] != "application/vnd.google-apps.folder"]
    return folders, files, res.get("nextPageToken")

def drive_download_file_bytes(drive_service, file_id):
    request = drive_service.files().get_media(fileId=file_id, supportsAllDrives=True)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    fh.seek(0)
    return fh.read()

# =========================
# اختيار مصدر الملفات
# =========================
st.markdown("## 🗂️ مصدر الملفات")
file_source = st.radio("اختر المصدر:", ["📁 رفع ملفات جديدة", "☁️ اختيار من Google Drive (مكتبتي)"])

sorted_file_copies = []

if file_source.startswith("📁"):
    uploaded_files = st.file_uploader(
        "📄 ارفع كل ملفات المادة (PDFs)",
        type=["pdf"],
        accept_multiple_files=True,
        key="file_upload_main"
    )
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

        sorted_file_copies = [(file.name, file.read()) for file in sorted_files]

else:
    st.info("اختر ملفاتك مباشرة من مكتبة Google Drive")

    if "lib_stack" not in st.session_state:
        root_name = drive_get_name(drive_service, LIB_FOLDER_ID)
        st.session_state.lib_stack = [(LIB_FOLDER_ID, root_name or "Root")]

    curr_id, curr_name = st.session_state.lib_stack[-1]

    st.markdown("### 🧭 المسار")
    slice_stack = st.session_state.lib_stack[-6:]
    bc_cols = st.columns(len(slice_stack))
    for i, (fid, fname) in enumerate(slice_stack):
        label = ("🏠 " if i == 0 else "📁 ") + f"{fname}"
        if bc_cols[i].button(label, key=f"bc_{i}_{fid}"):
            idx_global = st.session_state.lib_stack.index((fid, fname))
            st.session_state.lib_stack = st.session_state.lib_stack[:idx_global+1]
            st.session_state.drive_page_token = None
            st.session_state.last_page_tokens = []
            st.rerun()

    st.markdown("### 🔎 بحث وفلترة")
    search_text = st.text_input("ابحث بالاسم (اختياري):", value="")
    kind_filter = st.selectbox("نوع العناصر:", ["All", "PDF", "Images"], index=0)
    page_size = st.selectbox("عدد النتائج بالصفحة:", [20, 50, 100], index=1)

    if "drive_page_token" not in st.session_state:
        st.session_state.drive_page_token = None
    if "last_page_tokens" not in st.session_state:
        st.session_state.last_page_tokens = []

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if st.button("🔄 تحديث النتائج"):
            st.session_state.drive_page_token = None
            st.session_state.last_page_tokens = []
    with col_b:
        prev_clicked = st.button("⬅️ السابق", disabled=(len(st.session_state.last_page_tokens) == 0))
    with col_c:
        next_clicked = st.button("➡️ التالي")

    folders, files, next_token = drive_list_children(
        drive_service,
        folder_id=curr_id,
        query_text=search_text.strip(),
        page_token=st.session_state.drive_page_token,
        page_size=page_size,
        kind_filter=kind_filter
    )

    if next_clicked and next_token:
        if st.session_state.drive_page_token:
            st.session_state.last_page_tokens.append(st.session_state.drive_page_token)
        st.session_state.drive_page_token = next_token
        folders, files, next_token = drive_list_children(
            drive_service, curr_id, search_text.strip(),
            st.session_state.drive_page_token, page_size, kind_filter
        )

    if prev_clicked and st.session_state.last_page_tokens:
        st.session_state.drive_page_token = st.session_state.last_page_tokens.pop()
        folders, files, next_token = drive_list_children(
            drive_service, curr_id, search_text.strip(),
            st.session_state.drive_page_token, page_size, kind_filter
        )

    st.markdown("### 📂 المجلدات")
    if not folders:
        st.caption("لا توجد مجلدات في هذا المستوى.")
    else:
        cols = st.columns(4)
        for i, f in enumerate(folders):
            with cols[i % 4]:
                st.markdown(
                    f"""
                    <div style="border:1px solid #eee;border-radius:12px;padding:10px;margin-bottom:8px;">
                        <div>📁 <b>{f['name']}</b></div>
                        <div style="font-size:12px;color:#666;">ID: {f['id']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                if st.button("فتح", key=f"open_{f['id']}"):
                    st.session_state.lib_stack.append((f["id"], f["name"]))
                    st.session_state.drive_page_token = None
                    st.session_state.last_page_tokens = []
                    st.rerun()

    st.markdown("### 📄 الملفات")
    if not files:
        st.warning("لا توجد ملفات مطابقة … غيّر الفلتر أو ادخل مجلدًا آخر.")
    else:
        labels = [
            f"{it['name']} — {it.get('size','?')} bytes — {it.get('modifiedTime','')}"
            for it in files
        ]
        id_map = {labels[i]: files[i]["id"] for i in range(len(files))}
        name_map = {labels[i]: files[i]["name"] for i in range(len(files))}

        picked = st.multiselect("✅ اختر ملفات:", labels)

        if picked:
            drive_file_copies = []
            with st.spinner("⏳ تحميل الملفات المختارة من Drive…"):
                for lab in picked:
                    fid = id_map[lab]
                    fname = name_map[lab]
                    blob = drive_download_file_bytes(drive_service, fid)
                    try:
                        _ = PdfReader(BytesIO(blob))
                        drive_file_copies.append((fname, blob))
                    except Exception:
                        st.warning(f"تجاهل '{fname}': ليس PDF صالحًا.")
            sorted_file_copies = sorted(drive_file_copies, key=lambda x: x[0])
            st.success(f"تم تجهيز {len(sorted_file_copies)} ملف(ات) من المكتبة.")

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
        msg["Subject"] = "🔐 ملفاتك الجامعية جاهزة - eLite Acadimea"

        links_html = link_block_text.replace("\n", "<br>")
        links_html = re.sub(r"(https?://[^\s<]+)", r'<a href="\1" style="display: inline-block; padding: 5px 10px; margin-top: 5px; background-color: #0056b3; color: white; text-decoration: none; border-radius: 4px; font-size: 14px;">فتح الملف 🔗</a>', links_html)

        if extra_message.strip():
            extra_html = f'<div style="background-color: #fff3cd; color: #856404; padding: 15px; border-left: 4px solid #ffeeba; margin-top: 20px; border-radius: 4px;"><strong>📩 ملاحظة من الإدارة:</strong><br>{extra_message.strip()}</div>'
        else:
            extra_html = ""

        # تحديد شكل صندوق كلمة المرور بناءً على وجودها
        if password:
            password_section = f"""
            <div style="background-color: #f8eaeb; border-right: 5px solid #d9534f; padding: 15px; margin: 25px 0; border-radius: 4px; text-align: center;">
                <p style="margin: 0; font-size: 16px; color: #333;">🔑 <strong>كلمة المرور لفتح الملفات:</strong></p>
                <p style="margin: 10px auto 5px auto; font-size: 24px; color: #d9534f; font-weight: bold; direction: ltr; background: white; padding: 12px; border-radius: 6px; border: 2px dashed #d9534f; display: inline-block; font-family: monospace; -webkit-user-select: all; user-select: all;">{password}</p>
                <p style="margin: 0; font-size: 12px; color: #888;">(انقر مرتين على الكلمة لتحديدها ونسخها)</p>
            </div>
            """
        else:
            password_section = f"""
            <div style="background-color: #e2f0e6; border-right: 5px solid #28a745; padding: 15px; margin: 25px 0; border-radius: 4px; text-align: center;">
                <p style="margin: 0; font-size: 16px; color: #333;">🔓 <strong>حالة الملفات:</strong></p>
                <p style="margin: 10px auto 0 auto; font-size: 18px; color: #28a745; font-weight: bold;">الملفات مفتوحة ولا تحتاج إلى كلمة مرور</p>
            </div>
            """

        html_body = f"""
        <div dir="rtl" style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f7f6; padding: 30px;">
            <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
                
                <div style="background-color: #0056b3; color: white; padding: 25px; text-align: center;">
                    <h2 style="margin: 0; font-size: 26px;">eLite Acadimea 🎓</h2>
                </div>
                
                <div style="padding: 30px;">
                    <p style="font-size: 18px; color: #333;">مرحباً <strong>{name}</strong>،</p>
                    <p style="font-size: 16px; color: #555; line-height: 1.6;">تم تجهيز ملفاتك بنجاح. يرجى العلم أن هذه الملفات محمية بحقوق النشر ومخصصة لك فقط.</p>

                    {password_section}

                    <h3 style="color: #0056b3; border-bottom: 2px solid #eee; padding-bottom: 10px; margin-top: 30px;">📎 روابط الملفات:</h3>
                    <div style="line-height: 1.8; font-size: 16px; color: #444;">
                        {links_html}
                    </div>

                    {extra_html}
                </div>
                
                <div style="background-color: #f8f9fa; padding: 15px; text-align: center; color: #888; font-size: 13px; border-top: 1px solid #eee;">
                    © {datetime.now().year} جميع الحقوق محفوظة - منصة eLite Acadimea
                </div>
            </div>
        </div>
        """

        msg.attach(MIMEText(html_body, "html"))
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

        if email and re.match(r"[^@]+@[^@]+\.[^@]+", email.strip()):
            try:
                drive_service.permissions().create(
                    fileId=file_id,
                    body={"type": "user", "role": "reader", "emailAddress": email.strip()},
                    sendNotificationEmail=False,
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
    if not file_id:
        return ""
    try:
        media = MediaFileUpload(final_path, mimetype="application/pdf", resumable=False)
        drive_service.files().update(
            fileId=file_id,
            media_body=media,
            supportsAllDrives=True
        ).execute()

        drive_service.files().update(
            fileId=file_id,
            body={
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

    raw_text = f"خاص بـ {name}"
    bidi_text = get_display(arabic_reshaper.reshape(raw_text))

    try:
        c.setFillAlpha(alpha)
        alpha_supported = True
    except Exception:
        alpha_supported = False

    c.setFont("Cairo", font_size)
    if not alpha_supported:
        from reportlab.lib.colors import Color
        c.setFillColor(Color(0.6, 0.6, 0.6))

    for x in range(0, int(width), spacing):
        for y in range(0, int(height), spacing):
            c.saveState()
            c.translate(x, y)
            c.rotate(rotation)
            c.drawString(0, 0, bidi_text)
            c.restoreState()

    if alpha_supported:
        c.setFillAlpha(1)

    small_raw = "هذا الملف محمي ولا يجوز تداوله أو طباعته إلا بإذن خطي"
    small_bidi = get_display(arabic_reshaper.reshape(small_raw))
    c.setFont("Cairo", 8)
    c.drawString(30, 30, small_bidi)

    try:
        qr_img = generate_qr_code(link)
        c.drawImage(qr_img, width - 80, 15, width=50, height=50)
    except Exception:
        pass

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

    # التشفير يتم فقط إذا تم تمرير كلمة مرور
    if password:
        owner_password = secrets.token_urlsafe(16)
        try:
            writer.encrypt(user_password=password, owner_password=owner_password, use_128bit=True)
        except TypeError:
            writer.encrypt(password, owner_password)

    with open(output_path, "wb") as f:
        writer.write(f)

# =========================
# المعالجة الرئيسية للطلاب
# =========================
def process_students(file_copies, students, mode, allow_download, enable_password, logo_reader=None):
    temp_dir = tempfile.mkdtemp()
    password_file_path = os.path.join(temp_dir, "passwords_and_links.csv")
    pdf_paths = []

    with open(password_file_path, mode="w", newline="", encoding="utf-8") as pw_file:
        writer_csv = csv.writer(pw_file)
        writer_csv.writerow(["Student Name", "Email", "Password", "Drive Links"])

        for idx, (name, email) in enumerate(students):
            with st.spinner(f"🔄 جاري المعالجة: {name} ({idx+1}/{len(students)})"):
                safe_name = name.replace(" ", "_").replace("+", "plus")
                
                # تحديد كلمة المرور بناءً على اختيار المستخدم
                if enable_password:
                    pdf_password = name.replace(" ", "") + "@elite"
                    display_password = pdf_password
                else:
                    pdf_password = ""
                    display_password = "بدون باسورد"

                student_links = []

                for file_name, file_bytes in file_copies:
                    base_filename = os.path.splitext(file_name)[0]
                    final_name = f"{idx+1:02d} - {safe_name} - {base_filename}.pdf"

                    file_id = None
                    drive_link = "https://pdf.eliteacadimea.com/placeholder"
                    if mode == "Drive":
                        file_id, drive_link = precreate_drive_pdf(final_name, email)
                        if not file_id:
                            continue

                    temp_input = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
                    temp_input.write(file_bytes)
                    temp_input.close()

                    raw_path = os.path.join(temp_dir, f"{safe_name}_{base_filename}_raw.pdf")
                    protected_path = os.path.join(temp_dir, f"{safe_name}_{base_filename}.pdf")

                    reader = PdfReader(temp_input.name)
                    writer = PdfWriter()
                    watermark_page = create_watermark_page(name, drive_link, logo_reader=logo_reader)

                    for page in reader.pages:
                        page.merge_page(watermark_page)
                        writer.add_page(page)

                    with open(raw_path, "wb") as f_out:
                        writer.write(f_out)

                    apply_pdf_protection(raw_path, protected_path, pdf_password)
                    pdf_paths.append(protected_path)

                    if mode == "Drive":
                        final_link = finalize_drive_pdf(file_id, protected_path, allow_download)
                        student_links.append(final_link)

                if mode == "Drive" and student_links:
                    links_msg = "\n".join([
                        f"{i+1}. {os.path.basename(fc[0])}\n🔗 {lnk}"
                        for i, (fc, lnk) in enumerate(zip(file_copies, student_links))
                    ])
                    
                    # تعديل رسالة التيليجرام حسب التشفير
                    if enable_password:
                        message = f"📥 الملفات الخاصة بـ {name}:\n🔑 الباسورد: {display_password}\n{links_msg}"
                    else:
                        message = f"📥 الملفات الخاصة بـ {name}:\n🔓 (بدون باسورد)\n{links_msg}"
                        
                    send_telegram_message(message)
                    send_email_to_student(name, email, pdf_password, links_msg, custom_message)

                writer_csv.writerow([name, email, display_password, " | ".join(student_links)])

                try:
                    sheet.append_row([name, email, display_password, " | ".join(student_links), datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
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
enable_password = st.checkbox("🔐 حماية الملفات بكلمة مرور (تشفير PDF)", value=True)

if students:
    st.markdown("---")
    st.subheader("👁️‍🗨️ معاينة البيانات")
    st.dataframe(pd.DataFrame(students, columns=["الاسم", "الإيميل"]))
    st.markdown("---")
    st.subheader("📊 عدد الطلاب: " + str(len(students)))

# =========================
# زر التشغيل
# =========================
if sorted_file_copies and students:
    if st.button("🚀 بدء العملية"):
        with st.spinner("⏳ جاري تنفيذ العملية..."):
            mode = "Drive" if option.startswith("☁️") else "ZIP"
            file_copies = sorted_file_copies
            pdf_paths, password_file_path, temp_dir = process_students(
                file_copies, students, mode, allow_download, enable_password, logo_reader=logo_reader
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

            st.success("✅ اكتملت العملية بنجاح! تم إرسال الملفات للطلاب، يمكنك الآن تحميل الملفات عبر الزر أعلاه.")

st.markdown("---")
st.caption("🛡️ تم تطوير هذا النظام بواسطة د. محمد العمري - جميع الحقوق محفوظة لـ eLite Acadimea")
