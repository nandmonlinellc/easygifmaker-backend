
from flask import Blueprint, request, jsonify, send_file, current_app, send_from_directory, url_for
from flask_cors import cross_origin
from werkzeug.utils import secure_filename
import os
import logging
import tempfile
import uuid
import requests
import io
import subprocess
import shutil
from urllib.parse import urlparse
from celery import chain
from src.celery_app import celery as celery_app
from celery.result import AsyncResult, GroupResult
import yt_dlp # Import yt_dlp
from PIL import Image, ImageDraw, ImageFont
from src.utils.url_validation import validate_remote_url

from src.main import limiter



from src.tasks import (
    convert_video_to_gif_task,
    create_gif_from_images_task,
    resize_gif_task,
    crop_gif_task,
    optimize_gif_task,
    add_text_to_gif_task,
    add_text_layers_to_gif_task,
    handle_upload_task,
    orchestrate_gif_from_urls_task,
    download_file_from_url_task_helper,
)

from src.utils.gif_helpers import (
    resolve_input_gif,
    probe_gif,
    extract_layers,
    prepare_layers,
    dispatch_add_text_layers_task,
    allowed_file,
    ALLOWED_IMAGE_EXTENSIONS,
    ALLOWED_VIDEO_EXTENSIONS,
    create_session_dir,
    resolve_video_input,
)


gif_bp = Blueprint("gif", __name__)


@gif_bp.route("/ai/convert", methods=["POST"])
@limiter.limit("5 per minute")
def convert():
    data = request.get_json()
    if not data or "url" not in data:
        return jsonify({"error": "No URL provided"}), 400
    # For now, just acknowledge the request
    return jsonify({"message": "Conversion request received", "data": data}), 200

@gif_bp.route("/ai/add-text", methods=["POST"])
@limiter.limit("5 per minute")
def ai_add_text_layers():
    """AI endpoint: Add text to GIF with multi-layer support via JSON.
    Accepts: { url | base64_data, layers: [ { text, font_family, font_size, color, stroke_color, stroke_width, horizontal_align, vertical_align, offset_x, offset_y, start_time, end_time, animation_style, max_width_ratio, line_height, auto_fit, font_url } ] }
    Backward-compatible: if layers missing, supports top-level text/font settings.
    """
    try:
        data = request.get_json(silent=True) or {}
        if not data:
            return jsonify({"error": "Invalid or missing JSON body"}), 400

        temp_dir = tempfile.mkdtemp(dir=current_app.config.get('UPLOAD_FOLDER'))
        upload_folder = current_app.config['UPLOAD_FOLDER']


        try:
            gif_path = resolve_input_gif(url=data.get('url'), base64_data=data.get('base64_data'), temp_dir=temp_dir)
        except ValueError as ve:
            return jsonify({"error": str(ve)}), 400

        try:
            n_frames, fps = probe_gif(gif_path)
        except Exception as e:
            logging.error(f"/ai/add-text: Invalid GIF: {e}")
            return jsonify({"error": "Invalid GIF provided"}), 400
        layers = extract_layers(data)
        prepared_layers = prepare_layers(layers, fps, n_frames, temp_dir)
        task = dispatch_add_text_layers_task(gif_path, prepared_layers, temp_dir, upload_folder)
        logging.info(f"/ai/add-text returning task id: {task.id}")
        return jsonify({"task_id": task.id}), 202
    except Exception as e:
        logging.error(f"Error in /ai/add-text: {e}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred while adding text to the GIF."}), 500

