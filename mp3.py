from flask import Flask, request, jsonify, send_file
import os
import io
import shutil
import yt_dlp
import logging
import time
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Ensure the 'temp-downloaded-files' directory exists
DOWNLOAD_DIR = "temp-downloaded-files"
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# Progress variable to track download progress
conversion_progress = {}

# Setup logging
logging.basicConfig(level=logging.INFO)


def clean_up_download_dir():
    """Delete all contents of the temp-downloaded-files directory."""
    try:
        shutil.rmtree(DOWNLOAD_DIR)
        os.makedirs(DOWNLOAD_DIR)  # Recreate the directory after cleaning it up
    except Exception as e:
        logging.error(f"Error cleaning up directory: {e}")


def progress_hook(d):
    """Track the progress of the download."""
    if d['status'] == 'downloading':
        conversion_progress['status'] = 'downloading'
        conversion_progress['percent'] = d.get('_percent_str', '0%')
        conversion_progress['speed'] = d.get('_speed_str', 'N/A')
        conversion_progress['eta'] = d.get('_eta_str', 'N/A')
    elif d['status'] == 'finished':
        conversion_progress['status'] = 'finished'
        conversion_progress['percent'] = '100%'


def get_yt_dlp_options():
    """Return yt-dlp options with authentication."""
    return {
        'cookiesfrombrowser': ('chrome',),  # Extract fresh cookies from Chrome
        # Alternatively, use a cookies.txt file:
        # 'cookiefile': 'youtube_cookies.txt',
    }


@app.route('/video-info', methods=['POST'])
def video_info():
    """Fetch video information before downloading."""
    try:
        data = request.json
        url = data.get('url')

        if not url:
            return jsonify({'error': 'URL is required'}), 400

        # Delay to prevent rate-limiting
        time.sleep(2)

        ydl_opts = get_yt_dlp_options()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        video_data = {
            'title': info.get('title'),
            'thumbnail': info.get('thumbnail'),
            'duration': info.get('duration'),
        }

        return jsonify(video_data)

    except yt_dlp.utils.DownloadError as e:
        logging.error(f"DownloadError: {e}")
        return jsonify({'error': f'Error fetching video info: {str(e)}'}), 500
    except Exception as e:
        logging.error(f"Error fetching video info: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/convert', methods=['POST'])
def convert():
    """Download and convert video to MP3."""
    try:
        data = request.json
        url = data.get('url')

        if not url:
            return jsonify({'error': 'URL is required'}), 400

        # Reset conversion progress
        conversion_progress.clear()

        ydl_opts = get_yt_dlp_options()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title')

        # Ensure filename is safe
        safe_title = "".join(c for c in title if c.isalnum() or c in " -_").rstrip()
        download_path = os.path.join(DOWNLOAD_DIR, f'{safe_title}.%(ext)s')

        ydl_opts.update({
            'format': 'bestaudio/best',
            'outtmpl': download_path,
            'progress_hooks': [progress_hook],
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'ffmpeg_location': '/usr/bin/ffmpeg'  # Adjust this path if necessary
        })

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        mp3_file = os.path.join(DOWNLOAD_DIR, f'{safe_title}.mp3')

        # Serve the file and clean up
        with open(mp3_file, 'rb') as file_data:
            data = file_data.read()

        clean_up_download_dir()

        return send_file(
            io.BytesIO(data),
            mimetype='audio/mpeg',
            as_attachment=True,
            download_name=f"{safe_title}.mp3"
        )

    except yt_dlp.utils.DownloadError as e:
        logging.error(f"DownloadError: {e}")
        return jsonify({'error': f'Error during video download: {str(e)}'}), 500
    except Exception as e:
        logging.error(f"Error during conversion: {e}")
        return jsonify({'error': f'Error during video conversion: {str(e)}'}), 500


@app.route('/progress', methods=['GET'])
def get_progress():
    """Return the current progress of the conversion."""
    return jsonify(conversion_progress)


if __name__ == '__main__':
    app.run(debug=True)
