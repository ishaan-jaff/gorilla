# Copyright 2023 https://github.com/ShishirPatil/gorilla
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import sys
import json
import openai
import anthropic
import litellm
from litellm import completion
import multiprocessing as mp
import time
import os

def encode_question(question, api_name):
    """Encode multiple prompt instructions into a single string."""
    
    prompts = []
    if api_name == "torchhub":
        domains = "1. $DOMAIN is inferred from the task description and should include one of {Classification, Semantic Segmentation, Object Detection, Audio Separation, Video Classification, Text-to-Speech}."
    elif api_name == "huggingface":
        domains = "1. $DOMAIN should include one of {Multimodal Feature Extraction, Multimodal Text-to-Image, Multimodal Image-to-Text, Multimodal Text-to-Video, \
        Multimodal Visual Question Answering, Multimodal Document Question Answer, Multimodal Graph Machine Learning, Computer Vision Depth Estimation,\
        Computer Vision Image Classification, Computer Vision Object Detection, Computer Vision Image Segmentation, Computer Vision Image-to-Image, \
        Computer Vision Unconditional Image Generation, Computer Vision Video Classification, Computer Vision Zero-Shor Image Classification, \
        Natural Language Processing Text Classification, Natural Language Processing Token Classification, Natural Language Processing Table Question Answering, \
        Natural Language Processing Question Answering, Natural Language Processing Zero-Shot Classification, Natural Language Processing Translation, \
        Natural Language Processing Summarization, Natural Language Processing Conversational, Natural Language Processing Text Generation, Natural Language Processing Fill-Mask,\
        Natural Language Processing Text2Text Generation, Natural Language Processing Sentence Similarity, Audio Text-to-Speech, Audio Automatic Speech Recognition, \
        Audio Audio-to-Audio, Audio Audio Classification, Audio Voice Activity Detection, Tabular Tabular Classification, Tabular Tabular Regression, \
        Reinforcement Learning Reinforcement Learning, Reinforcement Learning Robotics }"
    elif api_name == "tensorhub":
        domains = "1. $DOMAIN is inferred from the task description and should include one of {text-sequence-alignment, text-embedding, text-language-model, text-preprocessing, text-classification, text-generation, text-question-answering, text-retrieval-question-answering, text-segmentation, text-to-mel, image-classification, image-feature-vector, image-object-detection, image-segmentation, image-generator, image-pose-detection, image-rnn-agent, image-augmentation, image-classifier, image-style-transfer, image-aesthetic-quality, image-depth-estimation, image-super-resolution, image-deblurring, image-extrapolation, image-text-recognition, image-dehazing, image-deraining, image-enhancemenmt, image-classification-logits, image-frame-interpolation, image-text-detection, image-denoising, image-others, video-classification, video-feature-extraction, video-generation, video-audio-text, video-text, audio-embedding, audio-event-classification, audio-command-detection, audio-paralinguists-classification, audio-speech-to-text, audio-speech-synthesis, audio-synthesis, audio-pitch-extraction}"
    else:
        print("Error: API name is not supported.")

    prompt = question + "\nWrite a python program in 1 to 2 lines to call API in " + api_name + ".\n\nThe answer should follow the format: <<<domain>>> $DOMAIN, <<<api_call>>>: $API_CALL, <<<api_provider>>>: $API_PROVIDER, <<<explanation>>>: $EXPLANATION, <<<code>>>: $CODE}. Here are the requirements:\n" + domains + "\n2. The $API_CALL should have only 1 line of code that calls api.\n3. The $API_PROVIDER should be the programming framework used.\n4. $EXPLANATION should be a step-by-step explanation.\n5. The $CODE is the python code.\n6. Do not repeat the format in your answer."
    prompts.append({"role": "system", "content": "You are a helpful API writer who can write APIs based on requirements."})
    prompts.append({"role": "user", "content": prompt})
    return prompts

def get_response(get_response_input, api_key):
    question, question_id, api_name, model = get_response_input
    question = encode_question(question, api_name)
    
    try:
        if model in litellm.model_list:
            openai.api_key = api_key
            responses = completion(
                model=model,
                messages=question,
                n=1,
                temperature=0,
            )
            response = responses['choices'][0]['message']['content']
        else:
            print("Error: Model is not supported.")
    except Exception as e:
        print("Error:", e)
        return None
        
    print("=>",)
    return {'text': response, "question_id": question_id, "answer_id": "None", "model_id": model, "metadata": {}}

def process_entry(entry, api_key):
    question, question_id, api_name, model = entry
    result = get_response((question, question_id, api_name, model), api_key)
    return result

def write_result_to_file(result, output_file):
    global file_write_lock
    with file_write_lock:
        with open(output_file, "a") as outfile:
            json.dump(result, outfile)
            outfile.write("\n")

def callback_with_lock(result, output_file):
    global file_write_lock
    write_result_to_file(result, output_file, file_write_lock)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, default=None, help="which model you want to use for eval, only support ['gpt*', 'claude*'] now")
    parser.add_argument("--api_key", type=str, default=None, help="the api key provided for calling")
    parser.add_argument("--output_file", type=str, default=None, help="the output file this script writes to")
    parser.add_argument("--question_data", type=str, default=None, help="path to the questions data file")
    parser.add_argument("--api_name", type=str, default=None, help="this will be the api dataset name you are testing, only support ['torchhub', 'tensorhun', 'huggingface'] now")
    args = parser.parse_args()

    start_time = time.time()
    # Read the question file
    questions = []
    question_ids = []
    with open(args.question_data, 'r') as f:
        for idx, line in enumerate(f):
            questions.append(json.loads(line)["text"])
            question_ids.append(json.loads(line)["question_id"])

    file_write_lock = mp.Lock()
    with mp.Pool(1) as pool:
        results = []
        for idx, (question, question_id) in enumerate(zip(questions, question_ids)):
            result = pool.apply_async(
                process_entry,
                args=((question, question_id, args.api_name, args.model), args.api_key),
                callback=lambda result: write_result_to_file(result, args.output_file),
            )
            results.append(result)
        pool.close()
        pool.join()

    end_time = time.time()
    print("Total time used: ", end_time - start_time)
