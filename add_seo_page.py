#!/usr/bin/env python3
"""
Helper script to add new SEO pages to the system.
Usage: python add_seo_page.py
"""

import json
import sys
import os
import ast

def add_seo_page():
    print("=== EasyGIFMaker SEO Page Generator ===\n")
    
    # Get page details
    slug = input("Enter slug (e.g., 'mp4-to-gif'): ").strip()
    if not slug:
        print("Slug is required!")
        return
    
    category = input("Enter category (convert/features/optimize/tools): ").strip()
    if category not in ['convert', 'features', 'optimize', 'tools']:
        print("Invalid category!")
        return
    
    title = input("Enter page title: ").strip()
    if not title:
        print("Title is required!")
        return
    
    description = input("Enter meta description: ").strip()
    if not description:
        print("Description is required!")
        return
    
    keywords = input("Enter keywords (comma-separated): ").strip()
    if not keywords:
        print("Keywords are required!")
        return
    
    h1 = input("Enter H1 heading: ").strip()
    if not h1:
        h1 = title
    
    # Get content sections
    print("\n=== Content Sections ===")
    content_sections = []
    while True:
        section_title = input("Enter section title (or press Enter to finish): ").strip()
        if not section_title:
            break
        
        section_content = input("Enter section content: ").strip()
        if section_content:
            content_sections.append({
                "title": section_title,
                "content": section_content
            })
    
    # Get FAQs
    print("\n=== FAQs ===")
    faqs = []
    while True:
        question = input("Enter FAQ question (or press Enter to finish): ").strip()
        if not question:
            break
        
        answer = input("Enter FAQ answer: ").strip()
        if answer:
            faqs.append({
                "question": question,
                "answer": answer
            })
    
    # Create the page data
    page_data = {
        "slug": slug,
        "title": title,
        "description": description,
        "keywords": keywords,
        "template": "seo_template.html",
        "category": category,
        "h1": h1,
        "content_sections": content_sections,
        "faqs": faqs
    }
    
    # Read existing seo_pages.py
    seo_file = "src/seo_pages.py"
    if not os.path.exists(seo_file):
        print(f"Error: {seo_file} not found!")
        return
    
    with open(seo_file, 'r') as f:
        content = f.read()

    # Parse the file content to find the seo_pages list
    tree = ast.parse(content)
    
    # Find the seo_pages assignment
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'seo_pages':
            seo_pages_node = node
            break
    else:
        print("Error: Could not find seo_pages list in the AST!")
        return

    # Convert the new page data to an AST node
    new_page_node = ast.parse(repr(page_data)).body[0].value

    # Append the new page to the list
    seo_pages_node.value.elts.append(new_page_node)

    # Unparse the AST back to code
    new_content = ast.unparse(tree)

    # Write back to file
    with open(seo_file, 'w') as f:
        f.write(new_content)
    
    print(f"\n✅ Successfully added SEO page: {category}/{slug}")
    url = f"https://easygifmaker.com/{category}/{slug}"
    print(f"URL: {url}")
    print("\nThe page will be automatically included in the sitemap.")

if __name__ == "__main__":
    add_seo_page()