@gif_bp.route("/gif-metadata", methods=["POST"])
@limiter.limit("5 per minute")
def gif_metadata():
    """Return duration (seconds) and frame count for a GIF file or URL."""
    try:
        url = request.form.get("url")
        duration = 0
        n_frames = 1
        if url:
            url = validate_remote_url(url)
            temp_dir = tempfile.mkdtemp(dir=current_app.config.get('UPLOAD_FOLDER'))
            gif_path = os.path.join(temp_dir, "temp_gif.gif")
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                with open(gif_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            with Image.open(gif_path) as gif_probe:
                n_frames = getattr(gif_probe, "n_frames", 1)
                duration_ms = gif_probe.info.get("duration", 100)
            duration = (duration_ms * n_frames) / 1000.0
            os.remove(gif_path)
        else:
            if "file" not in request.files:
                return jsonify({"error": "No file provided"}), 400
            file = request.files["file"]
            temp_dir = tempfile.mkdtemp(dir=current_app.config.get('UPLOAD_FOLDER'))
            gif_path = os.path.join(temp_dir, file.filename)
            file.save(gif_path)
            with Image.open(gif_path) as gif_probe:
                n_frames = getattr(gif_probe, "n_frames", 1)
                duration_ms = gif_probe.info.get("duration", 100)
            duration = (duration_ms * n_frames) / 1000.0
            os.remove(gif_path)
        return jsonify({"duration": duration, "frame_count": n_frames}), 200
    except Exception as e:
        logging.error(f"Error in gif_metadata: {e}", exc_info=True)
        return jsonify({"error": "Could not extract GIF metadata."}), 500

# Allowed file extensions

def get_aspect_ratio_dimensions(width, height, aspect_ratio):
    """Calculate crop dimensions based on aspect ratio"""
    if aspect_ratio == "square":
        size = min(width, height)
        return size, size
    elif aspect_ratio == "4:3":
        if width / height > 4/3:
            new_height = height
            new_width = int(height * 4/3)
        else:
            new_width = width
            new_height = int(width * 3/4)
        return new_width, new_height
    elif aspect_ratio == "16:9":
        if width / height > 16/9:
            new_height = height
            new_width = int(height * 16/9)
        else:
            new_width = width
            new_height = int(width * 9/16)
        return new_width, new_height
    elif aspect_ratio == "3:2":
        if width / height > 3/2:
            new_height = height
            new_width = int(height * 3/2)
        else:
            new_width = width
            new_height = int(width * 2/3)
        return new_width, new_height
    elif aspect_ratio == "2:1":
        if width / height > 2:
            new_height = height
            new_width = int(height * 2)
        else:
            new_width = width
            new_height = int(width / 2)
        return new_width, new_height
    elif aspect_ratio == "golden":
        golden_ratio = 1.618
        if width / height > golden_ratio:
            new_height = height
            new_width = int(height * golden_ratio)
        else:
            new_width = width
            new_height = int(width / golden_ratio)
        return new_width, new_height
    else:  # "free" or any other value
        return width, height

@gif_bp.route("/gif-maker", methods=["POST"])
@cross_origin()
@limiter.limit("5 per minute")
def create_gif_from_images():
    """Create GIF from uploaded images or URLs"""
    try:
        # Check if URLs are provided
        urls = request.form.getlist("urls")
        

        upload_folder = current_app.config['UPLOAD_FOLDER']
        session_dir = create_session_dir(upload_folder)
        logging.info(f"Created temporary directory for upload: {session_dir}")
        images = []

        try:
            if urls and any(u.strip() for u in urls):
                frame_duration = int(request.form.get("frame_duration", 500))
                loop_count = int(request.form.get("loop_count", 0))
                max_content_length = current_app.config['MAX_CONTENT_LENGTH']
                logging.info(f"Calling orchestrate_gif_from_urls_task with: urls={urls}, frame_duration={frame_duration}, loop_count={loop_count}, temp_dir={session_dir}, upload_folder={upload_folder}, max_content_length={max_content_length}")
                try:
                    chord_id = orchestrate_gif_from_urls_task.apply_async([urls, frame_duration, loop_count, session_dir, upload_folder, max_content_length], queue="fileops")
                except Exception as pub_err:
                    logging.error(f"Failed to publish orchestrate_gif_from_urls_task to broker: {pub_err}", exc_info=True)
                    return jsonify({"error": "queue_unavailable", "message": "Background queue is currently unavailable. Please retry shortly."}), 503
                logging.info(f"/gif-maker returning chord id as task_id: {getattr(chord_id, 'id', chord_id)}")
                return jsonify({"task_id": getattr(chord_id, 'id', chord_id)}), 202
            else:
                if "files" not in request.files:
                    return jsonify({"error": "No files provided"}), 400
                files = request.files.getlist("files")
                if not files or all(file.filename == "" for file in files):
                    return jsonify({"error": "No files selected"}), 400
                for file in files:
                    if file and allowed_file(file.filename, ALLOWED_IMAGE_EXTENSIONS):
                        filename = secure_filename(file.filename)
                        file_path = os.path.join(session_dir, filename)
                        file.save(file_path)
                        # --- ADD THIS VERIFICATION ---
                        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
                            logging.error(f"Failed to save uploaded file or file is empty: {file_path}")
                            if not os.listdir(session_dir):
                                shutil.rmtree(session_dir, ignore_errors=True)
                            return jsonify({"error": f"Failed to save uploaded file: {filename}. Please try again."}), 500
                        logging.info(f"Successfully saved uploaded file: {file_path} (size: {os.path.getsize(file_path)} bytes)")
                        # --- END ADDITION ---
                        images.append(file_path)

            if not images:
                return jsonify({"error": "No valid images or URLs provided"}), 400

            # Parse per-frame durations and effects if provided
            import json
            frame_durations_raw = request.form.get("frame_durations")
            effects_raw = request.form.get("effects")
            try:
                frame_durations = json.loads(frame_durations_raw) if frame_durations_raw else None
            except Exception:
                frame_durations = None
            try:
                effects = json.loads(effects_raw) if effects_raw else None
            except Exception:
                effects = None
            loop_count = int(request.form.get("loop_count", 0))
            # Fallback to global frame_duration if per-frame not provided
            frame_duration = int(request.form.get("frame_duration", 500))
            try:
                task = create_gif_from_images_task.apply_async(
                    args=[images, frame_duration, loop_count, session_dir, upload_folder, "high", frame_durations, effects],
                    queue="fileops"
                )
            except Exception as pub_err:
                logging.error(f"Failed to publish create_gif_from_images_task to broker: {pub_err}", exc_info=True)
                return jsonify({"error": "queue_unavailable", "message": "Background queue is currently unavailable. Please retry shortly."}), 503
            return jsonify({"task_id": task.id}), 202
        finally:
            # Do not delete session_dir here; let Celery task handle cleanup
            pass
            
    except Exception as e:
        logging.error(f"Error in create_gif_from_images: {e}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred while preparing the GIF."}), 500

