# # # import requests

# # # invoke_url = "https://integrate.api.nvidia.com/v1/chat/completions"
# # # stream = False

# # # headers = {
# # #     "Authorization": "Bearer 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",
# # #     "Accept": "text/event-stream" if stream else "application/json",
# # # }

# # # payload = {
# # #   "messages": [
# # #     {
# # #       "content": [
# # #         # {
# # #         #   "image_url": {
# # #         #     "url": "https://assets.ngc.nvidia.com/products/api-catalog/phi-3-5-vision/example1a.jpg"
# # #         #   },
# # #         #   "type": "image_url"
# # #         # },
# # #         {
# # #           "type": "text",
# # #           "text": "Hi, What's 1+1?"
# # #         }
# # #       ],
# # #       "role": "user"
# # #     }
# # #   ],
# # #   "model": "meta/llama-3.2-90b-vision-instruct",
# # #   "frequency_penalty": 0,
# # #   "max_tokens": 512,
# # #   "presence_penalty": 0,
# # #   "stream": stream,
# # #   "temperature": 0,
# # #   "top_p": 1
# # # }

# # # response = requests.post(invoke_url, headers=headers, json=payload, stream=stream)
# # # if stream:
# # #     for line in response.iter_lines():
# # #         if line:
# # #             print(line.decode("utf-8"))
# # # else:
# # #     print(response.json()['choices'][0]['message']['content'])





# # from openai import OpenAI

# # client = OpenAI(
# #   base_url = "https://nim.api.nvidia.com/v1",
# #   api_key = "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"
# # )

# # completion = client.chat.completions.create(
# #   model="meta-llama/Llama-3.1-8B-Instruct",
# #   messages=[{"role":"user","content":""}],
# #   temperature=0.5,
# #   top_p=1,
# #   max_tokens=1024,
# #   stream=True
# # )

# # for chunk in completion:
# #   if chunk.choices[0].delta.content is not None:
# #     print(chunk.choices[0].delta.content, end="")



# import gradio as gr
# import spaces
# import torch

# from transformers import (
#     AutoTokenizer,
#     AutoModelForCausalLM,
#     BitsAndBytesConfig,
# )

# MODEL_ID = "meta-llama/Llama-3.1-8B-Instruct"

# HF_TOKEN = "hf_your_token_here"

# tokenizer = None
# model = None


# def load_model():
#     global tokenizer, model

#     if model is not None:
#         return

#     quant_config = BitsAndBytesConfig(
#         load_in_4bit=True,
#         bnb_4bit_quant_type="nf4",
#         bnb_4bit_compute_dtype=torch.float16,
#         bnb_4bit_use_double_quant=True,
#     )

#     tokenizer = AutoTokenizer.from_pretrained(
#         MODEL_ID,
#         token=HF_TOKEN,
#     )

#     model = AutoModelForCausalLM.from_pretrained(
#         MODEL_ID,
#         token=HF_TOKEN,
#         quantization_config=quant_config,
#         device_map="cuda",
#         torch_dtype=torch.float16,
#     )

#     print("Model loaded on:", model.device)


# @spaces.GPU
# def greet(message):
#     load_model()

#     messages = [
#         {
#             "role": "user",
#             "content": message,
#         }
#     ]

#     prompt = tokenizer.apply_chat_template(
#         messages,
#         tokenize=False,
#         add_generation_prompt=True,
#     )

#     inputs = tokenizer(
#         prompt,
#         return_tensors="pt",
#     ).to("cuda")

#     with torch.inference_mode():
#         outputs = model.generate(
#             **inputs,
#             max_new_tokens=256,
#             temperature=0.7,
#             top_p=0.9,
#             do_sample=True,
#         )

#     generated_tokens = outputs[0][inputs["input_ids"].shape[-1]:]

#     return tokenizer.decode(
#         generated_tokens,
#         skip_special_tokens=True,
#     )


# demo = gr.Interface(
#     fn=greet,
#     inputs=gr.Textbox(
#         label="Message",
#         placeholder="Ask Llama something...",
#     ),
#     outputs=gr.Textbox(
#         label="Llama 3.1 8B Response",
#     ),
#     title="Llama 3.1 8B Instruct",
# )

# demo.launch()





from gradio_client import Client

client = Client("R910/Llama-API")
result = client.predict(
	message="Kaa haal ba!!",
	api_name="/greet",
)
print(result)