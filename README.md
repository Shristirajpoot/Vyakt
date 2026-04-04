# Vyakt: Unmute the Silent

![Vyakt Logo](static/images/VyaktLogo.png)

Vyakt is an accessibility-focused Flask platform for sign language communication and learning.
It combines:

- Real-time sign-to-text recognition (camera + gesture model)
- Text-to-sign animation playback
- A personalized learning journey with gamified lessons and quiz evaluation
- AI-powered language support (Gemini for correction and learning tips)

The goal is to help users move from passive recognition to confident expression.

## Screens

![Sign Language Alphabet](static/images/hand-signs-of-the-ASL-Language.png)
![Sign to Text](static/images/SignToText.png)
![Text to Sign](static/images/textToSign.png)
![Dashboard](static/images/Dashboard.png)
![Text to Sign Dashboard](static/images/TextToSignDashboard.png)

## Core Features

### 1. Sign-to-Text (Real Time)
- Streams webcam frames through `/video_feed`
- Extracts hand landmarks with MediaPipe
- Runs sequence classification using a Transformer model
- Supports capture session control (`/start_capture`, `/stop_capture`)
- Uses Gemini to optionally improve generated sentence quality

### 2. Text-to-Sign Animation
- Tokenizes and normalizes input text
- Maps words/phrases to sign assets from `static/assets`
- Handles contractions, stopword filtering, and fallback letter/digit expansion
- Supports speech input (`/speech_to_text`) and speech output (`/text_to_speech`)

### 3. Learning Module (Expression Journey)
- Island-based lesson progression UI
- Daily practice rewards and quest system
- Lesson sessions, answer tracking, and completion reports
- Gemini-generated memory suggestions for incorrect answers
- XP/coins/gems progression persisted in MongoDB

### 4. User & Product Surface
- Auth: register, login, logout, profile, settings
- Pages: dashboard, feedback, contact, about
- Learning and animation sections integrated in the main product flow

## Tech Stack

- Backend: Flask 3
- Datastore: MongoDB (PyMongo)
- ML/CV: PyTorch, OpenCV, MediaPipe, NumPy, scikit-learn
- Forms/Auth helpers: Flask-WTF, WTForms
- Audio/Voice: SpeechRecognition, PocketSphinx, Vosk, pydub
- AI APIs: Gemini (text correction + lesson memory tips), ElevenLabs (TTS API path in app)
- Frontend: Jinja templates + vanilla JS + modular CSS

## Project Structure

```text
Vyakt/
|- app.py                          # Main Flask app (routes, APIs, inference, learning logic)
|- requirements.txt                # Python dependencies for app runtime
|- .env.example                    # Environment template
|- templates/                      # Jinja pages
|- static/
|  |- css/
|  |- js/
|  |- images/
|  |- sounds/
|  \- assets/                     # Sign animation assets (mp4) used by animation flow
|- learning/
|  |- curriculum/                  # Learning vocab/levels/quiz/contracts JSONs
|  \- platform/                    # Learning service and API phase scripts
|- Model/                          # Model training/inference/data utilities
|- scripts/                        # Build and smoke scripts
|- config/                         # Domain configs (e.g. stopwords)
\- Combined/                       # Sign dataset image folders
```

## Prerequisites

- Python 3.10+ recommended
- MongoDB running locally or via remote URI
- Webcam access for sign recognition
- (Optional) Gemini API key for text correction + memory tips
- (Optional) ElevenLabs API key for text-to-speech endpoint

## Quick Start

### 1. Create virtual environment

```bash
python -m venv venv
```

Windows (PowerShell):

```bash
.\venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

Copy `.env.example` to `.env` and fill required values.
Note: `MYSQL_*` keys present in `.env.example` are legacy and not required by the current `app.py` runtime.

Minimum required for full local app:

```env
FLASK_SECRET_KEY=change_me
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
FLASK_DEBUG=true

MONGO_URI=mongodb://127.0.0.1:27017
MONGO_DB_NAME=Vyakt_learning
MONGO_URI_FALLBACK=mongodb://127.0.0.1:27017
APP_TIMEZONE=Asia/Kolkata

GEMINI_API_KEY=your_key_here
GEMINI_TEXT_MODEL=gemini-2.0-flash