@gif_bp.route("/video-to-gif", methods=["POST"])
@cross_origin()
@limiter.limit("5 per minute")
def convert_video_to_gif():
    """Convert video to GIF (optionally with audio as .mp4 for direct video links only)"""
    try:
        upload_folder = current_app.config['UPLOAD_FOLDER']
        session_dir = create_session_dir(upload_folder)
        logging.info(f"Created session directory for video upload: {session_dir}")

        try:
            url = request.form.get("url")
        except Exception as e:
            logging.error(f"Error reading form data: {e}")
            return jsonify({"error": "Failed to read form data. The upload may be too large or incomplete. Please try a smaller file or check your connection."}), 413

        file = request.files.get("file")
        max_content_length = current_app.config['MAX_CONTENT_LENGTH']
        try:
            video_path = resolve_video_input(url, file, session_dir, ALLOWED_VIDEO_EXTENSIONS, max_content_length)
        except ValueError as ve:
            return jsonify({"error": str(ve)}), 400

        start_time = float(request.form.get("start_time", 0))
        duration = float(request.form.get("duration", 10))
        fps = int(request.form.get("fps", 10))
        width = int(request.form.get("width", 480))
        height = int(request.form.get("height", 360))
        include_audio = request.form.get("include_audio", "false").lower() == "true"

        logging.debug(f"[video-to-gif] video_path={video_path}, start_time={start_time}, duration={duration}, fps={fps}, width={width}, height={height}, session_dir={session_dir}, upload_folder={upload_folder}, include_audio={include_audio}")
        task = convert_video_to_gif_task.apply_async([video_path, start_time, duration, fps, width, height, session_dir, upload_folder, include_audio], queue="fileops")
        logging.info(f"/video-to-gif returning task id: {task.id}")
        return jsonify({"task_id": task.id}), 202
    except Exception as e:
        logging.error(f"Error in convert_video_to_gif: {e}", exc_info=True)
        return jsonify({"error": str(e) if str(e) else "An unexpected error occurred during video conversion."}), 500

