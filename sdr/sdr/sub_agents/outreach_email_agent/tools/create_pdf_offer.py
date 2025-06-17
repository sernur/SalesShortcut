import markdown
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML, CSS
import os
import asyncio
import logging
from google.adk.tools import FunctionTool, ToolContext


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def _create_offer_file(refined_requirements: str) -> str:
    """Create a PDF commercial offer file based on `refined_requirements` Markdown.
    Applies the SalesShortcut UI theme using a page-template for background and header.

    Args:
        refined_requirements (str): The refined requirements in Markdown format.
    Returns:
        str: The file path of the created PDF offer file.
    """
    logger.info("Starting PDF generation process.")

    # Determine base directory for temporary files
    current_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
    logger.debug(f"Current working directory: {current_dir}")

    # File names for temporary files
    main_css_name = "styles.css"
    page_template_css_name = "page_template_styles.css"
    main_html_template_name = "offer_template.html"
    page_html_template_name = "page_background_template.html"
    output_pdf_file = "SalesShortcut_Proposal.pdf"

    # Full paths for temporary files
    main_css_path = os.path.join(current_dir, main_css_name)
    page_template_css_path = os.path.join(current_dir, page_template_css_name)
    main_html_template_path = os.path.join(current_dir, main_html_template_name)
    page_html_template_path = os.path.join(current_dir, page_html_template_name)
    output_pdf_path = os.path.abspath(os.path.join(current_dir, output_pdf_file))

    temp_files = [main_css_path, page_template_css_path, main_html_template_path, page_html_template_path]

    try:
        # --- Inline Main CSS Content (for the content card) ---
        main_css_content = f"""
/* Google Fonts Import */
@import url('https://fonts.com/css2?family=Inter:wght@300;400;500;600;700&family=Roboto:wght@300;400;500;700&display=swap');
@import url('https://com/css2?family=Roboto+Mono&display=swap'); /* For code blocks */

/* Design Tokens (Variables) */
:root {{
    --primary-color: #2563eb;
    --primary-dark: #1d4ed8;
    --secondary-color: #10b981;
    --accent-color: #f59e0b;
    --danger-color: #ef4444;
    --warning-color: #f97316;
    --success-color: #10b981;
    
    --gray-50: #f9fafb;
    --gray-100: #f3f4f6;
    --gray-200: #e5e7eb;
    --gray-300: #d1d5db;
    --gray-400: #9ca3af;
    --gray-500: #6b7280;
    --gray-600: #4b5563;
    --gray-700: #374151;
    --gray-800: #1f2937;
    --gray-900: #111827;
    
    --border-radius: 8px;
    --border-radius-lg: 12px;
    --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
    --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
    --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
    --shadow-xl: 0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1);
    
    --font-family-body: 'Roboto', sans-serif;
    --font-family-heading: 'Inter', sans-serif;
    --font-mono: 'Roboto Mono', monospace;
}}

/* WeasyPrint Page Rules for the main document flow */
@page {{
    size: A4;
    margin: 0; /* Important: No margin on the main document flow, content card will handle spacing */
    
    /* Reference the page template for background and repeating header/footer */
    @top-left {{ content: url('{os.path.basename(page_html_template_path)}'); }}
}}

* {{
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}}

body {{
    font-family: var(--font-family-body);
    line-height: 1.6;
    color: var(--gray-900);
    /* Body has no background here, as it's handled by the page-template */
}}

/* Main Content Card - mimicking .main-card from screenshot */
.pdf-wrapper {{
    background: white;
    border-radius: var(--border-radius-lg);
    box-shadow: var(--shadow-xl);
    overflow: hidden; /* For rounded corners and shadow */
    width: 100%;
    max-width: 700px; /* Width of the content card */
    margin: 4cm auto 2cm; /* Top margin for banner, auto for horizontal centering, bottom margin */
    padding: 2rem; /* Internal padding for card content */
    box-sizing: border-box; /* Ensure padding is within width */
    
    /* Allow the content inside the card to break across pages */
    page-break-inside: auto; 
}}

/* Markdown Element Styling within the Card */
h1 {{ /* Section headings like "0 · Purpose of This Document" */
    font-family: var(--font-family-heading);
    font-size: 1.6rem; 
    font-weight: 600;
    color: var(--primary-color);
    margin-top: 1.5rem; /* Space above each new section heading */
    margin-bottom: 0.8rem;
    page-break-after: avoid; /* Keep heading with its content */
}}

h2 {{ /* Sub-section headings like "1 · Business & Website Goals" */
    font-family: var(--font-family-heading);
    font-size: 1.4rem; 
    font-weight: 600;
    color: var(--primary-color);
    margin-top: 1.2rem;
    margin-bottom: 0.6rem;
    page-break-after: avoid;
}}

h3 {{
    font-family: var(--font-family-heading);
    font-size: 1.15rem; 
    font-weight: 600;
    color: var(--gray-900);
    margin-top: 1rem;
    margin-bottom: 0.5rem;
    page-break-after: avoid;
}}

h4, h5, h6 {{
    font-family: var(--font-family-heading);
    color: var(--gray-800);
    margin-top: 0.8rem;
    margin-bottom: 0.4rem;
    page-break-after: avoid;
}}

p {{
    font-family: var(--font-family-body);
    font-size: 0.95rem; /* Standard body text size */
    color: var(--gray-700);
    margin-bottom: 0.8rem;
    line-height: 1.6;
}}

a {{
    color: var(--primary-color);
    text-decoration: none;
}}

a:hover {{
    text-decoration: underline;
}}

strong {{
    font-weight: 700;
    color: var(--gray-900);
}}

em {{
    font-style: italic;
    color: var(--gray-600);
}}

ul, ol {{
    margin-bottom: 0.8rem;
    padding-left: 1.2rem;
    color: var(--gray-700);
}}

li {{
    margin-bottom: 0.4rem;
}}

table {{
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 1rem;
    page-break-inside: auto; /* Allows tables to break across pages if too long */
    border-radius: var(--border-radius);
    overflow: hidden; /* Ensures border-radius applies to table content */
    border: 1px solid var(--gray-200); /* Outer border for the table */
}}

table thead {{
    display: table-header-group; /* Ensures table headers repeat on new pages */
}}

th, td {{
    border: 1px solid var(--gray-200);
    padding: 0.6rem 0.8rem; /* Padding within table cells */
    text-align: left;
    font-family: var(--font-family-body);
    font-size: 0.9rem; /* Font size for table text */
}}

th {{
    background-color: var(--gray-100);
    font-weight: 600;
    color: var(--gray-700);
    border-bottom: 2px solid var(--gray-300); /* Stronger separator for header */
}}

/* Blockquote style similar to .process-info in the original CSS */
blockquote {{
    background: var(--gray-50);
    border-radius: var(--border-radius);
    padding: 1rem;
    margin: 1rem 0;
    border-left: 4px solid var(--primary-color); /* Primary color for border */
    color: var(--gray-700);
    font-style: normal; /* Override default markdown italic for blockquotes */
    line-height: 1.6;
}}

blockquote p {{
    margin-bottom: 0; /* Remove extra margin inside blockquote paragraphs */
    font-size: 0.95rem;
    color: var(--gray-700);
}}

hr {{
    border: none;
    border-top: 1px solid var(--gray-200);
    margin: 1.5rem 0;
}}

pre, code {{
    font-family: var(--font-mono);
    background-color: var(--gray-100);
    padding: 0.2em 0.4em;
    border-radius: 4px;
    font-size: 0.85em; /* Font size for inline code */
    color: var(--gray-800);
}}

pre {{ /* Styling for fenced code blocks */
    display: block;
    padding: 0.8em;
    margin: 0.8em 0;
    overflow-x: auto; /* Allows horizontal scrolling for long lines */
    border-radius: var(--border-radius);
    border: 1px solid var(--gray-200);
}}

img {{
    max-width: 100%;
    height: auto;
    display: block;
    margin: 0.8rem auto;
    border-radius: var(--border-radius);
}}

/* Ensure bold/italic styles in tables or other blocks inherit color */
table strong, table em,
blockquote strong, blockquote em {{
    color: inherit; 
}}
"""
        # --- Inline CSS for the Page Template (background and top banner) ---
        page_template_css_content = """
/* Google Fonts Import for the page template */
@import url('https://fonts.com/css2?family=Inter:wght@300;400;500;600;700&family=Roboto:wght@300;400;500;700&display=swap');

/* Design Tokens (Variables) - Must be redefined for page template's scope */
:root {
    --primary-color: #2563eb;
    --primary-dark: #1d4ed8;
    --accent-color: #f59e0b;
    --gray-600: #4b5563;
    --gray-900: #111827;
    --font-family-body: 'Roboto', sans-serif;
    --font-family-heading: 'Inter', sans-serif;
}

html, body {
    margin: 0;
    padding: 0;
    height: 100%;
    width: 100%;
    overflow: hidden; /* Prevent scrollbars on the page template */
    position: relative; /* For absolute positioning of elements inside */
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); /* Full page gradient */
}

/* Page Header - SalesShortcut logo and main proposal text */
.page-header {
    position: absolute;
    top: 2cm; /* Matches @page margin from main document */
    left: 50%;
    transform: translateX(-50%);
    width: 100%; /* Spans the width for centering */
    max-width: 700px; /* Align with the main content card width */
    text-align: center;
    color: white; /* White text on gradient background */
}

.page-header .logo-text {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
}

.page-header .logo-text .icon {
    font-size: 2.5rem; /* Slightly larger icon */
    color: var(--accent-color);
}

.page-header .logo-text h1 {
    font-family: var(--font-family-heading);
    font-size: 2.5rem; /* Larger main title */
    font-weight: 700;
    color: white; /* Solid white for main title on gradient */
}

.page-header .subtitle-text {
    font-family: var(--font-family-body);
    font-size: 1.1rem; /* Slightly larger subtitle */
    opacity: 0.9;
    font-weight: 300;
    color: rgba(255, 255, 255, 0.9); /* Slightly transparent white */
}

/* Page Footer - Page numbers */
.page-footer {
    position: absolute;
    bottom: 1cm; /* Adjust as needed from bottom */
    left: 0;
    width: 100%;
    text-align: center;
    font-family: var(--font-family-body);
    font-size: 9pt;
    color: var(--gray-600);
}
"""

        # --- Inline Main HTML Template Content (for the main document flow) ---
        main_html_template_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SalesShortcut Proposal</title>
    <link rel="stylesheet" href="{main_css_name}">
