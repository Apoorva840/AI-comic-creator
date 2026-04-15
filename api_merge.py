import os
import io
import time
import textwrap
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from pypdf import PdfWriter, PdfReader
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

# --- CONFIGURATION ---
SCOPES = ['https://www.googleapis.com/auth/drive']
FOLDER_NAME = 'Comic_Factory_Outputs' 
TARGET_PAGES = 4  # Set to exactly what you have in your folder
# ---------------------

def get_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('drive', 'v3', credentials=creds)

def create_layout_page(img_page, page_num, total_pages, filename):
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=A4)
    width, height = A4
    margin_left = width * 0.05 
    content_width = width * 0.9 
    
    clean_name = filename.replace('.pdf', '')
    if "__" in clean_name:
        parts = clean_name.split("__")
        dynamic_title = parts[0].replace('_', ' ')
        story_part = next((p for p in parts if p.startswith("Text_")), "Text_")
        story_text = story_part.replace('Text_', '').replace('_', ' ')
    else:
        dynamic_title = "AI COMPUTER VISION"
        story_text = clean_name.replace('_', ' ')

    can.setFont("Helvetica-Bold", 16)
    can.drawString(margin_left, height - 60, dynamic_title.upper())
    
    can.setFont("Helvetica", 14) 
    wrapped_lines = textwrap.wrap(story_text, width=68) 
    text_y = 175 
    for line in wrapped_lines:
        can.drawString(margin_left, text_y, line) 
        text_y -= 18 
    
    can.setFont("Helvetica-Bold", 10)
    can.drawRightString(width - margin_left, 30, f"Page {page_num} of {total_pages}")
    
    can.save()
    packet.seek(0)
    layout_overlay = PdfReader(packet).pages[0]
    img_page.scale_to(content_width, height * 0.60) 
    layout_overlay.merge_translated_page(img_page, margin_left, 215)
    return layout_overlay

def main():
    service = get_service()
    query = f"name = '{FOLDER_NAME}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    results = service.files().list(q=query).execute()
    if not results.get('files'):
        print(f"❌ Folder '{FOLDER_NAME}' not found.")
        return
        
    folder_id = results.get('files', [])[0]['id']
    print(f"🚀 Manual Override: Merging {TARGET_PAGES} existing pages...")

    file_query = f"'{folder_id}' in parents and mimeType='application/pdf' and trashed=false"
    results = service.files().list(q=file_query, fields="files(id, name)").execute()
    items = results.get('files', [])
    
    if len(items) >= TARGET_PAGES:
        items.sort(key=lambda x: x['name'])
        writer = PdfWriter()
        for i, item in enumerate(items[:TARGET_PAGES]):
            print(f"📥 Processing Page {i+1}...")
            request = service.files().get_media(fileId=item['id'])
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
            fh.seek(0)
            reader = PdfReader(fh)
            writer.add_page(create_layout_page(reader.pages[0], i+1, TARGET_PAGES, item['name']))
        
        output_name = f"Computer_Vision_Sample_4Pages.pdf"
        with open(output_name, "wb") as output:
            writer.write(output)
        print(f"✨ SUCCESS! '{output_name}' created with 4 pages.")
    else:
        print(f"⚠️ Only found {len(items)} files, need {TARGET_PAGES}.")

if __name__ == '__main__':
    main()