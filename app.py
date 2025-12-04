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


def get_attr(obj, *names, default=None):
    """Safely get an attribute or dict key from obj, trying several names."""
    for name in names:
        # dataclass / object
        if hasattr(obj, name):
            return getattr(obj, name)
        # dict-like
        if isinstance(obj, dict) and name in obj:
            return obj[name]
    return default


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


def render_timeline_preview(board_data: BoardData):
    """
    Show a user-friendly preview of the extracted timeline:
    - Bullets for groups
    - Under each, tasks with name + start/end dates
    """
    groups = getattr(board_data, "groups", []) or []
    items = getattr(board_data, "items", []) or []

    # Map group_key -> group_name
    group_key_to_name: dict[str, str] = {}
    for g in groups:
        key = get_attr(g, "key", "group_key", "id", default=None)
        name = get_attr(g, "name", "title", "label", default="Unnamed group")
        if key is not None:
            group_key_to_name[str(key)] = str(name)

    # Map group_key -> list of item dicts
    group_items: dict[str, list[dict]] = {k: [] for k in group_key_to_name}
    ungrouped: list[dict] = []

    for it in items:
        gkey = get_attr(it, "group_key", "group", "group_id", default=None)
        name = get_attr(it, "name", "title", default="Untitled task")
        start = get_attr(it, "start_date", "from", "start", default="")
        end = get_attr(it, "end_date", "to", "end", default="")

        task = {
            "name": str(name),
            "start": str(start) if start else "",
            "end": str(end) if end else "",
        }

        if gkey is not None and str(gkey) in group_items:
            group_items[str(gkey)].append(task)
        else:
            ungrouped.append(task)

    st.subheader("Detected timeline structure (from Writer AI)")

    if not group_key_to_name and not ungrouped:
        st.info("No timeline structure detected.")
        return

    # Render groups as bullets
    for gkey, gname in group_key_to_name.items():
        lines = [f"- **{gname}**"]
        tasks = group_items.get(gkey, [])
        if tasks:
            for t in tasks:
                if t["start"] or t["end"]:
                    lines.append(
                        f"  - {t['name']} — `{t['start']}` → `{t['end']}`"
                    )
                else:
                    lines.append(f"  - {t['name']}")
        else:
            lines.append("  - _No tasks detected for this group._")

        st.markdown("\n".join(lines))

    # Ungrouped tasks, if any
    if ungrouped:
        st.markdown("\n**Ungrouped tasks**")
        lines = []
        for t in ungrouped:
            if t["start"] or t["end"]:
                lines.append(f"- {t['name']} — `{t['start']}` → `{t['end']}`")
            else:
                lines.append(f"- {t['name']}")
        st.markdown("\n".join(lines))


def main():
    st.set_page_config(
        page_title="Text → Monday.com Timeline (Powered by Writer AI)",
        layout="centered",
    )

    st.title("Text → Timeline in Monday.com")
    st.markdown(
        "Turn **plain English project plans** into a structured **timeline board in Monday.com**.\n\n"
        "This app is **_powered by Writer AI_** for smart, structured timeline extraction. ✨"
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
        ["CSV file", "Text file", "Raw text"],
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
    else:  # Raw text
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

        if input_mode == "Raw text" and (not text_input or not text_input.strip()):
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

        # Show a concise, user-friendly preview (and keep it visible during Phase 2)
        render_timeline_preview(board_data)

        st.markdown("---")

        # -------------------------
        # PHASE 2 – Push to Monday.com
        # -------------------------
        with st.spinner(
            "Phase 2 – Creating your Monday.com board and pushing timeline items...\n"
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

        # Your specific board URL pattern
        board_url = f"https://writer698722.monday.com/boards/{board_id}"
        st.markdown(f"[Open the board in Monday.com]({board_url})")


if __name__ == "__main__":
    main()
