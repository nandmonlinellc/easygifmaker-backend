import os
import tempfile
import uuid
import shutil
import logging
import subprocess
import io
from PIL import Image, ImageDraw, ImageFont
import requests
from celery import group, chord
from urllib.parse import urlparse
import yt_dlp
import time
import resource
from src.utils.url_validation import validate_remote_url
import magic

# Import the shared Celery application instance
from src.celery_app import celery as celery_app
from src.models.user import db
from src.models.metrics import JobMetric
# Do not import Flask app at module level to avoid circular import
flask_app = None

def get_flask_app():
    """Get Flask app instance, importing it on demand to avoid circular imports."""
    global flask_app
    if flask_app is None:
        try:
            from src.main import app as flask_app
        except ImportError:
            flask_app = None
    return flask_app
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Memory safety guards (override via env if needed)
MAX_GIF_FRAMES = int(os.environ.get('MAX_GIF_FRAMES', '300'))  # cap on frames processed
MAX_GIF_PIXELS = int(os.environ.get('MAX_GIF_PIXELS', str(800 * 800)))  # cap on total pixels per frame (e.g., 800x800)

def _compute_scale_factor(width: int, height: int, max_pixels: int) -> float:
    total = width * height
    if total <= max_pixels:
        return 1.0
    ratio = (max_pixels / float(total)) ** 0.5
    return max(0.2, min(1.0, ratio))

