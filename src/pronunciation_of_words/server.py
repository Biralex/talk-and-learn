import io
import os
import torch
import numpy as np
import soundfile as sf
from flask import Flask, request, jsonify, Response
from kokoro import KModel, KPipeline

WEIGHTS_DIR = os.environ['WEIGHTS_DIR']

AVAILABLE_VOICES = {
    'af_alloy', 'af_bella', 'af_kore', 'af_nicole', 'af_sky',
    'am_adam', 'am_echo', 'am_michael'
}

pipelines = {}


def load_models_once():
    global pipelines

    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    kmodel = KModel(config=f"{WEIGHTS_DIR}/../config.json", model=f"{WEIGHTS_DIR}/kokoro-v1_0.pth").to(device)
    pipelines['a'] = KPipeline(lang_code='a', model=kmodel, device=device)


load_models_once()
app = Flask(__name__)


def generate_audio(text: str, voice: str, speed: float) -> bytes:
    lang_code = voice[0]
    voice_path = f"{WEIGHTS_DIR}/voices/{voice}.pt"
    chunks = [audio.numpy() for _, _, audio in pipelines[lang_code](text, voice=voice_path, speed=speed)]
    buf = io.BytesIO()
    sf.write(buf, np.concatenate(chunks), 24000, format='WAV')
    return buf.getvalue()


@app.route('/tts', methods=['POST'])
def tts():
    data = request.get_json()
    if not data or 'text' not in data:
        return jsonify({'error': 'JSON body with text field is required'}), 400

    text = data['text'].strip()
    voice = data.get('voice', 'af_sky')
    speed = float(data.get('speed', 1.0))

    if not text:
        return jsonify({'error': 'text cannot be empty'}), 400

    if voice not in AVAILABLE_VOICES:
        return jsonify({'error': f'Unknown voice "{voice}". Available: {sorted(AVAILABLE_VOICES)}'}), 400

    try:
        audio_bytes = generate_audio(text, voice, speed)
        return Response(audio_bytes, mimetype='audio/wav')
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ['TTS_PORT']))