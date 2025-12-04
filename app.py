from pathlib import Path
import tempfile

import streamlit as st

from config import Config
from writer_client import WriterClient
from monday_client import MondayClient
from models import BoardData


@st.cache_resource
def get_clients() -> tuple[WriterClient, MondayClient]:
    """
    Initialize and cache Writer + Monday clients for the Streamlit session.

    Config.validate() is called once here.
    """
    Config.validate()
    writer_client = WriterClient()
    monday_client = MondayClient()
    return writer_client, monday_client


def normalize_list_of_objects(objs):
    """Convert list of dataclass/objects/dicts into list of dicts for display."""
    if not objs:
        return []

    if isinstance(objs[0], dict):
        return objs

    try:
        from dataclasses import is_dataclass, asdict

        if is_dataclass(objs[0]):
            return [asdict(o) for o in objs]
    except Exception:
        pass

    # Fallback: use __dict__
    normalized = []
    for o in objs:
        if hasattr(o, "__dict__"):
            normalized.append({k: v for k, v in o.__dict__.items() if not k.startswith("_")})
        else:
            normalized.append({"value": str(o)})
    return normalized


def extract_board_data_from_csv(writer_client: WriterClient, uploaded_file) -> BoardData:
    """Save uploaded CSV to a temp file, call Writer extraction, then cleanup."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        tmp.write(uploaded_file.getvalue())
        tmp_path = tmp.name

    try:
        board_data = writer_client.extract_from_csv(tmp_path)
    finally:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            pass

    return board_data


def extract_board_data_from_text_file(writer_client: WriterClient, uploaded_file) -> BoardData:
    """Read uploaded text file, call Writer extraction."""
    content = uploaded_file.read().decode("utf-8", errors="ignore")
    return writer_client.extract_from_text(content)


def extract_board_data_from_text_input(writer_client: WriterClient, text_input: str) -> BoardData:
    """Call Writer extraction directly from textarea."""
    return writer_client.extract_from_text(text_input)


def main():
    st.set_page_config(
        page_title="Text → Monday.com Timeline (Powered by Writer AI)",
        layout="centered",
    )

    st.title("Text → Timeline in Monday.com")
    st.markdown(
        "Turn **plain English project plans** into a structured **timeline board in Monday.com**.\n\n"
        "**Powered by _Writer AI_ for structured timeline extraction.** 💡"
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

    run_clicked = st.button("Create Monday.com Timeline Board")

    if run_clicked:
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

        writer_client, monday_client = get_clients()

        # -------------------------
        # PHASE 1 – Writer AI extraction
        # -------------------------
        with st.spinner("Phase 1 – Writer AI is extracting a structured timeline from your input..."):
            try:
                if input_mode == "CSV file":
                    board_data = extract_board_data_from_csv(writer_client, uploaded_file)
                elif input_mode == "Text file":
                    board_data = extract_board_data_from_text_file(writer_client, uploaded_file)
                else:
                    board_data = extract_board_data_from_text_input(writer_client, text_input)
            except Exception as e:
                st.error(f"Writer extraction failed: {e}")
                return

        st.success("Phase 1 complete – Writer AI successfully extracted the timeline ✅")

        # Show extracted groups & items (visible now, and will stay visible during Phase 2)
        groups = normalize_list_of_objects(getattr(board_data, "groups", []))
        items = normalize_list_of_objects(getattr(board_data, "items", []))

        st.subheader("Detected groups (from Writer AI)")
        if groups:
            st.dataframe(groups, use_container_width=True)
        else:
            st.info("No groups detected.")

        st.subheader("Detected items (from Writer AI)")
        if items:
            st.dataframe(items, use_container_width=True)
        else:
            st.info("No items detected.")

        st.markdown("---")

        # -------------------------
        # PHASE 2 – Push to Monday.com
        # -------------------------
        with st.spinner(
            "Phase 2 – Creating your Monday.com board and pushing timeline items...\n"
            "(You can already review the extracted data above while this runs.)"
        ):
            try:
                board_id, group_ids = monday_client.create_board_from_data(
                    board_name,
                    board_data
                )
            except Exception as e:
                st.error(f"Failed to create board in Monday.com: {e}")
                return

        st.success("🎉 Timeline successfully pushed to Monday.com!")

        # Board info + link
        st.markdown(f"**Board ID:** `{board_id}`")

        # Generic board URL pattern (user may need to select account if they have multiple)
        board_url = f"https://app.monday.com/boards/{board_id}"
        st.markdown(f"[Open the board in Monday.com]({board_url})")

        # If you still want to expose group IDs mapping (but not raw logs)
        if group_ids:
            with st.expander("Show group mapping (group_key → Monday group ID)"):
                st.json(group_ids)


if __name__ == "__main__":
    main()
