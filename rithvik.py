import streamlit as st
import openai
import PyPDF2
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# OpenAI Key
openai.api_key = st.secrets["OPENAI_API_KEY"]

st.set_page_config(page_title="Resource AI Assistant", page_icon="📚", layout="wide")

# Session Init
for key, default in {
    "messages": [],
    "pdf_text": "",
    "pdf_name": "No document loaded",
    "links": [],
    "active_resource": None
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# --- Helper Functions ---

def extract_text_from_pdf(uploaded_file):
    try:
        reader = PyPDF2.PdfReader(uploaded_file)
        return "".join([page.extract_text() or "" for page in reader.pages])
    except Exception as e:
        st.error(f"PDF Extraction Error: {e}")
        return ""


def extract_text_from_static_url(url):
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            text = "\n".join([p.get_text() for p in soup.find_all('p')])
            return text if text.strip() else "No visible text found on the page."
        else:
            return f"Failed to fetch URL (Status {response.status_code})"
    except Exception as e:
        return f"Static Webpage Error: {e}"


def extract_text_from_dynamic_url(url):
    try:
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        driver = webdriver.Chrome(options=options)
        driver.get(url)

        # Wait until body is loaded
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        page_text = driver.find_element(By.TAG_NAME, "body").text
        driver.quit()

        return page_text if page_text.strip() else "No visible text found on the page."
    except Exception as e:
        return f"Selenium Error: {e}"


def get_ai_response(prompt, context=""):
    try:
        system_content = "You are a helpful assistant summarizing and answering based on uploaded documents or fetched webpages."
        if context:
            system_content += f"\n\nCurrent resource context:\n{context}"

        response = openai.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt},
                *[{"role": msg["role"], "content": msg["content"]}
                  for msg in st.session_state.messages[-6:]]
            ],
            temperature=0.7,
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI Error: {e}"


# --- Sidebar ---

with st.sidebar:
    st.title("Resource Navigator")
    st.divider()

    tab1, tab2 = st.tabs(["📄 Documents", "🔗 Links"])

    # Documents
    with tab1:
        uploaded_file = st.file_uploader("Upload a PDF Document", type=["pdf"])
        if uploaded_file:
            with st.spinner("Extracting text from PDF..."):
                text = extract_text_from_pdf(uploaded_file)
                st.session_state.pdf_text = text
                st.session_state.pdf_name = uploaded_file.name
                st.session_state.active_resource = {
                    "type": "document",
                    "name": uploaded_file.name,
                    "content": text[:10000]
                }
            st.success(f"Document loaded: {uploaded_file.name}")
            with st.spinner("Summarizing document..."):
                summary = get_ai_response("Summarize this document.", text[:10000])
                st.session_state.messages.append({"role": "assistant", "content": summary})
                st.chat_message("assistant").markdown(summary)

    # Links
    with tab2:
        with st.form("add_link_form"):
            st.subheader("Add New Link")
            title = st.text_input("Title")
            url = st.text_input("URL")
            category = st.selectbox("Category", ["General", "Research", "Article", "Reference", "Other"])
            mode = st.radio("Fetch Mode", ["Static (BeautifulSoup)", "Dynamic (Selenium)"])

            if st.form_submit_button("Add Link"):
                if title and url:
                    st.session_state.links.append({
                        "title": title,
                        "url": url,
                        "category": category,
                        "mode": mode
                    })
                    st.success("Link added successfully!")
                else:
                    st.warning("Please provide both Title and URL")

        st.divider()
        st.subheader("Saved Links")
        if not st.session_state.links:
            st.info("No links saved yet.")
        else:
            for i, link in enumerate(st.session_state.links):
                with st.container(border=True):
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.markdown(f"**{link['title']}**  \n{link['url']}")
                        st.caption(f"{link['category']} | {link['mode']}")
                    with col2:
                        if st.button("Select", key=f"select_{i}"):
                            with st.spinner("Fetching webpage content..."):
                                if link['mode'] == "Static (BeautifulSoup)":
                                    text = extract_text_from_static_url(link['url'])
                                else:
                                    text = extract_text_from_dynamic_url(link['url'])

                                if not text or "Error" in text or "Failed" in text:
                                    st.warning("Could not extract meaningful content from this link.")
                                else:
                                    st.session_state.active_resource = {
                                        "type": "link",
                                        "name": link['title'],
                                        "url": link['url'],
                                        "category": link['category'],
                                        "content": text[:10000]
                                    }
                                    with st.spinner("Summarizing webpage..."):
                                        summary = get_ai_response("Summarize this webpage.", text[:10000])
                                        st.session_state.messages.append({"role": "assistant", "content": summary})
                                        st.chat_message("assistant").markdown(summary)
                            st.rerun()

                        if st.button("❌", key=f"delete_{i}"):
                            st.session_state.links.pop(i)
                            st.rerun()


# --- Main Interface ---

resource_name = st.session_state.active_resource["name"] if st.session_state.active_resource else "No resource selected"
st.title(f"📚 Resource AI Assistant — {resource_name}")

if st.session_state.active_resource:
    with st.expander("Current Resource Details"):
        res = st.session_state.active_resource
        if res["type"] == "document":
            st.write(f"**Document:** {res['name']}")
        else:
            st.write(f"**Link:** {res['name']} — {res['url']}")
            st.write(f"**Category:** {res['category']}")
        st.caption(f"{len(res['content'])} characters loaded")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input(f"Ask about {resource_name}..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    context = st.session_state.active_resource.get("content", "") if st.session_state.active_resource else ""
    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            reply = get_ai_response(prompt, context)
        st.markdown(reply)
    st.session_state.messages.append({"role": "assistant", "content": reply})

if not st.session_state.active_resource:
    st.info("Upload a document or select a link to start.")
