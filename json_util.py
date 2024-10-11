import json

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

def process_json(input_json):
    output_json = []
    
    for item in input_json:
        if ',' in item['sentence'] or '.' in item['sentence']:
            new_sentences = split_sentence(item['sentence'], item['words'])
            output_json.extend(new_sentences)
        else:
            output_json.append(item)
    
    return output_json  # Return the list directly, not in a set or dict

def split_transcription(input_data):
    # Process the JSON
    output_data = process_json(input_data)
    return output_data  # Return the processed data directly
