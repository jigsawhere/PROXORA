import logging
import os
import sys
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup,
WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, filters,
ContextTypes, CallbackQueryHandler
from telegram.error import Conflict
 # Add the script's directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
 # Import all necessary API keys from config.py
from config import TELEGRAM_BOT_TOKEN, GEMINI_API_KEY, PLAYHT_API_KEY
import io
import requests # Import requests for API calls
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.enums import TA_CENTER
from docx import Document
import asyncio
import re
 # Configure logging
logging.basicConfig(
format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
level=logging.INFO
)
logger = logging.getLogger(__name__)
 import google.generativeai as genai
 # --- AI Model Integration ---
genai.configure(api_key=GEMINI_API_KEY)
 def generate_story_with_ai(prompt: str, full_markdown_mode: bool = False) ->
tuple[str | None, str | None]:
"""
Generates a story based on the prompt using Gemini Flash.
If full_markdown_mode is True, expects the AI to return the complete markdown
story. based  """
try:
model = genai.GenerativeModel('gemini-1.5-flash')
if full_markdown_mode:
# In full markdown mode, send the exact prompt and expect the full story back
response = model.generate_content(prompt,
generation_config=genai.types.GenerationConfig(
candidate_count=1,
max_output_tokens=2000,
temperature=0.7
))
full_text = response.text.strip()
return None, full_text # Return None for title, as full_text is the complete story
else:
# Original behavior: generate title and body separately
response = model.generate_content(f"Generate a story with a title and body
on the following prompt: {prompt}\n\nTitle:",
generation_config=genai.types.GenerationConfig(
candidate_count=1,
max_output_tokens=2000,
temperature=0.7
))
full_text = response.text.strip()
if "Title:" in full_text and "Story:" in full_text:
parts = full_text.split("Story:", 1)
title_line = parts[0].replace("Title:", "").strip()
story_body = parts[1].strip()
title = title_line.split('\n')[0].strip()
elif "\n\n" in full_text:
lines = full_text.split('\n\n', 1)
title = lines[0].strip()
story_body = lines[1].strip()
else:
title = "Generated Story"
story_body = full_text
return title, story_body
except Exception as e:
logger.error(f"Error generating story with Gemini: {e}")
return None, None def generate_ebook_with_ai(topic: str, language: str = "en") -> str:
"""
Generates educational material based on the topic using Gemini Flash.
"""
ebook_prompt = f'''Generate an educational ebook content about: {topic} in
{language}.
Include a title, introduction, a few chapters, and a conclusion.
Format in Markdown.
 📌 Output Requirements:
- Title (bold, 3–6 words)
- One-line summary in _italics_
- Full ebook content in short, poetic paragraphs
- Include vivid sensory detail
- End with a twist or emotional resolution
 🎨 Style Guide:
- Avoid clichés
- Include internal thoughts and subtle world-building
- Use descriptive metaphors or imagery
- Break long sections with logical paragraphing
- Optionally use emoji section breaks like 🌌, 🚀, 🪐
 Respond only with the final ebook in Markdown. Do not include instructions, tags, or
notes.'''
  _, ebook_content = retry_story_generation(ebook_prompt, 1,
full_markdown_mode=True)
return ebook_content if ebook_content else "**Error Generating
Ebook**\n\n_Could not generate the ebook. Please try again with a different topic._"
 def retry_story_generation(prompt: str, attempt: int, full_markdown_mode: bool =
False) -> tuple[str | None, str | None]:
"""
Retries story generation. This function now directly calls generate_story_with_ai
without rephrasing, as the core generation function is expected to be robust.
"""
logger.info(f"Attempting AI generation (attempt {attempt}) with prompt:
{prompt}, full_markdown_mode: {full_markdown_mode}")
title, story_body = generate_story_with_ai(prompt, full_markdown_mode)
if (title and story_body) or (full_markdown_mode and story_body):
return title, story_body
elif attempt < 3: # Allow a few retries in case of initial failure from
generate_story_with_ai
return retry_story_generation(prompt, attempt + 1, full_markdown_mode)
else:
if full_markdown_mode:
return None, "**Error Generating Story**\n\n_Could not generate the story.
Please try again with a different prompt._"
else:
return "A Mysterious Tale", "Once upon a time, a story unfolded that defied all
expectations. The end."
 # --- PDF/DOCX/TXT Export Functions ---
def create_pdf(content: str, filename: str):
doc = SimpleDocTemplate(filename, pagesize=letter)
styles = getSampleStyleSheet()
  title_style = styles['h1']
title_style.alignment = TA_CENTER
body_style = styles['Normal']
  elements = []
lines = content.split('\n')
  # Attempt to extract title from markdown (bolded or heading)
extracted_title = "Generated Document"
content_start_index = 0
  # Check for bolded title (e.g., **Title**)
title_match_bold = re.match(r'^\s*#*\s*\*\*(.*?)\*\*', lines[0], re.MULTILINE)
if title_match_bold:
extracted_title = title_match_bold.group(1).strip()
content_start_index = 1 # Skip the title line
else:
# Check for heading title (e.g., # Title)
title_match_heading = re.match(r'^\s*#+\s*(.*?)\s*$', lines[0], re.MULTILINE)
if title_match_heading:
extracted_title = title_match_heading.group(1).strip()
content_start_index = 1 # Skip the title line
  elements.append(Paragraph(extracted_title, title_style))elements.append(Spacer(1, 0.2 * 100))
  for line in lines[content_start_index:]:
if line.strip():
# Convert markdown bold/italic to HTML bold/italic for ReportLab
line = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', line) # Bold
line = re.sub(r'\_(.*?)\_', r'<i>\1</i>', line) # Italic
  # Handle chapters/sections as bold
if line.startswith("Chapter") or line.startswith("Introduction") or
line.startswith("Conclusion"):
elements.append(Paragraph(f"<b>{line}</b>", body_style))
else:
elements.append(Paragraph(line, body_style))
elements.append(Spacer(1, 0.1 * 100))
else:
elements.append(Spacer(1, 0.1 * 100))
  doc.build(elements)
 def create_docx(content: str, filename: str):
document = Document()
document.add_paragraph(content)
document.save(filename)
 def create_txt(content: str, filename: str):
with open(filename, 'w', encoding='utf-8') as f:
f.write(content)
 # --- Telegram Bot Command Handlers ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) 
> None:
# --- WebApp Button Integration ---
keyboard = [
[InlineKeyboardButton("🚀 Launch PROXORA WebApp",
web_app=WebAppInfo(url="https://jigsawhere.github.io/PROXORA/"))],
[
InlineKeyboardButton("📚 Story", callback_data='command_story'),
InlineKeyboardButton("📖 Ebook", callback_data='command_ebook'),
InlineKeyboardButton("✍️ Writer", callback_data='command_writer')
],
[InlineKeyboardButton("🗣️ Speak", callback_data='command_speak'),
InlineKeyboardButton("🎁 Refer", callback_data='command_refer'),
InlineKeyboardButton("📺 Watch Ad", callback_data='command_watchad')
],
[
InlineKeyboardButton("💳 Plans", callback_data='command_plans'),
InlineKeyboardButton("👤 Profile", callback_data='command_profile'),
InlineKeyboardButton("📊 Progress", callback_data='command_progress')
],
[
InlineKeyboardButton("❓ Help", callback_data='command_help'),
InlineKeyboardButton("🎮 Play", callback_data='command_play')
]
]
  reply_markup = InlineKeyboardMarkup(keyboard)
  welcome_message = (
"Click below to open PROXORA AI WebApp or use the shortcut buttons:\n\n"
"🧙‍♂️✨ Welcome to PROXORA, your ultra-intelligent storytelling and content
generation assistant! 📘\n\n"
"Here are the commands you can use:\n"
"📚 /story - Prompt me for a story input and I'll generate a full story with emojis
\n"
"📖 /ebook - Generate educational material on any topic.\n"
"✍️ /writer - Choose a tone (funny, serious, fantasy) and topic for your story.\n"
"🗣️ /speak - Activate voice chat / TTS (if enabled).\n"
"🎁 /refer - Get your referral link and check bonus status.\n"
"📺 /watchad - Watch ads for more credits.\n"
"💳 /plans - See premium pricing and features.\n"
"👤 /profile - View your books made, credits left, plan, and referral stats.\n"
"📊 /progress - Check your book usage count, quota remaining, and total stories
\n"
"❓ /help - Get a smart guide on how to use each feature.\n"
"🎮 /play - Enter gamified creative mode!\n\n"
"Let's make magic! What story shall we create today? ✨"
)
await update.effective_message.reply_text(welcome_message,
reply_markup=reply_markup)
 # Supported languages for content generationSUPPORTED_LANGUAGES = {
"English": "en", "Spanish": "es", "French": "fr", "German": "de", "Italian": "it",
"Portuguese": "pt", "Japanese": "ja", "Korean": "ko", "Chinese (Simplified)": "zh
CN",
"Russian": "ru", "Arabic": "ar", "Hindi": "hi", "Bengali": "bn", "Urdu": "ur",
"Turkish": "tr", "Vietnamese": "vi", "Thai": "th", "Indonesian": "id", "Dutch": "nl",
"Swedish": "sv", "Polish": "pl", "Ukrainian": "uk", "Romanian": "ro", "Greek": "el",
"Hebrew": "he", "Malay": "ms", "Filipino": "fil", "Swahili": "sw", "Zulu": "zu",
"Amharic": "am", "Nepali": "ne", "Sinhala": "si", "Tamil": "ta", "Telugu": "te",
"Kannada": "kn", "Malayalam": "ml", "Gujarati": "gu", "Punjabi": "pa", "Oriya": "or",
"Assamese": "as", "Kashmiri": "ks", "Konkani": "kok", "Maithili": "mai", "Manipuri":
"mni",
"Marathi": "mr", "Sindhi": "sd", "Sanskrit": "sa", "Dogri": "doi", "Bodo": "brx",
"Santali": "sat", "Santhali": "sat", "Khasi": "kha", "Mizo": "lus", "Garo": "grt",
"Kokborok": "kok", "Bhojpuri": "bho", "Haryanvi": "bgc", "Rajasthani": "raj",
"Magahi": "mag",
"Chhattisgarhi": "hne", "Awadhi": "awa", "Marwari": "mwr", "Bundeli": "bns",
"Bagheli": "bgp",
"Kangri": "xnr", "Kumaoni": "kuma", "Garhwali": "gbm", "Himachali": "him", "Dogri
(India)": "dgo",
"Kashmiri (India)": "kas", "Nepali (India)": "nep", "Manipuri (India)": "mni", "Bodo
(India)": "brx",
"Santali (India)": "sat", "Santhali (India)": "sat", "Khasi (India)": "kha", "Mizo (India)":
"lus",
"Garo (India)": "grt", "Kokborok (India)": "kok", "Bhojpuri (India)": "bho", "Haryanvi
(India)": "bgc",
"Rajasthani (India)": "raj", "Magahi (India)": "mag", "Chhattisgarhi (India)": "hne",
"Awadhi (India)": "awa",
"Marwari (India)": "mwr", "Bundeli (India)": "bns", "Bagheli (India)": "bgp", "Kangri
(India)": "xnr",
"Kumaoni (India)": "kuma", "Garhwali (India)": "gbm", "Himachali (India)": "him"
}
 async def send_language_selection(update: Update, context:
ContextTypes.DEFAULT_TYPE, next_state: str) -> None:
keyboard = []
# Create a 3-column layout for language buttons
languages = list(SUPPORTED_LANGUAGES.keys())
for i in range(0, len(languages), 3):
row = []
for lang in languages[i:i+3]:
row.append(InlineKeyboardButton(lang,callback_data=f'lang_{SUPPORTED_LANGUAGES[lang]}'))
keyboard.append(row)
  reply_markup = InlineKeyboardMarkup(keyboard)
