import cv2
import os
import requests
import re
import tempfile
import json
import wave
import time
from pathlib import Path
import uuid
from collections import deque
from dotenv import load_dotenv
import speech_recognition as sr
from flask import Flask, render_template, redirect, request, url_for, flash, session, Response, g, jsonify
from pymongo import MongoClient
from datetime import datetime
from bson.objectid import ObjectId
from num2words import num2words
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import torch
import numpy as np
import threading
camera_lock = threading.Lock()
latest_prediction = {"text": "", "confidence": 0.0, "state": "idle"}
captured_sequence = []
is_capturing = False
from Model.features import (
    FEATURE_SIZE,
    SEQUENCE_LENGTH,
    extract_landmark_features,
    is_no_hand_feature_vector,
    normalize_sequence,
)
from Model.gesture_model import GestureTransformer
from pydub import AudioSegment
from flask import session, redirect, url_for, request

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Secret key for session management
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev_secret_key')

# MongoDB Configuration
mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
mongo_client = MongoClient(mongo_uri)
db = mongo_client['vyakt_db']
app.config['GOOGLE_TRANSLATE_API_KEY'] = os.getenv('GOOGLE_TRANSLATE_API_KEY', '')


@app.context_processor
def inject_frontend_config():
    return {
        "google_translate_api_key": app.config.get("GOOGLE_TRANSLATE_API_KEY", ""),
        "emailjs_service_id": os.getenv("VITE_EMAILJS_SERVICE_ID", ""),
        "emailjs_template_id": os.getenv("VITE_EMAILJS_TEMPLATE_ID", ""),
        "emailjs_public_key": os.getenv("VITE_EMAILJS_PUBLIC_KEY", ""),
    }


# Configuration for file uploads
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')


# Registration Form
class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[Length(min=4, max=25), DataRequired()])
    email = StringField('Email', validators=[Email(), DataRequired()])
    password = PasswordField('Password', validators=[
        DataRequired(),
        EqualTo('confirm', message='Passwords must match')
    ])
    confirm = PasswordField('Confirm Password', validators=[DataRequired()])
    submit = SubmitField('Register')

