#!/usr/bin/env python3
"""
Helper script to add new SEO pages to the system.
Usage: python add_seo_page.py
"""

import json
import sys
import os

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
    
    # Find the seo_pages list
    start_marker = "seo_pages = ["
    end_marker = "]"
    
    start_idx = content.find(start_marker)
    if start_idx == -1:
        print("Error: Could not find seo_pages list!")
        return
    
    # Find the end of the list
    list_start = start_idx + len(start_marker)
    brace_count = 1
    end_idx = list_start
    
    for i, char in enumerate(content[list_start:], list_start):
        if char == '[':
            brace_count += 1
        elif char == ']':
            brace_count -= 1
            if brace_count == 0:
                end_idx = i
                break
    
    # Format the new page data
    page_str = f"""    {{
        "slug": "{slug}",
        "title": "{title}",
        "description": "{description}",
        "keywords": "{keywords}",
        "template": "seo_template.html",
        "category": "{category}",
        "h1": "{h1}",
        "content_sections": [
"""
    
    for section in content_sections:
        page_str += f"""            {{
                "title": "{section['title']}",
                "content": "{section['content']}"
            }},
"""
    
    page_str += "        ],\n        \"faqs\": [\n"
    
    for faq in faqs:
        page_str += f"""            {{
                "question": "{faq['question']}",
                "answer": "{faq['answer']}"
            }},
"""
    
    page_str += "        ]\n    }"
    
    # Insert the new page
    new_content = content[:end_idx] + ",\n" + page_str + content[end_idx:]
    
    # Write back to file
    with open(seo_file, 'w') as f:
        f.write(new_content)
    
    print(f"\n✅ Successfully added SEO page: {category}/{slug}")
    print(f"URL: https://easygifmaker.com/{category}/{slug}")
    print("\nThe page will be automatically included in the sitemap.")

if __name__ == "__main__":
    add_seo_page() 