await update.effective_message.reply_text("Choose a language for your content:
🌐", reply_markup=reply_markup)
context.user_data['state'] = next_state
 async def story_command(update: Update, context: ContextTypes.DEFAULT_TYPE) 
> None:
await send_language_selection(update, context,
'waiting_for_story_language_selection')
 async def ebook_command(update: Update, context: ContextTypes.DEFAULT_TYPE)
-> None:
await send_language_selection(update, context,
'waiting_for_ebook_language_selection')
 async def writer_command(update: Update, context: ContextTypes.DEFAULT_TYPE)
-> None:
await send_language_selection(update, context,
'waiting_for_writer_language_selection')
 # --- Play.ht API Integration ---
def generate_audio_with_playht(text: str, voice_id: str) -> str | None:
"""
Generates audio from text using Play.ht API.
Returns the path to the generated audio file or None on failure.
"""
url = "https://api.play.ht/api/v2/tts" # Play.ht TTS endpoint
headers = {
"Authorization": f"Bearer {PLAYHT_API_KEY}",
"X-User-Id": "YOUR_USER_ID", # Play.ht often requires a User ID, replace with
actual if available
"Content-Type": "application/json"
}
payload = {
"text": text,
"voice": voice_id,
"output_format": "mp3",
"quality": "medium" # Example quality setting
try:
response = requests.post(url, headers=headers, json=payload)
response.raise_for_status() # Raise an exception for HTTP errors
  # Play.ht API returns a JSON with 'audioUrl' or 'url'
response_json = response.json()
audio_url = response_json.get('audioUrl') or response_json.get('url')
if audio_url:
audio_response = requests.get(audio_url)
audio_response.raise_for_status()
audio_data = audio_response.content
audio_filename = f"generated_audio_{voice_id}_{hash(text)}.mp3"
with open(audio_filename, 'wb') as f:
f.write(audio_data)
return audio_filename
else:
logger.error(f"Play.ht API did not return an audio URL: {response_json}")
return None
except requests.exceptions.RequestException as e:
logger.error(f"Error generating audio with Play.ht API: {e}")
return None
 async def speak_command(update: Update, context: ContextTypes.DEFAULT_TYPE)
-> None:
keyboard = [
[InlineKeyboardButton("Male Voice 👨", callback_data='voice_male')],
[InlineKeyboardButton("Female Voice 👩", callback_data='voice_female')],
]
reply_markup = InlineKeyboardMarkup(keyboard)
await update.effective_message.reply_text("Choose a voice for Text-to-Speech:
🗣️", reply_markup=reply_markup)
context.user_data['state'] = 'waiting_for_tts_voice_selection'
 async def refer_command(update: Update, context: ContextTypes.DEFAULT_TYPE) 
> None:
referral_link = "https://t.me/proxora_bot?start=YOUR_REFERRAL_CODE" #
Placeholder
bonus_status = "You have 5 bonus credits! 🎉" # Placeholder
await update.effective_message.reply_text(f"🎁 Your referral link: {referral_link
\n\n{bonus_status}")
 async def watchad_command(update: Update, context:ContextTypes.DEFAULT_TYPE) -> None:
# Simulate adding credits
await update.effective_message.reply_text("📺 Ad watched! You've earned 10
credits. Enjoy! 🎉")
 async def plans_command(update: Update, context: ContextTypes.DEFAULT_TYPE)
-> None:
plans_info = (
"💳 PROXORA Premium Plans:\n\n"
"✨ Basic Plan: $4.99 USD / ₹399 INR / €4.49 EUR per month\n"
" - Unlimited stories, ad-free.\n\n"
"🌟 Pro Plan: $9.99 USD / ₹799 INR / €8.99 EUR per month\n"
" - All Basic features + advanced tools, illustrations, speed boosts.\n\n"
"Unlock unlimited creativity! 🚀"
)
await update.effective_message.reply_text(plans_info)
 async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE)
-> None:
books_made = 15
credits_left = 50
plan = "Free Tier"
referral_stats = "2 successful referrals"
  profile_info = (
f"👤 Your PROXORA Profile:\n\n"
f"📚 Books Generated: {books_made}\n"
f"💰 Credits Left: {credits_left}\n"
f"✨ Current Plan: {plan}\n"
f"🎁 Referral Stats: {referral_stats}\n\n"
f"Keep creating! 🌟"
)
await update.effective_message.reply_text(profile_info)
 async def progress_command(update: Update, context:
ContextTypes.DEFAULT_TYPE) -> None:
book_usage_count = 10
quota_remaining = "56 free books"
total_stories_generated = 15
  progress_info = (
f"📊 Your PROXORA Progress:\n\nf"📖 Books Used This Cycle: {book_usage_count}\n"
f"⏳ Quota Remaining: {quota_remaining}\n"
f"✨ Total Stories Generated: {total_stories_generated}\n\n"
f"You're doing great! Keep going! 💪"
)
await update.effective_message.reply_text(progress_info)
 async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) 
> None:
help_message = (
"❓ PROXORA Smart Guide:\n\n"
"📚 /story: Use this to generate a new story. After typing /story, "
"I'll ask you for a prompt. Just type your idea, like 'a detective solving a mystery
in space' "
"and I'll craft a unique tale for you! ✨\n\n"
"📖 /ebook: Want to learn something new? Use /ebook followed by a topic, "
"e.g., 'The Solar System', and I'll create an educational ebook for you. 💡\n\n"
"✍️ /writer: This command lets you customize your story's tone. "
"I'll give you options like Funny, Serious, or Fantasy. Choose one, then provide
your topic! 🎭\n\n"
"And so on for other commands... (Full help text would be here) 🚀"
)
await update.effective_message.reply_text(help_message)
 async def play_command(update: Update, context: ContextTypes.DEFAULT_TYPE) 
> None:
await update.effective_message.reply_text("🎮 Welcome to the Gamified Creative
Mode! What kind of game or interactive story would you like to play? (e.g., 'a mystery
riddle', 'a choose-your-own-adventure start', 'a quick trivia game') 🚀")
context.user_data['state'] = 'waiting_for_play_prompt'
 # --- WebApp Data Handler ---
async def handle_webapp_data(update: Update, context:
ContextTypes.DEFAULT_TYPE):
if update.effective_message.web_app_data:
data = update.effective_message.web_app_data.data
await update.effective_message.reply_text(f"✅ Data received from WebApp:
`{data}`", parse_mode='Markdown')
else:
await update.effective_message.reply_text("No data received from WebApp.")
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE)
-> None:
user_text = update.effective_message.text
chat_id = update.effective_message.chat_id
state = context.user_data.get('state')
  title, body = None, None
story_markdown = None # To hold the full markdown story
content_type = "story"
  selected_language = context.user_data.get('selected_language', 'en') # Default to
English
  if state == 'waiting_for_detailed_story_prompt':
story_length = context.user_data.get('story_length', 'short') # Default to short
word_count = 250
if story_length == 'medium':
word_count = 500
elif story_length == 'long':
word_count = 1000
  await update.effective_message.reply_text(f"Generating your {story_length}
story in {selected_language.upper()} about: {user_text}... Please wait! ⏳")
full_prompt = f'''Based on the user input "{user_text}", generate a complete
short story in {selected_language}.
 📝 User Prompt:
"{user_text}"
 📌 Output Requirements:
- Word count: Exactly {word_count} words
- Genre: Dark Fantasy / Science Fiction
- Tone: Cinematic, eerie, emotional
- Format in Markdown with the following structure:
• Title (bold, 3–6 words)
• One-line summary in _italics_
• Full story in short, poetic paragraphs
• Include vivid sensory detail
• End with a twist or emotional resolution
 🎨 Style Guide:
- Avoid clichés- Include internal thoughts and subtle world-building
- Use descriptive metaphors or imagery
- Break long sections with logical paragraphing
- Optionally use emoji section breaks like 🌌, 🚀, 🪐
 Respond only with the final story in Markdown. Do not include instructions, tags, or
notes.'''
  _, story_markdown = retry_story_generation(full_prompt, 1,
full_markdown_mode=True)
  if story_markdown:
# Truncate if too long for direct message, but always offer download
if len(story_markdown) > 2000: # Telegram message limit is 4096, but 2000 is
safer for readability + buttons
display_text = story_markdown[:1900] + "\n\n...[Story continues in
download]..."
await update.effective_message.reply_text(display_text,
parse_mode='Markdown')
else:
await update.effective_message.reply_text(story_markdown,
parse_mode='Markdown')
  # Store the full markdown for download
# Extract title and body from markdown for consistent storage
title_match = re.match(r'^\s*#*\s*\*\*(.*?)\*\*', story_markdown,
re.MULTILINE)
summary_match = re.match(r'^\s*\_(.*?)\_', story_markdown, re.MULTILINE)
  extracted_title = title_match.group(1).strip() if title_match else "Generated
Story"
# For body, remove title and summary lines, then clean up
extracted_body = story_markdown
if title_match:
extracted_body = extracted_body[title_match.end():].strip()
if summary_match:
extracted_body = extracted_body[summary_match.end():].strip()
  context.user_data['last_content'] = {'title': extracted_title,
'body': story_markdown, # Store full markdown for PDF
generation
'type': content_type}
  keyboard = [
[
InlineKeyboardButton("📄 📥 Download PDF",
callback_data='download_pdf'),
InlineKeyboardButton("📄 📥 Download DOCX",
callback_data='download_docx'),
InlineKeyboardButton("📄 📥 Download TXT",
callback_data='download_txt'),
],
[
InlineKeyboardButton("📚 Want more? Try /story, /writer, or /play",
callback_data='null'),
],
[
InlineKeyboardButton("🎁 Invite a friend with /refer to earn bonus
credits!", callback_data='null')
]
]
reply_markup = InlineKeyboardMarkup(keyboard)
await update.effective_message.reply_text("📦 Your story is ready to
download:", reply_markup=reply_markup)
  else:
await update.effective_message.reply_text("Sorry, I couldn't generate your
detailed story. Please try a different prompt.")
  context.user_data['state'] = None
if 'writer_tone' in context.user_data:
del context.user_data['writer_tone']
if 'story_length' in context.user_data:
del context.user_data['story_length']
if 'selected_language' in context.user_data:
del context.user_data['selected_language']
return # Exit early as this path handles its own response and state reset
  elif state == 'waiting_for_story_prompt':
await update.effective_message.reply_text(f"Generating a story in
{selected_language.upper()} about: {user_text}... Please wait! ⏳")
title, body = retry_story_generation(f"Generate a story in {selected_language}
about: {user_text}", 1)content_type = "story"
  elif state == 'waiting_for_ebook_topic':
await update.effective_message.reply_text(f"Generating an ebook in
{selected_language.upper()} about: {user_text}... Please wait! ⏳")
ebook_content = generate_ebook_with_ai(user_text, selected_language) # Pass
language to ebook generation
  if ebook_content and not ebook_content.startswith("**Error Generating
Ebook**"):
# Extract title from markdown for storage
title_match = re.match(r'^\s*#*\s*\*\*(.*?)\*\*', ebook_content, re.MULTILINE)
extracted_title = title_match.group(1).strip() if title_match else "Generated
Ebook"
  context.user_data['last_content'] = {
'title': extracted_title,
'body': ebook_content, # Store full markdown for PDF generation
'type': "ebook" # Set content type to ebook
}
  # Send a truncated message and offer download
display_text = ebook_content[:1900] + "\n\n...[Ebook continues in
download]..." if len(ebook_content) > 2000 else ebook_content
await update.effective_message.reply_text(display_text,
parse_mode='Markdown')
  keyboard = [
[
InlineKeyboardButton("📄 📥 Download PDF",
callback_data='download_pdf'),
InlineKeyboardButton("📄 📥 Download DOCX",
callback_data='download_docx'),
InlineKeyboardButton("📄 📥 Download TXT",
callback_data='download_txt'),
],
[
InlineKeyboardButton("📚 Want more? Try /story, /writer, or /play",
callback_data='null'),
],
[
InlineKeyboardButton("🎁 Invite a friend with /refer to earn bonuscredits!", callback_data='null')
]
]
reply_markup = InlineKeyboardMarkup(keyboard)
await update.effective_message.reply_text("📦 Your ebook is ready to
download:", reply_markup=reply_markup)
else:
await update.effective_message.reply_text("Sorry, I couldn't generate your
ebook. Please try a different topic.")
  context.user_data['state'] = None
if 'selected_language' in context.user_data:
del context.user_data['selected_language']
return # Exit early as this path handles its own response and state reset
  elif state == 'waiting_for_writer_topic':
tone = context.user_data.get('writer_tone')
selected_language = context.user_data.get('selected_language', 'en')
await update.effective_message.reply_text(f"Generating a {tone} story in
{selected_language.upper()} about: {user_text}... Please wait! ⏳")
title, body = retry_story_generation(f"Generate a story in {selected_language}
with a {tone} tone about: {user_text}", 1)
content_type = "writer_story"
if 'selected_language' in context.user_data:
del context.user_data['selected_language']
  elif state == 'waiting_for_tts_age':
age_match = re.search(r'\d+', user_text)
if age_match:
try:
age = int(age_match.group(0))
context.user_data['tts_age'] = age
context.user_data['state'] = 'waiting_for_tts_text'
await update.effective_message.reply_text(f"You entered age {age}. Now,
please send me the text you want to convert to speech. 🎤")
except ValueError:
# This should ideally not happen if re.search finds a valid number, but as a
safeguard
await update.effective_message.reply_text("Invalid age. Please enter a
number for the age (e.g., 30, 65): 🎂")
context.user_data['state'] = 'waiting_for_tts_age' # Stay in this state until
valid age is providedelse:
await update.effective_message.reply_text("Invalid age. Please enter a
number for the age (e.g., 30, 65): 🎂")
context.user_data['state'] = 'waiting_for_tts_age' # Stay in this state until valid
age is provided
return # Exit early as this path handles its own response and state reset
  elif state == 'waiting_for_tts_text':
tts_voice = context.user_data.get('tts_voice')
tts_age = context.user_data.get('tts_age')
voice_id = ""
  # Play.ht voice IDs (placeholders - replace with actual IDs from Play.ht
documentation)
PLAYHT_VOICES = {
'male': {
'young': "s3://voice-cloning-zero-shot/d9ff7a5d-9241-4a36
a57c-3b1077c3866e/original/manifest.json", # Example Play.ht voice ID
'adult': "s3://voice-cloning-zero-shot
8d42422c-122c-422f-806f-222222222222/original/manifest.json", # Example
Play.ht voice ID
'senior': "s3://voice-cloning-zero-shot/e0f2f2f2-f2f2-f2f2-f2f2-f2f2f2f2f2f2
original/manifest.json" # Example Play.ht voice ID
},
'female': {
'young': "s3://voice-cloning-zero-shot/a1b2c3d4
e5f6-7890-1234-567890abcdef/original/manifest.json", # Example Play.ht voice ID
'adult': "s3://voice-cloning-zero-shot/b2c3d4e5
f6a7-8901-2345-67890abcdef0/original/manifest.json", # Example Play.ht voice ID
'senior': "s3://voice-cloning-zero-shot/c3d4e5f6
a7b8-9012-3456-7890abcdef01/original/manifest.json" # Example Play.ht voice ID
}
}
if tts_voice in PLAYHT_VOICES:
if tts_age:
if tts_age < 30:
voice_id = PLAYHT_VOICES[tts_voice]['young']
elif 30 <= tts_age < 60:
voice_id = PLAYHT_VOICES[tts_voice]['adult']
else:
voice_id = PLAYHT_VOICES[tts_voice]['senior']
else:voice_id = PLAYHT_VOICES[tts_voice]['adult'] # Default to adult if no age
provided
  if not voice_id:
await update.effective_message.reply_text("Sorry, an invalid voice or age
combination was selected. Please try again with /speak.")
context.user_data['state'] = None
return
  await update.effective_message.reply_text(f"Thinking and generating audio
with {tts_voice} voice (age {tts_age if tts_age else 'default'})... Please wait! 🎤")
  # Use Gemini to generate a response based on user_text, incorporating "Slow
Toxin"
gemini_prompt_for_tts = f"Generate a concise and engaging response to the
following text, subtly or directly incorporating the concept of 'Slow Toxin' and
ensuring the tone is appropriate for a {tts_voice} voice of approximately {tts_age if
tts_age else 'an unspecified'} age: {user_text}"
  gemini_response_title, gemini_response_body =
retry_story_generation(gemini_prompt_for_tts, 1)
  if gemini_response_body:
audio_file_path = generate_audio_with_playht(gemini_response_body,
voice_id)
if audio_file_path:
with open(audio_file_path, 'rb') as audio_file:
await context.bot.send_audio(chat_id=update.effective_message.chat_id,
audio=audio_file, caption=f"Here's Gemini's response in {tts_voice} voice!")
os.remove(audio_file_path)
else:
await update.effective_message.reply_text("Sorry, I couldn't generate the
audio from Gemini's response. Please try again.")
else:
await update.effective_message.reply_text("Sorry, Gemini couldn't generate a
response for that. Please try again with a different text.")
  context.user_data['state'] = None
if 'tts_voice' in context.user_data:
del context.user_data['tts_voice']
if 'tts_age' in context.user_data:
del context.user_data['tts_age']return # Exit early as this path handles its own response and state reset
  elif state == 'waiting_for_play_prompt':
selected_language = context.user_data.get('selected_language', 'en')
await update.effective_message.reply_text(f"Generating a gamified creative
experience in {selected_language.upper()} based on: {user_text}... Please wait! 🎮")
game_prompt = f'''Generate an interactive game or creative challenge in
{selected_language} based on the user's request: "{user_text}".
 📌 Output Requirements:
- Start with a clear title for the game/challenge.
- Provide initial instructions or the first part of the interactive experience.
- If it's a choose-your-own-adventure, provide clear choices (e.g., "1. [Choice A]", "2.
[Choice B]").
- If it's a riddle or trivia, state the question clearly.
- Keep the response concise, encouraging further interaction.
- Format in Markdown.
 Respond only with the game/challenge content in Markdown. Do not include
instructions, tags, or notes.'''
  _, game_content = retry_story_generation(game_prompt, 1,
full_markdown_mode=True)
  if game_content:
await update.effective_message.reply_text(game_content,
parse_mode='Markdown')
context.user_data['last_content'] = {
'title': "Gamified Creative Mode",
'body': game_content,
'type': "game"
}
keyboard = [
[
InlineKeyboardButton("📚 Want more? Try /story, /writer, or /play",
callback_data='null'),
],
[
InlineKeyboardButton("🎁 Invite a friend with /refer to earn bonus
credits!", callback_data='null')
]
]reply_markup = InlineKeyboardMarkup(keyboard)
await update.effective_message.reply_text("What's your next move? Or try
another command!", reply_markup=reply_markup)
else:
await update.effective_message.reply_text("Sorry, I couldn't generate a
gamified experience for that. Please try a different prompt.")
  context.user_data['state'] = None
if 'selected_language' in context.user_data:
del context.user_data['selected_language']
return # Exit early as this path handles its own response and state reset
  else: # Default case for general story generation
selected_language = context.user_data.get('selected_language', 'en')
await update.effective_message.reply_text(f"Generating a story in
{selected_language.upper()} about: {user_text}... Please wait! ⏳")
title, body = retry_story_generation(f"Generate a story in {selected_language}
about: {user_text}", 1)
content_type = "story"
if 'selected_language' in context.user_data:
del context.user_data['selected_language']
  # This block handles all content generation (story, ebook, writer) that results in
text output
if title and body:
context.user_data['last_content'] = {
'title': title,
'body': body,
'type': content_type
}
  response_message = f"🧠 PROXORA AI PRESENTS\n" \
f"📖 “{title}”\n\n" \
f"---\n\n" \
f"{body}\n\n" \
f"---\n\n" \
f"✨ Every fate has its moment.\n" \
f"🖊️ Written by PROXORA\n" \
f"📦 Your content is ready to download:\n"
  keyboard = [
[InlineKeyboardButton("📄 📥 Download PDF",
callback_data='download_pdf'),
InlineKeyboardButton("📄 📥 Download DOCX",
callback_data='download_docx'),
InlineKeyboardButton("📄 📥 Download TXT",
callback_data='download_txt'),
],
[
InlineKeyboardButton("📚 Want more? Try /story, /writer, or /play",
callback_data='null'),
],
[
InlineKeyboardButton("🎁 Invite a friend with /refer to earn bonus credits!",
callback_data='null')
]
]
reply_markup = InlineKeyboardMarkup(keyboard)
  await update.effective_message.reply_text(response_message,
reply_markup=reply_markup)
else:
await update.effective_message.reply_text("Sorry, I couldn't generate content
for that. Please try a different prompt.")
  context.user_data['state'] = None
if 'writer_tone' in context.user_data:
del context.user_data['writer_tone']
if 'tts_voice' in context.user_data:
del context.user_data['tts_voice']
  async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) 
> None:
query = update.callback_query
await query.answer()
  if query.data.startswith('lang_'):
lang_code = query.data.replace('lang_', '')
context.user_data['selected_language'] = lang_code
# Determine the next step based on the previous state
previous_state = context.user_data.get('state')
if previous_state == 'waiting_for_story_language_selection':keyboard = [
[InlineKeyboardButton("Short (approx. 250 words)",
callback_data='length_short')],
[InlineKeyboardButton("Medium (approx. 500 words)",
callback_data='length_medium')],
[InlineKeyboardButton("Long (approx. 1000 words)",
callback_data='length_long')],
]
reply_markup = InlineKeyboardMarkup(keyboard)
await query.edit_message_text(f"Language set to {lang_code.upper()}. Now,
choose your desired story length: 📏", reply_markup=reply_markup)
context.user_data['state'] = 'waiting_for_story_length_selection'
elif previous_state == 'waiting_for_ebook_language_selection':
await query.edit_message_text(f"Language set to {lang_code.upper()}. What
topic should your educational ebook be about? For example: 'Quantum Physics' or
'The History of Ancient Rome'. 💡")
context.user_data['state'] = 'waiting_for_ebook_topic'
elif previous_state == 'waiting_for_writer_language_selection':
keyboard = [
[InlineKeyboardButton("Funny 😂", callback_data='tone_funny')],
[InlineKeyboardButton("Serious 🧐", callback_data='tone_serious')],
[InlineKeyboardButton("Fantasy 🧚", callback_data='tone_fantasy')],
]
reply_markup = InlineKeyboardMarkup(keyboard)
await query.edit_message_text(f"Language set to {lang_code.upper()}. Now,
choose a tone for your story:", reply_markup=reply_markup)
context.user_data['state'] = 'waiting_for_writer_tone'
else:
await query.edit_message_text("Language selected, but an unexpected state
occurred. Please try again with a command like /story.")
context.user_data['state'] = None
  elif query.data.startswith('tone_'):
tone = query.data.replace('tone_', '')
context.user_data['writer_tone'] = tone
context.user_data['state'] = 'waiting_for_writer_topic'
await query.edit_message_text(f"You chose {tone.capitalize()} tone. Now, what
topic should your story be about? ✍️")
  elif query.data.startswith('length_'):
length = query.data.replace('length_', '')
context.user_data['story_length'] = lengthcontext.user_data['state'] = 'waiting_for_detailed_story_prompt'
await query.edit_message_text(f"You chose a {length} story. Now, please tell me
the detailed prompt for your story! ✍️")
  elif query.data.startswith('voice_'):
voice_type = query.data.replace('voice_', '')
context.user_data['tts_voice'] = voice_type
context.user_data['state'] = 'waiting_for_tts_age'
await query.edit_message_text(f"You chose a {voice_type} voice persona. Now,
please enter an approximate age for the voice (e.g., 30, 65): 🎂")
  elif query.data.startswith('download_'):
file_format = query.data.replace('download_', '')
last_content = context.user_data.get('last_content')
if last_content:
title = last_content.get('title', 'Generated Document').replace(' ', '_').replace('"',
'').replace("'", "")
# Use the full markdown content for downloads to ensure fidelity
content_body = last_content.get('body', "No content available.")
file_path = f"{title}.{file_format}"
  if file_format == 'pdf':
create_pdf(content_body, file_path)
elif file_format == 'docx':
create_docx(content_body, file_path)
elif file_format == 'txt':
create_txt(content_body, file_path)
else:
await query.edit_message_text("Unsupported file format selected.")
return
  with open(file_path, 'rb') as f:
if file_format == 'pdf':
await context.bot.send_document(chat_id=query.message.chat_id,
document=f, caption=f"Here's your content as a {file_format.upper()}!")
elif file_format == 'docx':
await context.bot.send_document(chat_id=query.message.chat_id,
document=f, caption=f"Here's your content as a {file_format.upper()}!")
elif file_format == 'txt':
await context.bot.send_document(chat_id=query.message.chat_id,
document=f, caption=f"Here's your content as a {file_format.upper()}!")
os.remove(file_path) # Clean up the file after sendingawait query.edit_message_text(f"Your content has been sent as a
{file_format.upper()}! Enjoy! 🎉")
else:
await query.edit_message_text("No content found to download. Please
generate something first!")
elif query.data == 'null':
# Do nothing for 'null' callbacks, used for informational buttons
pass
elif query.data.startswith('command_'):
command = query.data.replace('command_', '')
# Simulate calling the command handler
if command == 'story':
await story_command(update, context)
elif command == 'ebook':
await ebook_command(update, context)
elif command == 'writer':
await writer_command(update, context)
elif command == 'speak':
await speak_command(update, context)
elif command == 'refer':
await refer_command(update, context)
elif command == 'watchad':
await watchad_command(update, context)
elif command == 'plans':
await plans_command(update, context)
elif command == 'profile':
await profile_command(update, context)
elif command == 'progress':
await progress_command(update, context)
elif command == 'help':
await help_command(update, context)
elif command == 'play':
await play_command(update, context)
await query.edit_message_reply_markup(reply_markup=None) # Remove
buttons after selection
 def main() -> None:
"""Start the bot."""
application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
  # Command Handlers
application.add_handler(CommandHandler("start", start_command))application.add_handler(CommandHandler("story", story_command))
application.add_handler(CommandHandler("ebook", ebook_command))
application.add_handler(CommandHandler("writer", writer_command))
application.add_handler(CommandHandler("speak", speak_command))
application.add_handler(CommandHandler("refer", refer_command))
application.add_handler(CommandHandler("watchad", watchad_command))
application.add_handler(CommandHandler("plans", plans_command))
application.add_handler(CommandHandler("profile", profile_command))
application.add_handler(CommandHandler("progress", progress_command))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(CommandHandler("play", play_command))
   # Message Handler for states and WebApp data
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,
handle_message))
application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA,
handle_webapp_data)) # Add this for WebApp data
  # Callback Query Handler for inline buttons
application.add_handler(CallbackQueryHandler(button_callback))
  logger.info("Bot starting...")
application.run_polling(allowed_updates=Update.ALL_TYPES)
  if __name__ == "__main__":
main()