# Login Form
class LoginForm(FlaskForm):
    email = StringField('Email', validators=[Email(), DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

ASSET_DIR = Path(app.root_path) / "static" / "assets"
_CONTRACTION_PATTERNS = [
    (re.compile(r"\bwon't\b", re.IGNORECASE), "will not"),
    (re.compile(r"\bcan't\b", re.IGNORECASE), "cannot"),
    (re.compile(r"n't\b", re.IGNORECASE), " not"),
    (re.compile(r"'re\b", re.IGNORECASE), " are"),
    (re.compile(r"'ve\b", re.IGNORECASE), " have"),
    (re.compile(r"'ll\b", re.IGNORECASE), " will"),
    (re.compile(r"'d\b", re.IGNORECASE), " would"),
    (re.compile(r"'m\b", re.IGNORECASE), " am"),
    (re.compile(r"'s\b", re.IGNORECASE), " is"),
]


def _normalize_asset_key(text):
    return re.sub(r"\s+", " ", text.strip().lower())


def _build_asset_maps():
    single_word = {}
    multi_word = {}
    alpha_numeric = set()

    if not ASSET_DIR.exists():
        return single_word, multi_word, alpha_numeric

    for mp4 in ASSET_DIR.glob("*.mp4"):
        stem = mp4.stem
        key = _normalize_asset_key(stem)
        if not key:
            continue

        if " " in key:
            multi_word[key] = stem
        else:
            single_word[key] = stem
            if len(stem) == 1 and stem.isalnum():
                alpha_numeric.add(stem.upper())

    return single_word, multi_word, alpha_numeric


ASSET_SINGLE_MAP, ASSET_MULTI_MAP, ASSET_ALPHA_NUMERIC = _build_asset_maps()
ASSET_MULTI_MAX_WORDS = max((len(k.split()) for k in ASSET_MULTI_MAP), default=1)
DEFAULT_SIGN_STOPWORDS = {
    "a", "an", "the", "is", "am", "are", "was", "were", "be", "been", "being",
    "for", "of", "to", "at", "in", "on", "by", "with", "from", "as",
    "and", "or", "if", "then", "than",
}
STOPWORDS_FILE = Path(app.root_path) / "config" / "sign_stopwords.txt"


def _load_sign_stopwords():
    if not STOPWORDS_FILE.exists():
        return set(DEFAULT_SIGN_STOPWORDS)

    words = set()
    for raw_line in STOPWORDS_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip().lower()
        if not line or line.startswith("#"):
            continue
        words.add(line)

    return words if words else set(DEFAULT_SIGN_STOPWORDS)


SIGN_STOPWORDS = _load_sign_stopwords()


def _expand_contractions(text):
    normalized = text.lower()
    for pattern, replacement in _CONTRACTION_PATTERNS:
        normalized = pattern.sub(replacement, normalized)
    return normalized


def _candidate_tokens(token):
    candidates = [token]
    if token.endswith("ies") and len(token) > 3:
        candidates.append(token[:-3] + "y")
    if token.endswith("ing") and len(token) > 4:
        base = token[:-3]
        candidates.append(base)
        candidates.append(base + "e")
    if token.endswith("ed") and len(token) > 3:
        base = token[:-2]
        candidates.append(base)
        candidates.append(base + "e")
    if token.endswith("es") and len(token) > 3:
        candidates.append(token[:-2])
    if token.endswith("s") and len(token) > 2:
        candidates.append(token[:-1])

    deduped = []
    seen = set()
    for item in candidates:
        if item and item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped


def _resolve_token_to_asset(token):
    for candidate in _candidate_tokens(token):
        if candidate in ASSET_SINGLE_MAP:
            return ASSET_SINGLE_MAP[candidate]
    return None


def process_text_for_animation(text, remove_stopwords=True):
    if not text:
        return []

    normalized = _expand_contractions(text)
    tokens = re.findall(r"[a-z0-9]+", normalized)
    if not tokens:
        return []

    final_words = []
    i = 0

    while i < len(tokens):
        matched_phrase = None
        max_window = min(ASSET_MULTI_MAX_WORDS, len(tokens) - i)

        for window in range(max_window, 1, -1):
            phrase_key = " ".join(tokens[i:i + window])
            if phrase_key in ASSET_MULTI_MAP:
                matched_phrase = ASSET_MULTI_MAP[phrase_key]
                i += window
                break

        if matched_phrase:
            final_words.append(matched_phrase)
            continue

        token = tokens[i]

        if remove_stopwords and token in SIGN_STOPWORDS:
            i += 1
            continue

        resolved = _resolve_token_to_asset(token)

        if resolved:
            final_words.append(resolved)
        else:
            for ch in token.upper():
                if ch in ASSET_ALPHA_NUMERIC:
                    final_words.append(ch)

        i += 1

    return final_words


LEARNING_CURRICULUM_ROOT = Path(app.root_path) / 'learning' / 'curriculum'
LEARNING_LEVELS_FILE = LEARNING_CURRICULUM_ROOT / 'phase2_levels.json'
LEARNING_LESSONS_FILE = LEARNING_CURRICULUM_ROOT / 'phase6_lesson_packs.json'
LEARNING_QUIZ_FILE = LEARNING_CURRICULUM_ROOT / 'phase6_quiz_templates.json'


def _utc_now():
    return datetime.utcnow()


def _learning_user_key():
    if session.get('user_id'):
        return f"user:{session['user_id']}"
    if session.get('email'):
        return f"email:{session['email']}"
    return f"guest:{request.remote_addr or 'local'}"


def _read_json_file(path_obj, fallback):
    try:
        if path_obj.exists():
            with path_obj.open('r', encoding='utf-8') as fh:
                return json.load(fh)
    except Exception:
        pass
    return fallback


def _default_learning_progress():
    return {
        'xp': 0,
        'coins': 0,
        'gems': 0,
        'hearts': 5,
        'streak_days': 0,
        'streak_freezes': 0,
        'badges': [],
        'completed_lessons': [],
        'total_lesson_attempts': 0,
        'total_questions_answered': 0,
        'total_correct_answers': 0,
        'total_xp_earned': 0,
        'last_activity_day': None,
    }


def _compute_next_streak(previous_streak, last_activity_day):
    today = datetime.utcnow().date()
    if not last_activity_day:
        return 1

    try:
        last_day = datetime.strptime(last_activity_day, '%Y-%m-%d').date()
    except Exception:
        return 1

    gap_days = (today - last_day).days
    if gap_days <= 0:
        # Same day completion does not inflate streak.
        return int(previous_streak or 0)
    if gap_days == 1:
        return int(previous_streak or 0) + 1
    return 1


def _get_learning_progress(user_key):
    progress = db.learning_progress.find_one({'user_key': user_key}, {'_id': 0, 'user_key': 0})
    base = _default_learning_progress()
    if progress:
        base.update(progress)
    return base


def _save_learning_progress(user_key, payload):
    payload = dict(payload)
    payload['updated_at'] = _utc_now()
    db.learning_progress.update_one({'user_key': user_key}, {'$set': payload}, upsert=True)


def _ensure_learning_indexes_and_seed_data():
    db.learning_progress.create_index('user_key', unique=True, name='learning_progress_user_key_unique')
    db.learning_progress.create_index('xp', name='learning_progress_xp_idx')

    db.learning_sessions.create_index('session_id', unique=True, name='learning_session_id_unique')
    db.learning_sessions.create_index([('user_key', 1), ('lesson_id', 1), ('started_at', -1)], name='learning_session_user_lesson_idx')

    db.learning_answer_attempts.create_index([('session_id', 1), ('question_id', 1), ('attempt_index', 1)], name='learning_answer_attempt_idx')
    db.learning_answer_attempts.create_index([('user_key', 1), ('created_at', -1)], name='learning_answer_user_time_idx')

    db.learning_lesson_reports.create_index([('user_key', 1), ('lesson_id', 1), ('completed_at', -1)], name='learning_report_user_lesson_idx')

    db.learning_quests.create_index('quest_id', unique=True, name='learning_quest_id_unique')
    db.learning_quests.create_index('window', name='learning_quest_window_idx')

    if db.learning_quests.count_documents({}) == 0:
        db.learning_quests.insert_many([
            {'quest_id': 'dq_1', 'title': 'Complete 2 lessons', 'reward_xp': 30, 'window': 'daily', 'active': True},
            {'quest_id': 'dq_2', 'title': 'Maintain streak today', 'reward_xp': 20, 'window': 'daily', 'active': True},
            {'quest_id': 'dq_3', 'title': 'Get 8 correct answers', 'reward_xp': 35, 'window': 'daily', 'active': True},
        ])


def _build_fallback_memory_tips(incorrect_items):
    def _is_letter_or_digit(token):
        s = str(token or '').strip()
        return len(s) == 1 and s.isalnum()

    def _tailored_tip(correct, selected):
        correct = str(correct or '').strip()
        selected = str(selected or '').strip()

        if _is_letter_or_digit(correct):
            return (
                f"Contrast drill '{selected}' vs '{correct}': watch the clip for '{correct}', then freeze the final handshape for 2 seconds and trace '{correct}' in the air 5 times. "
                f"Do a 5-3-1 recall set: 5 reps now, 3 reps after 10 minutes, 1 rep after 24 hours."
            )

        return (
            f"Memory anchor for '{correct}': say the word aloud while performing the sign 6 times, then do 3 contrast reps where you alternate '{selected}' and '{correct}' to feel the difference. "
            f"Finish with delayed recall: perform '{correct}' once after 10 minutes and once before sleep."
        )

    tips = []
    for item in incorrect_items:
        correct = item.get('correct_answer', 'the correct sign')
        selected = item.get('selected', 'your answer')
        tips.append(
            {
                'question_id': item.get('question_id', ''),
                'correct_answer': correct,
                'selected': selected,
                'suggestion': _tailored_tip(correct, selected),
            }
        )
    return tips


def _gemini_memory_tips(incorrect_items, lesson_context):
    api_key = os.getenv('GEMINI_API_KEY', '').strip()
    gemini_text_model = os.getenv('GEMINI_TEXT_MODEL', 'gemini-1.5-flash').strip()
    if not api_key or not incorrect_items:
        return _build_fallback_memory_tips(incorrect_items)

    prompt_lines = [
        'You are a sign-language memory coach.',
        'Task: write concrete memorization coaching for each incorrect answer.',
        'Hard constraints:',
        '1) NO generic advice (no lines like "practice more" or "keep trying").',
        '2) Each tip MUST explicitly mention both selected and correct answers.',
        '3) Each tip MUST include: contrast drill + repetition schedule + delayed recall checkpoint.',
        '4) Keep each tip 1-2 sentences, practical, and action-oriented.',
        'Return strict JSON only in this schema:',
        '{"tips":[{"question_id":"...","suggestion":"..."}]}',
        f"Lesson context: {lesson_context}",
    ]
    for idx, item in enumerate(incorrect_items, start=1):
        prompt_lines.append(
            f"{idx}. selected='{item.get('selected')}', correct='{item.get('correct_answer')}', prompt='{item.get('prompt')}'"
        )

    payload = {
        'contents': [
            {
                'parts': [
                    {'text': '\n'.join(prompt_lines)}
                ]
            }
        ],
        'generationConfig': {
            'temperature': 0.3,
            'maxOutputTokens': 400,
        },
    }

    try:
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1/models/{gemini_text_model}:generateContent?key={api_key}",
            json=payload,
            timeout=12,
        )
        response.raise_for_status()
        data = response.json()
        text = (
            data.get('candidates', [{}])[0]
            .get('content', {})
            .get('parts', [{}])[0]
            .get('text', '')
        )

        cleaned = text.strip()
        if cleaned.startswith('```'):
            cleaned = cleaned.strip('`')
            cleaned = cleaned.replace('json\n', '', 1).strip()

        parsed = json.loads(cleaned)
        raw_tips = parsed.get('tips', []) if isinstance(parsed, dict) else []
        if not raw_tips:
            return _build_fallback_memory_tips(incorrect_items)

        fallback_tips = _build_fallback_memory_tips(incorrect_items)

        def _is_generic_tip(tip_text, selected, correct):
            text = str(tip_text or '').strip().lower()
            if not text:
                return True

            generic_markers = [
                'practice more',
                'keep trying',
                'replay that sign 5 times',
                'say the word aloud',
                'test yourself again after 10 minutes',
                'good job',
            ]
            if any(marker in text for marker in generic_markers):
                return True

            # Must mention both the mistaken and correct answer for contrast coaching.
            selected_s = str(selected or '').strip().lower()
            correct_s = str(correct or '').strip().lower()
            if selected_s and selected_s not in text:
                return True
            if correct_s and correct_s not in text:
                return True

            # Must include concrete memory structure cues.
            required_cues = ['contrast', 'recall']
            if not any(cue in text for cue in required_cues):
                return True

            return False

        tips = []
        for idx, item in enumerate(incorrect_items):
            if idx < len(raw_tips):
                tip_line = str(raw_tips[idx].get('suggestion', '')).strip()
            else:
                tip_line = ''

            selected = item.get('selected', '')
            correct = item.get('correct_answer', '')

            if _is_generic_tip(tip_line, selected, correct):
                tip_line = fallback_tips[idx]['suggestion']

            tips.append(
                {
                    'question_id': item.get('question_id', ''),
                    'correct_answer': correct,
                    'selected': selected,
                    'suggestion': tip_line,
                }
            )
        return tips
    except Exception:
        return _build_fallback_memory_tips(incorrect_items)


def _asset_for_word(word):
    stem = _resolve_token_to_asset(str(word).strip().lower())
    if not stem:
        stem = str(word).strip()
    return f"static/assets/{stem}.mp4"


def correct_sentence_with_gemini(sentence: str) -> str:
    clean_sentence = str(sentence or "").strip()
    if not clean_sentence:
        app.logger.info("Gemini correction skipped: empty sentence.")
        return ""

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        app.logger.warning("Gemini correction skipped: GEMINI_API_KEY is not set.")
        return clean_sentence

    model_name = os.getenv("GEMINI_TEXT_MODEL", "gemini-1.5-flash").strip() or "gemini-1.5-flash"

    try:
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": (
                                "You are a grammar and fluency editor for sign-language-to-text output.\n"
                                "Rewrite the text into one clean, natural English sentence.\n"
                                "You may reorder words if needed, but keep the original meaning.\n"
                                "Do not return the exact input if it is not grammatical.\n"
                                "Return only the corrected sentence, no explanation.\n"
                                f"Input: {clean_sentence}"
                            )
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 120,
            },
        }
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1/models/{model_name}:generateContent?key={api_key}",
            json=payload,
            timeout=12,
        )
        response.raise_for_status()
        data = response.json()
        corrected = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
            .strip()
        )
        if corrected:
            app.logger.info(
                "Gemini correction success | input='%s' | output='%s' | model='%s'",
                clean_sentence,
                corrected,
                model_name,
            )
            return corrected

        app.logger.warning(
            "Gemini correction empty output; using original sentence. input='%s' model='%s'",
            clean_sentence,
            model_name,
        )
        return clean_sentence
    except Exception as exc:
        app.logger.exception(
            "Gemini correction failed; using original sentence. input='%s' model='%s' error='%s'",
            clean_sentence,
            model_name,
            exc,
        )
        return clean_sentence


