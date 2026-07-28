import bleach
from bleach.css_sanitizer import CSSSanitizer
import re

ALLOWED_TAGS = [
    'a', 'abbr', 'acronym', 'b', 'blockquote', 'code',
    'em', 'i', 'li', 'ol', 'strong', 'ul',
    'p', 'div', 'span', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'table', 'tbody', 'thead', 'tfoot', 'tr', 'th', 'td', 'col', 'colgroup',
    'img', 'br', 'hr', 'pre', 'center', 'font', 'style'
]

ALLOWED_ATTRIBUTES = {
    '*': ['class', 'style', 'id', 'width', 'height', 'dir', 'lang', 'align', 'valign', 'bgcolor', 'color', 'cellpadding', 'cellspacing', 'border'],
    'a': ['href', 'title', 'target', 'rel'],
    'img': ['src', 'alt', 'title', 'width', 'height']
}

# Extensive list of CSS properties needed for emails
css_sanitizer = CSSSanitizer(allowed_css_properties=[
    'color', 'background-color', 'width', 'height', 'margin', 'padding', 'font-family', 
    'font-size', 'font-weight', 'text-align', 'border', 'border-radius', 'display',
    'line-height', 'text-decoration', 'box-sizing', 'max-width', 'min-width'
])

def sanitize_email_html(html_content: str) -> str:
    if not html_content:
        return ""
    
    # Strip <script> blocks completely so their inner text (like JSON-LD) isn't rendered
    html_content = re.sub(r'<script\b[^>]*>.*?</script>', '', html_content, flags=re.IGNORECASE | re.DOTALL)

    return bleach.clean(
        html_content,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        css_sanitizer=css_sanitizer,
        strip=True
    )
