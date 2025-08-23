
from flask import Blueprint, request, jsonify, current_app
import os
import ast
from src.main import admin_required

seo_bp = Blueprint('seo_bp', __name__)

def update_seo_pages_file(new_page_data):
    seo_file_path = os.path.join(current_app.root_path, 'seo_pages.py')
    
    with open(seo_file_path, 'r') as f:
        content = f.read()

    tree = ast.parse(content)

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'seo_pages':
            seo_pages_node = node
            break
    else:
        raise RuntimeError("Could not find seo_pages list in the AST!")

    new_page_node = ast.parse(repr(new_page_data)).body[0].value
    seo_pages_node.value.elts.append(new_page_node)

    new_content = ast.unparse(tree)

    with open(seo_file_path, 'w') as f:
        f.write(new_content)

@seo_bp.route('/pages', methods=['POST'])
@admin_required
def add_seo_page():
    """
    Adds a new SEO page and submits it to IndexNow.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    # Basic validation
    required_fields = ['slug', 'title', 'description', 'keywords', 'category', 'h1']
    if not all(field in data for field in required_fields):
        return jsonify({"error": f"Missing required fields: {required_fields}"}), 400

    page_data = {
        "slug": data['slug'],
        "title": data['title'],
        "description": data['description'],
        "keywords": data['keywords'],
        "template": data.get('template', 'seo_template.html'),
        "category": data['category'],
        "h1": data['h1'],
        "content_sections": data.get('content_sections', []),
        "faqs": data.get('faqs', [])
    }

    try:
        update_seo_pages_file(page_data)
        url = f"https://easygifmaker.com/{page_data['category']}/{page_data['slug']}"
        
        return jsonify({"success": True, "message": "Page added successfully.", "url": url}), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500