def _augment_quiz_questions(lesson, quiz):
    if not lesson:
        return quiz or {'questions': []}

    quiz_payload = dict(quiz or {'lesson_id': lesson.get('lesson_id'), 'questions': []})
    existing_questions = list(quiz_payload.get('questions', []))
    target_words = list(lesson.get('target_words', []))

    covered_correct = {q.get('correct') for q in existing_questions}
    missing_words = [w for w in target_words if w not in covered_correct]

    if not missing_words:
        quiz_payload['questions'] = existing_questions
        return quiz_payload

    options_pool = [str(w) for w in target_words]
    next_index = len(existing_questions) + 1
    lesson_id = lesson.get('lesson_id', 'lesson')

    for word in missing_words:
        distractors = [opt for opt in options_pool if opt != word][:3]
        options = distractors + [word]

        if len(options) < 4:
            filler = ['Hello', 'Good', 'Study', 'Help']
            for item in filler:
                if item not in options:
                    options.append(item)
                if len(options) == 4:
                    break

        # Keep order deterministic but avoid always placing correct answer last.
        rotate = (next_index - 1) % len(options)
        options = options[rotate:] + options[:rotate]

        existing_questions.append(
            {
                'question_id': f"{lesson_id}_q{next_index:02d}",
                'type': 'identify_sign_from_video',
                'prompt': 'Watch the sign and choose the correct word.',
                'asset': _asset_for_word(word),
                'options': options[:4],
                'correct': word,
                'xp_on_correct': 10,
            }
        )
        next_index += 1

    quiz_payload['questions'] = existing_questions
    return quiz_payload


