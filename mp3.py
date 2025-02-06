from flask import Flask, request, jsonify, send_file
from pytube import YouTube
from pydub import AudioSegment
import os

app = Flask(__name__)

DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

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
        
        return send_file(mp3_filename, as_attachment=True)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
