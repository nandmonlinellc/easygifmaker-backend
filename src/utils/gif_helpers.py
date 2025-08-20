import os
import uuid
import base64
import logging
from typing import List, Dict, Optional, Tuple

import requests
from werkzeug.utils import secure_filename
from PIL import Image

from src.tasks import add_text_layers_to_gif_task

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "bmp", "webp", "apng", "heic", "heif", "mng", "jp2", "avif", "jxl", "pdf"}
ALLOWED_VIDEO_EXTENSIONS = {"mp4", "avi", "mov", "webm", "mkv", "flv"}


def allowed_file(filename: str, allowed_extensions: set) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


def create_session_dir(upload_folder: str) -> str:
    user_uploads_dir = os.path.join(upload_folder, "user_uploads")
    os.makedirs(user_uploads_dir, exist_ok=True)
    session_dir = os.path.join(user_uploads_dir, str(uuid.uuid4()))
    os.makedirs(session_dir, exist_ok=True)
    return session_dir


def resolve_input_gif(*, url: Optional[str] = None, base64_data: Optional[str] = None,
                      file=None, temp_dir: str) -> str:
    """Return local GIF path from url, base64 string, or uploaded file."""
    if url:
        gif_temp_path = os.path.join(temp_dir, "temp_gif.gif")
        with requests.get(url, stream=True, timeout=30) as r:
            r.raise_for_status()
            with open(gif_temp_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        return gif_temp_path
    if base64_data:
        if base64_data.startswith('data:'):
            base64_data = base64_data.split(',', 1)[1]
        binary = base64.b64decode(base64_data)
        gif_temp_path = os.path.join(temp_dir, f"b64_{uuid.uuid4().hex}.gif")
        with open(gif_temp_path, 'wb') as f:
            f.write(binary)
        return gif_temp_path
    if file:
        gif_path = os.path.join(temp_dir, secure_filename(file.filename))
        file.save(gif_path)
        return gif_path
    raise ValueError("Provide either 'url', 'base64_data', or file")


def probe_gif(gif_path: str) -> Tuple[int, float]:
    with Image.open(gif_path) as gif_probe:
        n_frames = getattr(gif_probe, "n_frames", 1)
        duration_ms = gif_probe.info.get("duration", 100)
    fps = 1000.0 / duration_ms if duration_ms > 0 else 10
    return n_frames, fps


def extract_layers(data: Dict) -> List[Dict]:
    layers = data.get('layers')
    if not layers:
        layers = [{
            'text': data.get('text', ''),
            'font_family': data.get('font_family') or data.get('font') or 'Arial',
            'font_size': int(data.get('font_size', 24)),
            'color': data.get('color') or data.get('font_color', '#ffffff'),
            'stroke_color': data.get('stroke_color', '#000000'),
            'stroke_width': int(data.get('stroke_width', data.get('outline_width', 0))),
            'horizontal_align': data.get('horizontal_align') or ('center' if data.get('position') is None else ('left' if data.get('position') == 'top-left' else ('center' if 'center' in str(data.get('position')) else 'right'))),
            'vertical_align': data.get('vertical_align') or ('middle' if data.get('position') is None else ('top' if 'top' in str(data.get('position')) else ('bottom' if 'bottom' in str(data.get('position')) else 'middle'))),
            'offset_x': int(data.get('x_offset', data.get('offset_x', 0)) or 0),
            'offset_y': int(data.get('y_offset', data.get('offset_y', 0)) or 0),
            'start_time': float(data.get('start_time', 0) or 0),
            'end_time': data.get('end_time', None),
            'animation_style': data.get('animation_style', 'none'),
            'max_width_ratio': float(data.get('max_width_ratio', 0.95)),
            'line_height': float(data.get('line_height', 1.2)),
            'auto_fit': bool(data.get('auto_fit', True)),
        }]
    return layers


def prepare_layers(layers: List[Dict], fps: float, n_frames: int, temp_dir: str) -> List[Dict]:
    prepared_layers = []
    for idx, l in enumerate(layers):
        start_time = float(l.get('start_time', 0) or 0)
        end_time_val = l.get('end_time', None)
        if end_time_val not in (None, ''):
            end_frame = int(round(float(end_time_val) * fps))
        else:
            end_frame = n_frames - 1
        start_frame = int(round(start_time * fps))
        entry = {
            'text': l.get('text', ''),
            'font_family': l.get('font_family', 'Arial'),
            'font_size': int(l.get('font_size', 24)),
            'color': l.get('color', '#ffffff'),
            'stroke_color': l.get('stroke_color', '#000000'),
            'stroke_width': int(l.get('stroke_width', 0)),
            'horizontal_align': l.get('horizontal_align', 'center'),
            'vertical_align': l.get('vertical_align', 'middle'),
            'offset_x': int(l.get('offset_x', 0)),
            'offset_y': int(l.get('offset_y', 0)),
            'start_frame': start_frame,
            'end_frame': end_frame,
            'animation_style': l.get('animation_style', 'none'),
            'max_width_ratio': float(l.get('max_width_ratio', 0.95)),
            'line_height': float(l.get('line_height', 1.2)),
            'auto_fit': bool(l.get('auto_fit', True)),
        }
        font_url = l.get('font_url')
        if font_url:
            try:
                with requests.get(font_url, stream=True, timeout=20) as r:
                    r.raise_for_status()
                    fname = f"font_{idx}_{uuid.uuid4().hex}.ttf"
                    font_path = os.path.join(temp_dir, secure_filename(fname))
                    with open(font_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                    entry['font_path'] = font_path
            except Exception as fe:
                logging.warning(f"Failed to fetch font_url for layer {idx}: {fe}")
        prepared_layers.append(entry)
    return prepared_layers


def dispatch_add_text_layers_task(gif_path: str, prepared_layers: List[Dict], temp_dir: str, upload_folder: str):
    return add_text_layers_to_gif_task.apply_async([gif_path, prepared_layers, temp_dir, upload_folder], queue="fileops")


def resolve_video_input(url: Optional[str], file, session_dir: str, allowed_extensions: set, max_content_length: int) -> str:
    from src.tasks import download_file_from_url_task_helper
    if url:
        if any(domain in url for domain in ["youtube.com", "youtu.be", "dailymotion.com", "facebook.com", "tiktok.com", "twitter.com"]):
            raise ValueError("For copyright and security reasons, we do not support YouTube, Facebook, TikTok, Twitter, or similar links. Please upload a video file or provide a direct video file URL (ending in .mp4, .webm, etc.).")
        return download_file_from_url_task_helper(url, session_dir, max_content_length)
    if not file:
        raise ValueError("No file provided")
    if file.filename == "" or not allowed_file(file.filename, allowed_extensions):
        raise ValueError("Invalid video file")
    file_path = os.path.join(session_dir, secure_filename(file.filename))
    file.save(file_path)
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        raise ValueError(f"Failed to save uploaded video: {file.filename}. Please try again.")
    return file_path