def _lesson_payload(lesson_id):
    lessons = _read_json_file(LEARNING_LESSONS_FILE, [])
    quizzes = _read_json_file(LEARNING_QUIZ_FILE, [])
    lesson = next((l for l in lessons if l.get('lesson_id') == lesson_id), None)
    quiz = next((q for q in quizzes if q.get('lesson_id') == lesson_id), None)
    return lesson, _augment_quiz_questions(lesson, quiz)


_ensure_learning_indexes_and_seed_data()


# Routes
@app.route('/')
def home():
    if 'username' in session:
        return render_template('home.html', username=session['username'])
    return render_template('home.html', username=None)

@app.route('/index')
def index():
    if 'username' in session:
        return render_template('index.html', username=session['username'])
    flash('Please log in first', 'danger')
    return redirect(url_for('login'))


@app.route('/learning')
def learning():
    if not session.get('username'):
        return redirect(url_for('login', next=request.url))  # 🔒 only after login
    return render_template('learning.html', username=session.get('username'))

@app.get('/api/v1/learning/state')
def learning_state():
    progress = _get_learning_progress(_learning_user_key())
    return jsonify(progress)


@app.get('/api/v1/quests/today')
def quests_today():
    quests = list(
        db.learning_quests.find({'window': 'daily', 'active': True}, {'_id': 0}).sort('quest_id', 1)
    )
    return jsonify({'quests': quests})


@app.get('/api/v1/learning/path')
def learning_path():
    level_data = _read_json_file(LEARNING_LEVELS_FILE, {'levels': []})
    lesson_data = _read_json_file(LEARNING_LESSONS_FILE, [])
    progress = _get_learning_progress(_learning_user_key())
    completed = set(progress.get('completed_lessons', []))

    lesson_by_sublevel = {}
    for lesson in lesson_data:
        lesson_by_sublevel.setdefault(lesson.get('sublevel', ''), []).append(lesson)

    for sublevel_name in lesson_by_sublevel:
        lesson_by_sublevel[sublevel_name].sort(key=lambda x: x.get('lesson_id', ''))

    path_levels = []
    unlocked_next = True
    for level in level_data.get('levels', []):
        level_payload = {'name': level.get('name', ''), 'sublevels': []}
        for sub in level.get('sublevels', []):
            sub_name = sub.get('name', '')
            lessons = lesson_by_sublevel.get(sub_name, [])
            lesson_nodes = []
            for idx, lesson in enumerate(lessons):
                lesson_id = lesson.get('lesson_id', '')
                is_completed = lesson_id in completed
                is_unlocked = unlocked_next or is_completed or (idx == 0 and not completed)
                lesson_nodes.append(
                    {
                        'lesson_id': lesson_id,
                        'label': f"Lesson {idx + 1}",
                        'goal': lesson.get('lesson_goal', ''),
                        'word_count': len(lesson.get('target_words', [])),
                        'completed': is_completed,
                        'unlocked': bool(is_unlocked),
                        'target_words': lesson.get('target_words', []),
                    }
                )
                if is_completed:
                    unlocked_next = True
                elif is_unlocked:
                    unlocked_next = False
            level_payload['sublevels'].append({'name': sub_name, 'lessons': lesson_nodes})
        path_levels.append(level_payload)

    return jsonify({'levels': path_levels})


@app.get('/api/v1/learning/lesson/<lesson_id>')
def learning_lesson_detail(lesson_id):
    lesson, quiz = _lesson_payload(lesson_id)
    if not lesson:
        return jsonify({'error': 'Lesson not found'}), 404
    return jsonify({'lesson': lesson, 'quiz': quiz or {'questions': []}})


@app.post('/api/v1/learning/session/start')
def learning_session_start():
    payload = request.get_json(silent=True) or {}
    lesson_id = payload.get('lesson_id', '').strip()
    sublevel = payload.get('sublevel', '').strip()

    if not lesson_id:
        return jsonify({'error': 'lesson_id is required'}), 400

    lesson, quiz = _lesson_payload(lesson_id)
    if not lesson or not quiz:
        return jsonify({'error': 'Lesson quiz not found'}), 404

    user_key = _learning_user_key()
    attempt_number = (
        db.learning_sessions.count_documents({'user_key': user_key, 'lesson_id': lesson_id}) + 1
    )
    session_id = uuid.uuid4().hex
    quiz_questions = quiz.get('questions', [])

    db.learning_sessions.insert_one(
        {
            'session_id': session_id,
            'user_key': user_key,
            'lesson_id': lesson_id,
            'sublevel': sublevel or lesson.get('sublevel', ''),
            'level': lesson.get('level', ''),
            'attempt_number': attempt_number,
            'status': 'in_progress',
            'started_at': _utc_now(),
            'question_count': len(quiz_questions),
            'correct_answers': 0,
            'wrong_answers': 0,
            'points_scored': 0,
            'xp_scored': 0,
            'coins_scored': 0,
            'answers': [],
            'quiz_snapshot': quiz_questions,
        }
    )

    return jsonify(
        {
            'session_id': session_id,
            'status': 'started',
            'attempt_number': attempt_number,
            'question_count': len(quiz_questions),
            'started_at': _utc_now().isoformat(),
        }
    )