def download_file_from_url_task_helper(url, temp_dir, max_size):
    try:
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir, exist_ok=True)
            logging.info(f"Created temp_dir: {temp_dir}")

        validate_remote_url(url)
        parsed_url = urlparse(url)

        # Handle video sources via yt-dlp
        if any(domain in url for domain in ["youtube.com", "youtu.be", "dailymotion.com"]):
            try:
                ydl_opts = {
                    "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                    "outtmpl": os.path.join(temp_dir, "%(id)s.%(ext)s"),
                    "noplaylist": True,
                    "quiet": True,
                    "no_warnings": True,
                    "retries": 10,
                    "fragment_retries": 10,
                    "skip_unavailable_fragments": True,
                    "nocheckcertificate": True,
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info_dict = ydl.extract_info(url, download=True)
                    video_path = ydl.prepare_filename(info_dict)
                    return video_path
            except yt_dlp.utils.DownloadError as e:
                logging.error(f"yt-dlp error: {e}")
                raise ValueError("Failed to download from the provided video URL.")

        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, stream=True, timeout=30, headers=headers)
        response.raise_for_status()

        content_length = response.headers.get('Content-Length')
        if content_length and int(content_length) > max_size:
            raise ValueError("File too large.")

        content_type = response.headers.get("content-type", "")
        logging.info(f"Downloading: {url} [content-type: {content_type}]")

        if 'text' in content_type.lower():
            snippet = response.content[:256]
            logging.warning(f"URL appears to return text/html, not an image: {snippet.decode(errors='ignore')}")
            raise ValueError("URL did not return an image. Possibly a 404 page or HTML response.")

        filename = os.path.basename(parsed_url.path) or "downloaded_file"
        if "." not in filename:
            if "image" in content_type:
                if "gif" in content_type: filename += ".gif"
                elif "png" in content_type: filename += ".png"
                elif "jpeg" in content_type or "jpg" in content_type: filename += ".jpeg"
                elif "webp" in content_type: filename += ".webp"
                else: filename += ".gif"
            elif "video" in content_type:
                filename += ".mp4"
            else:
                filename += ".bin"

        file_path = os.path.join(temp_dir, filename)

        logging.info(f"Saving file to: {file_path}")
        downloaded_size = 0
        with open(file_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                downloaded_size += len(chunk)
                if downloaded_size > max_size:
                    f.close()
                    os.remove(file_path)
                    raise ValueError("Download exceeded size limit.")
                f.write(chunk)

        if os.path.getsize(file_path) < 1024:
            with open(file_path, 'rb') as f:
                head = f.read(256)
                logging.warning(f"Downloaded file too small: {file_path}. Head: {head}")
            os.remove(file_path)
            raise ValueError(f"Downloaded file from {url} is too small or invalid.")

        return file_path

    except Exception as e:
        logging.error(f"Error downloading file: {e}", exc_info=True)
        raise ValueError("Download failed. Please check the URL and try again.")

@celery_app.task(bind=True)
def orchestrate_gif_from_urls_task(self, urls, frame_duration, loop_count, base_output_dir, upload_folder, max_content_length, quality_level="high"):
    """
    Orchestrates downloading images from URLs and then creating a GIF from them.
    """
    _task_start = time.time()
    try:
        # Create a single temporary directory for all downloads within this orchestration
        shared_download_dir = tempfile.mkdtemp(dir=base_output_dir)
        logging.info(f"Created shared_download_dir: {shared_download_dir} for orchestration.")

        download_tasks = []
        for url in urls:
            if url.strip():
                # Pass the shared_download_dir to each download task
                download_tasks.append(download_file_from_url_task.s(url, shared_download_dir, max_content_length).set(queue='fileops'))
        
        if not download_tasks:
            raise ValueError("No valid URLs provided.")
        
        # Use a chord: download all, then create GIF from results
        # Pass shared_download_dir to create_gif_from_images_task as the directory where inputs are
        callback = create_gif_from_images_task.s(frame_duration=frame_duration, loop_count=loop_count, output_dir=shared_download_dir, upload_folder=upload_folder, quality_level=quality_level).set(queue='fileops')
        job = chord(download_tasks)(callback)
        logging.info(f"Started chord for downloads and gif creation. Chord id: {job.id}")
        return job.id
    except Exception as e:
        logging.error(f"Error in orchestrate_gif_from_urls_task: {e}", exc_info=True)
        try:
            jm = JobMetric(tool='gif-maker', task_id=self.request.id if getattr(self,'request',None) else None,
                           status='FAILURE', error_message=str(e), processing_time_ms=int((time.time()-_task_start)*1000))
            flask_app = get_flask_app()
            if flask_app:
                with flask_app.app_context(): db.session.add(jm); db.session.commit()
            else:
                db.session.add(jm); db.session.commit()
        except Exception:
            pass
        raise

@celery_app.task(bind=True)
def convert_video_to_gif_task(self, video_path, start_time, duration, fps, width, height, output_dir, upload_folder, include_audio=False):
    _task_start = time.time()
    try:
        # Check if input file exists with retry mechanism for distributed file systems
        max_retries = 3
        for attempt in range(max_retries):
            if os.path.exists(video_path):
                break
            if attempt < max_retries - 1:
                logging.warning(f"[convert_video_to_gif_task] Input video file not found on attempt {attempt + 1}, retrying in 1 second: {video_path}")
                time.sleep(1)
            else:
                logging.error(f"[convert_video_to_gif_task] Input video file not found after {max_retries} attempts: {video_path}")
                # List directory contents for debugging
                dir_path = os.path.dirname(video_path)
                if os.path.exists(dir_path):
                    files = os.listdir(dir_path)
                    logging.error(f"[convert_video_to_gif_task] Directory contents of {dir_path}: {files}")
                else:
                    logging.error(f"[convert_video_to_gif_task] Directory does not exist: {dir_path}")
                raise Exception(f"Input video file not found: {video_path}")
        
        # Check file size to ensure it is not empty
        if os.path.getsize(video_path) == 0:
            logging.error(f"[convert_video_to_gif_task] Input video file is empty: {video_path}")
            raise Exception(f"Input video file is empty: {video_path}")
        
        # Add machine debugging for task processing
        import socket
        hostname = socket.gethostname()
        logging.info(f"[convert_video_to_gif_task] Task processing on machine: {hostname}")        
        logging.info(f"[convert_video_to_gif_task] Processing video: {video_path} (size: {os.path.getsize(video_path)} bytes)")
        output_gif = os.path.join(output_dir, f"output_{uuid.uuid4().hex}.gif")
        cmd_gif = [
            "ffmpeg", "-i", video_path,
            "-ss", str(start_time),
            "-t", str(duration),
            "-vf", f"fps={fps},scale={width}:{height}:flags=lanczos",
            "-y", output_gif
        ]
        logging.debug(f"[convert_video_to_gif_task] video_path={video_path}, output_gif={output_gif}, cmd={' '.join(cmd_gif)}")
        result_gif = subprocess.run(cmd_gif, capture_output=True, text=True)
        logging.debug(f"[convert_video_to_gif_task] ffmpeg stdout: {result_gif.stdout}")
        logging.debug(f"[convert_video_to_gif_task] ffmpeg stderr: {result_gif.stderr}")
        if result_gif.returncode != 0:
            logging.error(f"FFmpeg error for video-to-gif: {result_gif.stderr}")
            raise Exception("FFmpeg conversion failed. Please check video format and parameters.")
        if not os.path.exists(output_gif) or os.path.getsize(output_gif) < 1024:
            logging.error(f"Output GIF missing or too small: {output_gif}")
            raise Exception("Output GIF missing or too small.")
        result = {"gif": os.path.relpath(output_gif, upload_folder)}
        # If include_audio, also generate an mp4 with audio (check for audio stream, add robust error handling)
        if include_audio:
            # Check if input video has an audio stream
            probe_cmd = [
                "ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=codec_type", "-of", "default=noprint_wrappers=1:nokey=1", video_path
            ]
            try:
                probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
                has_audio = "audio" in probe_result.stdout
                logging.debug(f"[convert_video_to_gif_task] ffprobe output: {probe_result.stdout.strip()} (has_audio={has_audio})")
            except Exception as e:
                logging.error(f"ffprobe failed: {e}", exc_info=True)
                has_audio = False

            if not has_audio:
                logging.warning(f"Input video has no audio stream, skipping MP4 with audio generation: {video_path}")
            else:
                output_mp4 = os.path.join(output_dir, f"output_{uuid.uuid4().hex}.mp4")
                cmd_mp4 = [
                    "ffmpeg", "-i", video_path,
                    "-ss", str(start_time),
                    "-t", str(duration),
                    "-vf", f"scale={width}:{height}:flags=lanczos",
                    "-c:v", "libx264", "-c:a", "aac", "-y", output_mp4
                ]
                logging.debug(f"[convert_video_to_gif_task] output_mp4={output_mp4}, cmd={' '.join(cmd_mp4)}")
                try:
                    result_mp4 = subprocess.run(cmd_mp4, capture_output=True, text=True, timeout=60)
                    logging.debug(f"[convert_video_to_gif_task] ffmpeg mp4 stdout: {result_mp4.stdout}")
                    logging.debug(f"[convert_video_to_gif_task] ffmpeg mp4 stderr: {result_mp4.stderr}")
                    if result_mp4.returncode == 0 and os.path.exists(output_mp4) and os.path.getsize(output_mp4) > 1024:
                        result["mp4"] = os.path.relpath(output_mp4, upload_folder)
                    else:
                        logging.warning(f"Failed to generate mp4 with audio: {output_mp4}. FFmpeg stderr: {result_mp4.stderr}")
                except subprocess.TimeoutExpired:
                    logging.error(f"FFmpeg mp4 conversion timed out for: {output_mp4}")
                except Exception as e:
                    logging.error(f"Exception during ffmpeg mp4 conversion: {e}", exc_info=True)
        logging.info(f"[convert_video_to_gif_task] Successfully created GIF: {output_gif} (size: {os.path.getsize(output_gif)} bytes), include_audio={include_audio}")
        # metrics
        try:
            peak_kb = getattr(resource.getrusage(resource.RUSAGE_SELF),'ru_maxrss',0)
            jm = JobMetric(tool='video-to-gif', task_id=self.request.id if getattr(self,'request',None) else None,
                           status='SUCCESS', input_type='video', output_size_bytes=os.path.getsize(output_gif) if os.path.exists(output_gif) else None,
                           processing_time_ms=int((time.time()-_task_start)*1000), options=f"fps={fps}; size={width}x{height}; peak_kb={peak_kb}; audio={include_audio}")
            flask_app = get_flask_app()
            if flask_app:
                with flask_app.app_context(): db.session.add(jm); db.session.commit()
            else:
                db.session.add(jm); db.session.commit()
        except Exception:
            pass
        return result
    except Exception as e:
        logging.error(f"Error in convert_video_to_gif_task: {e}", exc_info=True)
        try:
            jm = JobMetric(tool='video-to-gif', task_id=self.request.id if getattr(self,'request',None) else None,
                           status='FAILURE', error_message=str(e), processing_time_ms=int((time.time()-_task_start)*1000))
            flask_app = get_flask_app()
            if flask_app:
                with flask_app.app_context(): db.session.add(jm); db.session.commit()
            else:
                db.session.add(jm); db.session.commit()
        except Exception:
            pass
        raise
    finally:
        try:
            if os.path.exists(video_path):
                os.remove(video_path)
        except Exception as e:
            logging.warning(f"Error deleting input video file {video_path}: {e}")

@celery_app.task(bind=True)
def create_gif_from_images_task(self, image_paths, frame_duration=None, loop_count=None, output_dir=None, upload_folder=None, quality_level="high", frame_durations=None, effects=None):
    _task_start = time.time()
    try:
        if isinstance(image_paths, list) and image_paths and isinstance(image_paths[0], list):
            image_paths = [item for sublist in image_paths for item in (sublist if isinstance(sublist, list) else [sublist])]

        logging.info(f"[create_gif_from_images_task] Received image_paths: {image_paths}")
        logging.info(f"[create_gif_from_images_task] frame_duration={frame_duration}, loop_count={loop_count}, output_dir={output_dir}, upload_folder={upload_folder}, quality_level={quality_level}")

        images = []
        enhanced_images = []

        # Quality settings based on quality_level
        quality_settings = {
            "low": {"colors": 128, "optimize": True, "enhance": False, "dither": True},
            "medium": {"colors": 256, "optimize": False, "enhance": True, "dither": True},
            "high": {"colors": 256, "optimize": False, "enhance": True, "dither": False},
            "ultra": {"colors": 256, "optimize": False, "enhance": True, "dither": False}
        }

        settings = quality_settings.get(quality_level, quality_settings["high"])

        for idx, path in enumerate(image_paths):
            exists = os.path.exists(path)
            if not exists:
                for _ in range(5):
                    time.sleep(0.1)
                    if os.path.exists(path):
                        exists = True
                        break
            if not exists:
                logging.error(f"File does not exist: {path}")
                continue

            file_size = os.path.getsize(path)
            if file_size < 1024:
                logging.error(f"Skipped: file too small ({file_size} bytes): {path}")
                continue

            try:
                img = Image.open(path)
                # Store original image for potential enhancement
                original_img = img.copy()
                # Flatten transparency if present (WEBP/PNG with alpha)
                if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                    background = Image.new("RGBA", img.size, (255, 255, 255, 255))
                    background.paste(img, mask=img.split()[-1])
                    img = background.convert("RGB")
                else:
                    img = img.convert("RGB")
                # Image enhancement for better quality
                if settings["enhance"]:
                    from PIL import ImageEnhance, ImageFilter
                    # Enhance sharpness
                    enhancer = ImageEnhance.Sharpness(img)
                    img = enhancer.enhance(1.2)
                    # Enhance contrast slightly
                    enhancer = ImageEnhance.Contrast(img)
                    img = enhancer.enhance(1.1)
                    # Enhance brightness if image is too dark
                    enhancer = ImageEnhance.Brightness(img)
                    img = enhancer.enhance(1.05)
                    # Apply subtle unsharp mask for better detail
                    img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=150, threshold=3))
                # --- Apply per-frame effect if specified ---
                effect = None
                if effects and idx < len(effects):
                    effect = effects[idx]
                if effect == "fade":
                    # Generate fade-in animation (white to image)
                    fade_frames = []
                    fade_steps = 6
                    for step in range(fade_steps):
                        alpha = int(255 * (1 - step / (fade_steps - 1)))
                        fade_img = img.convert("RGBA")
                        overlay = Image.new("RGBA", fade_img.size, (255, 255, 255, alpha))
                        blended = Image.alpha_composite(fade_img, overlay)
                        pal_img = blended.convert("P", palette=Image.ADAPTIVE)
                        fade_frames.append(pal_img)
                    images.extend(fade_frames)
                    enhanced_images.extend(fade_frames)
                    logging.info(f"Added {fade_steps} fade frames for {path}")
                elif effect == "zoom":
                    # Generate zoom-in animation
                    zoom_frames = []
                    zoom_steps = 6
                    w, h = img.size
                    for step in range(zoom_steps):
                        crop_pct = 0.1 * (1 - step / (zoom_steps - 1))
                        crop_box = (
                            int(w * crop_pct),
                            int(h * crop_pct),
                            int(w * (1 - crop_pct)),
                            int(h * (1 - crop_pct))
                        )
                        zoom_img = img.copy().crop(crop_box).resize((w, h), Image.Resampling.LANCZOS)
                        pal_img = zoom_img.convert("P", palette=Image.ADAPTIVE)
                        zoom_frames.append(pal_img)
                    images.extend(zoom_frames)
                    enhanced_images.extend(zoom_frames)
                    logging.info(f"Added {zoom_steps} zoom frames for {path}")
                else:
                    # Convert to palette mode with better color handling
                    if settings["dither"]:
                        img = img.convert("P", palette=Image.ADAPTIVE, dither=Image.FLOYDSTEINBERG)
                    else:
                        img = img.convert("P", palette=Image.ADAPTIVE)
                    images.append(img)
                    enhanced_images.append(img)
                    logging.info(f"Loaded and processed image {path}, size={img.size}, mode={img.mode}, enhanced={settings['enhance']}, effect={effect}")
            except Exception as e:
                logging.error(f"Failed to open/process image {path}: {e}")

        if not images:
            raise ValueError("No valid images to create GIF.")

        # Resize all images to the same dimensions for better compatibility
        if len(images) > 1:
            target_size = images[0].size
            images = [img if img.size == target_size else img.resize(target_size, Image.Resampling.LANCZOS) for img in images]

        if not output_dir or not os.path.isdir(output_dir):
            logging.error(f"Invalid or non-existent output_dir: {output_dir}. Falling back to tempfile.mkdtemp.")
            output_dir = tempfile.mkdtemp(dir=upload_folder)

        output_path = os.path.join(output_dir, f"output_{uuid.uuid4().hex}.gif")
        # Determine per-frame durations
        if frame_durations and isinstance(frame_durations, list) and len(frame_durations) == len(images):
            durations = [max(int(d), 20) for d in frame_durations]
        else:
            durations = [max(frame_duration or 100, 100)] * len(images)

        # Create GIF with improved settings and per-frame durations
        images[0].save(
            output_path,
            save_all=True,
            append_images=images[1:],
            duration=durations,
            loop=loop_count or 0,
            disposal=2,
            optimize=settings["optimize"],
            colors=settings["colors"]
        )

        logging.info(f"High-quality GIF created at: {output_path} ({os.path.getsize(output_path)} bytes)")
        rel = os.path.relpath(output_path, upload_folder)
        try:
            peak_kb = getattr(resource.getrusage(resource.RUSAGE_SELF),'ru_maxrss',0)
            jm = JobMetric(tool='gif-maker', task_id=self.request.id if getattr(self,'request',None) else None,
                           status='SUCCESS', input_type='images', output_size_bytes=os.path.getsize(output_path) if os.path.exists(output_path) else None,
                           processing_time_ms=int((time.time()-_task_start)*1000), options=f"n={len(image_paths)}; frame_ms={frame_duration}; peak_kb={peak_kb}; quality={quality_level}")
            flask_app = get_flask_app()
            if flask_app:
                with flask_app.app_context(): db.session.add(jm); db.session.commit()
            else:
                db.session.add(jm); db.session.commit()
        except Exception:
            pass
        return rel
    except Exception as e:
        logging.error(f"GIF creation error: {e}", exc_info=True)
        try:
            jm = JobMetric(tool='gif-maker', task_id=self.request.id if getattr(self,'request',None) else None,
                           status='FAILURE', error_message=str(e), processing_time_ms=int((time.time()-_task_start)*1000))
            flask_app = get_flask_app()
            if flask_app:
                with flask_app.app_context(): db.session.add(jm); db.session.commit()
            else:
                db.session.add(jm); db.session.commit()
        except Exception:
            pass
        raise
    finally:
        for img in images:
            try:
                img.close()
            except Exception:
                pass
        for path in image_paths:
            try:
                if os.path.exists(path):
                    os.remove(path)
                    logging.info(f"Deleted input image: {path}")
            except Exception as e:
                logging.warning(f"Error deleting input image {path}: {e}")


