import streamlit as st
import openai
import PyPDF2
import requests
from bs4 import BeautifulSoup

# Set OpenAI API key
openai.api_key = st.secrets["OPENAI_API_KEY"]

# App Config
st.set_page_config(page_title="Resource AI Assistant", page_icon="📚", layout="wide")

# Session State Initialization
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


def extract_text_from_url(url):
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            return "\n".join([p.get_text() for p in soup.find_all('p')])
        else:
            return f"Failed to fetch URL (Status {response.status_code})"
    except Exception as e:
        return f"Error fetching webpage: {e}"


def get_ai_response(prompt, context=""):
    try:
        system_content = "You are a helpful assistant summarizing and answering based on documents or web content."
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


# --- Sidebar: Resource Management ---
with st.sidebar:
    st.title("Resource Navigator")
    st.divider()

    tabs = st.tabs(["📄 Documents", "🔗 Links"])

    # --- Documents Tab ---
    with tabs[0]:
        uploaded_file = st.file_uploader("Upload a PDF Document", type=["pdf"])

        if uploaded_file:
            with st.spinner("Extracting text from document..."):
                pdf_text = extract_text_from_pdf(uploaded_file)
                st.session_state.pdf_text = pdf_text
                st.session_state.pdf_name = uploaded_file.name
                st.session_state.active_resource = {
                    "type": "document",
                    "name": uploaded_file.name,
                    "content": pdf_text[:10000]
                }

            st.success(f"Document loaded: {uploaded_file.name}")
            st.caption(f"Characters extracted: {len(pdf_text)}")

            with st.expander("Document Preview"):
                st.text_area("Extracted Text",
                             value=pdf_text[:2000] + ("..." if len(pdf_text) > 2000 else ""),
                             height=300, disabled=True)

            with st.spinner("Summarizing document..."):
                summary = get_ai_response("Summarize this document.", pdf_text[:10000])
                st.session_state.messages.append({"role": "assistant", "content": summary})
                st.chat_message("assistant").markdown(summary)

    # --- Links Tab ---
    with tabs[1]:
        with st.form("add_link_form"):
            st.subheader("Add New Link")
            link_title = st.text_input("Title")
            link_url = st.text_input("URL")
            link_category = st.selectbox("Category", ["General", "Research", "Article", "Reference", "Other"])

            if st.form_submit_button("Add Link"):
                if link_url and link_title:
                    st.session_state.links.append({
                        "title": link_title,
                        "url": link_url,
                        "category": link_category
                    })
                    st.success("Link added successfully!")
                else:
                    st.warning("Provide both title and URL")

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

                                with st.spinner("Summarizing webpage..."):
                                    summary = get_ai_response("Summarize this webpage.", page_text[:10000])
                                    st.session_state.messages.append({"role": "assistant", "content": summary})
                                    st.chat_message("assistant").markdown(summary)
                            st.rerun()

                    if st.button("❌", key=f"delete_{i}"):
                        st.session_state.links.pop(i)
                        st.rerun()


# --- Main Chat Interface ---
resource_name = st.session_state.active_resource["name"] if st.session_state.active_resource else "No resource selected"
st.title(f"📚 Resource AI Assistant - {resource_name}")

if st.session_state.active_resource:
    with st.expander("Current Resource Details", expanded=False):
        res = st.session_state.active_resource
        if res["type"] == "document":
            st.write(f"**Document:** {res['name']}")
            st.caption(f"{len(res['content'])} characters loaded")
        else:
            st.write(f"**Link:** {res['name']}")
            st.write(f"**URL:** {res['url']}")
            st.write(f"**Category:** {res['category']}")
            st.caption(f"{len(res['content'])} characters fetched")

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat Input Handler
if prompt := st.chat_input(f"Ask about {resource_name}..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    context = st.session_state.active_resource.get("content", "") if st.session_state.active_resource else ""
    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            response = get_ai_response(prompt, context)
        st.markdown(response)

    st.session_state.messages.append({"role": "assistant", "content": response})

if not st.session_state.active_resource:
    st.info("Upload a document or select a link to begin interacting with the AI.")
