from flask import Flask, request, jsonify, send_file
import youtube_dl
import os
import uuid

app = Flask(__name__)

@app.route('/convert', methods=['POST'])
def convert():
    data = request.json
    url = data.get('url')

    if not url:
        return jsonify({'error': 'No URL provided'}), 400

    unique_filename = str(uuid.uuid4())
    mp3_filename = f"{unique_filename}.mp3"

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'/tmp/{unique_filename}.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    try:
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        return send_file(f"/tmp/{mp3_filename}", as_attachment=True, attachment_filename=mp3_filename)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
