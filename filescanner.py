import streamlit as st
import openai
from PyPDF2 import PdfReader
import re
from PIL import Image

# Setup OpenAI client
client = openai.OpenAI(api_key="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")  # Replace with your actual API key

st.set_page_config(layout="wide")

# Initialize session state for page tracking
if "current_page" not in st.session_state:
    st.session_state["current_page"] = "Grant Scoring"

if "saved_apps" not in st.session_state:
    st.session_state["saved_apps"] = []
if "analyzed_results" not in st.session_state:
    st.session_state["analyzed_results"] = []

# Sidebar with logo and navigation buttons
logo = Image.open("logo.jpeg")  # Replace with your actual file name
with st.sidebar:
    st.image(logo, width=300)
    st.markdown("## Navigation")
    if st.button("Grant Scoring"):
        st.session_state["current_page"] = "Grant Scoring"
    if st.button("Saved Applications"):
        st.session_state["current_page"] = "Saved Applications"

page = st.session_state["current_page"]

# Helper functions
def extract_text(file):
    if file.type == "text/plain":
        return file.read().decode("utf-8")
    elif file.type == "application/pdf":
        return "".join(page.extract_text() + "\n" for page in PdfReader(file).pages)
    return ""

def check_plagiarism(text, all_texts):
    return any(other_text != text and text.strip()[:500] in other_text for other_text in all_texts)

def extract_score(ai_output):
    match = re.search(r"(score|scored|rating).*?(\d+)", ai_output.lower())
    return int(match.group(2)) if match else None

def extract_fraud_risk(ai_output):
    # Normalize the output (remove extra spaces and lowercase)
    cleaned_output = ai_output.lower().replace("\n", " ").replace(":", " ").strip()

    # Look for "fraud risk" followed by LOW, MEDIUM, or HIGH anywhere in the sentence
    if "fraud risk" in cleaned_output:
        if "low" in cleaned_output:
            return "LOW"
        elif "medium" in cleaned_output:
            return "MEDIUM"
        elif "high" in cleaned_output:
            return "HIGH"
    return "UNKNOWN"

# Page: Grant Scoring
if page == "Grant Scoring":
    st.title("Grant Application AI Scorer")

    st.markdown("""
    Upload multiple grant applications (PDF or TXT), and this tool will:
    - Score them based on the evaluation rubric
    - Detect fraud risk (plagiarism, missing sections, buzzword overload)
    - Rank and let you select which applications to save
    """)

    # Display rubric
    st.markdown("## Evaluation Rubric")
    st.markdown("""
    Application Evaluation:

    | Category                           | Maximum Points |
    |--------------------------------------|----------------|
    | Agency Mission/Vision                | 15             |
    | Outreach & Engagement                | 20             |
    | Agency Experience                    | 15             |
    | Outcome & Evaluation                 | 25             |
    | Proposed Services                    | 15             |
    | Proposed Budget                      | 10             |
    | **Bonus: Priority Neighborhood**     | +3             |
    | **Bonus: Equity Priority Community** | +2             |

   
    """)

    # Manual criteria input
    manual_criteria = st.text_area(
        "Optional: Enter any additional evaluation notes or criteria you'd like to include:",
        placeholder="E.g. Focus on environmental sustainability, prioritize youth services, etc."
    )

    uploaded_files = st.file_uploader("Upload grant applications (PDF or TXT):", type=["pdf", "txt"], accept_multiple_files=True)

    if st.button("Analyze Applications"):
        if not uploaded_files:
            st.warning("Please upload files.")
        else:
            with st.spinner("Analyzing..."):
                results = []
                texts = [extract_text(f) for f in uploaded_files]

                for file, app_text in zip(uploaded_files, texts):
                    is_plagiarized = check_plagiarism(app_text, texts)

                    prompt = f"""
You are a grant evaluator. Carefully read the following grant application and score it based on the evaluation rubric below.

Additional Notes from Evaluator:
{manual_criteria}

### Scoring Rubric:
1. Agency Mission/Vision (0-15 points)
2. Outreach & Engagement (0-20 points)
3. Agency Experience (0-15 points)
4. Outcome & Evaluation (0-25 points)
5. Proposed Services (0-15 points)
6. Proposed Budget (0-10 points)

Bonus Points:
- Priority Neighborhood (0-3 points)
- Equity Priority Community (0-2 points)

### Instructions:
- Score each section individually and explain your reasoning.
-Total Score: X out of 100 plus any bonus points.
-Fraud Risk: LOW / MEDIUM / HIGH. Clearly explain why.
- Clearly indicate any fraud risks such as plagiarism, missing content, or unrealistic claims. Analyze the following grant application and estimate whether the writing style seems AI-generated (e.g., written by ChatGPT). Look for generic phrases, overuse of buzzwords, lack of specifics, and mechanical structure.
- If the application is incomplete or fails eligibility, mark it as 'Fail' and do not score.

### Grant Application:
{app_text}

Provide your scoring breakdown, justification, and total score.
"""

                    try:
                        response = client.chat.completions.create(
                            model="gpt-4",
                            messages=[
                                {"role": "system", "content": "You are a professional grant evaluator."},
                                {"role": "user", "content": prompt}
                            ]
                        )
                        ai_output = response.choices[0].message.content
                        score = extract_score(ai_output) or 0
                        fraud_risk = extract_fraud_risk(ai_output)

                        results.append({
                            "filename": file.name,
                            "score": score,
                            "fraud_risk": fraud_risk,
                            "output": ai_output,
                            "file_data": file.getvalue()
                        })

                    except Exception as e:
                        st.error(f"Error analyzing {file.name}: {e}")

                st.session_state["analyzed_results"] = sorted(results, key=lambda x: (-x["score"], x["fraud_risk"]))

    # Show results with save option
    if st.session_state["analyzed_results"]:
        st.markdown("Ranked Applications")
        for idx, result in enumerate(st.session_state["analyzed_results"]):
            with st.expander(f"{idx+1}. {result['filename']} (Score: {result['score']})"):
                st.markdown("### AI Evaluation Breakdown")
                st.write(result["output"])
                if st.button(f"Save {result['filename']}", key=f"save_{result['filename']}"):
                    if result['filename'] not in [app['filename'] for app in st.session_state["saved_apps"]]:
                        st.session_state["saved_apps"].append({
                            "filename": result['filename'],
                            "file_data": result['file_data']
                        })
                        st.success(f"{result['filename']} saved successfully!")

# Page: Saved Applications
elif page == "Saved Applications":
    st.title("Saved Applications")
    if st.session_state["saved_apps"]:
        for app in st.session_state["saved_apps"]:
            st.download_button(
                label=f"Download {app['filename']}",
                data=app['file_data'],
                file_name=app['filename'],
                mime="application/octet-stream"
            )
    else:
        st.write("No applications saved yet.")