@gif_bp.route("/resize", methods=["POST"])
@limiter.limit("5 per minute")
def resize_gif():
    """Resize GIF"""
    try:
        # Check if URL is provided
        url = request.form.get("url")
        
        # Create temporary directory
        temp_dir = tempfile.mkdtemp(dir=current_app.config.get('UPLOAD_FOLDER'))
        
        try:
            width = int(request.form.get("width", 300))
            height = int(request.form.get("height", 300))
            maintain_aspect_ratio = request.form.get("maintain_aspect_ratio", "true").lower() == "true"

            if url:
                upload_folder = current_app.config['UPLOAD_FOLDER']
                max_content_length = current_app.config['MAX_CONTENT_LENGTH']
                # Download file from URL
                download_task = handle_upload_task.s(url, temp_dir, upload_folder, max_content_length)
                def process_downloaded_file(rel_path):
                    abs_path = os.path.join(upload_folder, rel_path)
                    ext = os.path.splitext(abs_path)[1].lower()
                    if ext == '.gif':
                        # If GIF, resize directly
                        return resize_gif_task.s(abs_path, width, height, maintain_aspect_ratio, temp_dir, upload_folder)()
                    elif ext in ['.mp4', '.mov', '.webm', '.avi', '.mkv', '.flv']:
                        # If video, convert to GIF first, then resize
                        # Use default start_time=0, duration=10, fps=10 for conversion
                        gif_output_path = os.path.join(temp_dir, f"converted_{uuid.uuid4().hex}.gif")
                        convert_task = convert_video_to_gif_task.s(abs_path, 0, 10, 10, width, height, temp_dir, upload_folder)
                        return chain(convert_task, resize_gif_task.s(width, height, maintain_aspect_ratio, temp_dir, upload_folder))()
                    else:
                        # Unsupported file type
                        raise Exception(f"Unsupported file type for resize: {ext}")
                # Start the download task, then on success, call process_downloaded_file
                result = download_task.apply_async([], queue="fileops")
                result.then(process_downloaded_file)
                logging.info(f"/resize (url) returning task id: {result.id}")
                return jsonify({"task_id": result.id}), 202
            else:
                # Handle file upload
                if "file" not in request.files:
                    return jsonify({"error": "No file provided"}), 400
                
                file = request.files["file"]
                if file.filename == "":
                    return jsonify({"error": "No file selected"}), 400
                
                # Save uploaded GIF
                gif_path = os.path.join(temp_dir, secure_filename(file.filename))
                file.save(gif_path)
            
            upload_folder = current_app.config['UPLOAD_FOLDER']
            task = resize_gif_task.apply_async([gif_path, width, height, maintain_aspect_ratio, temp_dir, upload_folder], queue="fileops")
            logging.info(f"/resize (file) returning task id: {task.id}")
            return jsonify({"task_id": task.id}), 202
            
        finally:
            # The task is responsible for cleaning up the temp_dir
            pass
            
    except Exception as e:
        logging.error(f"Error in resize_gif: {e}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred while resizing the GIF."}), 500

@gif_bp.route("/crop", methods=["POST"])
@limiter.limit("5 per minute")
def crop_gif():
    """Crop GIF with advanced options"""
    try:
        # Check if URL is provided
        url = request.form.get("url")
        
        # Create temporary directory
        temp_dir = tempfile.mkdtemp(dir=current_app.config.get('UPLOAD_FOLDER'))
        
        try:
            x = int(request.form.get("x", 0))
            y = int(request.form.get("y", 0))
            width = int(request.form.get("width", 100))
            height = int(request.form.get("height", 100))
            aspect_ratio = request.form.get("aspect_ratio", "free")

            if url:
                upload_folder = current_app.config['UPLOAD_FOLDER']
                max_content_length = current_app.config['MAX_CONTENT_LENGTH']
                # Download file from URL, then crop in a Celery chain
                download_task = handle_upload_task.s(url, temp_dir, upload_folder, max_content_length)
                crop_task = crop_gif_task.s(x, y, width, height, aspect_ratio, temp_dir, upload_folder)
                chain_result = (download_task | crop_task).apply_async([], queue="fileops")
                logging.info(f"/crop (url) returning task id: {chain_result.id}")
                return jsonify({"task_id": chain_result.id}), 202
            else:
                # Handle file upload
                if "file" not in request.files:
                    return jsonify({"error": "No file provided"}), 400
                
                file = request.files["file"]
                if file.filename == "":
                    return jsonify({"error": "No file selected"}), 400
                
                # Save uploaded GIF
                gif_path = os.path.join(temp_dir, secure_filename(file.filename))
                file.save(gif_path)
            
            upload_folder = current_app.config['UPLOAD_FOLDER']
            task = crop_gif_task.apply_async([gif_path, x, y, width, height, aspect_ratio, temp_dir, upload_folder], queue="fileops")
            logging.info(f"/crop (file) returning task id: {task.id}")
            return jsonify({"task_id": task.id}), 202
            
        finally:
            # The task is responsible for cleaning up the temp_dir
            pass
            
    except Exception as e:
        logging.error(f"Error in crop_gif: {e}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred while cropping the GIF."}), 500

