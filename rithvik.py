import streamlit as st
import openai
import PyPDF2
import requests
from bs4 import BeautifulSoup

# Set OpenAI API key from Streamlit Secrets
openai.api_key = st.secrets["OPENAI_API_KEY"]

# App Config
st.set_page_config(page_title="Resource AI Assistant", page_icon="📚", layout="wide")

# Session Initialization
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pdf_text" not in st.session_state:
    st.session_state.pdf_text = ""
if "pdf_name" not in st.session_state:
    st.session_state.pdf_name = "No document loaded"
if "links" not in st.session_state:
    st.session_state.links = []
if "active_resource" not in st.session_state:
    st.session_state.active_resource = None


# --- Helper Functions ---

def extract_text_from_pdf(uploaded_file):
    try:
        pdf_reader = PyPDF2.PdfReader(uploaded_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() or ""
        return text
    except Exception as e:
        st.error(f"Error extracting text: {e}")
        return ""


def extract_text_from_url(url):
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            paragraphs = [p.get_text() for p in soup.find_all('p')]
            return "\n".join(paragraphs)
        else:
            return f"Failed to fetch URL. Status code: {response.status_code}"
    except Exception as e:
        return f"Error fetching the webpage: {e}"


def get_ai_response(prompt, context=""):
    try:
        system_content = """You are a helpful AI assistant that answers questions about documents and web resources.
        Respond concisely but helpfully to user queries."""

        if context:
            system_content += f"\n\nCurrent resource context:\n{context}"

        response = openai.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt},
                *[
                    {"role": msg["role"], "content": msg["content"]}
                    for msg in st.session_state.messages[-6:]
                ]
            ],
            temperature=0.7,
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error getting AI response: {str(e)}"


# --- Sidebar ---
with st.sidebar:
    st.title("Resource Navigator")
    st.divider()

    tab1, tab2 = st.tabs(["📄 Documents", "🔗 Links"])

    with tab1:
        uploaded_file = st.file_uploader(
            "Upload a document", type=["pdf"],
            help="Upload a PDF file to analyze its content"
        )
        if uploaded_file:
            with st.spinner("Extracting text from document..."):
                extracted_text = extract_text_from_pdf(uploaded_file)
                st.session_state.pdf_text = extracted_text
                st.session_state.pdf_name = uploaded_file.name
                st.session_state.active_resource = {
                    "type": "document",
                    "name": uploaded_file.name,
                    "content": extracted_text[:10000]
                }
            st.success(f"Document loaded: {uploaded_file.name}")
            st.caption(f"Characters extracted: {len(extracted_text)}")
            with st.expander("Document Preview"):
                if extracted_text:
                    st.text_area(
                        "Extracted Text",
                        value=extracted_text[:2000] + ("..." if len(extracted_text) > 2000 else ""),
                        height=300,
                        disabled=True
                    )
                else:
                    st.warning("No text could be extracted from this document")

    with tab2:
        with st.form("add_link_form"):
            st.subheader("Add New Link")
            link_title = st.text_input("Title")
            link_url = st.text_input("URL")
            link_category = st.selectbox(
                "Category", ["General", "Research", "Article", "Reference", "Other"]
            )

            if st.form_submit_button("Add Link"):
                if link_url and link_title:
                    st.session_state.links.append({
                        "title": link_title,
                        "url": link_url,
                        "category": link_category
                    })
                    st.success("Link added successfully!")
                else:
                    st.warning("Please provide both title and URL")

        st.divider()
        st.subheader("Saved Links")
        if not st.session_state.links:
            st.info("No links saved yet")
        else:
            for i, link in enumerate(st.session_state.links):
                with st.container(border=True):
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.markdown(f"**{link['title']}**  \n{link['url']}")
                        st.caption(f"Category: {link['category']}")
                    with col2:
                        if st.button("Select", key=f"select_{i}"):
                            with st.spinner("Fetching webpage content..."):
                                page_text = extract_text_from_url(link['url'])
                                st.session_state.active_resource = {
                                    "type": "link",
                                    "name": link['title'],
                                    "url": link['url'],
                                    "category": link['category'],
                                    "content": page_text[:10000]
                                }
                            st.rerun()

                    if st.button("❌", key=f"delete_{i}"):
                        st.session_state.links.pop(i)
                        st.rerun()


# --- Main Chat Interface ---
current_resource_name = (
    st.session_state.active_resource["name"] if st.session_state.active_resource else "No resource selected"
)

st.title(f"📚 Resource AI Assistant - {current_resource_name}")

if st.session_state.active_resource:
    with st.expander("Current Resource Details", expanded=False):
        res = st.session_state.active_resource
        if res["type"] == "document":
            st.write(f"**Document:** {res['name']}")
            st.caption(f"{len(res['content'])} characters available for context")
        else:
            st.write(f"**Link:** {res['name']}")
            st.write(f"**URL:** {res['url']}")
            st.write(f"**Category:** {res['category']}")
            st.caption(f"{len(res['content'])} characters fetched from webpage")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input(f"Ask about {current_resource_name}..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    context = ""
    if st.session_state.active_resource:
        context = st.session_state.active_resource.get("content", "")

    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            response = get_ai_response(prompt, context)
        st.markdown(response)

    st.session_state.messages.append({"role": "assistant", "content": response})

if not st.session_state.active_resource:
    st.info("Please upload a document or select a link in the sidebar to begin chatting with the AI")

