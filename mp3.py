from flask import Flask, request, jsonify, send_file, abort
from pytube import YouTube
from pydub import AudioSegment
import os
import uuid

app = Flask(__name__)

# Ensure the downloads folder exists
DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

@app.route('/')
def home():
    return "YouTube to MP3 Converter API"

@app.route('/convert', methods=['POST'])
def convert():
    data = request.get_json()
    url = data.get('url')
    
    if not url:
        return jsonify({"error": "No URL provided"}), 400
    
    try:
        yt = YouTube(url)
        stream = yt.streams.filter(only_audio=True).first()
        
        temp_file = stream.download(output_path=DOWNLOAD_FOLDER)
        mp3_filename = os.path.splitext(temp_file)[0] + ".mp3"
        
        audio = AudioSegment.from_file(temp_file)
        audio.export(mp3_filename, format="mp3")
        
        os.remove(temp_file)
        
        download_link = f"/download/{os.path.basename(mp3_filename)}"
        
        return jsonify({"download_link": download_link})
    
    except Exception as e:
        app.logger.error(f"Error occurred: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/download/<filename>', methods=['GET'])
def download(filename):
    file_path = os.path.join(DOWNLOAD_FOLDER, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    return jsonify({"error": "File not found"}), 404

if __name__ == '__main__':
    app.run(debug=True)