@gif_bp.route("/optimize", methods=["POST"])
@limiter.limit("5 per minute")
def optimize_gif():
    """Optimize GIF to reduce file size"""
    try:
        # Check if URL is provided
        url = request.form.get("url")
        
        # Create temporary directory
        temp_dir = tempfile.mkdtemp(dir=current_app.config.get('UPLOAD_FOLDER'))
        
        try:
            quality = int(request.form.get("quality", 80))
            colors = int(request.form.get("colors", 256))
            lossy = int(request.form.get("lossy", 0))
            dither = request.form.get("dither", "floyd-steinberg")
            optimize_level = int(request.form.get("optimize_level", 3))

            if url:
                upload_folder = current_app.config['UPLOAD_FOLDER']
                max_content_length = current_app.config['MAX_CONTENT_LENGTH']
                # Create a chain: download first, then optimize.
                optimize_signature = optimize_gif_task.s(quality, colors, lossy, dither, optimize_level, temp_dir, upload_folder)
                task_chain = chain(handle_upload_task.s(url, temp_dir, upload_folder, max_content_length), optimize_signature)
                task = task_chain.apply_async([], queue="fileops")
                logging.info(f"/optimize (url) returning task id: {task.id}")
                return jsonify({"task_id": task.id}), 202
            else:
                # Handle file upload
                if "file" not in request.files:
                    return jsonify({"error": "No file provided"}), 400
                
                file = request.files["file"]
                if file.filename == "":
                    return jsonify({"error": "No file selected"}), 400
                
                # Save uploaded GIF
                gif_path = os.path.join(temp_dir, secure_filename(file.filename))
                file.save(gif_path)
            
            upload_folder = current_app.config['UPLOAD_FOLDER']
            task = optimize_gif_task.apply_async([gif_path, quality, colors, lossy, dither, optimize_level, temp_dir, upload_folder], queue="fileops")
            logging.info(f"/optimize (file) returning task id: {task.id}")
            return jsonify({"task_id": task.id}), 202
            
        finally:
            # The task is responsible for cleaning up the temp_dir
            pass
            
    except Exception as e:
        logging.error(f"Error in optimize_gif: {e}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred while optimizing the GIF."}), 500

@gif_bp.route("/reverse", methods=["POST"])
def reverse_gif():
    """Reverse GIF frames"""
    try:
        url = request.form.get("url")
        temp_dir = tempfile.mkdtemp(dir=current_app.config.get('UPLOAD_FOLDER'))
        try:
            if url:
                upload_folder = current_app.config['UPLOAD_FOLDER']
                max_content_length = current_app.config['MAX_CONTENT_LENGTH']
                download_task = handle_upload_task.apply(args=[url, temp_dir, upload_folder, max_content_length])
                gif_path = download_task.get()
            else:
                if "file" not in request.files:
                    return jsonify({"error": "No file provided"}), 400
                file = request.files["file"]
                if file.filename == "":
                    return jsonify({"error": "No file selected"}), 400
                gif_path = os.path.join(temp_dir, secure_filename(file.filename))
                file.save(gif_path)

            upload_folder = current_app.config['UPLOAD_FOLDER']
            task = reverse_gif_task.apply(args=[gif_path, temp_dir, upload_folder])
            rel = task.get()
            download_url = url_for('gif.download_result', filename=rel, _external=True)
            return jsonify({"download_url": download_url}), 200
        finally:
            pass
    except Exception as e:
        logging.error(f"Error in reverse_gif: {e}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred while reversing the GIF."}), 500

