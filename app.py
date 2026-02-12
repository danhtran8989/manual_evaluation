import gradio as gr
import pandas as pd
import os
from pathlib import Path

# ────────────────────────────────────────────────
# CONFIGURATION
# ────────────────────────────────────────────────
INPUT_COLUMNS = {
    "id": ["ID", "id", "prompt_id"],
    "input": ["input", "Input", "question", "prompt"],
    "output": ["output", "Output", "response", "answer", "content"]
}

OUTPUT_COLUMNS_INTERNAL = ["id", "input", "output", "score"]     # columns we work with internally
DISPLAY_COLUMNS = ["ID", "Input", "Output (markdown)", "Score"]  # what user sees

DEFAULT_PREFIX = "Danh"
SAVE_PATH = Path("evaluation_score")               # ← folder where marked files will be saved
SAVE_PATH.mkdir(exist_ok=True)          # create folder if it doesn't exist
DRIVE_PATH = "/content/drive/MyDrive/OSAS/osas_chat_bot/manual_test"

# ────────────────────────────────────────────────
def find_column(df: pd.DataFrame, possible_names: list[str]) -> str | None:
    """Find the first matching column name (case-insensitive)"""
    cols_lower = {c.lower(): c for c in df.columns}
    for name in possible_names:
        if name.lower() in cols_lower:
            return cols_lower[name.lower()]
    return None


def load_data(file_obj):
    if file_obj is None:
        return None, "Please upload a file first", None, None

    try:
        df = pd.read_excel(file_obj.name, engine="openpyxl")

        # Try to find required columns using flexible matching
        id_col    = find_column(df, INPUT_COLUMNS["id"])
        input_col = find_column(df, INPUT_COLUMNS["input"])
        output_col = find_column(df, INPUT_COLUMNS["output"])

        missing = []
        if not id_col:    missing.append("ID")
        if not input_col: missing.append("input")
        if not output_col: missing.append("output")

        if missing:
            return None, f"Missing required columns: {', '.join(missing)}", None, None

        # Rename to internal standard names
        rename_map = {}
        if id_col:    rename_map[id_col]    = "id"
        if input_col: rename_map[input_col] = "input"
        if output_col: rename_map[output_col] = "output"

        df = df.rename(columns=rename_map)

        # Add mark column if missing
        if "mark" not in df.columns:
            df["mark"] = ""

        # Keep only desired columns
        df = df[[c for c in OUTPUT_COLUMNS_INTERNAL if c in df.columns]]

        start_id = "unknown"
        end_id = "unknown"
        if "id" in df.columns and not df["id"].empty:
            start_id = str(df["id"].min())
            end_id = str(df["id"].max())

        filename = os.path.basename(file_obj.name)
        return df, f"Loaded {len(df)} rows from {filename}", start_id, end_id

    except Exception as e:
        return None, f"Error reading file: {str(e)}", None, None


def prepare_display_df(internal_df):
    if internal_df is None or internal_df.empty:
        return pd.DataFrame(columns=DISPLAY_COLUMNS)

    df = internal_df.copy()

    # Rename to display names
    rename_map = {
        "id": "ID",
        "input": "Input",
        "output": "Output (markdown)",
        "mark": "Mark"
    }
    df = df.rename(columns=rename_map)

    # Make sure all display columns exist
    for col in DISPLAY_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    return df[DISPLAY_COLUMNS]


def get_current_df_from_table(display_df, internal_df):
    """
    Merge updated marks from the displayed table back into the internal dataframe
    """
    if display_df is None or internal_df is None:
        return internal_df

    # Make a safe copy
    updated_df = internal_df.copy()

    # Rename display columns back to internal names
    display_df = display_df.rename(columns={
        "ID": "id",
        "Input": "input",
        "Output (markdown)": "output",
        "Mark": "mark"
    })

    # We only care about id → mark mapping
    if "id" not in display_df.columns or "mark" not in display_df.columns:
        return updated_df

    # Create mapping from displayed table
    mark_dict = {}
    for _, row in display_df.iterrows():
        if pd.notna(row["id"]):
            mark_dict[str(row["id"])] = row["mark"] if pd.notna(row["mark"]) else ""

    # Apply marks to internal df (preserve existing if no new value)
    updated_df["mark"] = updated_df["id"].astype(str).map(mark_dict).combine_first(updated_df["mark"])

    return updated_df


