import streamlit as st
import openai
import PyPDF2
import time

openai.api_key = st.secrets["OPENAI_API_KEY"]
st.set_page_config(page_title="Resource AI Assistant", page_icon="📚", layout="wide")

# --- Login Section ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_type" not in st.session_state:
    st.session_state.user_type = None
if "start_time" not in st.session_state:
    st.session_state.start_time = None
if "username" not in st.session_state:
    st.session_state.username = ""

def login():
    st.title("🔐 Login to Resource AI Assistant")
    st.session_state.username = st.text_input("Enter your username:")
    user_type = st.selectbox("Select User Type:", ["Free Demo (2 mins)", "Paid User"])
    if st.button("Login"):
        if st.session_state.username:
            st.session_state.authenticated = True
            st.session_state.user_type = user_type
            st.session_state.start_time = time.time()
            st.success(f"Welcome {st.session_state.username} ({user_type})")
            st.experimental_rerun()
        else:
            st.warning("Please enter a username to continue.")

if not st.session_state.authenticated:
    login()
    st.stop()

# --- Check Free Demo Timer ---
if st.session_state.user_type == "Free Demo (2 mins)":
    elapsed_time = time.time() - st.session_state.start_time
    if elapsed_time > 120:
        st.warning("⏰ Your Free Demo has expired after 2 minutes. Please upgrade to Paid User for full access.")
        st.stop()

# --- App State Init ---
for key, default in {
    "messages": [],
    "pdf_text": "",
    "pdf_name": "No document loaded",
    "links": [],
    "active_resource": None,
    "message_count": 0
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

def extract_text_from_pdf(uploaded_file):
    try:
        reader = PyPDF2.PdfReader(uploaded_file)
        return "".join(page.extract_text() for page in reader.pages if page.extract_text())
    except Exception as e:
        st.error(f"Error extracting text: {e}")
        return ""

def get_ai_response(prompt, context=""):
    try:
        system_content = (
            "You are a helpful AI assistant that answers questions about documents and web resources.\n"
            "Respond concisely but helpfully to user queries."
        )
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

# --- Sidebar Resource Management ---
with st.sidebar:
    st.title(f"Welcome {st.session_state.username}")
    st.caption(f"User Type: {st.session_state.user_type}")
    st.divider()

    doc_tab, link_tab = st.tabs(["📄 Documents", "🔗 Links"])

    with doc_tab:
        uploaded_file = st.file_uploader("Upload a document", type=["pdf"])
        if uploaded_file:
            with st.spinner("Extracting text..."):
                st.session_state.pdf_text = extract_text_from_pdf(uploaded_file)
                st.session_state.pdf_name = uploaded_file.name
                st.session_state.active_resource = {
                    "type": "document",
                    "name": uploaded_file.name,
                    "content": st.session_state.pdf_text[:10000]
                }
            st.success(f"Loaded: {uploaded_file.name}")
            with st.expander("Preview Extracted Text"):
                st.text_area(
                    "Extracted Text",
                    st.session_state.pdf_text[:2000] + ("..." if len(st.session_state.pdf_text) > 2000 else ""),
                    height=300,
                    disabled=True
                )

    with link_tab:
        with st.form("add_link"):
            st.subheader("Add New Link")
            title = st.text_input("Title")
            url = st.text_input("URL")
            category = st.selectbox("Category", ["General", "Research", "Article", "Reference", "Other"])
            if st.form_submit_button("Add Link"):
                if title and url:
                    st.session_state.links.append({"title": title, "url": url, "category": category})
                    st.success("Link added!")
                else:
                    st.warning("Title and URL required.")

        st.divider()
        st.subheader("Saved Links")
        if not st.session_state.links:
            st.info("No links saved yet.")
        else:
            for i, link in enumerate(st.session_state.links):
                with st.container(border=True):
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.markdown(f"**{link['title']}**\n{link['url']}")
                        st.caption(f"Category: {link['category']}")
                    with col2:
                        if st.button("Select", key=f"select_{i}"):
                            st.session_state.active_resource = {
                                "type": "link",
                                "name": link["title"],
                                "url": link["url"],
                                "category": link["category"]
                            }
                            st.rerun()
                        if st.button("❌", key=f"delete_{i}"):
                            st.session_state.links.pop(i)
                            st.rerun()

# --- Main Chat Section ---
st.title(f"📚 Resource AI Assistant — {st.session_state.active_resource['name'] if st.session_state.active_resource else 'No resource selected'}")

if st.session_state.active_resource:
    with st.expander("Resource Details"):
        res = st.session_state.active_resource
        if res["type"] == "document":
            st.write(f"**Document:** {res['name']}")
            st.caption(f"Characters available: {len(res['content'])}")
        else:
            st.write(f"**Link:** {res['name']}\n**URL:** {res['url']}\n**Category:** {res['category']}")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- Chat Interaction ---
if prompt := st.chat_input("Ask me anything..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    context = ""
    if st.session_state.active_resource:
        context = (
            st.session_state.active_resource["content"]
            if st.session_state.active_resource["type"] == "document"
            else f"Link: {st.session_state.active_resource['name']}\nURL: {st.session_state.active_resource['url']}"
        )

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = get_ai_response(prompt, context)
        st.markdown(response)

    st.session_state.messages.append({"role": "assistant", "content": response})

if not st.session_state.active_resource:
    st.info("Upload a document or select a link to begin.")