@celery_app.task(bind=True)
def resize_gif_task(self, gif_path, width, height, maintain_aspect_ratio, output_dir, upload_folder):
    _task_start = time.time()
    try:
        logging.info(f"[resize_gif_task] gif_path={gif_path}, width={width}, height={height}, maintain_aspect_ratio={maintain_aspect_ratio}, output_dir={output_dir}, upload_folder={upload_folder}")
        
        # Ensure gif_path is absolute
        if not os.path.isabs(gif_path):
            gif_path = os.path.join(upload_folder, gif_path)

        if not os.path.exists(gif_path):
            logging.error(f"[resize_gif_task] File does not exist: {gif_path}")
            raise FileNotFoundError(f"Input GIF for resize does not exist: {gif_path}")
        else:
            logging.info(f"[resize_gif_task] File size: {os.path.getsize(gif_path)} bytes")
            import mimetypes
            mime_type, _ = mimetypes.guess_type(gif_path)
            logging.info(f"[resize_gif_task] Detected mime type: {mime_type}")
        
        gif = Image.open(gif_path)
        frames = []

        if maintain_aspect_ratio:
            original_width, original_height = gif.size
            aspect_ratio = original_width / original_height
            if width / height > aspect_ratio:
                width = int(height * aspect_ratio)
            else:
                height = int(width / aspect_ratio)

        for frame in range(gif.n_frames):
            gif.seek(frame)
            resized_frame = gif.copy().resize((width, height), Image.Resampling.LANCZOS)
            frames.append(resized_frame)

        output_path = os.path.join(output_dir, f"resized_{uuid.uuid4().hex}.gif")
        frames[0].save(
            output_path,
            save_all=True,
            append_images=frames[1:],
            duration=gif.info.get("duration", 100),
            loop=gif.info.get("loop", 0)
        )
        if not os.path.exists(output_path) or os.path.getsize(output_path) < 1024:
            logging.error(f"[resize_gif_task] Output GIF missing or too small: {output_path}")
            raise Exception("Output GIF missing or too small.")
        logging.info(f"[resize_gif_task] Successfully created resized GIF: {output_path} (size: {os.path.getsize(output_path)} bytes)")
        rel = os.path.relpath(output_path, upload_folder)
        try:
            peak_kb = getattr(resource.getrusage(resource.RUSAGE_SELF),'ru_maxrss',0)
            jm = JobMetric(tool='resize', task_id=self.request.id if getattr(self,'request',None) else None,
                           status='SUCCESS', input_type='gif', output_size_bytes=os.path.getsize(output_path) if os.path.exists(output_path) else None,
                           processing_time_ms=int((time.time()-_task_start)*1000), options=f"size={width}x{height}; keep_ar={maintain_aspect_ratio}; peak_kb={peak_kb}")
            flask_app = get_flask_app()
            if flask_app:
                with flask_app.app_context(): db.session.add(jm); db.session.commit()
            else:
                db.session.add(jm); db.session.commit()
        except Exception:
            pass
        return rel
    except Exception as e:
        logging.error(f"Error in resize_gif_task: {e}", exc_info=True)
        try:
            jm = JobMetric(tool='resize', task_id=self.request.id if getattr(self,'request',None) else None,
                           status='FAILURE', error_message=str(e), processing_time_ms=int((time.time()-_task_start)*1000))
            flask_app = get_flask_app()
            if flask_app:
                with flask_app.app_context(): db.session.add(jm); db.session.commit()
            else:
                db.session.add(jm); db.session.commit()
        except Exception:
            pass
        raise
    finally:
        # Clean up the input GIF file. The output_dir is managed by the main cleanup task.
        try:
            if os.path.exists(gif_path):
                os.remove(gif_path)
        except Exception as e:
            logging.warning(f"Error deleting input GIF file {gif_path}: {e}")

