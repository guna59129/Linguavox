from googletrans import Translator
import os
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
import extract
from language import LANGUAGE_CODES, translate_text
from gtts import gTTS

load_dotenv()
api_key = os.getenv("NVIDIA_API_KEY")

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=api_key
)

def chunk_text(text, max_tokens=3000, overlap=500):
    chunk_size = max_tokens * 4
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size - overlap)]

def build_prompt(content, summary_type):
    return f"Provide a {summary_type} and neat summary of the following text without any tables, bullet points, or special characters like asterisks and plus signs:\n\n{content}"

def summarize_chunk(content, summary_type, max_output_tokens):
    prompt = build_prompt(content, summary_type)
    response = client.chat.completions.create(
        model="nvidia/llama-3.3-nemotron-super-49b-v1",
        messages=[
            {"role": "system", "content": "You are a helpful summarization assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.6,
        top_p=0.95,
        max_tokens=max_output_tokens,
        stream=False
    )
    summary = response.choices[0].message.content.strip()
    lines = summary.split("\n")
    if len(lines) > 1:
        summary = "\n".join(lines[1:]).strip()
    return summary

def summarize_file(full_text, summary_type):
    token_map = {"Brief": 500, "Detailed": 1024, "Important": 800}
    chunks = chunk_text(full_text)
    return "\n\n".join(summarize_chunk(chunk, summary_type, token_map[summary_type]) for chunk in chunks)

def ask_question(content, question):
    prompt = f"""Answer the question strictly based on the text below. Do not include any introductions, bullet points, or special characters.

Text:
\"\"\"{content}\"\"\"

Question:
{question}
"""
    response = client.chat.completions.create(
        model="nvidia/llama-3.3-nemotron-super-49b-v1",
        messages=[
            {"role": "system", "content": "You respond with concise, direct answers only."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        top_p=0.9,
        max_tokens=512,
        stream=False
    )
    return response.choices[0].message.content.strip()

def find_answer_in_text(text, question):
    for chunk in chunk_text(text):
        answer = ask_question(chunk, question)
        if "not present in the document" not in answer.lower():
            return answer
    return "The answer is not present in the document."

def generate_audio(text, lang='en', output_folder="temp_audio"):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    filename = os.path.join(output_folder, "generated_audio.mp3")
    try:
        tts = gTTS(text=text, lang=lang)
        tts.save(filename)
        if os.path.exists(filename):
            return filename
        else:
            return None
    except Exception:
        return None

st.set_page_config(page_title="LINGUAVOX", layout="wide")

st.sidebar.header("📁 Upload a File or Provide URL")
input_mode = st.sidebar.radio("Select Input Type", ["Upload File", "Enter URL"])

uploaded_file = None
url_input = ""

if input_mode == "Upload File":
    uploaded_file = st.sidebar.file_uploader("Upload a file", type=["pdf", "txt", "docx", "pptx", "png", "jpg", "jpeg"])
elif input_mode == "Enter URL":
    url_input = st.sidebar.text_input("Paste the URL here")

mode = st.sidebar.selectbox("Select Operation", ["Summarize", "Q&A", "Full Text"])

enable_translation = st.sidebar.checkbox("🌍 Enable Translation")
target_lang = 'en'

if enable_translation:
    selected_lang = st.sidebar.selectbox("Choose Target Language", list(LANGUAGE_CODES.keys()))
    target_lang = LANGUAGE_CODES[selected_lang]

if uploaded_file or url_input:
    extracted_text = ""
    if uploaded_file:
        filename = uploaded_file.name
        file_ext = filename.split('.')[-1].lower()
        if file_ext == "pdf":
            extracted_text = extract.extract_text_from_pdf(uploaded_file)
        elif file_ext == "txt":
            extracted_text = extract.extract_text_from_txt(uploaded_file)
        elif file_ext == "docx":
            extracted_text = extract.extract_text_from_docx(uploaded_file)
        elif file_ext == "pptx":
            extracted_text = extract.extract_text_from_pptx(uploaded_file)
        elif file_ext in ["png", "jpg", "jpeg"]:
            extracted_text = extract.extract_text_from_image(uploaded_file)
        else:
            st.error("Unsupported file type.")
            st.stop()
    elif url_input:
        extracted_text = extract.extract_text_from_url(url_input)

    st.session_state["text_data"] = extracted_text

    if mode == "Summarize":
        summary_type = st.sidebar.selectbox("Summary Type", ["Brief", "Detailed", "Important"])
        if st.sidebar.button("📝 Generate Summary"):
            with st.spinner("Generating summary..."):
                summary = summarize_file(extracted_text, summary_type)
                st.session_state["summary"] = summary
                st.session_state["mode_selected"] = "Summarize"
                if enable_translation:
                    with st.spinner("Translating summary..."):
                        st.session_state["translated_text"] = translate_text(summary, target_lang)
                else:
                    st.session_state["translated_text"] = None

    elif mode == "Q&A":
        if st.sidebar.button("📄 Process for Q&A"):
            st.session_state["processed_text"] = extracted_text
            st.session_state["mode_selected"] = "Q&A"
            st.session_state["qa_ready"] = True
            if enable_translation:
                with st.spinner("Translating full text..."):
                    st.session_state["translated_text"] = translate_text(extracted_text, target_lang)
            else:
                st.session_state["translated_text"] = None
            st.success("File/URL processed! You can now ask questions.")

    elif mode == "Full Text":
        st.session_state["processed_text"] = extracted_text
        st.session_state["mode_selected"] = "Full Text"
        if enable_translation:
            with st.spinner("Translating full text..."):
                st.session_state["translated_text"] = translate_text(extracted_text, target_lang)
        else:
            st.session_state["translated_text"] = None
        st.success("Full Text loaded. You can listen or ask questions.")

output_ready = (
    (st.session_state.get("mode_selected") == "Summarize" and "summary" in st.session_state) or
    (st.session_state.get("mode_selected") == "Q&A" and st.session_state.get("qa_ready", False)) or
    (st.session_state.get("mode_selected") == "Full Text" and "processed_text" in st.session_state)
)

if output_ready:
    st.markdown("## 🎯 Generated Content")

    if st.session_state.get("mode_selected") == "Summarize" and "summary" in st.session_state:
        with st.expander("📃 View Generated Summary", expanded=True):
            if enable_translation and st.session_state.get("translated_text"):
                st.text_area("Translated Summary", value=st.session_state["translated_text"], height=300)
            else:
                st.text_area("Summary", value=st.session_state["summary"], height=300)

    elif st.session_state.get("mode_selected") == "Q&A" and st.session_state.get("qa_ready", False):
        with st.expander("❓ Ask Questions About the Document", expanded=True):
            question = st.text_input("Type your question:")
            if question:
                with st.spinner("Searching for the answer..."):
                    answer = find_answer_in_text(st.session_state["processed_text"], question)
                    if enable_translation:
                        answer = translate_text(answer, target_lang)
                    st.session_state["latest_answer"] = answer
                    st.success("✅ Answer:")
                    st.write(answer)

    elif st.session_state.get("mode_selected") == "Full Text" and "processed_text" in st.session_state:
        with st.expander("📜 Full Text", expanded=True):
            if enable_translation and st.session_state.get("translated_text"):
                st.text_area("Translated Text", value=st.session_state["translated_text"], height=300)
            else:
                st.text_area("Full Text", value=st.session_state["processed_text"], height=400)

    if st.button("🔊 Read Aloud"):
        text_to_speak = ""
        if st.session_state.get("mode_selected") == "Summarize" and "summary" in st.session_state:
            text_to_speak = st.session_state["translated_text"] if enable_translation and st.session_state.get("translated_text") else st.session_state["summary"]
        elif st.session_state.get("mode_selected") == "Full Text" and "processed_text" in st.session_state:
            text_to_speak = st.session_state["translated_text"] if enable_translation and st.session_state.get("translated_text") else st.session_state["processed_text"]
        elif st.session_state.get("mode_selected") == "Q&A" and "latest_answer" in st.session_state:
            text_to_speak = st.session_state["latest_answer"]

        if text_to_speak:
            audio_file_path = generate_audio(text_to_speak, lang=target_lang)
            if audio_file_path:
                st.success("✅ Audio generated!")
                with open(audio_file_path, 'rb') as f:
                    st.audio(f.read(), format='audio/mp3', start_time=0)
else:
    st.markdown("""
    <div style='text-align: center;'>
        <h1 style='font-weight: bold;'>LINGUAVOX</h1>
        <h3 style='color: gray;'>A multi-format, multi-language Text-to-Audio system with voice personalization</h3>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 🌟 Features")
    st.markdown("""
    - 📝 Summarization: Quickly generate summaries from your documents.
    - ❓ Question & Answer: Ask questions and get intelligent answers from your uploaded file.
    - 🗣 Text-to-Speech Personalization: Listen to content with personalized voice settings.
    - 🌐 Multi-language Support: Handle and convert text in multiple languages.
    - 🎙 Spacebar Audio Control: Play/Pause generated audio using the Space key.
    """)