@app.post('/api/v1/learning/answer')
def learning_answer_submit():
    payload = request.get_json(silent=True) or {}
    session_id = payload.get('session_id', '').strip()
    question_id = payload.get('question_id', '').strip()
    selected = payload.get('selected')

    if not session_id or not question_id:
        return jsonify({'error': 'session_id and question_id are required'}), 400

    session_doc = db.learning_sessions.find_one({'session_id': session_id})
    if not session_doc:
        return jsonify({'error': 'Session not found'}), 404

    questions = session_doc.get('quiz_snapshot', [])
    question = next((q for q in questions if q.get('question_id') == question_id), None)
    if not question:
        return jsonify({'error': 'Question not found for session'}), 404

    correct_answer = question.get('correct')
    is_correct = selected == correct_answer
    xp_delta = int(question.get('xp_on_correct', 10)) if is_correct else 0
    points_delta = xp_delta
    coins_delta = 3 if is_correct else 0

    attempt_index = (
        db.learning_answer_attempts.count_documents({'session_id': session_id, 'question_id': question_id}) + 1
    )
    now = _utc_now()

    db.learning_answer_attempts.insert_one(
        {
            'session_id': session_id,
            'user_key': session_doc.get('user_key'),
            'lesson_id': session_doc.get('lesson_id'),
            'question_id': question_id,
            'prompt': question.get('prompt', ''),
            'selected': selected,
            'correct_answer': correct_answer,
            'is_correct': bool(is_correct),
            'attempt_index': attempt_index,
            'created_at': now,
        }
    )

    db.learning_sessions.update_one(
        {'session_id': session_id},
        {
            '$inc': {
                'correct_answers': 1 if is_correct else 0,
                'wrong_answers': 0 if is_correct else 1,
                'points_scored': points_delta,
                'xp_scored': xp_delta,
                'coins_scored': coins_delta,
            },
            '$push': {
                'answers': {
                    'question_id': question_id,
                    'prompt': question.get('prompt', ''),
                    'selected': selected,
                    'correct_answer': correct_answer,
                    'is_correct': bool(is_correct),
                    'attempt_index': attempt_index,
                    'answered_at': now,
                }
            },
            '$set': {'last_answered_at': now},
        },
    )

    return jsonify(
        {
            'correct': bool(is_correct),
            'correct_answer': correct_answer,
            'xp_delta': xp_delta,
            'points_delta': points_delta,
            'coins_delta': coins_delta,
        }
    )


