import os
import io
import shutil
import yt_dlp
import tempfile
import logging
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import time
import json

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Ensure the 'temp-downloaded-files' directory exists
DOWNLOAD_DIR = "temp-downloaded-files"
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

def clean_up_download_dir():
    """Delete all contents of the temp-downloaded-files directory."""
    try:
        shutil.rmtree(DOWNLOAD_DIR)
        os.makedirs(DOWNLOAD_DIR)  # Recreate the directory after cleaning it up
    except Exception as e:
        logging.error(f"Error cleaning up directory: {e}")

# Progress variable to track download progress
conversion_progress = {}

def progress_hook(d):
    if d['status'] == 'downloading':
        # Update conversion progress with percentage
        conversion_progress['status'] = 'downloading'
        conversion_progress['percent'] = d.get('_percent_str', '0%')
        conversion_progress['speed'] = d.get('_speed_str', 'N/A')
        conversion_progress['eta'] = d.get('_eta_str', 'N/A')
    elif d['status'] == 'finished':
        conversion_progress['status'] = 'finished'
        conversion_progress['percent'] = '100%'


def get_yt_dlp_options():
    """Return yt-dlp options with authentication using the cookies in Netscape format."""
    cookie_file = 'youtube_cookies.txt'  # Your cookies in Netscape format

    return {
        'cookiefile': cookie_file,  # Path to your Netscape formatted cookies.txt file
        'retries': 5,  # Retry 5 times before failing
        'retry_sleep': 10,  # Sleep for 10 seconds between retries
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),  # Save to temp directory
        'progress_hooks': [progress_hook],  # Hook to track progress
    }


@app.route('/video-info', methods=['POST'])
def video_info():
    try:
        data = request.json
        url = data.get('url')

        if not url:
            return jsonify({'error': 'URL is required'}), 400

        # Fetch video info using yt-dlp with cookies
        ydl_opts = get_yt_dlp_options()  # Use cookies from the txt file
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
    try:
        data = request.json
        url = data.get('url')

        if not url:
            return jsonify({'error': 'URL is required'}), 400

        # Reset conversion progress for a new conversion
        conversion_progress.clear()

        # Fetch video info to use the title as the filename
        ydl_opts = get_yt_dlp_options()  # Use cookies from the txt file
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title')

        # Path to download the MP3
        download_path = os.path.join(DOWNLOAD_DIR, f'{title}.%(ext)s')

        ydl_opts.update({
            'format': 'bestaudio/best',
            'outtmpl': download_path,  # Save to the temp-download-files directory
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'ffmpeg_location': '/usr/bin/ffmpeg',  # Adjust this path if necessary
        })

        # Retry logic to avoid rate limiting
        retries = 3
        for _ in range(retries):
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                break  # If the download is successful, break out of the retry loop
            except yt_dlp.utils.DownloadError as e:
                if '429' in str(e):  # Check for rate limiting error
                    logging.warning(f"Rate limit hit, retrying: {e}")
                    time.sleep(15)  # Sleep for 15 seconds before retrying
                    continue
                raise  # If it's not a rate limit error, raise the error

        mp3_file = os.path.join(DOWNLOAD_DIR, f'{title}.mp3')

        # Serve the file to the user and clean up
        with open(mp3_file, 'rb') as file_data:
            data = file_data.read()

        # Clean up the temp directory after serving the file
        clean_up_download_dir()

        # Send the MP3 file as a response
        return send_file(
            io.BytesIO(data),
            mimetype='audio/mpeg',
            as_attachment=True,
            download_name=f"{title}.mp3"
        )

    except yt_dlp.utils.DownloadError as e:
        logging.error(f"DownloadError: {e}")
        return jsonify({'error': f'Error during video download: {str(e)}'}), 500

    except Exception as e:
        logging.error(f"Error during conversion: {e}")
        return jsonify({'error': f'Error during video conversion: {str(e)}'}), 500

@app.route('/progress', methods=['GET'])
def get_progress():
    """API to get the current progress of the conversion"""
    return jsonify(conversion_progress)

if __name__ == '__main__':
    logging.basicConfig(level=logging.ERROR)
    app.run(debug=True, threaded=True)
