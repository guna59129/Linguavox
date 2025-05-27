from googletrans import Translator
import textwrap
import asyncio
import inspect

LANGUAGE_CODES = {
    "Hindi": "hi",
    "Telugu": "te",
    "French": "fr",
    "Spanish": "es",
    "German": "de",
    "Chinese (Simplified)": "zh-cn"
}

def chunk_text(text, max_length=5000):
    return textwrap.wrap(text, width=max_length, break_long_words=False, break_on_hyphens=False)

def translate_chunk(translator, chunk, dest_lang):
    result = translator.translate(chunk, dest=dest_lang)
    if inspect.iscoroutine(result):
        return asyncio.run(result).text
    else:
        return result.text

def translate_text(text, dest_lang='te'):
    if not text.strip():
        return ""
    if dest_lang not in LANGUAGE_CODES.values():
        raise ValueError(f"Unsupported language code: {dest_lang}")
    translator = Translator()
    chunks = chunk_text(text)
    translated_chunks = []
    for i, chunk in enumerate(chunks):
        try:
            translated = translate_chunk(translator, chunk, dest_lang)
            translated_chunks.append(translated)
        except Exception:
            translated_chunks.append(f"[Error translating chunk {i+1}]")
    return " ".join(translated_chunks)