@app.post('/api/v1/learning/complete')
def learning_complete():
    payload = request.get_json(silent=True) or {}
    session_id = payload.get('session_id', '').strip()

    session_doc = None
    if session_id:
        session_doc = db.learning_sessions.find_one({'session_id': session_id})

    if not session_doc:
        return jsonify({'error': 'session_id is required and must be valid'}), 400

    lesson_id = session_doc.get('lesson_id', '')
    total_questions = max(int(session_doc.get('question_count', 0)), 1)
    correct_answers = int(session_doc.get('correct_answers', 0))
    wrong_answers = int(session_doc.get('wrong_answers', 0))
    score_percent = int(round((correct_answers / total_questions) * 100))

    points_scored = int(session_doc.get('points_scored', 0))
    xp_scored = int(session_doc.get('xp_scored', 0))
    coins_scored = int(session_doc.get('coins_scored', 0))

    xp_bonus = 25 if score_percent == 100 else (10 if score_percent >= 80 else 0)
    coins_bonus = 10 if score_percent >= 80 else 0
    gems_awarded = 1 if score_percent >= 90 else 0

    xp_awarded = xp_scored + xp_bonus
    coins_awarded = coins_scored + coins_bonus
    hearts_delta = 0 if score_percent >= 80 else -1

    incorrect_items = [a for a in session_doc.get('answers', []) if not a.get('is_correct')]
    lesson_context = f"Lesson {lesson_id}, score {score_percent}%"
    suggestions = _gemini_memory_tips(incorrect_items, lesson_context)

    user_key = session_doc.get('user_key') or _learning_user_key()
    progress = _get_learning_progress(user_key)
    next_streak = _compute_next_streak(
        progress.get('streak_days', 0),
        progress.get('last_activity_day')
    )

    completed_lessons = list(progress.get('completed_lessons', []))
    if lesson_id and lesson_id not in completed_lessons:
        completed_lessons.append(lesson_id)

    updated_progress = dict(progress)
    updated_progress.update(
        {
            'xp': int(progress.get('xp', 0)) + xp_awarded,
            'coins': int(progress.get('coins', 0)) + coins_awarded,
            'gems': int(progress.get('gems', 0)) + gems_awarded,
            'hearts': max(0, min(5, int(progress.get('hearts', 5)) + hearts_delta)),
            'streak_days': next_streak,
            'completed_lessons': completed_lessons,
            'total_lesson_attempts': int(progress.get('total_lesson_attempts', 0)) + 1,
            'total_questions_answered': int(progress.get('total_questions_answered', 0)) + total_questions,
            'total_correct_answers': int(progress.get('total_correct_answers', 0)) + correct_answers,
            'total_xp_earned': int(progress.get('total_xp_earned', 0)) + xp_awarded,
            'last_activity_day': time.strftime('%Y-%m-%d'),
        }
    )
    _save_learning_progress(user_key, updated_progress)

    now = _utc_now()
    db.learning_sessions.update_one(
        {'session_id': session_id},
        {
            '$set': {
                'status': 'completed',
                'completed_at': now,
                'score_percent': score_percent,
                'xp_awarded': xp_awarded,
                'coins_awarded': coins_awarded,
                'gems_awarded': gems_awarded,
                'suggestions': suggestions,
            }
        },
    )

    db.learning_lesson_reports.insert_one(
        {
            'session_id': session_id,
            'user_key': user_key,
            'lesson_id': lesson_id,
            'attempt_number': int(session_doc.get('attempt_number', 1)),
            'score_percent': score_percent,
            'correct_answers': correct_answers,
            'wrong_answers': wrong_answers,
            'total_questions': total_questions,
            'points_scored': points_scored,
            'xp_scored': xp_scored,
            'xp_awarded': xp_awarded,
            'coins_awarded': coins_awarded,
            'gems_awarded': gems_awarded,
            'incorrect_suggestions': suggestions,
            'completed_at': now,
        }
    )

    return jsonify(
        {
            'state': updated_progress,
            'stats': {
                'correct_answers': correct_answers,
                'wrong_answers': wrong_answers,
                'total_questions': total_questions,
                'score_percent': score_percent,
                'points_scored': points_scored,
                'xp_scored': xp_scored,
                'xp_awarded': xp_awarded,
                'coins_awarded': coins_awarded,
                'gems_awarded': gems_awarded,
            },
            'memory_suggestions': suggestions,
            'session_id': session_id,
        }
    )

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        username = form.username.data
        email = form.email.data
        password = generate_password_hash(form.password.data)

        existing_user = db.users.find_one({"email": email})
        if existing_user:
            flash('Email already registered', 'danger')
            return redirect(url_for('register'))

        db.users.insert_one({
            "username": username,
            "email": email,
            "password": password,
            "profile_picture": None
        })

        flash('You are now registered and can log in', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password_candidate = form.password.data

        user = db.users.find_one({"email": email})

        if user:
            if check_password_hash(user['password'], password_candidate):
                session['logged_in'] = True
                session['username'] = user['username']
                session['email'] = user['email']
                session['user_id'] = str(user['_id'])
                
                # Session and Login History
                session_id = str(uuid.uuid4())
                db.sessions.insert_one({
                    "session_id": session_id,
                    "user_id": str(user['_id']),
                    "created_at": datetime.now(),
                    "last_active": datetime.now()
                })
                
                ip_address = request.remote_addr
                db.user_login_history.insert_one({
                    "user_id": str(user['_id']),
                    "ip_address": ip_address,
                    "successful": 1
                })
                
                db.logs.insert_one({
                    "user_id": str(user['_id']),
                    "activity_type": 'login',
                    "description": f"{user['username']} logged in",
                    "timestamp": datetime.now()
                })
                session['session_id'] = session_id
                
                flash('You are now logged in', 'success')
                return redirect(url_for('index'))
            else:
                flash('Invalid password', 'danger')
        else:
            flash('User not registered', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
def logout():
    if 'user_id' in session:
        user_id = session['user_id']
        username = session['username']
        
        db.logs.insert_one({
            "user_id": user_id, 
            "activity_type": 'logout', 
            "description": f'{username} logged out',
            "timestamp": datetime.now()
        })
        ip_address = request.remote_addr
        db.user_login_history.insert_one({
            "user_id": user_id,
            "ip_address": ip_address,
            "successful": 0
        })

    if 'session_id' in session:
        session_id = session['session_id']
        db.sessions.update_one(
            {"session_id": session_id},
            {"$set": {"last_active": datetime.now()}}
        )
        
    session.clear()
    flash('You have been successfully logged out!', 'success')
    return redirect(url_for('login'))

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'email' not in session:
        flash('Please log in to view your profile.', 'danger')
        return redirect(url_for('login'))

    user = db.users.find_one({"email": session['email']})

    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('logout'))

    user_data = {
        'id': str(user['_id']),
        'username': user.get('username', ''),
        'email': user.get('email', ''),
        'profile_picture': user.get('profile_picture')
    }

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        profile_picture = request.files.get('profile_picture')

        update_fields = {
            "username": username,
            "email": email
        }

        if profile_picture:
            upload_folder = os.path.join(app.root_path, 'static', 'uploads')
            os.makedirs(upload_folder, exist_ok=True)
            
            image_filename = secure_filename(profile_picture.filename)
            profile_picture.save(os.path.join(upload_folder, image_filename))
            db_path = f'uploads/{image_filename}'
            update_fields['profile_picture'] = db_path

        db.users.update_one({"email": session['email']}, {"$set": update_fields})
        
        if email != session['email']:
            session['email'] = email
            
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))


    return render_template('profile.html', user=user_data)

@app.route('/dashboard')
def dashboard():
    if 'username' in session:
        return render_template('dashboard.html', username=session['username'])
    flash('Please log in first', 'danger')
    return redirect(url_for('login'))

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if 'username' in session:
        if request.method == 'POST':
            selected_theme = request.form.get('theme')
            session['theme'] = selected_theme

            db.settings.update_one(
                {"settings_user_id": session['user_id']},
                {"$set": {"dark_mode": selected_theme}},
                upsert=True
            )

            flash(f'Theme changed to {selected_theme}!', 'success')
            return redirect(url_for('settings'))
        
        theme_record = db.settings.find_one({"settings_user_id": session['user_id']})
        current_theme = theme_record.get('dark_mode') if theme_record else session.get('theme', 'default')

        return render_template('settings.html', username=session['username'], theme=current_theme)

    flash('Please log in first', 'danger')
    return redirect(url_for('login'))

@app.before_request
def before_request():
    g.language = session.get('language', 'en')

