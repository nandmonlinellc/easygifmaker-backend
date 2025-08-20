import os
import base64
import tempfile
from PIL import Image

from src.utils.gif_helpers import resolve_input_gif, probe_gif, extract_layers, prepare_layers


def _create_base64_gif() -> str:
    with tempfile.NamedTemporaryFile(suffix=".gif", delete=False) as tmp:
        img = Image.new("RGB", (10, 10), color="red")
        img.save(tmp.name, format="GIF", duration=100, loop=0)
        tmp.seek(0)
        data = base64.b64encode(tmp.read()).decode("utf-8")
    os.unlink(tmp.name)
    return data


def test_resolve_input_gif_base64(tmp_path):
    b64 = _create_base64_gif()
    path = resolve_input_gif(base64_data=b64, temp_dir=str(tmp_path))
    assert os.path.exists(path)


def test_probe_gif(tmp_path):
    gif_path = os.path.join(tmp_path, "test.gif")
    img = Image.new("RGB", (10, 10), color="blue")
    img.save(gif_path, format="GIF", duration=100, loop=0)
    n_frames, fps = probe_gif(gif_path)
    assert n_frames == 1
    assert fps == 10


def test_extract_and_prepare_layers(tmp_path):
    data = {'text': 'hello'}
    layers = extract_layers(data)
    assert layers[0]['text'] == 'hello'
    prepared = prepare_layers(layers, fps=10, n_frames=10, temp_dir=str(tmp_path))
    assert prepared[0]['start_frame'] == 0
    assert prepared[0]['end_frame'] == 9