@celery_app.task(bind=True)
def crop_gif_task(self, gif_path, x, y, width, height, aspect_ratio, output_dir, upload_folder):
    _task_start = time.time()
    try:
        logging.info(f"[crop_gif_task] gif_path={gif_path}, x={x}, y={y}, width={width}, height={height}, aspect_ratio={aspect_ratio}, output_dir={output_dir}, upload_folder={upload_folder}")
        
        # Ensure gif_path is absolute
        if not os.path.isabs(gif_path):
            gif_path = os.path.join(upload_folder, gif_path)

        if not os.path.exists(gif_path):
            logging.error(f"[crop_gif_task] File does not exist: {gif_path}")
            raise FileNotFoundError(f"Input GIF for crop does not exist: {gif_path}")
        else:
            logging.info(f"[crop_gif_task] File size: {os.path.getsize(gif_path)} bytes")
            import mimetypes
            mime_type, _ = mimetypes.guess_type(gif_path)
            logging.info(f"[crop_gif_task] Detected mime type: {mime_type}")
        
        gif = Image.open(gif_path)
        original_width, original_height = gif.size
        logging.info(f"[crop_gif_task] Original GIF size: {original_width}x{original_height}, n_frames: {getattr(gif, 'n_frames', 1)}")

        # Helper function from gif.py
        def get_aspect_ratio_dimensions(w, h, ar):
            if ar == "square": size = min(w, h); return size, size
            elif ar == "4:3": return (int(h * 4/3), h) if w / h > 4/3 else (w, int(w * 3/4))
            elif ar == "16:9": return (int(h * 16/9), h) if w / h > 16/9 else (w, int(w * 9/16))
            elif ar == "3:2": return (int(h * 3/2), h) if w / h > 3/2 else (w, int(w * 2/3))
            elif ar == "2:1": return (int(h * 2), h) if w / h > 2 else (w, int(w / 2))
            elif ar == "golden": golden_ratio = 1.618; return (int(h * golden_ratio), h) if w / h > golden_ratio else (w, int(w / golden_ratio))
            else: return w, h

        if aspect_ratio != "free":
            width, height = get_aspect_ratio_dimensions(width, height, aspect_ratio)

        x = max(0, min(x, original_width - width))
        y = max(0, min(y, original_height - height))
        width = min(width, original_width - x)
        height = min(height, original_height - y)

        frames = []
        for frame in range(gif.n_frames):
            gif.seek(frame)
            cropped_frame = gif.copy().crop((x, y, x + width, y + height))
            logging.info(f"[crop_gif_task] Cropped frame {frame}: {cropped_frame.size}")
            frames.append(cropped_frame)

        output_path = os.path.join(output_dir, f"cropped_{uuid.uuid4().hex}.gif")
        frames[0].save(
            output_path,
            save_all=True,
            append_images=frames[1:],
            duration=gif.info.get("duration", 100),
            loop=gif.info.get("loop", 0)
        )
        if not os.path.exists(output_path) or os.path.getsize(output_path) < 1024:
            logging.error(f"[crop_gif_task] Output GIF missing or too small: {output_path}")
            raise Exception("Output GIF missing or too small.")
        else:
            logging.info(f"[crop_gif_task] Output GIF size: {os.path.getsize(output_path)} bytes")
        rel = os.path.relpath(output_path, upload_folder)
        try:
            peak_kb = getattr(resource.getrusage(resource.RUSAGE_SELF),'ru_maxrss',0)
            jm = JobMetric(tool='crop', task_id=self.request.id if getattr(self,'request',None) else None,
                           status='SUCCESS', input_type='gif', output_size_bytes=os.path.getsize(output_path) if os.path.exists(output_path) else None,
                           processing_time_ms=int((time.time()-_task_start)*1000), options=f"crop={x},{y},{width},{height}; ar={aspect_ratio}; peak_kb={peak_kb}")
            flask_app = get_flask_app()
            if flask_app:
                with flask_app.app_context(): db.session.add(jm); db.session.commit()
            else:
                db.session.add(jm); db.session.commit()
        except Exception:
            pass
        return rel
    except Exception as e:
        logging.error(f"Error in crop_gif_task: {e}", exc_info=True)
        try:
            jm = JobMetric(tool='crop', task_id=self.request.id if getattr(self,'request',None) else None,
                           status='FAILURE', error_message=str(e), processing_time_ms=int((time.time()-_task_start)*1000))
            flask_app = get_flask_app()
            if flask_app:
                with flask_app.app_context(): db.session.add(jm); db.session.commit()
            else:
                db.session.add(jm); db.session.commit()
        except Exception:
            pass
        raise
    finally:
        # Clean up the input GIF file. The output_dir is managed by the main cleanup task.
        try:
            if os.path.exists(gif_path):
                os.remove(gif_path)
        except Exception as e:
            logging.warning(f"Error deleting input GIF file {gif_path}: {e}")

