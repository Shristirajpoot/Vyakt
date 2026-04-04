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
latest_prediction = ""
captured_sequence = []
is_capturing = False
from Model.features import FEATURE_SIZE, SEQUENCE_LENGTH, extract_landmark_features, normalize_sequence
from Model.gesture_model import GestureTransformer
from pydub import AudioSegment


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

        # Convert WEBM → WAV
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
MODEL_CHECKPOINT = Path(os.getenv("GESTURA_MODEL_PATH", "Model/artifacts/gesture_transformer.pth"))
LABEL_MAP_PATH = Path(os.getenv("GESTURA_LABEL_MAP_PATH", "Model/artifacts/label_map.json"))
MODEL_DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
CAMERA_INDEX = int(os.getenv("GESTURA_CAMERA_INDEX", "0"))
CAMERA_BACKEND = cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY


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

    with camera_lock:  # ✅ FIX: prevent multiple access
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

                sequence.append(extract_landmark_features(results))

                if gesture_model is not None and len(sequence) == model_sequence_length:
                    input_np = normalize_sequence(
                        sequence,
                        sequence_length=model_sequence_length,
                        feature_size=model_feature_size,
                    )
                    input_tensor = torch.tensor(input_np, dtype=torch.float32).unsqueeze(0).to(MODEL_DEVICE)

                    with torch.no_grad():
                        logits = gesture_model(input_tensor)
                        pred_idx = int(torch.argmax(logits, dim=1).item())

                    if gesture_labels and pred_idx < len(gesture_labels):
                        prediction_text = str(gesture_labels[pred_idx])
                        latest_prediction = prediction_text

                        # ✅ Capture logic (FIXED)
                        if is_capturing:
                            if prediction_text != last_added:
                                captured_sequence.append(prediction_text)
                                last_added = prediction_text

                if prediction_text:
                    cv2.putText(
                        frame,
                        f"Prediction: {prediction_text}",
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
    return jsonify({"text": latest_prediction})

@app.route('/start_capture', methods=['POST'])
def start_capture():
    global captured_sequence, is_capturing
    captured_sequence = []
    is_capturing = True
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

    combined = "".join(captured_sequence)  # "123"

    try:
        number_value = int(combined)
        words = num2words(number_value)
    except:
        words = combined

    return jsonify({
        "sequence": captured_sequence,
        "combined": combined,
        "words": words
    })
@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


if __name__ == '__main__':
    app.run(debug=True)
