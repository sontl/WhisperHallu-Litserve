# Read the README file
with open('/home/son/Production/litserve/README.md', 'r') as f:
    lines = f.readlines()

# Find the line with "Download the upscaled video:"
insert_index = None
for i, line in enumerate(lines):
    if "**Download the upscaled video:**" in line:
        insert_index = i
        break

# If we found the line, insert our new content before it
if insert_index is not None:
    new_content = [
        "  \n",
        "  **Using JSON payload (URL download):**\n",
        "  ```bash\n",
        "  curl -X POST http://localhost:8866/upscale-json \\\n",
        "    -H \"Content-Type: application/json\" \\\n",
        "    -d '{\"url\": \"https://example.com/your_video.mp4\", \"scale\": 3}'\n",
        "  ```\n",
        "  \n",
        "  **Using JSON payload with file upload:**\n",
        "  ```bash\n",
        "  curl -X POST http://localhost:8866/upscale-json \\\n",
        "    -H \"Content-Type: application/json\" \\\n",
        "    -F \"file=@your_video.mp4\" \\\n",
        "    -d '{\"scale\": 3, \"isAnime\": false, \"urlOutput\": false}'\n",
        "  ```\n",
        "  \n"
    ]
    
    # Insert the new content
    for i, content_line in enumerate(new_content):
        lines.insert(insert_index + i, content_line)
    
    # Write the updated content back to the file
    with open('/home/son/Production/litserve/README.md', 'w') as f:
        f.writelines(lines)
else:
    print("Could not find the insertion point in the README file")