@celery_app.task(bind=True)
def optimize_gif_task(self, gif_path, quality, colors, lossy, dither, optimize_level, output_dir, upload_folder):
    _task_start = time.time()
    try:
        # Ensure gif_path is absolute
        if not os.path.isabs(gif_path):
            gif_path = os.path.join(upload_folder, gif_path)
        
        logging.info(f"[optimize_gif_task] gif_path={gif_path}, quality={quality}, colors={colors}, lossy={lossy}, dither={dither}, optimize_level={optimize_level}, output_dir={output_dir}, upload_folder={upload_folder}")
        if not os.path.exists(gif_path):
            logging.error(f"[optimize_gif_task] File does not exist: {gif_path}")
            raise FileNotFoundError(f"Input GIF for optimize does not exist: {gif_path}")
        else:
            logging.info(f"[optimize_gif_task] File size: {os.path.getsize(gif_path)} bytes")
            import mimetypes
            mime_type, _ = mimetypes.guess_type(gif_path)
            logging.info(f"[optimize_gif_task] Detected mime type: {mime_type}")
        
        output_path = os.path.join(output_dir, f"optimized_{uuid.uuid4().hex}.gif")
        
        # Quality-based optimization settings
        if quality >= 95:
            # Very high quality: minimal compression but still optimize
            optimized_colors = min(colors, 200)
            optimized_lossy = 0
            optimized_level = 2
        elif quality >= 80:
            # High quality: light compression
            optimized_colors = min(colors, 128)
            optimized_lossy = max(0, lossy // 3)
            optimized_level = 2
        elif quality >= 60:
            # Medium quality: moderate compression
            optimized_colors = min(colors, 64)
            optimized_lossy = lossy
            optimized_level = 3
        else:
            # Low quality: aggressive compression
            optimized_colors = min(colors, 32)
            optimized_lossy = min(100, lossy * 2)
            optimized_level = 3
        
        logging.info(f"[optimize_gif_task] Quality-based settings: colors={optimized_colors}, lossy={optimized_lossy}, level={optimized_level}")
        
        try:
            # Enhanced gifsicle optimization
            cmd = ["gifsicle", f"--optimize={optimized_level}", f"--colors={optimized_colors}"]
            
            # Add lossy compression if specified
            if optimized_lossy > 0:
                cmd.extend([f"--lossy={optimized_lossy}"])
            
            # Add dithering for better color quality
            if dither and dither != "none":
                cmd.extend([f"--dither={dither}"])
            
            # Add additional optimizations for better compression
            cmd.extend(["--no-extensions", "--no-comments", "--no-names"])
            
            # Add frame optimization for better compression
            cmd.extend(["--optimize-frames"])
            
            # Add interlace optimization
            cmd.extend(["--interlace"])
            
            cmd.extend([gif_path, "-o", output_path])
            
            logging.info(f"[optimize_gif_task] Running gifsicle command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logging.warning(f"Gifsicle optimization failed: {result.stderr}. Falling back to PIL.")
                raise subprocess.CalledProcessError(result.returncode, cmd)
                
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Fallback to PIL optimization
            logging.info("[optimize_gif_task] Using PIL fallback optimization")
            gif = Image.open(gif_path)
            
            # Check if it's an animated GIF
            try:
                # Get all frames
                frames = []
                durations = []
                
                while True:
                    frames.append(gif.copy())
                    durations.append(gif.info.get('duration', 100))
                    gif.seek(gif.tell() + 1)
            except EOFError:
                pass
            
            logging.info(f"[optimize_gif_task] Found {len(frames)} frames in animated GIF")
            
            # Apply quality-based PIL optimization to each frame
            optimized_frames = []
            for frame in frames:
                if optimized_colors < 256:
                    # Convert to palette mode for color reduction
                    optimized_frame = frame.quantize(colors=optimized_colors, dither=Image.Dither.FLOYDSTEINBERG if dither == "floyd-steinberg" else Image.Dither.NONE)
                else:
                    optimized_frame = frame
                optimized_frames.append(optimized_frame)
            
            # Save as animated GIF with all frames
            if optimized_frames:
                optimized_frames[0].save(
                    output_path,
                    save_all=True,
                    append_images=optimized_frames[1:],
                    optimize=True,
                    duration=durations,
                    loop=0
                )
        
        if not os.path.exists(output_path) or os.path.getsize(output_path) < 1024:
            logging.error(f"[optimize_gif_task] Output GIF missing or too small: {output_path}")
            raise Exception("Output GIF missing or too small.")
        
        # Calculate compression ratio
        original_size = os.path.getsize(gif_path)
        optimized_size = os.path.getsize(output_path)
        compression_ratio = ((original_size - optimized_size) / original_size) * 100
        
        logging.info(f"[optimize_gif_task] Successfully created optimized GIF: {output_path}")
        logging.info(f"[optimize_gif_task] Original size: {original_size} bytes, Optimized size: {optimized_size} bytes")
        logging.info(f"[optimize_gif_task] Compression ratio: {compression_ratio:.1f}%")
        
        rel = os.path.relpath(output_path, upload_folder)
        try:
            peak_kb = getattr(resource.getrusage(resource.RUSAGE_SELF),'ru_maxrss',0)
            jm = JobMetric(tool='optimize', task_id=self.request.id if getattr(self,'request',None) else None,
                           status='SUCCESS', input_type='gif', output_size_bytes=os.path.getsize(output_path) if os.path.exists(output_path) else None,
                           processing_time_ms=int((time.time()-_task_start)*1000), options=f"quality={quality}; colors={colors}; lossy={lossy}; dither={dither}; level={optimize_level}; peak_kb={peak_kb}")
            flask_app = get_flask_app()
            if flask_app:
                with flask_app.app_context(): db.session.add(jm); db.session.commit()
            else:
                db.session.add(jm); db.session.commit()
        except Exception:
            pass
        return rel
    except Exception as e:
        logging.error(f"Error in optimize_gif_task: {e}", exc_info=True)
        try:
            jm = JobMetric(tool='optimize', task_id=self.request.id if getattr(self,'request',None) else None,
                           status='FAILURE', error_message=str(e), processing_time_ms=int((time.time()-_task_start)*1000))
            flask_app = get_flask_app()
            if flask_app:
                with flask_app.app_context(): db.session.add(jm); db.session.commit()
            else:
                db.session.add(jm); db.session.commit()
        except Exception:
            pass
        raise
    finally:
        # Clean up the input GIF file. The output_dir is managed by the main cleanup task.
        try:
            if os.path.exists(gif_path):
                os.remove(gif_path)
        except Exception as e:
            logging.warning(f"Error deleting input GIF file {gif_path}: {e}")

@celery_app.task(bind=True)
def reverse_gif_task(self, gif_path, output_dir, upload_folder):
    _task_start = time.time()
    try:
        logging.info(f"[reverse_gif_task] gif_path={gif_path}, output_dir={output_dir}, upload_folder={upload_folder}")
        
        # Handle case where gif_path comes from a chained task (relative path)
        if not os.path.isabs(gif_path):
            gif_path = os.path.join(upload_folder, gif_path)
            
        if not os.path.exists(gif_path):
            logging.error(f"[reverse_gif_task] File does not exist: {gif_path}")
            raise FileNotFoundError(f"Input GIF for reverse does not exist: {gif_path}")
            
        logging.info(f"[reverse_gif_task] File size: {os.path.getsize(gif_path)} bytes")
        
        # Check if it's a GIF file
        mime = magic.from_file(gif_path, mime=True)
        if mime != 'image/gif':
            logging.error(f"[reverse_gif_task] File is not a GIF: {mime}")
            raise ValueError(f"File is not a GIF: {mime}")
        
        logging.info(f"[reverse_gif_task] Detected mime type: {mime}")
        
        gif = Image.open(gif_path)
        frames = []
        durations = []
        
        try:
            for frame in range(getattr(gif, 'n_frames', 1)):
                gif.seek(frame)
                frames.append(gif.copy())
                durations.append(gif.info.get('duration', 100))
        except EOFError:
            pass
            
        if not frames:
            raise ValueError("No frames found in GIF")
            
        logging.info(f"[reverse_gif_task] Found {len(frames)} frames to reverse")
        
        # Reverse the frames and durations
        frames.reverse()
        durations.reverse()
        
        output_path = os.path.join(output_dir, f"reversed_{uuid.uuid4().hex}.gif")
        
        frames[0].save(
            output_path,
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=gif.info.get('loop', 0)
        )
        
        if not os.path.exists(output_path) or os.path.getsize(output_path) < 1024:
            logging.error(f"[reverse_gif_task] Output GIF missing or too small: {output_path}")
            raise Exception("Output GIF missing or too small.")
            
        logging.info(f"[reverse_gif_task] Successfully created reversed GIF: {output_path} (size: {os.path.getsize(output_path)} bytes)")
        
        rel = os.path.relpath(output_path, upload_folder)
        try:
            peak_kb = getattr(resource.getrusage(resource.RUSAGE_SELF), 'ru_maxrss', 0)
            jm = JobMetric(tool='reverse', task_id=self.request.id if getattr(self, 'request', None) else None,
                           status='SUCCESS', input_type='gif',
                           output_size_bytes=os.path.getsize(output_path) if os.path.exists(output_path) else None,
                           processing_time_ms=int((time.time()-_task_start)*1000),
                           options=f"peak_kb={peak_kb}")
            flask_app = get_flask_app()
            if flask_app:
                with flask_app.app_context():
                    db.session.add(jm)
                    db.session.commit()
            else:
                db.session.add(jm)
                db.session.commit()
        except Exception:
            pass
        return rel
    except Exception as e:
        logging.error(f"Error in reverse_gif_task: {e}", exc_info=True)
        try:
            jm = JobMetric(tool='reverse', task_id=self.request.id if getattr(self, 'request', None) else None,
                           status='FAILURE', error_message=str(e),
                           processing_time_ms=int((time.time()-_task_start)*1000))
            flask_app = get_flask_app()
            if flask_app:
                with flask_app.app_context():
                    db.session.add(jm)
                    db.session.commit()
            else:
                db.session.add(jm)
                db.session.commit()
        except Exception:
            pass
        raise
    finally:
        try:
            if os.path.exists(gif_path):
                os.remove(gif_path)
        except Exception as e:
            logging.warning(f"Error deleting input GIF file {gif_path}: {e}")
@celery_app.task(bind=True)
def add_text_to_gif_task(self, gif_path, text, font_size, color, font_family, stroke_color, stroke_width, horizontal_align, vertical_align, offset_x, offset_y, start_frame, end_frame, animation_style, output_dir, upload_folder):
    _task_start = time.time()
    # Resolve gif_path to absolute path if not already
    if not os.path.isabs(gif_path):
        abs_gif_path = os.path.join(upload_folder, gif_path)
    else:
        abs_gif_path = gif_path

    # Utility to convert hex color to RGB tuple
    def hex_to_rgb(value):
        value = value.lstrip('#')
        lv = len(value)
        return tuple(int(value[i:i + lv // 3], 16) for i in range(0, lv, lv // 3))

    # Convert color and stroke_color to RGB tuples if needed
    orig_color = color
    orig_stroke_color = stroke_color
    if isinstance(color, str) and color.startswith('#'):
        color = hex_to_rgb(color)
    if isinstance(stroke_color, str) and stroke_color.startswith('#'):
        stroke_color = hex_to_rgb(stroke_color)

    # Open GIF just to get n_frames, then close
    with Image.open(abs_gif_path) as gif_probe:
        n_frames = getattr(gif_probe, "n_frames", 1)
    if end_frame == -1 or end_frame is None:
        end_frame = n_frames - 1

    logging.info(f"[add_text_to_gif_task] Drawing text '{text}' from frame {start_frame} to {end_frame} with color {color} (original: {orig_color}), stroke_color {stroke_color} (original: {orig_stroke_color})")

    try:
        gif = Image.open(abs_gif_path)
        logging.info(f"[add_text_to_gif_task] gif_path={gif_path}, abs_gif_path={abs_gif_path}, text='{text}', font_size={font_size}, color={color}, font_family={font_family}, stroke_color={stroke_color}, stroke_width={stroke_width}, horizontal_align={horizontal_align}, vertical_align={vertical_align}, offset_x={offset_x}, offset_y={offset_y}, start_frame={start_frame}, end_frame={end_frame}, animation_style={animation_style}, output_dir={output_dir}, upload_folder={upload_folder}")
        if not os.path.exists(abs_gif_path):
            logging.error(f"[add_text_to_gif_task] Input GIF does not exist: {abs_gif_path}")
            raise FileNotFoundError(f"Input GIF does not exist: {abs_gif_path}")
        logging.info(f"[add_text_to_gif_task] Input GIF size: {os.path.getsize(abs_gif_path)} bytes")
        _basedir = os.path.abspath(os.path.dirname(__file__)) # This will be src/
        font_paths = {
            "Arial": [os.path.join(_basedir, "fonts/DejaVuSans.ttf")],
            "Helvetica": [os.path.join(_basedir, "fonts/DejaVuSans.ttf")],
            "Times New Roman": [os.path.join(_basedir, "fonts/DejaVuSerif.ttf")],
            "Courier New": [os.path.join(_basedir, "fonts/DejaVuSansMono.ttf")],
            "Verdana": [os.path.join(_basedir, "fonts/DejaVuSans.ttf")],
            "Georgia": [os.path.join(_basedir, "fonts/DejaVuSerif.ttf")],
            "Comic Sans MS": [os.path.join(_basedir, "fonts/ComicNeue-Regular.ttf")],
            "Impact": [os.path.join(_basedir, "fonts/impact.ttf")]
        }
        font = None
        font_loaded = False
        # Try to load custom fonts with better error handling
        if font_family in font_paths:
            for font_path in font_paths[font_family]:
                try:
                    # Check if file exists first
                    if os.path.exists(font_path):
                        font = ImageFont.truetype(font_path, font_size)
                        font_loaded = True
                        logging.info(f"[add_text_to_gif_task] Loaded font: {font_path}")
                        break
                    else:
                        logging.warning(f"[add_text_to_gif_task] Font file not found: {font_path}")
                except (IOError, ImportError, OSError) as fe:
                    logging.warning(f"[add_text_to_gif_task] Could not load font {font_path}: {fe}")
        # Try fallback font
        if font is None:
            try:
                fallback_font_path = os.path.join(_basedir, "fonts/DejaVuSans.ttf")
                if os.path.exists(fallback_font_path):
                    font = ImageFont.truetype(fallback_font_path, font_size)
                    font_loaded = True
                    logging.info(f"[add_text_to_gif_task] Loaded fallback font: {fallback_font_path}")
                else:
                    logging.warning(f"[add_text_to_gif_task] Fallback font not found: {fallback_font_path}")
            except (IOError, ImportError, OSError) as fe:
                logging.warning(f"[add_text_to_gif_task] Could not load fallback font: {fe}")
        # Use default font as last resort
        if font is None:
            try:
                font = ImageFont.load_default()
                font_loaded = True
                logging.info(f"[add_text_to_gif_task] Using default font")
            except Exception as fe:
                logging.error(f"[add_text_to_gif_task] Could not load any font: {fe}")
                raise Exception("No fonts available for text rendering")
        frames = []
        frame_count = 0
        # Downscale factor for large frames
        base_w, base_h = gif.size
        scale = _compute_scale_factor(base_w, base_h, MAX_GIF_PIXELS)
        if scale < 1.0:
            logging.info(f"[add_text_to_gif_task] Downscaling frames by factor {scale:.2f} due to size {base_w}x{base_h}")
        
        # Function to calculate text position based on alignment and offset
        def calculate_text_position(img_width, img_height, text_width, text_height, horizontal_align, vertical_align, offset_x, offset_y):
            # Calculate base position based on alignment
            if horizontal_align == 'left':
                base_x = 0
            elif horizontal_align == 'center':
                base_x = (img_width - text_width) // 2
            elif horizontal_align == 'right':
                base_x = img_width - text_width
            else:
                base_x = (img_width - text_width) // 2
            
            if vertical_align == 'top':
                base_y = 0
            elif vertical_align == 'middle':
                base_y = (img_height - text_height) // 2
            elif vertical_align == 'bottom':
                base_y = img_height - text_height
            else:
                base_y = (img_height - text_height) // 2
            
            # Apply offsets
            final_x = base_x + offset_x
            final_y = base_y + offset_y
            
            return final_x, final_y

        def wrap_text(draw, text, font, max_width):
            if not text:
                return []
            lines = []
            paragraphs = text.split('\n')
            for para in paragraphs:
                words = para.split()
                line = ''
                for word in words:
                    test = f"{line} {word}".strip()
                    w = draw.textlength(test, font=font)
                    if w <= max_width or not line:
                        line = test
                    else:
                        lines.append(line)
                        line = word
                if line:
                    lines.append(line)
            return lines

        def draw_text_block(draw, lines, top_left, font, fill, stroke_color=None, stroke_width=0, line_height=None):
            if not lines:
                return
            if line_height is None:
                ascent, descent = font.getmetrics()
                line_height = ascent + descent + 2
            x, y = top_left
            for i, line in enumerate(lines):
                ly = y + i * line_height
                if stroke_width and stroke_width > 0 and stroke_color is not None:
                    # draw stroke by offsetting around
                    for dx in range(-stroke_width, stroke_width + 1):
                        for dy in range(-stroke_width, stroke_width + 1):
                            if dx != 0 or dy != 0:
                                draw.text((x + dx, ly + dy), line, font=font, fill=stroke_color)
                draw.text((x, ly), line, font=font, fill=fill)

        def apply_animation(draw, lines, position, font, color, stroke_color, stroke_width, animation_style, frame_index, start_frame, end_frame, line_height):
            progress = max(0.0, min(1.0, (frame_index - start_frame) / max(1, (end_frame - start_frame))))
            if animation_style == 'fade':
                alpha = int(255 * progress)
                rgba = (*color, alpha) if isinstance(color, tuple) and len(color) == 3 else color
                draw_text_block(draw, lines, position, font, rgba, stroke_color, stroke_width, line_height)
            elif animation_style == 'slide_up':
                y_offset = int(50 * (1 - progress))
                draw_text_block(draw, lines, (position[0], position[1] + y_offset), font, color, stroke_color, stroke_width, line_height)
            else:
                draw_text_block(draw, lines, position, font, color, stroke_color, stroke_width, line_height)

        # Check if image is animated (GIF) or static (PNG, JPEG, etc.)
        is_animated = getattr(gif, "is_animated", False)

        if is_animated:
            # Sample frames if too many
            total_frames = gif.n_frames
            step = max(1, int((total_frames + MAX_GIF_FRAMES - 1) // MAX_GIF_FRAMES))
            for frame in range(0, total_frames, step):
                gif.seek(frame)
                frame_copy = gif.copy().convert("RGBA")
                if scale < 1.0:
                    new_size = (max(1, int(frame_copy.width * scale)), max(1, int(frame_copy.height * scale)))
                    frame_copy = frame_copy.resize(new_size, Image.Resampling.LANCZOS)
                draw = ImageDraw.Draw(frame_copy)

                if start_frame <= frame <= end_frame:
                    # Wrap text to frame width with small padding
                    max_text_width = int(frame_copy.width * 0.95)
                    lines = wrap_text(draw, text, font, max_text_width)
                    # Compute text block size
                    ascent, descent = font.getmetrics()
                    line_height = ascent + descent + 2
                    text_width = max((draw.textlength(line, font=font) for line in lines), default=0)
                    text_height = line_height * max(len(lines), 1)

                    # Calculate position based on alignment and offset for the whole block
                    final_x, final_y = calculate_text_position(
                        frame_copy.width, frame_copy.height, text_width, text_height,
                        horizontal_align, vertical_align, offset_x, offset_y
                    )

                    apply_animation(
                        draw, lines, (final_x, final_y), font, color, stroke_color,
                        stroke_width, animation_style, frame, start_frame, end_frame, line_height
                    )

                frames.append(frame_copy.convert("RGB"))
                frame_count += 1
            logging.info(f"[add_text_to_gif_task] Processed {frame_count} frames (animated GIF).")
        else:
            # Static image (PNG, JPEG, etc.)
            frame_copy = gif.convert("RGBA")
            if scale < 1.0:
                new_size = (max(1, int(frame_copy.width * scale)), max(1, int(frame_copy.height * scale)))
                frame_copy = frame_copy.resize(new_size, Image.Resampling.LANCZOS)
            draw = ImageDraw.Draw(frame_copy)

            # Wrap text to image width with small padding
            max_text_width = int(frame_copy.width * 0.95)
            lines = wrap_text(draw, text, font, max_text_width)
            ascent, descent = font.getmetrics()
            line_height = ascent + descent + 2
            text_width = max((draw.textlength(line, font=font) for line in lines), default=0)
            text_height = line_height * max(len(lines), 1)

            # Calculate position based on alignment and offset for the whole block
            final_x, final_y = calculate_text_position(
                frame_copy.width, frame_copy.height, text_width, text_height,
                horizontal_align, vertical_align, offset_x, offset_y
            )

            # Draw multi-line block with optional stroke
            draw_text_block(draw, lines, (final_x, final_y), font, color, stroke_color, stroke_width, line_height)
            frames.append(frame_copy.convert("RGB"))
            frame_count = 1
            logging.info(f"[add_text_to_gif_task] Processed 1 frame (static image).")
        
        output_path = os.path.join(output_dir, f"text_{uuid.uuid4().hex}.gif")
        frames[0].save(
            output_path,
            save_all=True,
            append_images=frames[1:] if len(frames) > 1 else [],
            duration=gif.info.get("duration", 100),
            loop=gif.info.get("loop", 0)
        )
        
        if os.path.exists(output_path):
            logging.info(f"[add_text_to_gif_task] Output GIF created: {output_path}, size: {os.path.getsize(output_path)} bytes")
        else:
            logging.error(f"[add_text_to_gif_task] Output GIF was not created: {output_path}")
            raise Exception("Output GIF was not created.")
        rel = os.path.relpath(output_path, upload_folder)
        # Record metrics (best-effort)
        try:
            out_size = os.path.getsize(output_path)
            peak_kb = getattr(resource.getrusage(resource.RUSAGE_SELF), 'ru_maxrss', 0)
            proc_ms = int((time.time() - _task_start) * 1000)
            jm = JobMetric(
                tool='add-text',
                task_id=self.request.id if getattr(self, 'request', None) else None,
                status='SUCCESS',
                input_type='gif',
                input_width=base_w,
                input_height=base_h,
                input_frames=n_frames,
                input_size_bytes=os.path.getsize(abs_gif_path) if os.path.exists(abs_gif_path) else None,
                output_size_bytes=out_size,
                processing_time_ms=proc_ms,
                options=f"anim={animation_style}; stroke={stroke_width}; font={font_family}; peak_kb={peak_kb}"
            )
            flask_app = get_flask_app()
            if flask_app:
                with flask_app.app_context():
                    db.session.add(jm)
                    db.session.commit()
            else:
                db.session.add(jm)
                db.session.commit()
        except Exception as _me:
            logging.warning(f"[metrics] add-text save failed: {_me}")
        return rel
    except Exception as e:
        logging.error(f"Error in add_text_to_gif_task: {e}", exc_info=True)
        try:
            jm = JobMetric(
                tool='add-text',
                task_id=self.request.id if getattr(self, 'request', None) else None,
                status='FAILURE',
                error_message=str(e),
                processing_time_ms=int((time.time() - _task_start) * 1000)
            )
            flask_app = get_flask_app()
            if flask_app:
                with flask_app.app_context():
                    db.session.add(jm)
                    db.session.commit()
            else:
                db.session.add(jm)
                db.session.commit()
        except Exception:
            pass
        raise
    finally:
        # Clean up the input GIF file. The output_dir is managed by the main cleanup task.
        try:
            if os.path.exists(abs_gif_path):
                os.remove(abs_gif_path)
        except Exception as e:
            logging.warning(f"Error deleting input GIF file {abs_gif_path}: {e}")

@celery_app.task(bind=True)
def add_text_layers_to_gif_task(self, gif_path, layers, output_dir, upload_folder):
    _task_start = time.time()
    # gif_path may be absolute or relative
    if not os.path.isabs(gif_path):
        abs_gif_path = os.path.join(upload_folder, gif_path)
    else:
        abs_gif_path = gif_path

    def hex_to_rgb(value):
        value = value.lstrip('#')
        lv = len(value)
        return tuple(int(value[i:i + lv // 3], 16) for i in range(0, lv, lv // 3))

    def load_font(font_family, font_size):
        _basedir = os.path.abspath(os.path.dirname(__file__))
        font_paths = {
            "Arial": [os.path.join(_basedir, "fonts/DejaVuSans.ttf")],
            "Helvetica": [os.path.join(_basedir, "fonts/DejaVuSans.ttf")],
            "Times New Roman": [os.path.join(_basedir, "fonts/DejaVuSerif.ttf")],
            "Courier New": [os.path.join(_basedir, "fonts/DejaVuSansMono.ttf")],
            "Verdana": [os.path.join(_basedir, "fonts/DejaVuSans.ttf")],
            "Georgia": [os.path.join(_basedir, "fonts/DejaVuSerif.ttf")],
            "Comic Sans MS": [os.path.join(_basedir, "fonts/ComicNeue-Regular.ttf")],
            "Impact": [os.path.join(_basedir, "fonts/impact.ttf")]
        }
        font = None
        # Try named fonts first
        if font_family in font_paths:
            for p in font_paths[font_family]:
                try:
                    if os.path.exists(p):
                        font = ImageFont.truetype(p, font_size)
                        break
                except Exception:
                    continue
        if font is None:
            # Fallback
            try:
                fallback = os.path.join(_basedir, "fonts/DejaVuSans.ttf")
                if os.path.exists(fallback):
                    font = ImageFont.truetype(fallback, font_size)
            except Exception:
                pass
        if font is None:
            font = ImageFont.load_default()
        return font

    def wrap_text(draw, text, font, max_width):
        if not text:
            return []
        lines = []
        for para in text.split('\n'):
            words = para.split()
            line = ''
            for w in words:
                test = f"{line} {w}".strip()
                if draw.textlength(test, font=font) <= max_width or not line:
                    line = test
                else:
                    lines.append(line)
                    line = w
            if line:
                lines.append(line)
        return lines

    def draw_text_block(draw, lines, top_left, font, fill, stroke_color=None, stroke_width=0, line_height=None):
        if not lines:
            return
        if line_height is None:
            ascent, descent = font.getmetrics()
            line_height = ascent + descent + 2
        x, y = top_left
        for i, line in enumerate(lines):
            ly = y + i * line_height
            if stroke_width and stroke_width > 0 and stroke_color is not None:
                for dx in range(-stroke_width, stroke_width + 1):
                    for dy in range(-stroke_width, stroke_width + 1):
                        if dx != 0 or dy != 0:
                            draw.text((x + dx, ly + dy), line, font=font, fill=stroke_color)
            draw.text((x, ly), line, font=font, fill=fill)

    def calculate_position(img_w, img_h, block_w, block_h, h_align, v_align, offset_x, offset_y):
        if h_align == 'left':
            base_x = 0
        elif h_align == 'center':
            base_x = (img_w - block_w) // 2
        elif h_align == 'right':
            base_x = img_w - block_w
        else:
            base_x = (img_w - block_w) // 2
        if v_align == 'top':
            base_y = 0
        elif v_align == 'middle':
            base_y = (img_h - block_h) // 2
        elif v_align == 'bottom':
            base_y = img_h - block_h
        else:
            base_y = (img_h - block_h) // 2
        return base_x + offset_x, base_y + offset_y

    def apply_animation(draw, lines, position, font, color, stroke_color, stroke_width, animation_style, frame_index, start_frame, end_frame, line_height):
        progress = max(0.0, min(1.0, (frame_index - start_frame) / max(1, (end_frame - start_frame))))
        if animation_style == 'fade':
            alpha = int(255 * progress)
            rgba = (*color, alpha) if isinstance(color, tuple) and len(color) == 3 else color
            draw_text_block(draw, lines, position, font, rgba, stroke_color, stroke_width, line_height)
        elif animation_style == 'slide_up':
            y_offset = int(50 * (1 - progress))
            draw_text_block(draw, lines, (position[0], position[1] + y_offset), font, color, stroke_color, stroke_width, line_height)
        else:
            draw_text_block(draw, lines, position, font, color, stroke_color, stroke_width, line_height)

    try:
        gif = Image.open(abs_gif_path)
        is_animated = getattr(gif, 'is_animated', False)
        frames = []
        # Downscale factor for large frames
        base_w, base_h = gif.size
        scale = _compute_scale_factor(base_w, base_h, MAX_GIF_PIXELS)
        if scale < 1.0:
            logging.info(f"[add_text_layers_to_gif_task] Downscaling frames by factor {scale:.2f} due to size {base_w}x{base_h}")
        # Convert any hex colors to RGB
        normalized_layers = []
        for l in layers:
            col = l.get('color', '#ffffff')
            sc = l.get('stroke_color', '#000000')
            if isinstance(col, str) and col.startswith('#'):
                col = hex_to_rgb(col)
            if isinstance(sc, str) and sc.startswith('#'):
                sc = hex_to_rgb(sc)
            normalized_layers.append({ **l, 'color': col, 'stroke_color': sc })

        if is_animated:
            total_frames = gif.n_frames
            step = max(1, int((total_frames + MAX_GIF_FRAMES - 1) // MAX_GIF_FRAMES))
            for frame_idx in range(0, total_frames, step):
                gif.seek(frame_idx)
                frame_img = gif.copy().convert('RGBA')
                if scale < 1.0:
                    new_size = (max(1, int(frame_img.width * scale)), max(1, int(frame_img.height * scale)))
                    frame_img = frame_img.resize(new_size, Image.Resampling.LANCZOS)
                draw = ImageDraw.Draw(frame_img)
                for l in normalized_layers:
                    if frame_idx < l['start_frame'] or frame_idx > l['end_frame']:
                        continue
                    # Font: try custom font via temporary path? If font_field is provided, it refers to a file saved by Flask in temp upload dir.
                    font_size = int(l.get('font_size', 24))
                    if l.get('font_path') and os.path.exists(l['font_path']):
                        try:
                            font = ImageFont.truetype(l['font_path'], font_size)
                        except Exception:
                            font = load_font(l.get('font_family', 'Arial'), font_size)
                    else:
                        font = load_font(l.get('font_family', 'Arial'), font_size)
                    max_width = int(frame_img.width * float(l.get('max_width_ratio', 0.95)))
                    lines = wrap_text(draw, l.get('text', ''), font, max_width)
                    ascent, descent = font.getmetrics()
                    base_line_h = ascent + descent + 2
                    line_height = max(10, int(base_line_h * float(l.get('line_height', 1.2))))
                    block_w = max((draw.textlength(line, font=font) for line in lines), default=0)
                    block_h = max(1, len(lines)) * line_height
                    # auto-fit: shrink font if too tall
                    if l.get('auto_fit', True):
                        guard = 0
                        while block_h > frame_img.height * 0.95 and font_size > 8 and guard < 50:
                            font_size = max(8, int(font_size * 0.9))
                            if l.get('font_path') and os.path.exists(l['font_path']):
                                try:
                                    font = ImageFont.truetype(l['font_path'], font_size)
                                except Exception:
                                    font = load_font(l.get('font_family', 'Arial'), font_size)
                            else:
                                font = load_font(l.get('font_family', 'Arial'), font_size)
                            ascent, descent = font.getmetrics()
                            line_height = max(10, int((ascent + descent + 2) * float(l.get('line_height', 1.2))))
                            lines = wrap_text(draw, l.get('text', ''), font, max_width)
                            block_w = max((draw.textlength(line, font=font) for line in lines), default=0)
                            block_h = max(1, len(lines)) * line_height
                            guard += 1
                    pos = calculate_position(frame_img.width, frame_img.height, block_w, block_h,
                                              l.get('horizontal_align', 'center'), l.get('vertical_align', 'middle'),
                                              int(l.get('offset_x', 0)), int(l.get('offset_y', 0)))
                    apply_animation(draw, lines, pos, font, l['color'], l['stroke_color'], int(l.get('stroke_width', 0)),
                                    l.get('animation_style', 'none'), frame_idx, int(l['start_frame']), int(l['end_frame']), line_height)
                frames.append(frame_img.convert('RGB'))
        else:
            frame_img = gif.convert('RGBA')
            if scale < 1.0:
                new_size = (max(1, int(frame_img.width * scale)), max(1, int(frame_img.height * scale)))
                frame_img = frame_img.resize(new_size, Image.Resampling.LANCZOS)
            draw = ImageDraw.Draw(frame_img)
            for l in normalized_layers:
                font_size = int(l.get('font_size', 24))
                if l.get('font_path') and os.path.exists(l['font_path']):
                    try:
                        font = ImageFont.truetype(l['font_path'], font_size)
                    except Exception:
                        font = load_font(l.get('font_family', 'Arial'), font_size)
                else:
                    font = load_font(l.get('font_family', 'Arial'), font_size)
                max_width = int(frame_img.width * float(l.get('max_width_ratio', 0.95)))
                lines = wrap_text(draw, l.get('text', ''), font, max_width)
                ascent, descent = font.getmetrics()
                base_line_h = ascent + descent + 2
                line_height = max(10, int(base_line_h * float(l.get('line_height', 1.2))))
                block_w = max((draw.textlength(line, font=font) for line in lines), default=0)
                block_h = max(1, len(lines)) * line_height
                if l.get('auto_fit', True):
                    guard = 0
                    while block_h > frame_img.height * 0.95 and font_size > 8 and guard < 50:
                        font_size = max(8, int(font_size * 0.9))
                        if l.get('font_path') and os.path.exists(l['font_path']):
                            try:
                                font = ImageFont.truetype(l['font_path'], font_size)
                            except Exception:
                                font = load_font(l.get('font_family', 'Arial'), font_size)
                        else:
                            font = load_font(l.get('font_family', 'Arial'), font_size)
                        ascent, descent = font.getmetrics()
                        line_height = max(10, int((ascent + descent + 2) * float(l.get('line_height', 1.2))))
                        lines = wrap_text(draw, l.get('text', ''), font, max_width)
                        block_w = max((draw.textlength(line, font=font) for line in lines), default=0)
                        block_h = max(1, len(lines)) * line_height
                        guard += 1
                pos = calculate_position(frame_img.width, frame_img.height, block_w, block_h,
                                          l.get('horizontal_align', 'center'), l.get('vertical_align', 'middle'),
                                          int(l.get('offset_x', 0)), int(l.get('offset_y', 0)))
                draw_text_block(draw, lines, pos, font, l['color'], l['stroke_color'], int(l.get('stroke_width', 0)), line_height)
            frames.append(frame_img.convert('RGB'))

        output_path = os.path.join(output_dir, f"text_layers_{uuid.uuid4().hex}.gif")
        frames[0].save(
            output_path,
            save_all=True,
            append_images=frames[1:] if len(frames) > 1 else [],
            duration=gif.info.get("duration", 100),
            loop=gif.info.get("loop", 0)
        )

        if os.path.exists(output_path):
            logging.info(f"[add_text_layers_to_gif_task] Output GIF created: {output_path}, size: {os.path.getsize(output_path)} bytes")
        else:
            logging.error(f"[add_text_layers_to_gif_task] Output GIF was not created: {output_path}")
            raise Exception("Output GIF was not created.")
        rel = os.path.relpath(output_path, upload_folder)
        # Record metrics (best-effort)
        try:
            out_size = os.path.getsize(output_path)
            peak_kb = getattr(resource.getrusage(resource.RUSAGE_SELF), 'ru_maxrss', 0)
            proc_ms = int((time.time() - _task_start) * 1000)
            jm = JobMetric(
                tool='add-text-layers',
                task_id=self.request.id if getattr(self, 'request', None) else None,
                status='SUCCESS',
                input_type='gif',
                input_width=base_w,
                input_height=base_h,
                input_frames=getattr(gif, 'n_frames', 1),
                input_size_bytes=os.path.getsize(abs_gif_path) if os.path.exists(abs_gif_path) else None,
                output_size_bytes=out_size,
                processing_time_ms=proc_ms,
                options=f"layers={len(layers)}; peak_kb={peak_kb}"
            )
            flask_app = get_flask_app()
            if flask_app:
                with flask_app.app_context():
                    db.session.add(jm)
                    db.session.commit()
            else:
                db.session.add(jm)
                db.session.commit()
        except Exception as _me:
            logging.warning(f"[metrics] add-text-layers save failed: {_me}")
        return rel
    except Exception as e:
        logging.error(f"Error in add_text_layers_to_gif_task: {e}", exc_info=True)
        try:
            jm = JobMetric(
                tool='add-text-layers',
                task_id=self.request.id if getattr(self, 'request', None) else None,
                status='FAILURE',
                error_message=str(e),
                processing_time_ms=int((time.time() - _task_start) * 1000)
            )
            flask_app = get_flask_app()
            if flask_app:
                with flask_app.app_context():
                    db.session.add(jm)
                    db.session.commit()
            else:
                db.session.add(jm)
                db.session.commit()
        except Exception:
            pass
        raise
    finally:
        try:
            if os.path.exists(abs_gif_path):
                os.remove(abs_gif_path)
        except Exception as e:
            logging.warning(f"Error deleting input GIF file {abs_gif_path}: {e}")

@celery_app.task(bind=True)
def handle_upload_task(self, url, output_dir, upload_folder, max_content_length):
    try:
        logging.info(f"[handle_upload_task] url={url}, output_dir={output_dir}, upload_folder={upload_folder}, max_content_length={max_content_length}")
        video_path = download_file_from_url_task_helper(url, output_dir, max_content_length)
        if os.path.exists(video_path):
            logging.info(f"[handle_upload_task] Downloaded file: {video_path}, size: {os.path.getsize(video_path)} bytes")
            import mimetypes
            mime_type, _ = mimetypes.guess_type(video_path)
            logging.info(f"[handle_upload_task] Detected mime type: {mime_type}")
        else:
            logging.error(f"[handle_upload_task] Downloaded file does not exist: {video_path}")
            raise FileNotFoundError(f"Downloaded file does not exist: {video_path}")
        # For handle_upload, we just need to return the path to the downloaded file
        # The frontend will then request this file via a separate endpoint.
        return video_path  # Return absolute path instead of relative path
    except Exception as e:
        logging.error(f"Error in handle_upload_task: {e}", exc_info=True)
        # Let Celery handle the failure state. Re-raise the exception.
        raise e
    finally:
        # The output_dir is the temp_dir created for this specific download.
        # It should be cleaned up after the file is served or processed further.
        # For now, we'll let the main cleanup task handle it, or a subsequent task
        # that uses this file will clean it up.
        pass

# Celery task wrapper for downloading a file from URL
@celery_app.task
def download_file_from_url_task(url, temp_dir, max_size):
    # This task is specifically for orchestrate_gif_from_urls_task
    # It passes the shared temp_dir to the helper.
    result = download_file_from_url_task_helper(url, temp_dir, max_size)
    logging.info(f"[download_file_from_url_task] Downloaded file: {result}")
    return result
