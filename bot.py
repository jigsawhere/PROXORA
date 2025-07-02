import logging
import os
import sys
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.error import Conflict
import io
import requests
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.enums import TA_CENTER
from docx import Document
import asyncio
import re
import google.generativeai as genai

# Add the script's directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import all necessary API keys from config.py
from config import TELEGRAM_BOT_TOKEN, GEMINI_API_KEY, PLAYHT_API_KEY

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- AI Model Integration ---
genai.configure(api_key=GEMINI_API_KEY)

def generate_story_with_ai(prompt: str, full_markdown_mode: bool = False) -> tuple[str | None, str | None]:
    """
    Generates a story based on the prompt using Gemini Flash.
    If full_markdown_mode is True, expects the AI to return the complete markdown story.
    """
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        if full_markdown_mode:
            # In full markdown mode, send the exact prompt and expect the full story back
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    candidate_count=1,
                    max_output_tokens=2000,
                    temperature=0.7
                )
            )
            full_text = response.text.strip()
            return None, full_text  # Return None for title, as full_text is the complete story
        else:
            # Original behavior: generate title and body separately
            response = model.generate_content(
                f"Generate a story with a title and body on the following prompt: {prompt}\n\nTitle:",
                generation_config=genai.types.GenerationConfig(
                    candidate_count=1,
                    max_output_tokens=2000,
                    temperature=0.7
                )
            )
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
        return None, None

def generate_ebook_with_ai(topic: str, language: str = "en") -> str:
    """
    Generates educational material based on the topic using Gemini Flash.
    """
    ebook_prompt = f'''Generate an educational ebook content about: {topic} in {language}.
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

Respond only with the final ebook in Markdown. Do not include instructions, tags, or notes.'''

    _, ebook_content = retry_story_generation(ebook_prompt, 1, full_markdown_mode=True)
    return ebook_content if ebook_content else "**Error Generating Ebook**\n\n_Could not generate the ebook. Please try again with a different topic._"

def retry_story_generation(prompt: str, attempt: int, full_markdown_mode: bool = False) -> tuple[str | None, str | None]:
    """
    Retries story generation. This function now directly calls generate_story_with_ai
    without rephrasing, as the core generation function is expected to be robust.
    """
    logger.info(f"Attempting AI generation (attempt {attempt}) with prompt: {prompt}, full_markdown_mode: {full_markdown_mode}")
    title, story_body = generate_story_with_ai(prompt, full_markdown_mode)
    if (title and story_body) or (full_markdown_mode and story_body):
        return title, story_body
    elif attempt < 3:
        return retry_story_generation(prompt, attempt + 1, full_markdown_mode)
    else:
        if full_markdown_mode:
            return None, "**Error Generating Story**\n\n_Could not generate the story. Please try again with a different prompt._"
        else:
            return "A Mysterious Tale", "Once upon a time, a story unfolded that defied all expectations. The end."

