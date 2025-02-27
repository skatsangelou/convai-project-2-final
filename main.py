from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
from google.cloud import speech, texttospeech
from google.cloud import language_v1
import os

app = Flask(__name__)

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
TTS_FOLDER = 'tts'
ALLOWED_EXTENSIONS = {'wav'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(TTS_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_files(folder):
    files = [filename for filename in os.listdir(folder) if allowed_file(filename)]
    files.sort(reverse=True)
    return files

def analyze_sentiment(text):
    client = language_v1.LanguageServiceClient()
    document = language_v1.Document(content=text, type_=language_v1.Document.Type.PLAIN_TEXT)
    sentiment = client.analyze_sentiment(request={"document": document}).document_sentiment

    if sentiment.score > 0.2:
        sentiment_label = "Positive"
    elif sentiment.score < -0.2:
        sentiment_label = "Negative"
    else:
        sentiment_label = "Neutral"

    return sentiment.score, sentiment.magnitude, sentiment_label

@app.route('/')
def index():
    files = get_files(UPLOAD_FOLDER)
    tts_files = get_files(TTS_FOLDER)
    return render_template('index.html', files=files, tts_files=tts_files)

@app.route('/upload', methods=['POST'])
def upload_audio():
    if 'audio_data' not in request.files:
        flash('No audio data')
        return redirect(request.url)
    
    file = request.files['audio_data']
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)
    
    if file:
        filename = datetime.now().strftime("%Y%m%d-%I%M%S%p") + '.wav'
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        client = speech.SpeechClient()
        with open(file_path, 'rb') as audio_file:
            content = audio_file.read()

        audio = speech.RecognitionAudio(content=content)
        config = speech.RecognitionConfig(language_code="en-US", audio_channel_count=1)
        response = client.recognize(config=config, audio=audio)

        transcript = "".join([result.alternatives[0].transcript for result in response.results])
        transcript_path = file_path + '.txt'

        score, magnitude, sentiment_label = analyze_sentiment(transcript)

        with open(transcript_path, 'w') as f:
            f.write(f"Transcription: {transcript}")
            f.write("\n")
            # f.write(f"Sentiment Score: {score}")
            # f.write(f"Sentiment Magnitude: {magnitude}")
            f.write(f"Sentiment: {sentiment_label}")

    return redirect('/')

@app.route('/upload_text', methods=['POST'])
def upload_text():
    text = request.form['text']
    if not text.strip():
        flash("Text input is empty")
        return redirect(request.url)

    score, magnitude, sentiment_label = analyze_sentiment(text)

    filename = datetime.now().strftime("%Y%m%d-%I%M%S%p") + '.txt'
    print(filename)
    file_path = os.path.join(TTS_FOLDER, filename)

    with open(file_path, 'w') as f:
        f.write(f"Input Text: {text}")
        f.write("\n")
        # f.write(f"Sentiment Score: {score}")
        # f.write(f"Sentiment Magnitude: {magnitude}")
        f.write(f"Sentiment: {sentiment_label}")

    client = texttospeech.TextToSpeechClient()
    input_text = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(language_code="en-US", ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL)
    audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.LINEAR16)

    response = client.synthesize_speech(input=input_text, voice=voice, audio_config=audio_config)

    audio_filename = filename.replace('.txt', '.wav')
    audio_path = os.path.join(TTS_FOLDER, audio_filename)

    with open(audio_path, 'wb') as out:
        out.write(response.audio_content)

    return redirect('/')

@app.route('/<folder>/<filename>')
def uploaded_file(folder, filename):
    if folder not in [UPLOAD_FOLDER, TTS_FOLDER]:
        return "Invalid folder", 404

    return send_from_directory(folder, filename)

@app.route('/script.js', methods=['GET'])
def scripts_js():
    return send_from_directory('', 'script.js')

if __name__ == '__main__':
    app.run(debug=True)