@gif_bp.route("/add-text", methods=["POST"])
@limiter.limit("5 per minute")
def add_text_to_gif():
    """Add text to GIF with advanced customization"""
    try:
        # Check if URL is provided
        url = request.form.get("url")
        
        # Create temporary directory
        temp_dir = tempfile.mkdtemp(dir=current_app.config.get('UPLOAD_FOLDER'))
        
        try:
            text = request.form.get("text", "Sample Text")
            # Use alignment-based positioning instead of fixed x,y coordinates
            font_size = int(request.form.get("font_size", 20))
            color = request.form.get("color", "#ffffff")
            font_family = request.form.get("font_family", "Arial")
            stroke_color = request.form.get("stroke_color", "#000000")
            stroke_width = int(request.form.get("stroke_width", 1))
            horizontal_align = request.form.get("horizontal_align", "center")
            vertical_align = request.form.get("vertical_align", "middle")
            offset_x = int(request.form.get("offset_x", 0))
            offset_y = int(request.form.get("offset_y", 0))

            # --- Time to frame conversion logic ---
            # Accept start_time and end_time in seconds from frontend, convert to frame indices
            start_time = float(request.form.get("start_time", 0))
            end_time = request.form.get("end_time", None)
            animation_style = request.form.get("animation_style", "none")
            # We'll get frame count and duration from the GIF after upload
            if url:
                # Download GIF to temp_dir to probe metadata
                url = validate_remote_url(url)
                gif_temp_path = os.path.join(temp_dir, "temp_gif.gif")
                with requests.get(url, stream=True) as r:
                    r.raise_for_status()
                    with open(gif_temp_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                gif_path_for_probe = gif_temp_path
            else:
                file = request.files["file"]
                gif_path_for_probe = os.path.join(temp_dir, secure_filename(file.filename))
                file.save(gif_path_for_probe)
                # Check file validity after save
                try:
                    with Image.open(gif_path_for_probe) as test_img:
                        test_img.verify()
                except Exception as e:
                    logging.error(f"Uploaded file is not a valid image: {gif_path_for_probe}, error: {e}")
                    return jsonify({"error": "Uploaded file is not a valid GIF image."}), 400


            with Image.open(gif_path_for_probe) as gif_probe:
                n_frames = getattr(gif_probe, "n_frames", 1)
                duration_ms = gif_probe.info.get("duration", 100)  # duration per frame in ms
            total_duration = (duration_ms * n_frames) / 1000.0  # in seconds
            fps = 1000.0 / duration_ms if duration_ms > 0 else 10
            logging.info(f"[add_text_to_gif] GIF metadata: n_frames={n_frames}, duration_ms={duration_ms}, total_duration={total_duration:.2f}s, fps={fps:.2f}")
            logging.info(f"[add_text_to_gif] Received start_time={start_time}, end_time={end_time}")
            # Convert start_time/end_time (seconds) to frame indices
            start_frame = int(round(start_time * fps))
            if end_time is not None and end_time != '':
                end_frame = int(round(float(end_time) * fps))
            else:
                end_frame = n_frames - 1
            logging.info(f"[add_text_to_gif] Calculated start_frame={start_frame}, end_frame={end_frame}")

            # Clean up temp gif if url
            if url and os.path.exists(gif_temp_path):
                os.remove(gif_temp_path)

            if url:
                upload_folder = current_app.config['UPLOAD_FOLDER']
                max_content_length = current_app.config['MAX_CONTENT_LENGTH']
                # Instead of passing all args, use .si() for handle_upload_task so result is injected
                task_chain = chain(
                    handle_upload_task.s(url, temp_dir, upload_folder, max_content_length),
                    add_text_to_gif_task.s(
                        text, font_size, color, font_family, stroke_color, stroke_width,
                        horizontal_align, vertical_align, offset_x, offset_y,
                        start_frame, end_frame, animation_style, temp_dir, upload_folder
                    )
                )
                task = task_chain.apply_async([], queue="fileops")
                logging.info(f"/add-text (url) returning task id: {task.id}")
                return jsonify({"task_id": task.id}), 202
            else:
                # For file upload, reuse gif_path_for_probe for the task
                gif_path = gif_path_for_probe
                upload_folder = current_app.config['UPLOAD_FOLDER']
                task = add_text_to_gif_task.apply_async(
                    gif_path, text, font_size, color, font_family, stroke_color, stroke_width,
                    horizontal_align, vertical_align, offset_x, offset_y,
                    start_frame, end_frame, animation_style, temp_dir, upload_folder
                )
                logging.info(f"/add-text (file) returning task id: {task.id}")
                return jsonify({"task_id": task.id}), 202
            
        finally:
            # The task is responsible for cleaning up the temp_dir
            pass
            
    except Exception as e:
        logging.error(f"Error in add_text_to_gif: {e}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred while adding text to the GIF."}), 500

@gif_bp.route("/add-text-layers", methods=["POST"])
@limiter.limit("5 per minute")
def add_text_layers_to_gif():
    """Add multiple text layers to a GIF with per-layer customization and optional custom fonts."""
    try:
        url = request.form.get("url")
        file = request.files.get("file")
        temp_dir = tempfile.mkdtemp(dir=current_app.config.get('UPLOAD_FOLDER'))
        try:

            gif_path = resolve_input_gif(url=url, file=file, temp_dir=temp_dir)
        except ValueError as ve:
            return jsonify({"error": str(ve)}), 400


        try:
            n_frames, fps = probe_gif(gif_path)
        except Exception as e:
            logging.error(f"Uploaded file is not a valid image: {gif_path}, error: {e}")
            return jsonify({"error": "Uploaded file is not a valid GIF image."}), 400

        import json
        layers_raw = request.form.get("layers")
        if not layers_raw:
            return jsonify({"error": "Missing layers data"}), 400
        try:
            layers = json.loads(layers_raw)
        except Exception:
            return jsonify({"error": "Invalid layers JSON"}), 400

        prepared_layers = prepare_layers(layers, fps, n_frames, temp_dir)

        upload_folder = current_app.config['UPLOAD_FOLDER']
        task = dispatch_add_text_layers_task(gif_path, prepared_layers, temp_dir, upload_folder)
        logging.info(f"/add-text-layers returning task id: {task.id}")
        return jsonify({"task_id": task.id}), 202
    except Exception as e:
        logging.error(f"Error in add_text_layers_to_gif: {e}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred while adding text layers to the GIF."}), 500

