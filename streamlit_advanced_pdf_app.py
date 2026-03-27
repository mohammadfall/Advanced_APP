# ✅ Advanced PDF Tool by eLite Acadimea (Pro Edition)
# — جاهز مع متصفح Google Drive (مجلدات + ملفات + Breadcrumbs) واختيار متعدد —
# — المعالجة المتوازية (Parallel Processing) لسرعة خارقة + ETA —
# — ذكاء العلامة المائية (تتكيف مع حجم الصفحة طولي/عرضي) —
# — استئناف ذكي عند الفشل (Checkpoints) + صلاحية روابط مؤقتة —
# — إدخال ذكي للأسماء (نسخ ولصق بدون قيود الإكسل) وإخفاء الإكسل —

import os
import re
import csv
import json
import time
import pickle
import secrets
import tempfile
import concurrent.futures
from io import BytesIO
from zipfile import ZipFile
from datetime import datetime, timedelta

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
# أسرار التطبيق و Google Auth
# =========================
FOLDER_ID = st.secrets["FOLDER_ID"]
SHEET_ID = st.secrets["SHEET_ID"]
TELEGRAM_BOT_TOKEN = st.secrets["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]
EMAIL_SENDER = st.secrets["EMAIL_SENDER"]
EMAIL_PASSWORD = st.secrets["EMAIL_PASSWORD"]
LIB_FOLDER_ID = st.secrets.get("LIB_FOLDER_ID", FOLDER_ID)

SCOPES = ["https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/spreadsheets"]
creds = None
OAUTH_STATE_FILE = "oauth_state.json"
TOKEN_FILE = "token.pickle"

if st.button("🔁 إعادة تسجيل الدخول من جديد"):
    if os.path.exists(TOKEN_FILE): os.remove(TOKEN_FILE)
    if os.path.exists(OAUTH_STATE_FILE): os.remove(OAUTH_STATE_FILE)
    st.query_params.clear()
    st.rerun()

if os.path.exists(TOKEN_FILE):
    with open(TOKEN_FILE, "rb") as token: creds = pickle.load(token)

if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        try: creds.refresh(Request())
        except Exception as e:
            st.error(f"📛 فشل تحديث التوكن: {e}")
            if os.path.exists(TOKEN_FILE): os.remove(TOKEN_FILE)
            st.stop()
    else:
        try:
            flow = Flow.from_client_secrets_file("client_secret.json", scopes=SCOPES, redirect_uri="https://advancedapp-version2.streamlit.app/")
        except Exception as e:
            st.error(f"📛 تعذر قراءة client_secret.json: {e}")
            st.stop()

        query_params = st.query_params
        if "code" in query_params:
            auth_code = query_params["code"]
            try:
                if os.path.exists(OAUTH_STATE_FILE):
                    with open(OAUTH_STATE_FILE, "r") as f:
                        flow.code_verifier = json.load(f).get("code_verifier")
                flow.fetch_token(code=auth_code)
                creds = flow.credentials
                with open(TOKEN_FILE, "wb") as token: pickle.dump(creds, token)
                st.query_params.clear()
                if os.path.exists(OAUTH_STATE_FILE): os.remove(OAUTH_STATE_FILE)
                st.success("✅ تم تسجيل الدخول بنجاح! جاري إعداد بيئة العمل...")
                time.sleep(1.5)
                st.rerun()
            except Exception as e:
                st.error(f"📛 فشل الحصول على التوكن: {e}")
                st.stop()
        else:
            auth_url, _ = flow.authorization_url(prompt='consent', include_granted_scopes='true')
            with open(OAUTH_STATE_FILE, "w") as f: json.dump({"code_verifier": flow.code_verifier}, f)
            st.markdown(f"### [🔐 اضغط هنا لتسجيل الدخول والمصادقة باستخدام حساب Google]({auth_url})")
            st.info("بعد تسجيل الدخول، سيتم توجيهك تلقائياً إلى التطبيق ولن تحتاج لإدخال أي كود يدوياً.")
            st.stop()

# إنشاء الخدمات الأساسية
try:
    drive_service = build("drive", "v3", credentials=creds)
    gc = gspread.authorize(creds)
    sheet = gc.open_by_key(SHEET_ID).worksheet("PDF Tracking Log")
except Exception as e:
    st.error(f"📛 فشل إنشاء خدمات Google: {e}")
    st.stop()

def get_thread_safe_drive():
    """خدمة آمنة لكل Thread لتجنب التداخل"""
    return build("drive", "v3", credentials=creds)

# =========================
# 📊 لوحة الإحصائيات (Mini-Dashboard)
# =========================
st.markdown("---")
try:
    all_records = sheet.get_all_values()
    if len(all_records) > 1:
        total_files = len(all_records) - 1
        unique_students = len(set([row[1] for row in all_records[1:]])) 
        c1, c2, c3 = st.columns(3)
        c1.metric("📦 إجمالي الملفات المُرسلة", total_files)
        c2.metric("🎓 عدد الطلاب المستفيدين", unique_students)
        c3.metric("🟢 حالة النظام", "متصل وجاهز للعمل")
except Exception:
    pass
st.markdown("---")

# =========================
# رفع اللوجو
# =========================
logo_file = st.file_uploader("🖼️ اختياري: ارفع لوجو ليظهر على كل الصفحات", type=["png", "jpg", "jpeg"], key="logo")
logo_bytes = logo_file.read() if logo_file else None

# =========================
# رسائل جاهزة وإعدادات متقدمة
# =========================
col_msg, col_set = st.columns([2, 1])

with col_msg:
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
        f"""<div style="display:flex;align-items:center;margin-bottom:10px;">
            <div style="width:20px;height:20px;background:{selected_color};border-radius:50%;margin-right:10px;"></div>
            <span style="font-size:16px;">الخيار الحالي: <b>{selected_option}</b></span>
        </div>""", unsafe_allow_html=True
    )

    custom_message = st.text_area("📝 الرسالة المختارة (يمكنك تعديلها):", value=default_message, height=120)

