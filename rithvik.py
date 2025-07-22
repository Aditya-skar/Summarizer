import streamlit as st
import openai
import PyPDF2
import os
from io import BytesIO
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# App title and config
st.set_page_config(page_title="Resource AI Assistant", page_icon="📚", layout="wide")

# Initialize session state
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


# Function to extract text from PDF
def extract_text_from_pdf(uploaded_file):
    try:
        pdf_reader = PyPDF2.PdfReader(uploaded_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()
        return text
    except Exception as e:
        st.error(f"Error extracting text: {e}")
        return ""


# Function to get AI response
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
                *[{"role": msg["role"], "content": msg["content"]} for msg in st.session_state.messages[-6:]]
            ],
            temperature=0.7,
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error getting AI response: {str(e)}"


# Sidebar for resource management
with st.sidebar:
    st.title("Resource Navigator")
    st.divider()

    # Tab interface for resources
    tab1, tab2 = st.tabs(["📄 Documents", "🔗 Links"])

    with tab1:
        uploaded_file = st.file_uploader(
            "Upload a document",
            type=["pdf"],
            help="Upload a PDF file to analyze its content"
        )

        if uploaded_file is not None:
            # Process PDF
            with st.spinner("Extracting text from document..."):
                st.session_state.pdf_text = extract_text_from_pdf(uploaded_file)
                st.session_state.pdf_name = uploaded_file.name
                st.session_state.active_resource = {
                    "type": "document",
                    "name": uploaded_file.name,
                    "content": st.session_state.pdf_text[:10000]  # Store first 10k chars
                }

            st.success(f"Document loaded: {uploaded_file.name}")
            st.caption(f"Text characters extracted: {len(st.session_state.pdf_text)}")

            # Show document info
            with st.expander("Document Preview"):
                if st.session_state.pdf_text:
                    st.text_area(
                        "Extracted Text",
                        value=st.session_state.pdf_text[:2000] + (
                            "..." if len(st.session_state.pdf_text) > 2000 else ""),
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
                "Category",
                ["General", "Research", "Article", "Reference", "Other"]
            )

            if st.form_submit_button("Add Link"):
                if link_url and link_title:
                    new_link = {
                        "title": link_title,
                        "url": link_url,
                        "category": link_category
                    }
                    st.session_state.links.append(new_link)
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
                            st.session_state.active_resource = {
                                "type": "link",
                                "name": link['title'],
                                "url": link['url'],
                                "category": link['category']
                            }
                            st.rerun()

                    if st.button("❌", key=f"delete_{i}"):
                        st.session_state.links.pop(i)
                        st.rerun()

# Main chat interface
current_resource = st.session_state.active_resource[
    "name"] if st.session_state.active_resource else "No resource selected"
st.title(f"📚 Resource AI Assistant - {current_resource}")

# Display resource info if selected
if st.session_state.active_resource:
    with st.expander("Current Resource Details", expanded=False):
        if st.session_state.active_resource["type"] == "document":
            st.write(f"**Document:** {st.session_state.active_resource['name']}")
            st.caption(f"{len(st.session_state.active_resource['content'])} characters available for context")
        else:
            st.write(f"**Link:** {st.session_state.active_resource['name']}")
            st.write(f"**URL:** {st.session_state.active_resource['url']}")
            st.write(f"**Category:** {st.session_state.active_resource['category']}")

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input(f"Ask about {current_resource}..."):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)

    # Get context based on active resource
    context = ""
    if st.session_state.active_resource:
        if st.session_state.active_resource["type"] == "document":
            context = st.session_state.active_resource["content"]
        else:
            context = f"Link: {st.session_state.active_resource['name']}\nURL: {st.session_state.active_resource['url']}"

    # Display assistant response
    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            response = get_ai_response(prompt, context)

        st.markdown(response)

    # Add assistant response to chat history
    st.session_state.messages.append({"role": "assistant", "content": response})

# Instructions when no resource is selected
if not st.session_state.active_resource:
    st.info("Please upload a document or select a link in the sidebar to begin chatting with the AI")