@gif_bp.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy", 
        "message": "EasyGIFMaker API is running",
        "max_file_size": "200MB",
        "supported_formats": {
            "images": list(ALLOWED_IMAGE_EXTENSIONS),
            "videos": list(ALLOWED_VIDEO_EXTENSIONS)
        }
    })

@gif_bp.route("/upload", methods=["POST"])
@limiter.limit("5 per minute")
def handle_upload():
    """Handle URL uploads and return the video file content as a direct response (for preview/playback)"""
    data = request.get_json()
    if not data or "url" not in data:
        return jsonify({"error": "No URL provided"}), 400
    url = data["url"]
    temp_dir = tempfile.mkdtemp(dir=current_app.config.get('UPLOAD_FOLDER'))
    upload_folder = current_app.config['UPLOAD_FOLDER']
    max_content_length = current_app.config['MAX_CONTENT_LENGTH']
    try:
        logging.info(f"[handle_upload] Downloading: url={url}, temp_dir={temp_dir}, upload_folder={upload_folder}, max_content_length={max_content_length}")
        video_path = download_file_from_url_task_helper(url, temp_dir, max_content_length)
        if not os.path.exists(video_path):
            return jsonify({"error": "Download failed"}), 500
        # Guess mimetype
        ext = os.path.splitext(video_path)[1].lower()
        mimetype = 'video/mp4' if ext == '.mp4' else 'application/octet-stream'
        logging.info(f"[handle_upload] Serving video file: {video_path} (mimetype: {mimetype})")
        return send_file(video_path, mimetype=mimetype, as_attachment=False, download_name=os.path.basename(video_path))
    except Exception as e:
        logging.error(f"Error in handle_upload (URL proxy): {e}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred while processing the URL."}), 500
    finally:
        pass

@gif_bp.route("/task-status/<task_id>", methods=["GET"])
def get_task_status(task_id):
    """Endpoint to check the status of a Celery task."""
    try:
        task = GroupResult.restore(task_id, backend=celery_app.backend) or AsyncResult(task_id, backend=celery_app.backend)
    except Exception:
        task = AsyncResult(task_id, backend=celery_app.backend)
    logging.info(f"[get_task_status] Task {task_id} state: {task.state}")
    if task.state == 'PENDING':
        response = {
            'state': task.state,
            'status': 'Pending...'
        }
    elif task.state == 'PROGRESS':
        response = {
            'state': task.state,
            'status': task.info.get('status', 'Processing...'),
            'progress': task.info.get('progress', 0)
        }
    elif task.state == 'SUCCESS':
        # Always return the actual GIF path as 'result', even for chords
        result = None
        try:
            result = task.get(timeout=1)
            # If result is a list (from a chord), return the first item (the GIF path)
            if isinstance(result, list) and len(result) == 1:
                result = result[0]
            # If result is a string and looks like a Celery task id, fetch its result
            if isinstance(result, str) and len(result) == 36 and '-' in result:
                callback_task = AsyncResult(result, backend=celery_app.backend)
                logging.info(f"[get_task_status] Resolving callback task id: {result} (state: {callback_task.state})")
                if callback_task.state == 'SUCCESS':
                    result = callback_task.get(timeout=1)
        except Exception as e:
            logging.error(f"[get_task_status] Error getting result for {task_id}: {e}")
        logging.info(f"[get_task_status] Task {task_id} resolved result: {result}")
        response = {
            'state': task.state,
            'status': 'Task completed!',
            'result': result
        }
    elif task.state == 'FAILURE':
        error_msg = 'An unknown error occurred during processing.'
        if isinstance(task.info, Exception):
            if isinstance(task.info, ValueError):
                error_msg = str(task.info)
            else:
                logging.error(f"Task {task_id} failed with an unhandled exception: {task.info!r}")
        response = {
            'state': task.state,
            'status': 'Task failed!',
            'error': error_msg,
        }
    else:
        response = {
            'state': task.state,
            'status': 'Unknown state'
        }
    return jsonify(response)

