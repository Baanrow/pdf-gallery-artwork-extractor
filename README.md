# 🖼️ PDF Gallery Artwork Extractor

Modular Python utility to extract structured artwork data and images from art gallery PDFs using PyMuPDF. It intelligently filters pages, parses common layout patterns, and outputs cleaned metadata to JSON — with optional base64-encoded image snippets.

This tool is ideal for digitizing gallery catalogs or building searchable art databases.

---

## 📄 What It Does

- Scans a folder of PDF files and iterates through pages
- Identifies artwork pages using regex and layout heuristics
- Extracts metadata like title, artist, year, medium, and dimensions
- Optionally saves artwork images (largest on page) and encodes to base64
- Outputs structured JSON with image paths and confidence scoring

---

## 📁 File Structure

| File / Folder              | Purpose                                                    |
|---------------------------|------------------------------------------------------------|
| `pdf_to_supabase_extractor.py` | Main script that processes gallery PDFs                   |
| `state_db/art_pdf/`       | Source PDFs for processing                                  |
| `state_db/art_json/`      | Output folder for JSON files                                |
| `state_db/art_images/`    | Folder where extracted artwork images are saved             |

---

## 🔧 Tools & Technologies

- **PyMuPDF (`pymupdf`)** – PDF parsing and image extraction
- **Regex** – For matching artwork attributes (e.g., dimensions, year, price)
- **Base64** – For embedding image previews in JSON
- **Pathlib / Dataclasses** – Clean I/O handling and structured output

---

## 🚀 Example Use Case

> A gallery curator wants to digitize exhibition catalogs, extract metadata like title and medium, and upload images to a Supabase or internal CMS.

This script will:
1. Parse each PDF page
2. Detect and extract relevant metadata
3. Save artwork data to JSON (with image preview included)
4. Skip artist bio or text-heavy pages automatically

---

## 🧩 Notes

- The script is designed to handle **multiple layout styles** (line breaks, inline separators).
- Each artwork record receives a **confidence score** based on the fields found.
- Image data is trimmed in JSON to prevent large files — adjust if full output is needed.
- Built-in filtering ensures robustness across varied catalogs or page structures.

---

## 👤 About

Created by Brett C.  
I develop modular Python automation pipelines that handle real-world document processing, metadata extraction, and scalable backend integrations. This project reflects a reusable structure designed to digitize rich visual and textual content from domain-specific sources like gallery catalogs or educational records.
