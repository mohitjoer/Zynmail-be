import re

def sanitize_email_html(html_content: str) -> str:
    if not html_content:
        return ""
    
    # Strip <script> blocks completely
    html_content = re.sub(r'<script\b[^>]*>.*?</script>', '', html_content, flags=re.IGNORECASE | re.DOTALL)
    
    # Strip inline event handlers (e.g. onclick="...")
    html_content = re.sub(r'\bon[a-z]+\s*=\s*(["\']).*?\1', '', html_content, flags=re.IGNORECASE)
    
    # Return the raw HTML (minus scripts). 
    # The frontend MUST use an <iframe sandbox="..."> to render this securely.
    return html_content
