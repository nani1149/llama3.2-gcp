from openai import AsyncOpenAI
import chainlit as cl
import openai
from google.auth import default, transport
from google.auth.transport import requests
import google.auth.transport.requests
import base64
from google.cloud import storage

MODEL_LOCATION = "us-central1"
MAAS_ENDPOINT = f"{MODEL_LOCATION}-aiplatform.googleapis.com"
credentials, _ = default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
auth_request = requests.Request()
credentials.refresh(auth_request)
PROJECT_ID="tribal-catfish-433217-f9"
LOCATION="us-central1"
BUCKET="ndonthi1-llm"

welcome_message = """Welcome to the Code generation tool from flow diagram! To get started:
                        1. Upload a image file
                        2. Ask for python code genration"""



def upload_blob(bucket_name, source_file_name, destination_blob_name):
    """Uploads a file to the bucket and returns the gs:// path."""
    # The ID of your GCS bucket
    # bucket_name = "your-bucket-name"
    # The path to your file to upload
    # source_file_name = "local/path/to/file"
    # The ID of your GCS object
    # destination_blob_name = "storage-object-name"

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    # Optional: set a generation-match precondition to avoid potential race conditions
    # and data corruptions.
    generation_match_precondition = 0

    blob.upload_from_filename(source_file_name)

    print(f"File {source_file_name} uploaded to {destination_blob_name}.")

    print(f"gs://{bucket_name}/{destination_blob_name}")
    return f"gs://{bucket_name}/{destination_blob_name}"



client = openai.OpenAI(
    base_url=f"https://{MAAS_ENDPOINT}/v1beta1/projects/{PROJECT_ID}/locations/{LOCATION}/endpoints/openapi",
    api_key=credentials.token,
)

# Instrument the OpenAI client
cl.instrument_openai()

settings = {
    "model": "meta/llama-3.2-90b-vision-instruct-maas",
    "temperature": 0,
    # ... more settings
}

def encode_image(image_path):
  with open(image_path, "rb") as image_file:
    return base64.b64encode(image_file.read()).decode('utf-8')

@cl.on_chat_start
async def start():

    res = await cl.AskActionMessage(
        content="Select a Vision Tool!",
        actions=[
            cl.Action(name="Car Damage Estimation", value="CDE"),
            cl.Action(name="Code Generation", value="CG"),
            cl.Action(name="Diet Suggestion Tool", value="DT"),
             cl.Action(name="Know Your Fridge", value="KYF"),
        ],
    ).send()
    select_prompt=""
    if res and res.get("value") == "CDE":
        select_prompt = f"""
                Analyze the provided image of a car and provide the following information:

                1. Damage Type: Identify the primary type of damage visible in the image (e.g., dent, scratch, cracked windshield, etc.).
                2. Severity: Estimate the severity of the damage on a scale of 1 to 5, where 1 is minor and 5 is severe.
                3. Estimated Repair Cost: Provide an approximate range for the repair cost in USD.   

                Return the results in JSON format with damagetype, severity, and cost fields.
                """ 
        welcome_message = """Welcome to the Car Damage Evaluation Tool! To get started:
                            1. Upload a image file
                            2. Ask Estimated damagage cost of the car
                            """  
    elif res and res.get("value") == "CG":
       select_prompt = f"""
                Summarize the flow of techinical diagram in text and then return a python script that implements the flow..
                """
       welcome_message = """Welcome to the Code generation tool from flow diagram! To get started:
                                1. Upload a image file
                                2. Ask for python code genration
"""  
    elif res and res.get("value") == "DT":
       select_prompt = f"""
                I am on a diet. Which drink should I drink?
                Generete nurtrition facts of the two drinks in JSON format for easy comparison.
                """
       welcome_message = """Welcome to the Diet Suggestion Tool! To get started:
                                1. Upload a image file
                                2. Ask for suggestion on diet plan based on the image of your meal
""" 
    elif res and res.get("value") == "KYF":
       select_prompt = f"""
                What're in the fridge? What kind of food can be made? Give me 2 examples, based on only the ingredients in the fridge.
                """
       welcome_message = """Welcome to the Diet Suggestion Tool! To get started:
                                1. Upload a image file
                                2. Ask for possible ingredients"""
       
    else:
       select_prompt=""    
       welcome_message = """Welcome to the Car Damage Evaluation Tool! To get started:
                            1. Upload a image file
                            2. Ask Estimated damagage cost of the car
                            """  
       
       
    
    files = None
    while files is None:
        files = await cl.AskFileMessage(
            content=welcome_message,
            accept=["image/jpeg","image/png"],
            max_size_mb=20,
            timeout=180,
        ).send()

    file = files[0]
    image = cl.Image(path=file.path, name="image1", display="inline")

    # Attach the image to the message
    await cl.Message(
        content="This message has an image!",
        elements=[image],
    ).send()

    msg = cl.Message(content=f"Processing `{file.name}`...")
    await msg.send()
    gcs_image_path = upload_blob(BUCKET, file.path, "image.jpg") # Process the file and get the download link
    
    cl.user_session.set("user_prompt", select_prompt)
    cl.user_session.set("gcs_image", gcs_image_path)




@cl.on_message
async def on_message(msg: cl.Message):
    max_tokens = 4096
    MODEL_ID = "meta/llama-3.2-90b-vision-instruct-maas" 

    gcs_image_path = cl.user_session.get("gcs_image")
    user_prompt = cl.user_session.get("user_prompt")

    #base64_image = encode_image(images[0].path)

    # Get the text content from the message if present
    message_text = msg.content if msg.content else "No text provided"
    context= cl.chat_context.to_openai()
    #conversation_context.append({"role": "user", "content": message_text})
    if user_prompt=="":
        prompt = f"""
        Analyze the provided image of a car and provide the following information:

        1. Damage Type: Identify the primary type of damage visible in the image (e.g., dent, scratch, cracked windshield, etc.).
        2. Severity: Estimate the severity of the damage on a scale of 1 to 5, where 1 is minor and 5 is severe.
        3. Estimated Repair Cost: Provide an approximate range for the repair cost in USD.   

        Return the results in JSON format with damagetype, severity, and cost fields.
        """
    else:
       prompt = user_prompt

    response = client.chat.completions.create(
        model=MODEL_ID,
        messages=[
            {
                "role": "user",
                "content": [
                    {"image_url": {"url": gcs_image_path}, "type": "image_url"},
                    {"text": prompt, "type": "text"},
                ],
            },
        ],
        max_tokens=max_tokens,
    )     


    await cl.Message(content=response.choices[0].message.content).send()
