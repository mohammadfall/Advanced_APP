# ✅ Advanced PDF Tool by eLite Acadimea (Enterprise Edition)
# — متصفح Google Drive + المعالجة المتوازية (Parallel Processing) —
# — تخصيص العلامة المائية (UI Controls) وحل مشكلة تداخل الـ QR —
# — استئناف ذكي عند الفشل (Checkpoints) + صلاحية روابط مؤقتة —
# — استخراج ذكي للأسماء والإيميلات (Smart Regex) —
# — إخراج ZIP احترافي (مجلدات بأسماء الطلاب) —
# — واجهة مستخدم نظيفة بنظام التبويبات (Tabs) وبطاقات إحصائيات حديثة —

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
# إعدادات الواجهة
# =========================
st.set_page_config(page_title="🔐 eLite Acadimea PDF Protector", layout="wide")
st.title("🔐 نظام الحماية الذكي - eLite Acadimea")

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

if st.sidebar.button("🔁 إعادة تسجيل الدخول بخدمات جوجل"):
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
# 📊 لوحة الإحصائيات الأنيقة (Modern Dashboard)
# =========================
try:
    all_records = sheet.get_all_values()
    total_files = 0
    unique_students = 0
    if len(all_records) > 1:
        total_files = len(all_records) - 1
        unique_students = len(set([row[1] for row in all_records[1:]]))
        
    st.markdown(f"""
    <div style="display: flex; gap: 20px; justify-content: space-between; margin-bottom: 30px;">
        <div style="flex: 1; background: linear-gradient(135deg, #ffffff, #f8f9fa); padding: 25px; border-radius: 15px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); border: 1px solid #eaeaea; text-align: center;">
            <div style="font-size: 38px; font-weight: 800; color: #1f77b4; line-height: 1;">{total_files}</div>
            <div style="color: #555; font-size: 15px; margin-top: 8px; font-weight: 600;">📦 إجمالي الملفات المُرسلة</div>
        </div>
        <div style="flex: 1; background: linear-gradient(135deg, #ffffff, #f8f9fa); padding: 25px; border-radius: 15px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); border: 1px solid #eaeaea; text-align: center;">
            <div style="font-size: 38px; font-weight: 800; color: #2ca02c; line-height: 1;">{unique_students}</div>
            <div style="color: #555; font-size: 15px; margin-top: 8px; font-weight: 600;">🎓 عدد الطلاب المستفيدين</div>
        </div>
        <div style="flex: 1; background: linear-gradient(135deg, #ffffff, #f8f9fa); padding: 25px; border-radius: 15px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); border: 1px solid #eaeaea; text-align: center;">
            <div style="font-size: 38px; font-weight: 800; color: #27ae60; line-height: 1;">متصل</div>
            <div style="color: #555; font-size: 15px; margin-top: 8px; font-weight: 600;">🟢 حالة النظام (جاهز للعمل)</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
except Exception:
    pass

# =========================
# واجهة التبويبات النظيفة (Clean Tabs UI)
# =========================
tab_msg, tab_settings, tab_wm = st.tabs([
    "📩 إعدادات الرسائل", 
    "⚙️ إعدادات الإخراج والحماية", 
    "🎛️ تخصيص العلامة المائية"
])

with tab_msg:
    messages_options = {
        "مكمل": {"color": "#1f77b4", "message": "📘 عزيزي الطالب، هذه الرسالة خاصة بالمكمل وتشمل جميع التعليمات الهامة."},
        "فيرست": {"color": "#ff7f0e", "message": "🟠 مرحبًا، هذه مواد الفيرست فقط، نرجو مراجعتها بعناية."},
        "فيرست + سكند": {"color": "#d62728", "message": "🔴 الملفات التالية تحتوي مواد الفيرست والسكند كاملة."},
        "سكند": {"color": "#2ca02c", "message": "✅ هذه الملفات خاصة بالسكند فقط."},
        "ميد": {"color": "#9467bd", "message": "🟣 مرحبًا، هذه ملفات الميد الخاصة بك."},
        "فاينل": {"color": "#17becf", "message": "🔵 هذه الملفات خاصة بالفينال النهائي."},
        "كامل المادة": {"color": "#e377c2", "message": "🌸 الملفات التالية تحتوي كامل المادة من البداية للنهاية."},
        "✏️ كتابة رسالة مخصصة...": {"color": "#7f7f7f", "message": ""}
    }

    selected_option = st.selectbox("اختر رسالة جاهزة للطلاب:", list(messages_options.keys()))
    selected_color = messages_options[selected_option]["color"]
    default_message = messages_options[selected_option]["message"]

    st.markdown(
        f"""
        <div style="display:flex;align-items:center;margin-bottom:15px; padding: 10px; background-color: #f8f9fa; border-radius: 8px;">
            <div style="width:15px;height:15px;background:{selected_color};border-radius:50%;margin-left:10px;"></div>
            <span style="font-size:15px;">اللون التعريفي للمادة المختارة</span>
        </div>
        """,
        unsafe_allow_html=True
    )

    if selected_option == "✏️ كتابة رسالة مخصصة...":
        custom_message = st.text_area("📝 اكتب رسالتك الخاصة هنا:", placeholder="اكتب رسالة شكر أو تعليمات...", height=120)
    else:
        custom_message = st.text_area("📝 محتوى الرسالة (يمكنك التعديل عليها):", value=default_message, height=120)

with tab_settings:
    st.markdown("#### ⚙️ خيارات الرفع والإخراج")
    option = st.radio("كيف تفضل إخراج الملفات النهائية؟", ["☁️ رفع إلى Google Drive + مشاركة تلقائية", "📦 تحميل كملف ZIP (مجلد لكل طالب)"])
    
    st.markdown("#### 🔐 خيارات الحماية")
    enable_password = st.checkbox("🔐 حماية ملفات الـ PDF بكلمة مرور (تشفير)", value=True)
    allow_download = st.checkbox("✅ السماح للطلاب بتنزيل الملف (في حال الرفع لـ Drive)", value=False)
    expiration_days = st.number_input("⏳ أيام صلاحية الرابط في Drive (0 = مفتوح دائم):", min_value=0, value=0, help="سيفقد الطالب الصلاحية تلقائياً بعد هذا العدد من الأيام.")

with tab_wm:
    st.markdown("#### 🎛️ التحكم الدقيق بالعلامة المائية")
    col_wm1, col_wm2 = st.columns(2)
    with col_wm1:
        wm_opacity = st.slider("الشفافية (Opacity):", min_value=0.01, max_value=1.0, value=0.12, step=0.01)
        wm_size = st.slider("حجم الخط (Font Size):", min_value=10, max_value=150, value=25, step=1)
    with col_wm2:
        wm_spacing = st.slider("المسافة بين التكرارات (Spacing):", min_value=50, max_value=600, value=200, step=10)
        wm_angle = st.slider("زاوية الميلان (Rotation):", min_value=0, max_value=90, value=35, step=1)
        
    st.markdown("---")
    show_qr_footer = st.checkbox("✅ إظهار كود الـ QR وحقوق النشر أسفل كل صفحة", value=True)


# =========================
# الخط العربي (Cairo)
# =========================
FONT_PATH = "Cairo-Regular.ttf"
try:
    pdfmetrics.registerFont(TTFont("Cairo", FONT_PATH))
except Exception as e:
    st.warning(f"⚠️ تعذر تسجيل الخط '{FONT_PATH}'. تأكد من وجود الملف.")

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
file_source = st.radio("اختر المصدر:", ["📁 رفع ملفات جديدة من جهازي", "☁️ اختيار من Google Drive (مكتبتي)"])

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
        sort_mode = st.radio("اختر طريقة الترتيب:", ["ترتيب تلقائي (حسب الاسم)", "ترتيب يدوي"])

        file_names = [f.name for f in uploaded_files]
        if sort_mode.startswith("ترتيب تلقائي"):
            sorted_files = sorted(uploaded_files, key=lambda f: f.name)
            st.success("✅ تم الترتيب تلقائيًا حسب اسم الملف.")
        else:
            custom_order = st.multiselect("🔀 رتب الملفات يدوياً (اسحب وأفلت):", file_names, default=file_names)
            if set(custom_order) == set(file_names):
                sorted_files = sorted(uploaded_files, key=lambda f: custom_order.index(f.name))
                st.success("✅ تم تطبيق الترتيب اليدوي بنجاح.")
            else:
                st.warning("⚠️ الرجاء التأكد من إضافة جميع الملفات للقائمة أعلاه للترتيب.")
                sorted_files = uploaded_files

        sorted_file_copies = [(file.name, file.read()) for file in sorted_files]

else:
    st.info("اختر ملفاتك مباشرة من مجلدات مكتبتك على Google Drive")

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

    col_a, col_b, col_c = st.columns([2, 1, 1])
    search_text = col_a.text_input("🔎 ابحث بالاسم (اختياري):", value="")
    kind_filter = col_b.selectbox("نوع العناصر:", ["All", "PDF", "Images"], index=0)
    page_size = col_c.selectbox("عدد النتائج بالصفحة:", [20, 50, 100], index=1)

    if "drive_page_token" not in st.session_state:
        st.session_state.drive_page_token = None
    if "last_page_tokens" not in st.session_state:
        st.session_state.last_page_tokens = []

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("🔄 تحديث النتائج"):
            st.session_state.drive_page_token = None
            st.session_state.last_page_tokens = []
    with c2:
        prev_clicked = st.button("⬅️ السابق", disabled=(len(st.session_state.last_page_tokens) == 0))
    with c3:
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
                if st.button("فتح المجلد", key=f"open_{f['id']}"):
                    st.session_state.lib_stack.append((f["id"], f["name"]))
                    st.session_state.drive_page_token = None
                    st.session_state.last_page_tokens = []
                    st.rerun()

    st.markdown("### 📄 الملفات")
    if not files:
        st.warning("لا توجد ملفات مطابقة. جرب تغيير الفلتر أو الدخول لمجلد آخر.")
    else:
        labels = [
            f"{it['name']} — {it.get('size','?')} bytes — {it.get('modifiedTime','')}"
            for it in files
        ]
        id_map = {labels[i]: files[i]["id"] for i in range(len(files))}
        name_map = {labels[i]: files[i]["name"] for i in range(len(files))}

        picked = st.multiselect("✅ اختر ملفات (اضغط لإضافة أكثر من ملف):", labels)

        if picked:
            drive_file_copies = []
            with st.spinner("⏳ جاري تحميل الملفات المختارة من Drive…"):
                for lab in picked:
                    fid = id_map[lab]
                    fname = name_map[lab]
                    blob = drive_download_file_bytes(drive_service, fid)
                    try:
                        _ = PdfReader(BytesIO(blob))
                        drive_file_copies.append((fname, blob))
                    except Exception:
                        st.warning(f"تجاهل '{fname}': يبدو أنه ليس PDF صالحًا.")
            sorted_file_copies = sorted(drive_file_copies, key=lambda x: x[0])
            st.success(f"تم تجهيز {len(sorted_file_copies)} ملف(ات) بنجاح.")

# =========================
# 📋 إدخال الأسماء (الاستخراج الذكي)
# =========================
st.markdown("## 📋 قائمة الطلاب (الإدخال الذكي)")
st.info("💡 **انسخ والصق مباشرة:** الصق قائمة الطلاب من الواتساب أو ملف نصي كيفما كانت. النظام سيبحث تلقائياً عن الإيميل ويفصل الاسم بكل ذكاء.")

raw_students_data = st.text_area("أدخل الأسماء والإيميلات هنا:", height=150)

students = []
if raw_students_data:
    for line in raw_students_data.splitlines():
        if not line.strip():
            continue
            
        # استخراج الإيميل باستخدام Regex ذكي
        email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', line)
        if email_match:
            email = email_match.group(0)
            
            # إزالة الإيميل من السطر لاستخراج الاسم
            name_raw = line.replace(email, '').strip()
            
            # تنظيف الاسم من الفواصل، والأقواس، والخطوط، والمسافات الزائدة
            name = re.sub(r'[|,\t\-\_()]+', ' ', name_raw).strip()
            name = re.sub(r'\s+', ' ', name)
            
            if name:
                students.append([name, email])

if students:
    st.markdown("---")
    st.subheader("👁️‍🗨️ معاينة البيانات المستخرجة")
    st.dataframe(pd.DataFrame(students, columns=["الاسم (المنظف)", "الإيميل (المستخرج)"]), use_container_width=True)
    st.success(f"📊 تم التعرف بنجاح على: {len(students)} طالب جاهز للمعالجة.")

# =========================
# أدوات إرسال و PDF
# =========================
def send_telegram_message(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        requests.post(url, data=data, timeout=15)
    except Exception:
        pass

def send_email_to_student(name, email, password, link_block_text, extra_message=""):
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_SENDER
        msg["To"] = email
        msg["Subject"] = "🔐 ملفاتك الجامعية جاهزة - eLite Acadimea"

        links_html = link_block_text.replace("\n", "<br>")
        links_html = re.sub(
            r"(https?://[^\s<]+)", 
            r'<a href="\1" style="display: inline-block; padding: 6px 12px; margin-top: 5px; background-color: #0056b3; color: white; text-decoration: none; border-radius: 5px; font-size: 14px; font-weight: bold;">فتح الملف 🔗</a>', 
            links_html
        )

        if extra_message.strip():
            extra_html = f"""
            <div style="background-color: #fff3cd; color: #856404; padding: 15px; border-left: 4px solid #ffeeba; margin-top: 20px; border-radius: 4px;">
                <strong>📩 ملاحظة من الإدارة:</strong><br>{extra_message.strip()}
            </div>
            """
        else:
            extra_html = ""

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
            <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
                
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
    except Exception:
        pass

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

def precreate_drive_pdf(filename: str, email: str, thread_drive_service, exp_days: int):
    temp_placeholder = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    create_placeholder_pdf(temp_placeholder.name)
    
    file_metadata = {
        "name": filename,
        "parents": [FOLDER_ID],
        "mimeType": "application/pdf",
    }
    
    media = MediaFileUpload(temp_placeholder.name, mimetype="application/pdf", resumable=False)
    
    try:
        created = thread_drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id",
            supportsAllDrives=True
        ).execute()
        
        file_id = created["id"]
        link = f"https://drive.google.com/file/d/{file_id}/view"

        if email and re.match(r"[^@]+@[^@]+\.[^@]+", email.strip()):
            try:
                perm_body = {
                    "type": "user",
                    "role": "reader",
                    "emailAddress": email.strip()
                }
                
                if exp_days > 0:
                    perm_body["expirationTime"] = (datetime.utcnow() + timedelta(days=exp_days)).isoformat() + "Z"
                    
                thread_drive_service.permissions().create(
                    fileId=file_id,
                    body=perm_body,
                    sendNotificationEmail=False,
                    supportsAllDrives=True
                ).execute()
            except HttpError:
                pass

        return file_id, link
    except HttpError:
        return None, ""
    finally:
        try:
            os.unlink(temp_placeholder.name)
        except Exception:
            pass

def finalize_drive_pdf(file_id: str, final_path: str, allow_download: bool, thread_drive_service) -> str:
    if not file_id:
        return ""
    try:
        media = MediaFileUpload(final_path, mimetype="application/pdf", resumable=False)
        thread_drive_service.files().update(
            fileId=file_id,
            media_body=media,
            supportsAllDrives=True
        ).execute()

        thread_drive_service.files().update(
            fileId=file_id,
            body={
                "viewersCanCopyContent": bool(allow_download),
                "copyRequiresWriterPermission": (not allow_download),
            },
            supportsAllDrives=True
        ).execute()

        return f"https://drive.google.com/file/d/{file_id}/view"
    except HttpError:
        return ""

def create_dynamic_watermark_page(name: str, link: str, w=letter[0], h=letter[1], opacity=0.12, size=25, spacing=200, angle=35, show_footer=True):
    """
    علامة مائية يتم التحكم بها عبر الواجهة، مع ضبط النص والـ QR أسفل الصفحة لمنع التداخل
    """
    packet = BytesIO()
    c = canvas.Canvas(packet, pagesize=(w, h))

    raw_text = f"خاص بـ {name}"
    bidi_text = get_display(arabic_reshaper.reshape(raw_text))

    try:
        c.setFillAlpha(opacity)
        alpha_supported = True
    except Exception:
        from reportlab.lib.colors import Color
        c.setFillColor(Color(0.6, 0.6, 0.6))
        alpha_supported = False

    c.setFont("Cairo", size)

    # حلقة التكرار للعلامة المائية
    for x in range(-int(w), int(w)*2, spacing):
        for y in range(-int(h), int(h)*2, spacing):
            c.saveState()
            c.translate(x, y)
            c.rotate(angle)
            c.drawString(0, 0, bidi_text)
            c.restoreState()

    if alpha_supported:
        c.setFillAlpha(1)

    if show_footer:
        # 1. النص التحذيري أسفل الوسط (صغير ولا يأخذ مساحة)
        small_raw = "هذا الملف محمي ولا يجوز تداوله أو طباعته إلا بإذن خطي"
        small_bidi = get_display(arabic_reshaper.reshape(small_raw))
        c.setFont("Cairo", 9)
        c.drawCentredString(w / 2.0, 12, small_bidi)

        # 2. كود الـ QR بحجم صغير وفي أقصى الزاوية السفلية لمنع حجب الأسئلة
        try:
            qr_img = generate_qr_code(link)
            c.drawImage(qr_img, w - 50, 8, width=40, height=40)
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

    if password:
        owner_password = secrets.token_urlsafe(16)
        try:
            writer.encrypt(user_password=password, owner_password=owner_password, use_128bit=True)
        except TypeError:
            writer.encrypt(password, owner_password)

    with open(output_path, "wb") as f:
        writer.write(f)

# =========================
# دالة معالجة الطالب (Thread Target)
# =========================
def process_single_student_thread(idx, name, email, file_copies, mode, allow_download, enable_password, temp_dir, exp_days, wm_op, wm_sz, wm_sp, wm_ang, show_ftr):
    if mode.startswith("☁️"):
        thread_drive = build("drive", "v3", credentials=creds)
    else:
        thread_drive = None
        
    safe_name = name.replace(" ", "_").replace("+", "plus")
    
    if enable_password:
        pdf_password = name.replace(" ", "") + "@elite"
        display_password = pdf_password
    else:
        pdf_password = ""
        display_password = "بدون باسورد"

    student_links = []
    generated_pdfs = []

    for file_name, file_bytes in file_copies:
        base_filename = os.path.splitext(file_name)[0]
        final_name = f"{idx+1:02d} - {safe_name} - {base_filename}.pdf"

        file_id = None
        drive_link = "https://pdf.eliteacadimea.com/placeholder"
        
        if mode.startswith("☁️"):
            file_id, drive_link = precreate_drive_pdf(final_name, email, thread_drive, exp_days)
            if not file_id:
                continue

        temp_input = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        temp_input.write(file_bytes)
        temp_input.close()

        raw_path = os.path.join(temp_dir, f"{safe_name}_{base_filename}_raw.pdf")
        protected_path = os.path.join(temp_dir, f"{safe_name}_{base_filename}.pdf")

        reader = PdfReader(temp_input.name)
        writer = PdfWriter()
        
        for page in reader.pages:
            w = float(page.mediabox.width)
            h = float(page.mediabox.height)
            watermark_page = create_dynamic_watermark_page(
                name, drive_link, w, h, 
                opacity=wm_op, size=wm_sz, spacing=wm_sp, angle=wm_ang, show_footer=show_ftr
            )
            page.merge_page(watermark_page)
            writer.add_page(page)

        with open(raw_path, "wb") as f_out:
            writer.write(f_out)

        apply_pdf_protection(raw_path, protected_path, pdf_password)
        generated_pdfs.append(protected_path)

        if mode.startswith("☁️"):
            final_link = finalize_drive_pdf(file_id, protected_path, allow_download, thread_drive)
            student_links.append(final_link)

    if mode.startswith("☁️") and student_links:
        links_msg = "\n".join([
            f"{i+1}. {os.path.basename(fc[0])}\n🔗 {lnk}"
            for i, (fc, lnk) in enumerate(zip(file_copies, student_links))
        ])
        
        if enable_password:
            message = f"📥 الملفات الخاصة بـ {name}:\n🔑 الباسورد: {display_password}\n{links_msg}"
        else:
            message = f"📥 الملفات الخاصة بـ {name}:\n🔓 (بدون باسورد)\n{links_msg}"
            
        send_telegram_message(message)
        send_email_to_student(name, email, pdf_password, links_msg, custom_message)

    row_data = [name, email, display_password, " | ".join(student_links), datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
    return row_data, generated_pdfs, safe_name

# =========================
# زر التشغيل (المعالج المتوازي مع المجلدات)
# =========================
CHECKPOINT_FILE = "elite_checkpoint.json"

if sorted_file_copies and students:
    completed_emails = []
    
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, "r") as f:
            completed_emails = json.load(f)
            
    if completed_emails:
        st.warning(f"⚠️ نظام الاستئناف الذكي: يوجد عملية سابقة توقفت. تم العثور على {len(completed_emails)} طالب استلموا بالفعل ولن يتم الإرسال لهم مجدداً.")
        if st.button("🗑️ مسح الذاكرة والبدء من جديد لجميع الطلاب"):
            os.remove(CHECKPOINT_FILE)
            st.rerun()
            
    students_to_process = [s for s in students if s[1] not in completed_emails]

    if st.button("🚀 بدء العملية وتجهيز الملفات", type="primary", use_container_width=True):
        if not students_to_process:
            st.success("✅ جميع الطلاب في هذه القائمة تم إرسال ملفاتهم مسبقاً!")
            st.stop()

        with st.spinner("⏳ جاري تنفيذ العملية بوضع المعالجة المتوازية للسرعة القصوى..."):
            temp_dir = tempfile.mkdtemp()
            password_file_path = os.path.join(temp_dir, "passwords_and_links.csv")
            
            sheet_data_to_append = []
            student_files_map = [] 
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            eta_text = st.empty()
            
            total_students = len(students_to_process)
            start_time = time.time()
            
            # المعالجة المتوازية للسرعة (4 طلاب في نفس اللحظة)
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                future_to_student = {
                    executor.submit(
                        process_single_student_thread, 
                        idx, s[0], s[1], sorted_file_copies, option, allow_download, enable_password, temp_dir, expiration_days,
                        wm_opacity, wm_size, wm_spacing, wm_angle, show_qr_footer
                    ): s for idx, s in enumerate(students_to_process)
                }
                
                completed_count = 0
                for future in concurrent.futures.as_completed(future_to_student):
                    student = future_to_student[future]
                    try:
                        row_data, pdf_paths, safe_name = future.result()
                        sheet_data_to_append.append(row_data)
                        
                        # تجميع الملفات لغايات مجلدات الـ ZIP
                        student_files_map.append((safe_name, pdf_paths))
                        
                        completed_emails.append(student[1])
                        with open(CHECKPOINT_FILE, "w") as f:
                            json.dump(completed_emails, f)
                            
                    except Exception as exc:
                        st.error(f"❌ خطأ مع الطالب {student[0]}: {exc}")
                    
                    completed_count += 1
                    progress_bar.progress(completed_count / total_students)
                    
                    elapsed = time.time() - start_time
                    avg_time = elapsed / completed_count
                    remaining = total_students - completed_count
                    eta_secs = int(avg_time * remaining)
                    
                    status_text.markdown(f"**🔄 جاري المعالجة... إنجاز {completed_count} من {total_students}**")
                    eta_text.markdown(f"**⏳ الوقت المتبقي تقريباً:** `{timedelta(seconds=eta_secs)}`")

            # كتابة ملف الروابط والباسوردات
            with open(password_file_path, "w", newline="", encoding="utf-8") as pw_file:
                writer_csv = csv.writer(pw_file)
                writer_csv.writerow(["Student Name", "Email", "Password", "Drive Links"])
                for row in sheet_data_to_append:
                    writer_csv.writerow(row[:4])

            # تحديث شيت جوجل
            if sheet_data_to_append:
                status_text.text("💾 جاري حفظ السجلات في مساحة التخزين السحابي...")
                try:
                    sheet.append_rows(sheet_data_to_append)
                except Exception as e:
                    st.warning(f"⚠️ فشل إضافة السجل إلى الشيت: {e}")
            
            if os.path.exists(CHECKPOINT_FILE):
                os.remove(CHECKPOINT_FILE)

            status_text.empty()
            eta_text.empty()

            if option.startswith("📦"):
                zip_path = os.path.join(temp_dir, "Pro_Students_Files.zip")
                with ZipFile(zip_path, "w") as zipf:
                    # بناء مجلدات داخل الـ ZIP لكل طالب
                    for student_folder_name, paths in student_files_map:
                        for fpath in paths:
                            zip_internal_path = f"{student_folder_name}/{os.path.basename(fpath)}"
                            zipf.write(fpath, arcname=zip_internal_path)
                    
                    zipf.write(password_file_path, arcname="All_Passwords_and_Links.csv")
                
                with open(zip_path, "rb") as f:
                    st.download_button("📦 تحميل الملفات (مجلدات منظمة لكل طالب)", f.read(), file_name="Students_Folders.zip", type="primary", use_container_width=True)
            else:
                with open(password_file_path, "rb") as f:
                    st.download_button("📄 تحميل ملف كلمات السر والروابط (CSV)", f.read(), file_name="passwords_and_links.csv", type="primary", use_container_width=True)

            st.success("🎉 اكتملت العملية بنجاح! تم تجهيز الملفات بإحترافية عالية، يمكنك الآن تحميلها عبر الزر أعلاه.")
            st.balloons()

st.markdown("---")
st.caption("🛡️ تم تطوير هذا النظام بواسطة د. محمد العمري - جميع الحقوق محفوظة لـ eLite Acadimea")