</head>
<body>
    <div class="pdf-wrapper">
        <main>
            {{{{ content | safe }}}}
        </main>
    </div>
</body>
</html>
"""

        logger.info("Converting Markdown to HTML.")
        html_content = markdown.markdown(refined_requirements, extensions=['tables', 'fenced_code'])

        # Simple extraction for the main title and subtitle from the markdown offer
        document_main_title = "AI-Powered Lead Generation & Management Proposal"
        document_main_subtitle = "Prepared by BrightWeb Studio"
        
        lines = refined_requirements.split('\n')
        if lines:
            # Extract content of the first H1
            if lines[0].strip().startswith('#'):
                document_main_title = lines[0].strip('# ').strip()
            # Find the first italicized line after the H1
            for i in range(1, min(len(lines), 3)): # Check first few lines for the subtitle
                line = lines[i].strip()
                if line.startswith('*') and line.endswith('*') and len(line) > 2:
                    document_main_subtitle = line.strip('*').strip()
                    break # Found the subtitle, stop searching
        logger.info(f"Extracted document title: '{document_main_title}', subtitle: '{document_main_subtitle}'")

        # --- Inline Page Background HTML Template Content ---
        page_html_template_content_final = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Page Template</title>
    <link rel="stylesheet" href="{os.path.basename(page_template_css_path)}">
</head>
<body>
    <div class="page-header">
        <div class="logo-text">
            <span class="icon">&#x1F680;</span> <h1>SalesShortcut</h1>
        </div>
        <p class="subtitle-text">{document_main_title}<br><em>{document_main_subtitle}</em></p>
    </div>
    <div class="page-footer">
        <span></span> / <span></span> 
    </div>
</body>
</html>
"""
        
        logger.info("Writing temporary CSS and HTML files.")
        # Write temporary CSS files
        with open(main_css_path, "w", encoding="utf-8") as f:
            f.write(main_css_content)
            logger.debug(f"Written main CSS to {main_css_path}")
        with open(page_template_css_path, "w", encoding="utf-8") as f:
            f.write(page_template_css_content)
            logger.debug(f"Written page template CSS to {page_template_css_path}")

        # Write temporary HTML templates
        with open(main_html_template_path, "w", encoding="utf-8") as f:
            f.write(main_html_template_content)
            logger.debug(f"Written main HTML template to {main_html_template_path}")
        
        with open(page_html_template_path, "w", encoding="utf-8") as f:
            f.write(page_html_template_content_final)
            logger.debug(f"Written page background HTML template to {page_html_template_path}")

        env = Environment(loader=FileSystemLoader(current_dir))
        main_template = env.get_template(main_html_template_name)
        
        logger.info("Rendering main HTML template with Markdown content.")
        rendered_main_html = main_template.render(content=html_content)

        logger.info(f"Generating PDF: {output_pdf_path}")
        # Load the main CSS file
        main_css = CSS(filename=main_css_path, base_url=current_dir)
        
        # WeasyPrint will automatically load the page-template HTML and its associated CSS
        # when it encounters the @top-left rule in main_css.
        HTML(string=rendered_main_html, base_url=current_dir).write_pdf(output_pdf_path, stylesheets=[main_css])
        
        logger.info(f"PDF successfully created at: {output_pdf_path}")
        return output_pdf_path

    except FileNotFoundError as e:
        logger.error(f"File not found error during PDF generation: {e}")
        raise
    except Exception as e:
        logger.exception(f"An unexpected error occurred during PDF generation: {e}")
        raise
    finally:
        logger.info("Cleaning up temporary files.")
        for f_path in temp_files:
            if os.path.exists(f_path):
                try:
                    os.remove(f_path)
                    logger.debug(f"Removed temporary file: {f_path}")
                except OSError as e:
                    logger.warning(f"Could not remove temporary file {f_path}: {e}")
                    
                    
                    
create_offer_file = FunctionTool(func=_create_offer_file)