GOOGLE_TRANSLATE_API_KEY=your_google_translate_key
VITE_EMAILJS_SERVICE_ID=your_service
VITE_EMAILJS_TEMPLATE_ID=your_template
VITE_EMAILJS_PUBLIC_KEY=your_public_key

ELEVENLABS_API_KEY=your_elevenlabs_key

Vyakt_MODEL_PATH=Model/artifacts/gesture_transformer.pth
Vyakt_LABEL_MAP_PATH=Model/artifacts/label_map.json
Vyakt_CAMERA_INDEX=0
Vyakt_CONFIDENCE_THRESHOLD=0.70
Vyakt_UNKNOWN_THRESHOLD=0.50
Vyakt_FRAME_MAX_WIDTH=512
Vyakt_FRAME_MAX_HEIGHT=384
Vyakt_ANNOTATED_JPEG_QUALITY=82
Vyakt_MAX_HANDS=2
Vyakt_HAND_MIN_SPAN=0.08
Vyakt_HAND_STABLE_FRAMES=2
Vyakt_NO_HAND_RESET_FRAMES=2
Vyakt_SHOW_FRAME_OVERLAY=0
```

### 4. Run server

```bash
python app.py
```

Open: `http://127.0.0.1:5000`

## Route Map

### App Pages
- `/`
- `/index`
- `/learning`
- `/register`, `/login`, `/logout`
- `/profile`, `/dashboard`, `/settings`
- `/feedback`, `/contact`, `/about`
- `/animation_home`, `/animation`

### Learning APIs
- `GET /api/v1/learning/state`
- `POST /claim_reward`
- `GET /api/v1/quests/today`
- `GET /api/v1/learning/path`
- `GET /api/v1/learning/lesson/<lesson_id>`
- `POST /api/v1/learning/session/start`
- `POST /api/v1/learning/answer`
- `POST /api/v1/learning/complete`

### Sign / Media APIs
- `POST /process_frame`
- `POST /reset_frame_state`
- `GET /generate_frames`
- `GET /get_prediction`
- `POST /reset_capture_state`
- `POST /start_capture`
- `POST /stop_capture`
- `GET /video_feed`
- `POST /speech_to_text`
- `POST /text_to_speech`

## Data Model Notes (MongoDB)

At runtime, the app creates/uses collections such as:

- `learning_progress`
- `learning_sessions`
- `learning_answer_attempts`
- `learning_lesson_reports`
- `learning_quests`
- user/profile/activity collections used by auth/profile pages

Indexes and quest seed data are initialized from `app.py` during app startup.

## Training & Model Utilities (Optional)

Use these scripts only if you are rebuilding the gesture model.

```bash
python Model/collect_imgs.py
python Model/create_dataset.py --data-dir data --output Model/artifacts/data_seq.pickle --sequence-length 30
python Model/train.py --data Model/artifacts/data_seq.pickle --output Model/artifacts/gesture_transformer_126.pth --epochs 30 --batch-size 32
python Model/inference_classifier.py --checkpoint Model/artifacts/gesture_transformer_126.pth
```

## Development Utilities

- Auth smoke test:

```bash
python scripts/smoke_auth.py
```

## Troubleshooting

### MongoDB not connecting
- Verify `MONGO_URI` and `MONGO_DB_NAME`
- Ensure MongoDB service is running
- The app will start with limited DB features if Mongo is unavailable

### Camera/gesture stream issues
- Confirm webcam permissions
- Try different `Vyakt_CAMERA_INDEX` values (`0`, `1`, ...)
- Ensure model files exist at paths configured in `.env`

### Gemini features not working
- Set `GEMINI_API_KEY` (or `GOOGLE_API_KEY`)
- Optionally set model via `GEMINI_TEXT_MODEL`

### TTS endpoint failures
- Ensure `ELEVENLABS_API_KEY` is set if using ElevenLabs route

### Missing static sign assets
- Verify expected `.mp4` assets under `static/assets`

## Security & Config Notes

- Do not commit `.env` or secret keys.
- `google-translate-credentials.json` and similar credential files are already gitignored.
- Set a strong `FLASK_SECRET_KEY` in production.
- Review CORS, CSRF, and deployment hardening before public release.

## License

Add your project license here (MIT/Apache-2.0/etc.) if not already defined.

## Acknowledgements

Built to support inclusive communication and help users express themselves with confidence through sign language.
