import base64
from openai import OpenAI
import time
# 1. Setup Client
client = OpenAI(base_url="http://localhost:8001/v1", api_key="EMPTY")

# 2. Get correct model name
model_name = client.models.list().data[0].id

# 3. Function to encode a local image
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# REPLACE THIS with a path to a real jpg on your computer
local_image_path = "./test_image.png" 



# Only run if you have a file named test_image.jpg
try:
    base64_image = encode_image(local_image_path)
    
    start = time.time()

    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What is in this image?"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        },
                    },
                ],
            }
        ],
        max_tokens=50,
    )
    end = time.time()
    print(f"Time taken: {end - start} seconds")
    print(response.choices[0].message.content)

except FileNotFoundError:
    print("Please save a 'test_image.jpg' in this folder to test without Internet.")