import re

with open('/home/son/Production/litserve/README.md', 'r') as f:
    content = f.read()

# Pattern to match the old section
pattern = r'(5\. \\*\\*Test the Service\\*\\*\\s+\\*\\*For regular video upscaling \\(file upload\\):\\*\\*.*?\\*\\*For anime video upscaling \\(URL download\\):\\*\\*.*?```bash.*?isAnime=true.*?```)'

# New content to replace with
replacement = '''5. **Test the Service**
  
  **Using form data (file upload):**
  ```bash
  curl -X POST http://localhost:8866/upscale \\\\
    -F "file=@your_video.mp4" \\\\
    -F "scale=3"
  ```
  
  **Using form data (URL download):**
  ```bash
  curl -X POST http://localhost:8866/upscale \\\\
    -F "url=https://example.com/your_video.mp4" \\\\
    -F "scale=3"
  ```
  
  **Using form data (anime video upscaling):**
  ```bash
  curl -X POST http://localhost:8866/upscale \\\\
    -F "file=@anime_video.mp4" \\\\
    -F "scale=4" \\\\
    -F "isAnime=true"
  ```
  
  **Using JSON payload (URL download):**
  ```bash
  curl -X POST http://localhost:8866/upscale-json \\\\
    -H "Content-Type: application/json" \\\\
    -d '{"url": "https://example.com/your_video.mp4", "scale": 3}'
  ```
  
  **Using JSON payload with file upload:**
  ```bash
  curl -X POST http://localhost:8866/upscale-json \\\\
    -H "Content-Type: application/json" \\\\
    -F "file=@your_video.mp4" \\\\
    -d '{"scale": 3, "isAnime": false, "urlOutput": false}'
  ```'''

# Replace the content
updated_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

with open('/home/son/Production/litserve/README.md', 'w') as f:
    f.write(updated_content)