# --- PDF/DOCX/TXT Export Functions ---
def create_pdf(content: str, filename: str):
    doc = SimpleDocTemplate(filename, pagesize=letter)
    styles = getSampleStyleSheet()

    title_style = styles['h1']
    title_style.alignment = TA_CENTER
    body_style = styles['Normal']

    elements = []
    lines = content.split('\n')

    extracted_title = "Generated Document"
    content_start_index = 0

    # Check for bolded title (e.g., **Title**)
    if lines:
        title_match_bold = re.match(r'^\s*#*\s*\*\*(.*?)\*\*', lines[0], re.MULTILINE)
        if title_match_bold:
            extracted_title = title_match_bold.group(1).strip()
            content_start_index = 1
        else:
            # Check for heading title (e.g., # Title)
            title_match_heading = re.match(r'^\s*#+\s*(.*?)\s*$', lines[0], re.MULTILINE)
            if title_match_heading:
                extracted_title = title_match_heading.group(1).strip()
                content_start_index = 1

    elements.append(Paragraph(extracted_title, title_style))
    elements.append(Spacer(1, 0.2 * 100))

    for line in lines[content_start_index:]:
        if line.strip():
            # Convert markdown bold/italic to HTML bold/italic for ReportLab
            line = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', line)
            line = re.sub(r'\_(.*?)\_', r'<i>\1</i>', line)

            # Handle chapters/sections as bold
            if line.startswith("Chapter") or line.startswith("Introduction") or line.startswith("Conclusion"):
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
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [InlineKeyboardButton("🚀 Launch PROXORA WebApp", web_app=WebAppInfo(url="https://jigsawhere.github.io/PROXORA/"))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_message = (
        "Click below to open PROXORA AI WebApp:\n\n"
        "🧙‍♂️✨ Welcome to PROXORA, your ultra-intelligent storytelling and content generation assistant! 📘\n\n"
        "Here are the commands you can use:\n"
        "📚 /story - Prompt me for a story input and I'll generate a full story with emojis\n"
        "📖 /ebook - Generate educational material on any topic.\n"
        "✍️ /writer - Choose a tone (funny, serious, fantasy) and topic for your story.\n"
        "🗣️ /speak - Activate voice chat / TTS (if enabled).\n"
        "🎁 /refer - Get your referral link and check bonus status.\n"
        "📺 /watchad - Watch ads for more credits.\n"
        "💳 /plans - See premium pricing and features.\n"
        "👤 /profile - View your books made, credits left, plan, and referral stats.\n"
        "📊 /progress - Check your book usage count, quota remaining, and total stories\n"
        "❓ /help - Get a smart guide on how to use each feature.\n"
        "🎮 /play - Enter gamified creative mode!\n\n"
        "Let's make magic! What story shall we create today? ✨"
    )
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)

# Supported languages for content generation
SUPPORTED_LANGUAGES = {
    "English": "en", "Spanish": "es", "French": "fr", "German": "de", "Italian": "it",
    "Portuguese": "pt", "Japanese": "ja", "Korean": "ko", "Chinese (Simplified)": "zh-CN",
    "Russian": "ru", "Arabic": "ar", "Hindi": "hi" # Add more as needed
}

async def send_language_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, next_state: str) -> None:
    keyboard = []
    languages = list(SUPPORTED_LANGUAGES.keys())
    for i in range(0, len(languages), 3):
        row = []
        for lang in languages[i:i+3]:
            row.append(InlineKeyboardButton(lang, callback_data=f'lang_{SUPPORTED_LANGUAGES[lang]}'))
        keyboard.append(row)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Choose a language for your content: 🌐", reply_markup=reply_markup)
    context.user_data['state'] = next_state

async def story_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_language_selection(update, context, 'waiting_for_story_language_selection')

async def ebook_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_language_selection(update, context, 'waiting_for_ebook_language_selection')

async def writer_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_language_selection(update, context, 'waiting_for_writer_language_selection')