@gif_bp.route("/download-result/<path:filename>", methods=["GET"])
def download_result(filename):
    """Endpoint to download the processed file."""
    # Ensure the filename is secure and within the UPLOAD_FOLDER
    # This is a critical security point. Do NOT allow arbitrary file paths.
    # The filename should be a full path returned by the task, and we should
    # verify it's within the allowed UPLOAD_FOLDER.
    
    # Example of securing the path:
    base_upload_folder = current_app.config.get('UPLOAD_FOLDER')
    full_path = os.path.join(base_upload_folder, filename)
    
    # Prevent directory traversal attacks
    if not os.path.abspath(full_path).startswith(os.path.abspath(base_upload_folder)):
        return jsonify({"error": "Invalid file path"}), 400

    if not os.path.exists(full_path):
        return jsonify({"error": "File not found"}), 404

    try:
        # Allow inline playing for common video and image formats for preview
        inline_extensions = {'.mp4', '.webm', '.mov', '.gif', '.png', '.jpg', '.jpeg', '.webp'}
        _, ext = os.path.splitext(filename)
        as_attachment = ext.lower() not in inline_extensions

        return send_file(full_path, as_attachment=as_attachment, download_name=os.path.basename(full_path))
    except Exception as e:
        logging.error(f"Error serving file {full_path}: {e}", exc_info=True)
        return jsonify({"error": "Could not serve file"}), 500
    finally:
        # Optionally, delete the file after it's served.
        # This depends on your cleanup strategy. The main cleanup task will eventually get it.
        # If you want immediate deletion, uncomment:
        # try:
        #     if os.path.isfile(full_path):
        #         os.remove(full_path)
        #         logging.info(f"Deleted served file: {full_path}")
        #     elif os.path.isdir(full_path): # If the task returned a directory
        #         shutil.rmtree(full_path, ignore_errors=True)
        #         logging.info(f"Deleted served directory: {full_path}")
        # except Exception as e:
        #     logging.error(f"Error deleting served file/dir {full_path}: {e}")
        pass

@gif_bp.route("/download/<path:filename>", methods=["GET"])
def download_gif(filename):
    """
    Download a generated GIF file
    Expected filename format: 'tmp_folder/output_hash.gif'
    """
    try:
        # Security validation
        if '..' in filename or filename.startswith('/'):
            return jsonify({'error': 'Invalid filename'}), 400
        upload_folder = current_app.config.get('UPLOAD_FOLDER')
        if not upload_folder:
            return jsonify({'error': 'Server configuration error'}), 500
        full_path = os.path.join(upload_folder, filename)
        # Security: Ensure path is within upload folder
        if not os.path.abspath(full_path).startswith(os.path.abspath(upload_folder)):
            return jsonify({'error': 'Access denied'}), 403
        # DEBUG LOGGING
        logging.info(f"Download request: {filename}")
        logging.info(f"Full path: {full_path}")
        logging.info(f"File exists: {os.path.exists(full_path)}")
        if os.path.exists(full_path):
            file_size = os.path.getsize(full_path)
            logging.info(f"File size: {file_size} bytes")
        else:
            logging.error(f"File not found: {full_path}")
            return jsonify({'error': 'File not found'}), 404
        
        # Check file extension to determine if it's a GIF or MP4
        file_extension = os.path.splitext(filename)[1].lower()
        
        if file_extension == '.gif':
            # Validate GIF files by checking the first few bytes
            try:
                with open(full_path, 'rb') as f:
                    header = f.read(6)
                    if not header.startswith(b'GIF87a') and not header.startswith(b'GIF89a'):
                        logging.error(f"File is not a valid GIF: {full_path}")
                        return jsonify({'error': 'Invalid GIF file'}), 400
            except Exception as e:
                logging.error(f"Error reading file header: {e}")
                return jsonify({'error': 'File read error'}), 500
            
            # Serve GIF file
            response = send_from_directory(
                upload_folder,
                filename,
                mimetype='image/gif',
                as_attachment=False
            )
        elif file_extension == '.mp4':
            # For MP4 files, just check if file exists (no header validation needed)
            response = send_from_directory(
                upload_folder,
                filename,
                mimetype='video/mp4',
                as_attachment=True  # Force download for MP4 files
            )
        else:
            logging.error(f"Unsupported file type: {file_extension}")
            return jsonify({'error': 'Unsupported file type'}), 400
        
        # Add additional headers to ensure proper download
        response.headers['Cache-Control'] = 'no-cache'
        
        return response
    except Exception as e:
        logging.error(f"Download error for {filename}: {e}", exc_info=True)
        return jsonify({'error': 'Download failed'}), 500

@gif_bp.route('/debug-file/<path:filename>')
def debug_file_info(filename):
    """Debug endpoint to check file status"""
    try:
        upload_folder = current_app.config.get('UPLOAD_FOLDER')
        full_path = os.path.join(upload_folder, filename)
        return jsonify({
            'filename': filename,
            'full_path': full_path,
            'exists': os.path.exists(full_path),
            'is_file': os.path.isfile(full_path) if os.path.exists(full_path) else False,
            'size': os.path.getsize(full_path) if os.path.exists(full_path) else 0,
            'readable': os.access(full_path, os.R_OK) if os.path.exists(full_path) else False
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
