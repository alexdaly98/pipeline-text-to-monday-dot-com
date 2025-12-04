import tempfile
from pathlib import Path
import streamlit as st
import traceback

from pipeline import TimelinePipeline


@st.cache_resource
def get_pipeline() -> TimelinePipeline:
    """
    Create a single TimelinePipeline instance per Streamlit session.

    This ensures:
    - Config.validate() is called once
    - WriterClient and MondayClient are reused
    """
    return TimelinePipeline()


def run_from_csv_file(pipeline: TimelinePipeline, uploaded_file, board_name: str):
    """Save uploaded CSV to temp file and run pipeline.from_csv."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        tmp.write(uploaded_file.getvalue())
        tmp_path = tmp.name

    try:
        board_id, group_ids = pipeline.run_from_csv(tmp_path, board_name)
    finally:
        # Best-effort cleanup
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            pass

    return board_id, group_ids


def run_from_text_file(pipeline: TimelinePipeline, uploaded_file, board_name: str):
    """Read uploaded text file and run pipeline.from_text."""
    # uploaded_file is a BytesIO-like object
    content = uploaded_file.read().decode("utf-8", errors="ignore")
    board_id, group_ids = pipeline.run_from_text(content, board_name)
    return board_id, group_ids


def run_from_text_input(pipeline: TimelinePipeline, text_input: str, board_name: str):
    """Run pipeline directly from textarea input."""
    board_id, group_ids = pipeline.run_from_text(text_input, board_name)
    return board_id, group_ids


def main():
    st.set_page_config(
        page_title="Text → Monday.com Timeline",
        layout="centered",
    )

    st.title("Text → Timeline in Monday.com")
    st.write(
        "Give me a **CSV or free-form text** describing a project timeline, "
        "and I'll use **Writer + Monday.com** to create a timeline board for you."
    )

    st.markdown("---")

    # --- Board name ---
    board_name = st.text_input(
        "Board name in Monday.com",
        value="Q4 Campaign Timeline",
        placeholder="e.g. Product Launch Plan",
    )

    # --- Input type selection ---
    input_mode = st.radio(
        "Input type",
        ["CSV file", "Text file", "Direct text"],
        index=0,
        horizontal=True,
    )

    uploaded_file = None
    text_input = None

    if input_mode == "CSV file":
        uploaded_file = st.file_uploader(
            "Upload a CSV file describing the timeline",
            type=["csv"],
        )
    elif input_mode == "Text file":
        uploaded_file = st.file_uploader(
            "Upload a text file (.txt) with a project description",
            type=["txt"],
        )
    else:  # Direct text
        text_input = st.text_area(
            "Paste your project description",
            height=220,
            placeholder=(
                "Example:\n"
                "Overall Timeline: Kickoff on Sept 18, 2025. "
                "Briefing on Oct 3. Email Development: Creative starts Nov 24 through Dec 3."
            ),
        )

    st.markdown("---")

    if st.button("Create Monday.com Board"):
        # Basic validation
        if not board_name.strip():
            st.error("Please enter a board name.")
            return

        if input_mode in ["CSV file", "Text file"] and uploaded_file is None:
            st.error("Please upload a file first.")
            return

        if input_mode == "Direct text" and (not text_input or not text_input.strip()):
            st.error("Please enter some text describing your project.")
            return

        pipeline = get_pipeline()

        try:
            with st.spinner("Running pipeline and creating your Monday.com board..."):
                if input_mode == "CSV file":
                    board_id, group_ids = run_from_csv_file(
                        pipeline, uploaded_file, board_name
                    )
                elif input_mode == "Text file":
                    board_id, group_ids = run_from_text_file(
                        pipeline, uploaded_file, board_name
                    )
                else:
                    board_id, group_ids = run_from_text_input(
                        pipeline, text_input, board_name
                    )

            # --- Success UI ---
            st.success("🎉 Board creation completed successfully!")
            st.markdown(f"**Board ID:** `{board_id}`")

            if group_ids:
                st.markdown("**Groups created (key → Monday group ID):**")
                st.json(group_ids)

        except Exception as e:
            st.error(f"Pipeline failed: {e}")
            with st.expander("Show full traceback"):
                st.code(traceback.format_exc(), language="python")


if __name__ == "__main__":
    main()