# --- Play.ht API Integration ---
def generate_audio_with_playht(text: str, voice_id: str) -> str | None:
    """
    Generates audio from text using Play.ht API.
    Returns the path to the generated audio file or None on failure.
    """
    url = "https://api.play.ht/api/v2/tts"
    headers = {
        "Authorization": f"Bearer {PLAYHT_API_KEY}",
        "X-User-Id": "YOUR_USER_ID",  # Replace with actual User ID if required
        "Content-Type": "application/json"
    }
    payload = {
        "text": text,
        "voice": voice_id,
        "output_format": "mp3",
        "quality": "medium"
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()

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

async def speak_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [InlineKeyboardButton("Male Voice 👨", callback_data='voice_male')],
        [InlineKeyboardButton("Female Voice 👩", callback_data='voice_female')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Choose a voice for Text-to-Speech: 🗣️", reply_markup=reply_markup)
    context.user_data['state'] = 'waiting_for_tts_voice_selection'

async def refer_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    referral_link = "https://t.me/proxora_bot?start=YOUR_REFERRAL_CODE"  # Placeholder
    bonus_status = "You have 5 bonus credits! 🎉"  # Placeholder
    await update.message.reply_text(f"🎁 Your referral link: {referral_link}\n\n{bonus_status}")

async def watchad_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("📺 Ad watched! You've earned 10 credits. Enjoy! 🎉")

async def plans_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    plans_info = (
        "💳 PROXORA Premium Plans:\n\n"
        "✨ Basic Plan: $4.99 USD / ₹399 INR / €4.49 EUR per month\n"
        " - Unlimited stories, ad-free.\n\n"
        "🌟 Pro Plan: $9.99 USD / ₹799 INR / €8.99 EUR per month\n"
        " - All Basic features + advanced tools, illustrations, speed boosts.\n\n"
        "Unlock unlimited creativity! 🚀"
    )
    await update.message.reply_text(plans_info)

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
    await update.message.reply_text(profile_info)

async def progress_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    book_usage_count = 10
    quota_remaining = "56 free books"
    total_stories_generated = 15

    progress_info = (
        f"📊 Your PROXORA Progress:\n\n"
        f"📖 Books Used This Cycle: {book_usage_count}\n"
        f"⏳ Quota Remaining: {quota_remaining}\n"
        f"✨ Total Stories Generated: {total_stories_generated}\n\n"
        f"You're doing great! Keep going! 💪"
    )
    await update.message.reply_text(progress_info)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_message = (
        "❓ PROXORA Smart Guide:\n\n"
        "📚 /story: Use this to generate a new story. After typing /story, I'll ask you for a prompt. Just type your idea, like 'a detective solving a mystery in space' and I'll craft a unique tale for you! ✨\n\n"
        "📖 /ebook: Want to learn something new? Use /ebook followed by a topic, e.g., 'The Solar System', and I'll create an educational ebook for you. 💡\n\n"
        "✍️ /writer: This command lets you customize your story's tone. I'll give you options like Funny, Serious, or Fantasy. Choose one, then provide your topic! 🎭\n\n"
        "And so on for other commands... (Full help text would be here) 🚀"
    )
    await update.message.reply_text(help_message)

async def play_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("🎮 Welcome to the Gamified Creative Mode! What kind of game or interactive story would you like to play? (e.g., 'a mystery riddle', 'a choose-your-own-adventure start', 'a quick trivia game') 🚀")
    context.user_data['state'] = 'waiting_for_play_prompt'

# --- WebApp Data Handler ---
async def handle_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.web_app_data:
        data = update.message.web_app_data.data
        await update.message.reply_text(f"✅ Data received from WebApp: `{data}`", parse_mode='Markdown')
    else:
        await update.message.reply_text("No data received from WebApp.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_text = update.message.text
    chat_id = update.message.chat_id
    state = context.user_data.get('state')

    title, body = None, None
    story_markdown = None
    content_type = "story"

    selected_language = context.user_data.get('selected_language', 'en')

    if state == 'waiting_for_detailed_story_prompt':
        story_length = context.user_data.get('story_length', 'short')
        word_count = 250
        if story_length == 'medium':
            word_count = 500
        elif story_length == 'long':
            word_count = 1000

        await update.message.reply_text(f"Generating your {story_length} story in {selected_language.upper()} about: {user_text}... Please wait! ⏳")
        full_prompt = f'''Based on the user input "{user_text}", generate a complete short story in {selected_language}.

📝 User Prompt:
"{user_text}"

📌 Output Requirements:
- Word count: Approximately {word_count} words
- Genre: Dark Fantasy / Science Fiction
- Tone: Cinematic, eerie, emotional
- Format in Markdown with the following structure:
• Title (bold, 3–6 words)
• One-line summary in _italics_
• Full story in short, poetic paragraphs
• Include vivid sensory detail
• End with a twist or emotional resolution

🎨 Style Guide:
- Avoid clichés
- Include internal thoughts and subtle world-building
- Use descriptive metaphors or imagery
- Break long sections with logical paragraphing
- Optionally use emoji section breaks like 🌌, 🚀, 🪐

Respond only with the final story in Markdown. Do not include instructions, tags, or notes.'''

        _, story_markdown = retry_story_generation(full_prompt, 1, full_markdown_mode=True)

        if story_markdown:
            if len(story_markdown) > 3000:
                display_text = story_markdown[:2900] + "\n\n...[Story continues in download]..."
                await update.message.reply_text(display_text, parse_mode='Markdown')
            else:
                await update.message.reply_text(story_markdown, parse_mode='Markdown')

            title_match = re.search(r'\*\*(.*?)\*\*', story_markdown)
            extracted_title = title_match.group(1).strip() if title_match else "Generated Story"
            
            context.user_data['last_content'] = {
                'title': extracted_title,
                'body': story_markdown,
                'type': content_type
            }

            keyboard = [
                [
                    InlineKeyboardButton("📄 📥 Download PDF", callback_data='download_pdf'),
                    InlineKeyboardButton("📄 📥 Download DOCX", callback_data='download_docx'),
                    InlineKeyboardButton("📄 📥 Download TXT", callback_data='download_txt'),
                ],
                [InlineKeyboardButton("📚 Want more? Try /story, /writer, or /play", callback_data='null')],
                [InlineKeyboardButton("🎁 Invite a friend with /refer to earn bonus credits!", callback_data='null')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("📦 Your story is ready to download:", reply_markup=reply_markup)
        else:
            await update.message.reply_text("Sorry, I couldn't generate your detailed story. Please try a different prompt.")

        context.user_data['state'] = None
        # Clean up context
        for key in ['writer_tone', 'story_length', 'selected_language']:
            if key in context.user_data:
                del context.user_data[key]
        return

    elif state == 'waiting_for_story_prompt':
        await update.message.reply_text(f"Generating a story in {selected_language.upper()} about: {user_text}... Please wait! ⏳")
        title, body = retry_story_generation(f"Generate a story in {selected_language} about: {user_text}", 1)
        content_type = "story"

    elif state == 'waiting_for_ebook_topic':
        await update.message.reply_text(f"Generating an ebook in {selected_language.upper()} about: {user_text}... Please wait! ⏳")
        ebook_content = generate_ebook_with_ai(user_text, selected_language)

        if ebook_content and not ebook_content.startswith("**Error Generating Ebook**"):
            title_match = re.search(r'\*\*(.*?)\*\*', ebook_content)
            extracted_title = title_match.group(1).strip() if title_match else "Generated Ebook"
            context.user_data['last_content'] = {
                'title': extracted_title,
                'body': ebook_content,
                'type': "ebook"
            }

            display_text = ebook_content[:2900] + "\n\n...[Ebook continues in download]..." if len(ebook_content) > 3000 else ebook_content
            await update.message.reply_text(display_text, parse_mode='Markdown')

            keyboard = [
                [
                    InlineKeyboardButton("📄 📥 Download PDF", callback_data='download_pdf'),
                    InlineKeyboardButton("📄 📥 Download DOCX", callback_data='download_docx'),
                    InlineKeyboardButton("📄 📥 Download TXT", callback_data='download_txt'),
                ],
                [InlineKeyboardButton("📚 Want more? Try /story, /writer, or /play", callback_data='null')],
                [InlineKeyboardButton("🎁 Invite a friend with /refer to earn bonus credits!", callback_data='null')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("📦 Your ebook is ready to download:", reply_markup=reply_markup)
        else:
            await update.message.reply_text("Sorry, I couldn't generate your ebook. Please try a different topic.")

        context.user_data['state'] = None
        if 'selected_language' in context.user_data:
            del context.user_data['selected_language']
        return

    elif state == 'waiting_for_writer_topic':
        tone = context.user_data.get('writer_tone')
        await update.message.reply_text(f"Generating a {tone} story in {selected_language.upper()} about: {user_text}... Please wait! ⏳")
        title, body = retry_story_generation(f"Generate a story in {selected_language} with a {tone} tone about: {user_text}", 1)
        content_type = "writer_story"

    elif state == 'waiting_for_tts_age':
        age_match = re.search(r'\d+', user_text)
        if age_match:
            try:
                age = int(age_match.group(0))
                context.user_data['tts_age'] = age
                context.user_data['state'] = 'waiting_for_tts_text'
                await update.message.reply_text(f"You entered age {age}. Now, please send me the text you want to convert to speech. 🎤")
            except ValueError:
                await update.message.reply_text("Invalid age. Please enter a number for the age (e.g., 30, 65): 🎂")
        else:
            await update.message.reply_text("Invalid age. Please enter a number for the age (e.g., 30, 65): 🎂")
        return

    elif state == 'waiting_for_tts_text':
        tts_voice = context.user_data.get('tts_voice')
        tts_age = context.user_data.get('tts_age')
        voice_id = ""
        
        # Placeholder voice IDs
        PLAYHT_VOICES = {
            'male': "s3://voice-cloning-zero-shot/d9ff7a5d-9241-4a36-a57c-3b1077c3866e/original/manifest.json",
            'female': "s3://voice-cloning-zero-shot/a1b2c3d4-e5f6-7890-1234-567890abcdef/original/manifest.json"
        }
        voice_id = PLAYHT_VOICES.get(tts_voice)

        if not voice_id:
            await update.message.reply_text("Sorry, an invalid voice was selected. Please try again with /speak.")
            context.user_data['state'] = None
            return

        await update.message.reply_text(f"Thinking and generating audio... Please wait! 🎤")
        
        gemini_prompt_for_tts = f"Generate a concise and engaging response to the following text: {user_text}"
        _, gemini_response_body = retry_story_generation(gemini_prompt_for_tts, 1)

        if gemini_response_body:
            audio_file_path = generate_audio_with_playht(gemini_response_body, voice_id)
            if audio_file_path:
                with open(audio_file_path, 'rb') as audio_file:
                    await context.bot.send_audio(chat_id=chat_id, audio=audio_file, caption=f"Here's Gemini's response in {tts_voice} voice!")
                os.remove(audio_file_path)
            else:
                await update.message.reply_text("Sorry, I couldn't generate the audio. Please try again.")
        else:
            await update.message.reply_text("Sorry, Gemini couldn't generate a response. Please try again.")
        
        # Clean up context
        context.user_data['state'] = None
        for key in ['tts_voice', 'tts_age']:
            if key in context.user_data:
                del context.user_data[key]
        return

    elif state == 'waiting_for_play_prompt':
        await update.message.reply_text(f"Generating a gamified creative experience in {selected_language.upper()} based on: {user_text}... Please wait! 🎮")
        game_prompt = f'''Generate an interactive game or creative challenge in {selected_language} based on the user's request: "{user_text}".

📌 Output Requirements:
- Start with a clear title.
- Provide initial instructions or the first part of the experience.
- If it's a choose-your-own-adventure, provide clear choices.
- Keep the response concise to encourage interaction.
- Format in Markdown.

Respond only with the game/challenge content.'''

        _, game_content = retry_story_generation(game_prompt, 1, full_markdown_mode=True)

        if game_content:
            await update.message.reply_text(game_content, parse_mode='Markdown')
            context.user_data['last_content'] = {'title': "Gamified Creative Mode", 'body': game_content, 'type': "game"}
            keyboard = [
                [InlineKeyboardButton("📚 Want more? Try /story, /writer, or /play", callback_data='null')],
                [InlineKeyboardButton("🎁 Invite a friend with /refer to earn bonus credits!", callback_data='null')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("What's your next move? Or try another command!", reply_markup=reply_markup)
        else:
            await update.message.reply_text("Sorry, I couldn't generate a gamified experience. Please try a different prompt.")

        context.user_data['state'] = None
        if 'selected_language' in context.user_data:
            del context.user_data['selected_language']
        return

    # This block handles the general text output for simpler commands
    if title and body:
        context.user_data['last_content'] = {'title': title, 'body': body, 'type': content_type}

        response_message = f"🧠 PROXORA AI PRESENTS\n📖 “{title}”\n\n---\n\n{body}\n\n---\n\n✨ Every fate has its moment.\n🖊️ Written by PROXORA\n📦 Your content is ready to download:\n"

        keyboard = [
            [
                InlineKeyboardButton("📄 📥 Download PDF", callback_data='download_pdf'),
                InlineKeyboardButton("📄 📥 Download DOCX", callback_data='download_docx'),
                InlineKeyboardButton("📄 📥 Download TXT", callback_data='download_txt'),
            ],
            [InlineKeyboardButton("📚 Want more? Try /story, /writer, or /play", callback_data='null')],
            [InlineKeyboardButton("🎁 Invite a friend with /refer to earn bonus credits!", callback_data='null')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(response_message, reply_markup=reply_markup)
    elif state is not None:
        await update.message.reply_text("Sorry, I couldn't generate content for that. Please try a different prompt.")
    
    # Final cleanup of state and context variables
    context.user_data['state'] = None
    for key in ['writer_tone', 'tts_voice', 'selected_language']:
        if key in context.user_data:
            del context.user_data[key]

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith('lang_'):
        lang_code = data.replace('lang_', '')
        context.user_data['selected_language'] = lang_code
        previous_state = context.user_data.get('state')

        if previous_state == 'waiting_for_story_language_selection':
            keyboard = [
                [InlineKeyboardButton("Short (~250 words)", callback_data='length_short')],
                [InlineKeyboardButton("Medium (~500 words)", callback_data='length_medium')],
                [InlineKeyboardButton("Long (~1000 words)", callback_data='length_long')],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(f"Language set to {lang_code.upper()}. Now, choose your story length: 📏", reply_markup=reply_markup)
            context.user_data['state'] = 'waiting_for_story_length_selection'
        
        elif previous_state == 'waiting_for_ebook_language_selection':
            await query.edit_message_text(f"Language set to {lang_code.upper()}. What topic for the ebook? (e.g., 'Quantum Physics') 💡")
            context.user_data['state'] = 'waiting_for_ebook_topic'

        elif previous_state == 'waiting_for_writer_language_selection':
            keyboard = [
                [InlineKeyboardButton("Funny 😂", callback_data='tone_funny')],
                [InlineKeyboardButton("Serious 🧐", callback_data='tone_serious')],
                [InlineKeyboardButton("Fantasy 🧚", callback_data='tone_fantasy')],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(f"Language set to {lang_code.upper()}. Now, choose a tone:", reply_markup=reply_markup)
            context.user_data['state'] = 'waiting_for_writer_tone'
        else:
            await query.edit_message_text("Language selected, but an unexpected state occurred. Please start over with a command.")
            context.user_data['state'] = None

    elif data.startswith('tone_'):
        tone = data.replace('tone_', '')
        context.user_data['writer_tone'] = tone
        context.user_data['state'] = 'waiting_for_writer_topic'
        await query.edit_message_text(f"Tone: {tone.capitalize()}. What's the topic? ✍️")

    elif data.startswith('length_'):
        length = data.replace('length_', '')
        context.user_data['story_length'] = length
        context.user_data['state'] = 'waiting_for_detailed_story_prompt'
        await query.edit_message_text(f"Length: {length}. Now, please provide the detailed prompt! ✍️")

    elif data.startswith('voice_'):
        voice_type = data.replace('voice_', '')
        context.user_data['tts_voice'] = voice_type
        context.user_data['state'] = 'waiting_for_tts_age'
        await query.edit_message_text(f"Voice: {voice_type}. Please enter an approximate age (e.g., 30, 65): 🎂")

    elif data.startswith('download_'):
        file_format = data.replace('download_', '')
        last_content = context.user_data.get('last_content')
        if last_content:
            title = re.sub(r'[\s"\'/\\?*:]', '_', last_content.get('title', 'Generated_Document'))
            content_body = last_content.get('body', "No content available.")
            file_path = f"{title}.{file_format}"
            
            try:
                if file_format == 'pdf':
                    create_pdf(content_body, file_path)
                elif file_format == 'docx':
                    create_docx(content_body, file_path)
                elif file_format == 'txt':
                    create_txt(content_body, file_path)
                else:
                    await query.edit_message_text("Unsupported file format.")
                    return

                with open(file_path, 'rb') as f:
                    await context.bot.send_document(chat_id=query.message.chat_id, document=f, caption=f"Here is your {file_format.upper()} file!")
                os.remove(file_path)
                await query.edit_message_text(f"Download sent! Enjoy your {file_format.upper()}! 🎉")
            except Exception as e:
                logger.error(f"Error creating or sending file: {e}")
                await query.edit_message_text("Sorry, there was an error creating your file.")
        else:
            await query.edit_message_text("No content found to download. Please generate something first!")

    elif data == 'null':
        pass  # Do nothing for informational buttons

def main() -> None:
    """Start the bot."""
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Command Handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("story", story_command))
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
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))

    # Callback Query Handler for inline buttons
    application.add_handler(CallbackQueryHandler(button_callback))

    logger.info("Bot starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