@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    if 'username' not in session:
        flash('Please log in first', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        feedback_text = request.form.get('feedback')
        rating = request.form.get('rating')
        
        if not feedback_text:
            flash('Feedback cannot be empty!', 'danger')
            return redirect(url_for('feedback'))
        
        if rating == '':
            rating = None
            
        db.feedback.insert_one({
            "feedback_user_id": session['user_id'],
            "message": feedback_text,
            "rating": rating,
            "timestamp": datetime.now()
        })

        flash('Your feedback has been submitted!', 'success')
        return redirect(url_for('feedback'))

    return render_template('feedback.html', username=session['username'])

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if 'username' not in session:
        flash('Please log in first', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        message = request.form['message']
        
        user_id = session.get('user_id')
        if user_id:
            db.contact.insert_one({
                "customer_id": user_id, 
                "message": message,
                "timestamp": datetime.now()
            })
            flash('Your message has been sent!', 'success')
        else:
            flash('User not found. Please log in again.', 'danger')

        return redirect(url_for('contact'))

    return render_template('contact.html', username=session['username'])

@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/animation_home')
def animation_home():
    return render_template('animation_home.html')

@app.route('/animation', methods=['GET', 'POST'])
def animation():
    if 'username' not in session:
        flash('Please log in to use the animation feature.', 'danger')
        return redirect(url_for('login'))

    text = ""
    words = []

    if request.method == 'POST':
        text = request.form.get('sen', '')
        remove_stopwords = request.form.get('remove_stopwords') == 'on'
        words = process_text_for_animation(text, remove_stopwords=remove_stopwords)

    return render_template('animation.html', words=words, text=text)


@app.route('/speech_to_text', methods=['POST'])
def speech_to_text():
    if 'username' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    audio_file = request.files.get('audio')
    if not audio_file:
        return jsonify({"error": "No audio file provided"}), 400

    try:
        # Save WEBM file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
            input_path = tmp.name
            audio_file.save(input_path)

        # Convert WEBM â†’ WAV
        wav_path = input_path.replace(".webm", ".wav")

        audio = AudioSegment.from_file(input_path, format="webm")
        audio.export(wav_path, format="wav", parameters=["-ac", "1", "-ar", "16000"])

        # Speech Recognition
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)

        text = recognizer.recognize_google(audio_data)

        return jsonify({"text": text})

    except Exception as e:
        return jsonify({"error": f"Speech processing failed: {str(e)}"}), 500
@app.route('/text_to_speech', methods=['POST'])
def text_to_speech():
    if 'username' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    text = data.get("text", "")

    if not text:
        return jsonify({"error": "No text provided"}), 400

    try:
        api_key = os.getenv("ELEVENLABS_API_KEY")

        url = "https://api.elevenlabs.io/v1/text-to-speech/JBFqnCBsd6RMkjVDRZzb"

        headers = {
            "xi-api-key": api_key,
            "Content-Type": "application/json"
        }

        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2"
        }

        response = requests.post(url, json=payload, headers=headers)

        if response.status_code != 200:
            return jsonify({"error": "TTS failed"}), 500

        # Save audio
        filename = f"{uuid.uuid4()}.mp3"
        filepath = os.path.join("static", filename)

        with open(filepath, "wb") as f:
            f.write(response.content)

        return jsonify({"audio_url": url_for('static', filename=filename)})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
# Video Stream Routes
MODEL_CHECKPOINT = Path(os.getenv("Vyakt_MODEL_PATH", "Model/artifacts/gesture_transformer.pth"))
LABEL_MAP_PATH = Path(os.getenv("Vyakt_LABEL_MAP_PATH", "Model/artifacts/label_map.json"))
MODEL_DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
CAMERA_INDEX = int(os.getenv("Vyakt_CAMERA_INDEX", "0"))
CAMERA_BACKEND = cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY
PREDICTION_CONFIDENCE_THRESHOLD = float(os.getenv("Vyakt_CONFIDENCE_THRESHOLD", "0.70"))
UNKNOWN_CONFIDENCE_THRESHOLD = float(os.getenv("Vyakt_UNKNOWN_THRESHOLD", "0.50"))


def load_gesture_model():
    if not MODEL_CHECKPOINT.exists():
        print(f"Model checkpoint not found: {MODEL_CHECKPOINT}")
        return None, [], SEQUENCE_LENGTH, FEATURE_SIZE

    try:
        checkpoint = torch.load(MODEL_CHECKPOINT, map_location=MODEL_DEVICE)

        sequence_length = int(checkpoint.get("sequence_length", SEQUENCE_LENGTH))
        feature_size = int(checkpoint.get("feature_size", FEATURE_SIZE))
        num_classes = int(checkpoint.get("num_classes", 0))

        label_map = list(checkpoint.get("label_map", []))
        if LABEL_MAP_PATH.exists():
            with open(LABEL_MAP_PATH, "r", encoding="utf-8") as f:
                label_json = json.load(f)
            index_to_label = label_json.get("index_to_label", {})
            label_map = [
                index_to_label[str(i)]
                for i in range(len(index_to_label))
                if str(i) in index_to_label
            ]

        if not label_map and num_classes > 0:
            label_map = [str(i) for i in range(num_classes)]

        if num_classes <= 0:
            num_classes = len(label_map)

        model = GestureTransformer(
            input_dim=feature_size,
            seq_length=sequence_length,
            num_classes=max(num_classes, 1),
        )
        model.load_state_dict(checkpoint["model_state_dict"])
        model.to(MODEL_DEVICE)
        model.eval()

        if label_map and len(label_map) != num_classes:
            print(
                f"Label map size ({len(label_map)}) does not match model classes ({num_classes}). "
                "Using checkpoint label_map fallback where possible."
            )
            checkpoint_label_map = list(checkpoint.get("label_map", []))
            if len(checkpoint_label_map) == num_classes:
                label_map = checkpoint_label_map

        return model, label_map, sequence_length, feature_size
    except Exception as exc:
        print(f"Error loading gesture model: {exc}")
        return None, [], SEQUENCE_LENGTH, FEATURE_SIZE