with col_set:
    st.markdown("### ⚙️ إعدادات الحماية")
    expiration_days = st.number_input("⏳ أيام صلاحية الرابط في Drive (0 = مفتوح دائم):", min_value=0, value=0, help="سيفقد الطالب صلاحية فتح الملف تلقائياً بعد هذه الأيام.")
    option = st.radio("اختيار طريقة الإخراج:", ["☁️ رفع إلى Google Drive + مشاركة تلقائية", "📦 تحميل ZIP"])
    allow_download = st.checkbox("✅ السماح بتنزيل الملف من Google Drive", value=False)
    enable_password = st.checkbox("🔐 حماية الملفات بكلمة مرور", value=True)

# تسجيل الخط العربي
FONT_PATH = "Cairo-Regular.ttf"
try: pdfmetrics.registerFont(TTFont("Cairo", FONT_PATH))
except Exception: pass

# =========================
# دوال Google Drive (مجلدات + ملفات + تنزيل)
# =========================
def drive_get_name(drive_service, file_id: str) -> str:
    try: return drive_service.files().get(fileId=file_id, fields="name", supportsAllDrives=True).execute().get("name", "Root")
    except Exception: return "Root"

def drive_list_children(drive_service, folder_id, query_text="", page_token=None, page_size=50, kind_filter="All"):
    base = [f"'{folder_id}' in parents", "trashed=false"]
    if kind_filter == "PDF": base.append("mimeType='application/pdf'")
    elif kind_filter == "Images": base.append("(mimeType contains 'image/')")
    if query_text: base.append(f"name contains '{query_text.replace('\'', '\\\'')}'")
    
    res = drive_service.files().list(
        q=" and ".join(base), fields="files(id,name,mimeType,size,modifiedTime),nextPageToken",
        pageToken=page_token, pageSize=page_size, orderBy="folder,name,modifiedTime desc",
        includeItemsFromAllDrives=True, supportsAllDrives=True
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
    while not done: _, done = downloader.next_chunk()
    fh.seek(0)
    return fh.read()

# =========================
# اختيار مصدر الملفات
# =========================
st.markdown("## 🗂️ مصدر الملفات")
file_source = st.radio("اختر المصدر:", ["📁 رفع ملفات جديدة", "☁️ اختيار من Google Drive (مكتبتي)"])

sorted_file_copies = []

if file_source.startswith("📁"):
    uploaded_files = st.file_uploader("📄 ارفع كل ملفات المادة (PDFs)", type=["pdf"], accept_multiple_files=True, key="file_upload_main")
    if uploaded_files:
        st.markdown("### 🔃 ترتيب الملفات")
        sort_mode = st.radio("اختر طريقة الترتيب:", ["تلقائي", "يدوي"])
        file_names = [f.name for f in uploaded_files]
        if sort_mode == "تلقائي":
            sorted_files = sorted(uploaded_files, key=lambda f: f.name)
        else:
            custom_order = st.multiselect("🔀 رتب الملفات يدويًا:", file_names, default=file_names)
            sorted_files = sorted(uploaded_files, key=lambda f: custom_order.index(f.name)) if set(custom_order) == set(file_names) else uploaded_files
        sorted_file_copies = [(file.name, file.read()) for file in sorted_files]

else:
    st.info("اختر ملفاتك مباشرة من مكتبة Google Drive")
    if "lib_stack" not in st.session_state:
        st.session_state.lib_stack = [(LIB_FOLDER_ID, drive_get_name(drive_service, LIB_FOLDER_ID) or "Root")]

    curr_id, curr_name = st.session_state.lib_stack[-1]

    st.markdown("### 🧭 المسار")
    slice_stack = st.session_state.lib_stack[-6:]
    bc_cols = st.columns(len(slice_stack))
    for i, (fid, fname) in enumerate(slice_stack):
        if bc_cols[i].button(("🏠 " if i == 0 else "📁 ") + f"{fname}", key=f"bc_{i}_{fid}"):
            st.session_state.lib_stack = st.session_state.lib_stack[:st.session_state.lib_stack.index((fid, fname))+1]
            st.session_state.drive_page_token = None
            st.session_state.last_page_tokens = []
            st.rerun()

    st.markdown("### 🔎 بحث وفلترة")
    search_text = st.text_input("ابحث بالاسم (اختياري):", value="")
    kind_filter = st.selectbox("نوع العناصر:", ["All", "PDF", "Images"], index=0)
    page_size = st.selectbox("عدد النتائج بالصفحة:", [20, 50, 100], index=1)

    if "drive_page_token" not in st.session_state: st.session_state.drive_page_token = None
    if "last_page_tokens" not in st.session_state: st.session_state.last_page_tokens = []

    col_a, col_b, col_c = st.columns(3)
    if col_a.button("🔄 تحديث النتائج"): st.session_state.drive_page_token = None; st.session_state.last_page_tokens = []
    prev_clicked = col_b.button("⬅️ السابق", disabled=(len(st.session_state.last_page_tokens) == 0))
    next_clicked = col_c.button("➡️ التالي")

    folders, files, next_token = drive_list_children(drive_service, curr_id, search_text.strip(), st.session_state.drive_page_token, page_size, kind_filter)

    if next_clicked and next_token:
        st.session_state.last_page_tokens.append(st.session_state.drive_page_token)
        st.session_state.drive_page_token = next_token
        st.rerun()

    if prev_clicked and st.session_state.last_page_tokens:
        st.session_state.drive_page_token = st.session_state.last_page_tokens.pop()
        st.rerun()

    st.markdown("### 📂 المجلدات")
    if folders:
        cols = st.columns(4)
        for i, f in enumerate(folders):
            with cols[i % 4]:
                st.markdown(f"""<div style="border:1px solid #eee;border-radius:12px;padding:10px;margin-bottom:8px;">
                                <div>📁 <b>{f['name']}</b></div>
                                <div style="font-size:12px;color:#666;">ID: {f['id']}</div></div>""", unsafe_allow_html=True)
                if st.button("فتح", key=f"open_{f['id']}"):
                    st.session_state.lib_stack.append((f["id"], f["name"]))
                    st.session_state.drive_page_token = None
                    st.session_state.last_page_tokens = []
                    st.rerun()
    else: st.caption("لا توجد مجلدات في هذا المستوى.")

    st.markdown("### 📄 الملفات")
    if files:
        labels = [f"{it['name']} — {it.get('size','?')} bytes" for it in files]
        id_map = {labels[i]: files[i]["id"] for i in range(len(files))}
        name_map = {labels[i]: files[i]["name"] for i in range(len(files))}
        picked = st.multiselect("✅ اختر ملفات:", labels)

        if picked:
            drive_file_copies = []
            with st.spinner("⏳ تحميل الملفات المختارة من Drive…"):
                for lab in picked:
                    blob = drive_download_file_bytes(drive_service, id_map[lab])
                    try:
                        _ = PdfReader(BytesIO(blob))
                        drive_file_copies.append((name_map[lab], blob))
                    except: st.warning(f"تجاهل '{name_map[lab]}': ليس PDF صالحًا.")
            sorted_file_copies = sorted(drive_file_copies, key=lambda x: x[0])
            st.success(f"تم تجهيز {len(sorted_file_copies)} ملف(ات) من المكتبة.")
    else: st.warning("لا توجد ملفات مطابقة.")

# =========================
# 📋 إدخال الأسماء (الإدخال الذكي وإخفاء الإكسل)
# =========================
st.markdown("## 📋 قائمة الطلاب")
st.info("💡 اكتب أو انسخ الأسماء والإيميلات هنا. النظام ذكي بما يكفي ليفصل بينها سواء استخدمت الفاصلة، أو التاب، أو الخط |.")

raw_students_data = st.text_area("أدخل الأسماء (مثال: أحمد محمد | ahmed@gmail.com أو أحمد , ahmed@gmail.com):", height=150)

# خيار الإكسل مخفي كخيار جانبي (Expander)
students_from_excel = []
with st.expander("📁 خيار جانبي: استيراد من ملف Excel (A: الاسم، B: الإيميل)"):
    excel_file = st.file_uploader("📄 ارفع ملف Excel", type=["xlsx"])
    if excel_file:
        try:
            df = pd.read_excel(excel_file)
            students_from_excel = df.iloc[:, :2].dropna().values.tolist()
        except Exception as e:
            st.error(f"📛 تعذر قراءة ملف Excel: {e}")

students = []
if raw_students_data:
    for line in raw_students_data.splitlines():
        parts = re.split(r'[|,\t]', line)
        if len(parts) >= 2:
            name, email = parts[0].strip(), parts[-1].strip()
            if name and "@" in email: students.append([name, email])

# دمج القوائم
students.extend(students_from_excel)

if students:
    st.markdown("---")
    st.subheader("👁️‍🗨️ معاينة البيانات")
    st.dataframe(pd.DataFrame(students, columns=["الاسم", "الإيميل"]))
    st.subheader(f"📊 إجمالي عدد الطلاب: {len(students)}")

# =========================
# أدوات العلامة المائية والإرسال
# =========================
def generate_qr_code(link: str) -> ImageReader:
    qr = qrcode.make(link)
    output = BytesIO()
    qr.save(output, format="PNG")
    output.seek(0)
    return ImageReader(output)

def create_dynamic_watermark(name: str, link: str, w: float, h: float, logo_bytes=None):
    """علامة مائية ذكية تتكيف مع الطول والعرض"""
    packet = BytesIO()
    c = canvas.Canvas(packet, pagesize=(w, h))
    
    bidi_text = get_display(arabic_reshaper.reshape(f"خاص بـ {name}"))
    min_dim = min(w, h)
    font_size = max(14, int(min_dim * 0.04))
    spacing = int(min_dim * 0.4)
    
    try: c.setFillAlpha(0.12)
    except: c.setFillColorRGB(0.6, 0.6, 0.6)
    
    c.setFont("Cairo", font_size)
    for x in range(0, int(w)*2, spacing):
        for y in range(-int(h), int(h)*2, spacing):
            c.saveState(); c.translate(x, y); c.rotate(35); c.drawString(0, 0, bidi_text); c.restoreState()

    try: c.setFillAlpha(1)
    except: pass

    small_bidi = get_display(arabic_reshaper.reshape("هذا الملف محمي ولا يجوز تداوله إلا بإذن خطي"))
    c.setFont("Cairo", max(8, int(min_dim * 0.015)))
    c.drawString(20, 20, small_bidi)
    
    try:
        qr_size = int(min_dim * 0.1)
        c.drawImage(generate_qr_code(link), w - qr_size - 20, 20, width=qr_size, height=qr_size)
    except: pass

    if logo_bytes:
        try:
            logo_sz = int(min_dim * 0.12)
            c.drawImage(ImageReader(BytesIO(logo_bytes)), 20, h - logo_sz - 20, width=logo_sz, height=logo_sz, mask='auto')
        except: pass

    c.save()
    packet.seek(0)
    return PdfReader(packet).pages[0]

def send_telegram_message(message: str):
    try: requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", data={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=15)
    except: pass

def send_email_to_student(name, email, password, link_block_text, extra_message=""):
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_SENDER
        msg["To"] = email
        msg["Subject"] = "🔐 ملفاتك الجامعية جاهزة - eLite Acadimea"

        links_html = link_block_text.replace("\n", "<br>")
        links_html = re.sub(r"(https?://[^\s<]+)", r'<a href="\1" style="display: inline-block; padding: 5px 10px; margin-top: 5px; background-color: #0056b3; color: white; text-decoration: none; border-radius: 4px; font-size: 14px;">فتح الملف 🔗</a>', links_html)
        extra_html = f'<div style="background-color: #fff3cd; color: #856404; padding: 15px; border-left: 4px solid #ffeeba; margin-top: 20px; border-radius: 4px;"><strong>📩 ملاحظة من الإدارة:</strong><br>{extra_message.strip()}</div>' if extra_message.strip() else ""

        password_section = f"""<div style="background-color: #f8eaeb; border-right: 5px solid #d9534f; padding: 15px; margin: 25px 0; border-radius: 4px; text-align: center;">
            <p style="margin: 0; font-size: 16px; color: #333;">🔑 <strong>كلمة المرور لفتح الملفات:</strong></p>
            <p style="margin: 10px auto 5px auto; font-size: 24px; color: #d9534f; font-weight: bold; direction: ltr; background: white; padding: 12px; border-radius: 6px; border: 2px dashed #d9534f; display: inline-block; font-family: monospace; user-select: all;">{password}</p>
            </div>""" if password else f"""<div style="background-color: #e2f0e6; border-right: 5px solid #28a745; padding: 15px; margin: 25px 0; border-radius: 4px; text-align: center;">
            <p style="margin: 0; font-size: 16px; color: #333;">🔓 <strong>حالة الملفات:</strong></p>
            <p style="margin: 10px auto 0 auto; font-size: 18px; color: #28a745; font-weight: bold;">الملفات مفتوحة ولا تحتاج إلى كلمة مرور</p></div>"""

        html_body = f"""<div dir="rtl" style="font-family: 'Segoe UI', Tahoma, sans-serif; background-color: #f4f7f6; padding: 30px;">
            <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
                <div style="background-color: #0056b3; color: white; padding: 25px; text-align: center;"><h2 style="margin: 0; font-size: 26px;">eLite Acadimea 🎓</h2></div>
                <div style="padding: 30px;">
                    <p style="font-size: 18px; color: #333;">مرحباً <strong>{name}</strong>،</p>
                    <p style="font-size: 16px; color: #555; line-height: 1.6;">تم تجهيز ملفاتك بنجاح. يرجى العلم أن هذه الملفات محمية بحقوق النشر ومخصصة لك فقط.</p>
                    {password_section}
                    <h3 style="color: #0056b3; border-bottom: 2px solid #eee; padding-bottom: 10px; margin-top: 30px;">📎 روابط الملفات:</h3>
                    <div style="line-height: 1.8; font-size: 16px; color: #444;">{links_html}</div>
                    {extra_html}
                </div>
                <div style="background-color: #f8f9fa; padding: 15px; text-align: center; color: #888; font-size: 13px; border-top: 1px solid #eee;">
                    © {datetime.now().year} جميع الحقوق محفوظة - منصة eLite Acadimea
                </div></div></div>"""

        msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
    except Exception: pass

# =========================
# ⚙️ المعالجة لعملية Thread المتوازية
# =========================
def process_single_student(idx, name, email, file_copies, mode, allow_dl, enable_pwd, exp_days, custom_msg, logo_bytes, temp_dir):
    drive_srv = get_thread_safe_drive() if mode == "Drive" else None
    safe_name = name.replace(" ", "_").replace("+", "plus")
    display_password = name.replace(" ", "") + "@elite" if enable_pwd else "بدون باسورد"
    pdf_password = name.replace(" ", "") + "@elite" if enable_pwd else ""
    
    student_links = []
    generated_pdfs_paths = []

    for file_name, file_bytes in file_copies:
        base_filename = os.path.splitext(file_name)[0]
        final_name = f"{idx+1:02d} - {safe_name} - {base_filename}.pdf"
        file_id, drive_link = None, "https://pdf.eliteacadimea.com/placeholder"

        if mode == "Drive":
            file_metadata = {"name": final_name, "parents": [FOLDER_ID], "mimeType": "application/pdf"}
            tmp_ph = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            c = canvas.Canvas(tmp_ph.name, pagesize=letter); c.drawString(72, 720, "جاري التجهيز..."); c.save()
            media = MediaFileUpload(tmp_ph.name, mimetype="application/pdf", resumable=False)
            created = drive_srv.files().create(body=file_metadata, media_body=media, fields="id", supportsAllDrives=True).execute()
            file_id, drive_link = created["id"], f"https://drive.google.com/file/d/{created['id']}/view"
            
            # الصلاحيات وتاريخ الانتهاء
            perm_body = {"type": "user", "role": "reader", "emailAddress": email.strip()}
            if exp_days > 0: perm_body["expirationTime"] = (datetime.utcnow() + timedelta(days=exp_days)).isoformat() + "Z"
            try: drive_srv.permissions().create(fileId=file_id, body=perm_body, sendNotificationEmail=False, supportsAllDrives=True).execute()
            except: pass
            os.unlink(tmp_ph.name)

        reader = PdfReader(BytesIO(file_bytes))
        writer = PdfWriter()
        
        for page in reader.pages:
            w, h = float(page.mediabox.width), float(page.mediabox.height)
            watermark = create_dynamic_watermark(name, drive_link, w, h, logo_bytes)
            page.merge_page(watermark)
            writer.add_page(page)
            
        if pdf_password:
            try: writer.encrypt(user_password=pdf_password, owner_password=secrets.token_urlsafe(16), use_128bit=True)
            except TypeError: writer.encrypt(pdf_password, secrets.token_urlsafe(16))

        protected_path = os.path.join(temp_dir, final_name)
        with open(protected_path, "wb") as f_out: writer.write(f_out)
        generated_pdfs_paths.append(protected_path)
        
        if mode == "Drive" and file_id:
            media_final = MediaFileUpload(protected_path, mimetype="application/pdf", resumable=False)
            drive_srv.files().update(fileId=file_id, media_body=media_final, supportsAllDrives=True).execute()
            drive_srv.files().update(fileId=file_id, body={"viewersCanCopyContent": allow_dl, "copyRequiresWriterPermission": not allow_dl}, supportsAllDrives=True).execute()
            student_links.append(drive_link)

    # الإشعارات
    if mode == "Drive" and student_links:
        links_msg = "\n".join([f"{i+1}. {os.path.basename(fc[0])}\n🔗 {lnk}" for i, (fc, lnk) in enumerate(zip(file_copies, student_links))])
        tg_msg = f"📥 {name}:\n🔑 الباسورد: {display_password}\n{links_msg}" if enable_pwd else f"📥 {name}:\n🔓 (بدون باسورد)\n{links_msg}"
        send_telegram_message(tg_msg)
        send_email_to_student(name, email, pdf_password, links_msg, custom_msg)

    row_data = [name, email, display_password, " | ".join(student_links), datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
    return row_data, generated_pdfs_paths

# =========================
# 🚀 زر التشغيل والنظام المتوازي
# =========================
CHECKPOINT_FILE = "elite_checkpoint.json"

if sorted_file_copies and students:
    completed_emails = []
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, "r") as f: completed_emails = json.load(f)
            
    if completed_emails:
        st.warning(f"⚠️ نظام الاستئناف الذكي: يوجد عملية سابقة توقفت. تم العثور على {len(completed_emails)} طالب استلموا بالفعل ولن يتم الإرسال لهم مجدداً.")
        if st.button("🗑️ مسح الذاكرة والبدء من جديد للجميع"):
            os.remove(CHECKPOINT_FILE)
            st.rerun()
            
    students_to_process = [s for s in students if s[1] not in completed_emails]

    if st.button("🚀 بدء العملية"):
        if not students_to_process:
            st.success("✅ جميع الطلاب في هذه القائمة تم إرسال ملفاتهم مسبقاً!")
            st.stop()
            
        mode = "Drive" if option.startswith("☁️") else "ZIP"
        progress_bar = st.progress(0)
        status_text = st.empty()
        eta_text = st.empty()
        
        sheet_data_to_append = []
        all_generated_pdfs = []
        temp_dir = tempfile.mkdtemp()
        
        total_students = len(students_to_process)
        start_time = time.time()
        
        # المعالجة المتوازية
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_to_student = {
                executor.submit(process_single_student, idx, s[0], s[1], sorted_file_copies, mode, allow_download, enable_password, expiration_days, custom_message, logo_bytes, temp_dir): s 
                for idx, s in enumerate(students_to_process)
            }
            
            completed_count = 0
            for future in concurrent.futures.as_completed(future_to_student):
                student = future_to_student[future]
                try:
                    row_data, pdf_paths = future.result()
                    sheet_data_to_append.append(row_data)
                    all_generated_pdfs.extend(pdf_paths)
                    
                    completed_emails.append(student[1])
                    with open(CHECKPOINT_FILE, "w") as f: json.dump(completed_emails, f)
                except Exception as exc:
                    st.error(f"❌ خطأ مع الطالب {student[0]}: {exc}")
                
                completed_count += 1
                progress_bar.progress(completed_count / total_students)
                
                # حساب الـ ETA
                elapsed = time.time() - start_time
                avg_time = elapsed / completed_count
                remaining = total_students - completed_count
                eta_secs = int(avg_time * remaining)
                
                status_text.text(f"🔄 جاري المعالجة... إنجاز {completed_count} من {total_students}")
                eta_text.markdown(f"**⏳ الوقت المتبقي تقريباً:** {timedelta(seconds=eta_secs)}")

        # تحديث الشيت
        if sheet_data_to_append:
            status_text.text("💾 جاري حفظ البيانات في Google Sheets دفعة واحدة...")
            try: sheet.append_rows(sheet_data_to_append)
            except Exception as e: st.warning(f"⚠️ فشل إضافة بعض البيانات للشيت: {e}")
        
        if os.path.exists(CHECKPOINT_FILE): os.remove(CHECKPOINT_FILE)
            
        # تجهيز مخرجات الـ ZIP
        password_file_path = os.path.join(temp_dir, "passwords_and_links.csv")
        with open(password_file_path, "w", newline="", encoding="utf-8") as pw_file:
            writer_csv = csv.writer(pw_file)
            writer_csv.writerow(["Student Name", "Email", "Password", "Drive Links"])
            for row in sheet_data_to_append: writer_csv.writerow(row[:4])

        status_text.empty()
        eta_text.empty()

        if mode == "ZIP":
            zip_path = os.path.join(temp_dir, "protected_students.zip")
            with ZipFile(zip_path, "w") as zipf:
                for fpath in all_generated_pdfs: zipf.write(fpath, arcname=os.path.basename(fpath))
                zipf.write(password_file_path, arcname="passwords_and_links.csv")
            with open(zip_path, "rb") as f:
                st.download_button("📦 تحميل ZIP", f.read(), file_name="students_files.zip")
        else:
            with open(password_file_path, "rb") as f:
                st.download_button("📄 تحميل ملف CSV للروابط", f.read(), file_name="passwords_and_links.csv")

        st.success("🎉 تمت العملية بنجاح! تم إرسال جميع الملفات، يمكنك الآن تحميل الملخص عبر الزر أعلاه.")
        st.balloons()

st.markdown("---")
st.caption("🛡️ تم تطوير هذا النظام بواسطة د. محمد العمري - جميع الحقوق محفوظة لـ eLite Acadimea")
