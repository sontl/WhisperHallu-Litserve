import json

def _get_utterances(gladia_response, is_translation_empty):
    """Helper function to extract utterances from the response"""
    if not is_translation_empty:
        translation_results = gladia_response.get("translation", {}).get("results", {})[0]
        return translation_results.get("utterances", [])
    return gladia_response.get("transcription", {}).get("utterances", [])

def _create_json_segment(utterance):
    """Helper function to create a JSON segment from an utterance"""
    json_segment = {
        "start": utterance.get("start", 0),
        "end": utterance.get("end", 0),
        "sentence": utterance.get("text", "").strip(),
        "words": []
    }
    
    for word in utterance.get("words", []):
        json_segment["words"].append({
            "start": word.get("start", 0),
            "end": word.get("end", 0),
            "text": word.get("word", "").strip()
        })
    
    return json_segment

def _get_text_and_srt(gladia_response, is_translation_empty):
    """Helper function to extract text and srt from the response"""
    if is_translation_empty:
        transcription = gladia_response.get("transcription", {})
        return {
            "text": transcription.get("full_transcript", ""),
            "srt": transcription.get("subtitles", [])[0].get("subtitles", "")
        }
    
    translation_results = gladia_response.get("translation", {}).get("results", {})[0]
    subtitles = translation_results.get("subtitles", [])
    return {
        "text": translation_results.get("full_transcript", ""),
        "srt": subtitles[0].get("subtitles", "") if subtitles else ""
    }

def convert_gladia_to_internal_format(gladia_response):
    result = {
        "text": "",
        "srt": "",
        "json": []
    }

    gladia_response = gladia_response.get("result", {})
    is_translation_empty = True
    # Get utterances and process them
    utterances = _get_utterances(gladia_response, is_translation_empty)
    result["json"] = [_create_json_segment(utterance) for utterance in utterances]

    # Get text and srt
    text_and_srt = _get_text_and_srt(gladia_response, is_translation_empty)
    result["text"] = text_and_srt["text"]
    result["srt"] = text_and_srt["srt"]

    return result

def split_sentence(sentence, words):
    parts = [part.strip() for part in sentence.replace('.', ',').split(',') if part.strip()]
    new_sentences = []
    current_words = []
    current_part = []
    
    for word in words:
        current_words.append(word)
        current_part.append(word['text'])
        
        if (word['text'].strip().endswith(',') or word['text'].strip().endswith('.')) and len(current_part) >= 3:
            new_sentence = {
                'start': current_words[0]['start'],
                'end': current_words[-1]['end'],
                'sentence': ' '.join(w['text'] for w in current_words).strip(),
                'words': current_words
            }
            new_sentences.append(new_sentence)
            current_words = []
            current_part = []
    
    if current_words:
        if new_sentences and len(current_words) < 3:
            # Append short remaining part to the last sentence
            last_sentence = new_sentences[-1]
            last_sentence['end'] = current_words[-1]['end']
            last_sentence['sentence'] += ' ' + ' '.join(w['text'] for w in current_words)
            last_sentence['words'].extend(current_words)
        else:
            new_sentence = {
                'start': current_words[0]['start'],
                'end': current_words[-1]['end'],
                'sentence': ' '.join(w['text'] for w in current_words).strip(),
                'words': current_words
            }
            new_sentences.append(new_sentence)
    
    return new_sentences

def contains_weird_words(text):
    weird_words = ["Hãy đăng ký kênh", "subscribe cho", "Ghiền Mì Gõ"]
    return any(word.lower() in text.lower() for word in weird_words)

def process_json(input_json):
    output_json = []
    
    for item in input_json:
        if contains_weird_words(item['sentence']):
            item['sentence'] = ""
            item['words'] = []  # Set words to an empty array
      
        if ',' in item['sentence'] or '.' in item['sentence']:
            new_sentences = split_sentence(item['sentence'], item['words'])
            output_json.extend(new_sentences)
        else:
            output_json.append(item)
    
    return output_json

def split_transcription(input_data):
    # Process the JSON
    output_data = process_json(input_data)
    return output_data  # Return the processed data directly