gesture_model, gesture_labels, model_sequence_length, model_feature_size = load_gesture_model()


def _error_frame(message: str, width: int = 960, height: int = 540) -> bytes:
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    cv2.putText(
        frame,
        "Sign-to-text stream unavailable",
        (30, 60),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (0, 0, 255),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        frame,
        message[:95],
        (30, 105),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    ok, buffer = cv2.imencode(".jpg", frame)
    if not ok:
        return b""
    return buffer.tobytes()


def _yield_error_stream(message: str):
    frame = _error_frame(message)
    if not frame:
        return
    while True:
        yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        time.sleep(0.5)


@app.route('/generate_frames')
def generate_frames():
    global latest_prediction, is_capturing, captured_sequence

    try:
        from mediapipe import solutions as mp_solutions
    except ImportError:
        message = "mediapipe import failed."
        yield from _yield_error_stream(message)
        return

    with camera_lock:
        cap = cv2.VideoCapture(CAMERA_INDEX, CAMERA_BACKEND)

        if not cap.isOpened():
            yield from _yield_error_stream("Camera not opening")
            return

        mp_hands = mp_solutions.hands
        mp_drawing = mp_solutions.drawing_utils

        hands = mp_hands.Hands(
            static_image_mode=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
            max_num_hands=2,
        )

        sequence = deque(maxlen=model_sequence_length)
        prediction_text = ""
        prediction_confidence = 0.0
        last_added = ""

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = hands.process(frame_rgb)

                if results and results.multi_hand_landmarks:
                    for hand_landmarks in results.multi_hand_landmarks:
                        mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

                current_features = extract_landmark_features(results)
                has_hand_landmarks = bool(results and results.multi_hand_landmarks)
                no_hand_frame = (not has_hand_landmarks) or is_no_hand_feature_vector(current_features)

                if no_hand_frame:
                    sequence.clear()
                    prediction_text = ""
                    prediction_confidence = 0.0
                    latest_prediction = {"text": "", "confidence": 0.0, "state": "no_hand"}
                else:
                    sequence.append(current_features)
                    latest_prediction = {"text": "Identifying", "confidence": 0.0, "state": "identifying"}

                    if gesture_model is not None and len(sequence) == model_sequence_length:
                        input_np = normalize_sequence(
                            sequence,
                            sequence_length=model_sequence_length,
                            feature_size=model_feature_size,
                        )
                        input_tensor = torch.tensor(input_np, dtype=torch.float32).unsqueeze(0).to(MODEL_DEVICE)

                        with torch.no_grad():
                            logits = gesture_model(input_tensor)
                            probs = torch.softmax(logits, dim=1)
                            top_confidence, top_index = torch.max(probs, dim=1)
                            pred_idx = int(top_index.item())
                            prediction_confidence = float(top_confidence.item())

                        if gesture_labels and pred_idx < len(gesture_labels):
                            raw_label = str(gesture_labels[pred_idx])

                            if prediction_confidence < UNKNOWN_CONFIDENCE_THRESHOLD:
                                prediction_text = "Unknown Gesture"
                                prediction_state = "unknown"
                            elif prediction_confidence < PREDICTION_CONFIDENCE_THRESHOLD:
                                prediction_text = "Identifying"
                                prediction_state = "identifying"
                            else:
                                prediction_text = raw_label
                                prediction_state = "predicted"

                            latest_prediction = {
                                "text": prediction_text,
                                "confidence": round(prediction_confidence, 4),
                                "state": prediction_state,
                            }

                            if is_capturing and prediction_state == "predicted":
                                if prediction_text != last_added:
                                    captured_sequence.append(prediction_text)
                                    last_added = prediction_text

                if prediction_text:
                    overlay_confidence = int(round(prediction_confidence * 100))
                    cv2.putText(
                        frame,
                        f"Prediction: {prediction_text} ({overlay_confidence}%)",
                        (10, 35),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1.0,
                        (0, 255, 0),
                        2,
                        cv2.LINE_AA,
                    )

                ok, buffer = cv2.imencode('.jpg', frame)
                if not ok:
                    continue

                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' +
                       buffer.tobytes() + b'\r\n')

        finally:
            cap.release()
            hands.close()

@app.route('/get_prediction')
def get_prediction():
    global latest_prediction
    return jsonify(latest_prediction)


def _build_sentence_from_gesture_tokens(tokens):
    cleaned_tokens = [str(token).strip() for token in tokens if str(token).strip()]
    if not cleaned_tokens:
        return "", ""

    if all(token.isdigit() for token in cleaned_tokens):
        digit_string = "".join(cleaned_tokens)
        try:
            return digit_string, num2words(int(digit_string))
        except Exception:
            return digit_string, digit_string

    sentence = " ".join(cleaned_tokens)
    return sentence, sentence


@app.route('/start_capture', methods=['POST'])
def start_capture():
    global captured_sequence, is_capturing, latest_prediction
    captured_sequence = []
    is_capturing = True
    latest_prediction = {"text": "", "confidence": 0.0, "state": "idle"}
    return jsonify({"status": "started"})

@app.route('/stop_capture', methods=['POST'])
def stop_capture():
    global captured_sequence, is_capturing

    is_capturing = False

    if not captured_sequence:
        return jsonify({
            "sequence": [],
            "combined": "",
            "words": "No input detected"
        })

    combined, words = _build_sentence_from_gesture_tokens(captured_sequence)
    corrected_words = correct_sentence_with_gemini(words)

    return jsonify({
        "sequence": captured_sequence,
        "combined": combined,
        "words": corrected_words,
        "original_words": words
    })
@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


if __name__ == '__main__':
    host = os.getenv('FLASK_HOST', '127.0.0.1')
    port = int(os.getenv('FLASK_PORT', '5000'))
    debug = os.getenv('FLASK_DEBUG', 'true').lower() in {'1', 'true', 'yes', 'on'}
    app.run(host=host, port=port, debug=debug)