def get_output_filename(tester, user, start_id, end_id):
    tester = (tester or "tester").strip() or "tester"
    user   = (user   or "user").strip()   or "user"
    user = user.replace(" ", "_")
    start_id = start_id or "unknown"
    end_id   = end_id   or "unknown"

    return f"{tester}--{user}--{start_id}--{end_id}.xlsx"


def save_data(internal_df, tester, user, start_id, end_id):
    if internal_df is None or internal_df.empty:
        return "No data to save", None

    try:
        df_to_save = internal_df[["id", "mark"]].copy()
        df_to_save = df_to_save.rename(columns={"id": "ID"})

        filename = get_output_filename(tester, user, start_id, end_id)
        if DRIVE_PATH:
            output_path = DRIVE_PATH / filename
        else:
            output_path = SAVE_PATH / filename

        # Save (overwrites if exists)
        df_to_save.to_excel(
            output_path,
            index=False,
            engine="openpyxl"
        )

        msg = f"Saved **{filename}** ({len(df_to_save)} rows — ID + mark only)"
        return msg, str(output_path)

    except Exception as e:
        return f"Save failed: {str(e)}", None


# ────────────────────────────────────────────────
# Interface
# ────────────────────────────────────────────────
with gr.Blocks(title="Excel Mark & Overwrite Tool") as demo:
    gr.Markdown("# Excel Marking Tool")
    gr.Markdown(
        "Upload .xlsx → edit **Mark** column → save **ID + mark only**\n\n"
    )

    with gr.Row():
        with gr.Column(scale=1):
            tester_input = gr.Textbox(
                label="Tester / Reviewer",
                placeholder="your name or ID (e.g. alexk, reviewer01)",
                max_lines=1
            )

            user_input = gr.Textbox(
                label="User / Subject",
                placeholder="e.g. userA, studentB, batch2025",
                max_lines=1
            )

            file_input = gr.File(
                label="Upload your .xlsx file",
                file_types=[".xlsx"],
                type="filepath"
            )

            with gr.Row():
                load_btn = gr.Button("Load file", variant="primary")
                save_btn = gr.Button("Save", variant="secondary")

            status = gr.Textbox(label="Status", interactive=False, lines=3)

            download_file = gr.File(
                label="Download result (ID + mark only)",
                file_types=[".xlsx"],
                interactive=False,
                visible=False
            )

        with gr.Column(scale=7):
            data_table = gr.Dataframe(
                label="Data (Output rendered as Markdown)",
                headers=DISPLAY_COLUMNS,
                datatype=["str", "str", "markdown", "str"],
                interactive=True,
                wrap=True,
            )

    # States
    df_state = gr.State(None)
    start_id_state = gr.State(None)
    end_id_state = gr.State(None)

    # ── Load flow ───────────────────────────────────────
    load_btn.click(
        fn=load_data,
        inputs=file_input,
        outputs=[df_state, status, start_id_state, end_id_state]
    ).then(
        fn=prepare_display_df,
        inputs=df_state,
        outputs=data_table
    )

    # ── Save flow ───────────────────────────────────────
    def save_flow(display_df, internal_df, tester, user, start_id, end_id):
        updated_internal = get_current_df_from_table(display_df, internal_df)
        msg, filepath = save_data(updated_internal, tester, user, start_id, end_id)

        return (
            updated_internal,                    # df_state
            msg,                                 # status
            filepath,                            # download_file value
            prepare_display_df(updated_internal),# refresh table
            gr.update(value=filepath, visible=bool(filepath))
        )

    save_btn.click(
        fn=save_flow,
        inputs=[data_table, df_state, tester_input, user_input, start_id_state, end_id_state],
        outputs=[df_state, status, download_file, data_table, download_file]
    )

    # Ctrl + S support
    demo.load(None, js="""
    () => {
        window.addEventListener('keydown', function(e) {
            if (e.ctrlKey && e.key === 's') {
                e.preventDefault();
                document.querySelector('button:has(span:contains("Save"))')?.click();
            }
        });
    }
    """)


if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7890,
        debug=True,
        share=True
    )
