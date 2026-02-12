import gradio as gr
import pandas as pd
import os
from pathlib import Path
import re

# ────────────────────────────────────────────────
# CONFIGURATION
# ────────────────────────────────────────────────
INPUT_COLUMNS = {
    "id": ["ID", "id", "prompt_id"],
    "input": ["input", "Input", "question", "prompt"],
    "output": ["output", "Output", "response", "answer", "content"]
}

OUTPUT_COLUMNS_INTERNAL = ["id", "input", "output", "score"]   # internal working columns
DISPLAY_COLUMNS = ["ID", "Input", "Output (markdown)", "Score"]  # displayed columns

SAVE_PATH = Path("evaluation_score")
SAVE_PATH.mkdir(exist_ok=True)

DRIVE_PATH = Path("/content/drive/MyDrive/OSAS/osas_chat_bot/manual_test")

# ────────────────────────────────────────────────
# Helper functions
# ────────────────────────────────────────────────
def find_column(df: pd.DataFrame, possible_names: list[str]) -> str | None:
    """Find first matching column name (case-insensitive)"""
    cols_lower = {c.lower(): c for c in df.columns}
    for name in possible_names:
        if name.lower() in cols_lower:
            return cols_lower[name.lower()]
    return None


def load_data(file_obj):
    if file_obj is None:
        return None, "Please upload a file first", None, None, None

    try:
        filepath = file_obj.name
        original_filename = os.path.basename(filepath)
        name_no_ext, _ = os.path.splitext(original_filename)

        df = pd.read_excel(filepath, engine="openpyxl")

        id_col    = find_column(df, INPUT_COLUMNS["id"])
        input_col = find_column(df, INPUT_COLUMNS["input"])
        output_col = find_column(df, INPUT_COLUMNS["output"])

        missing = []
        if not id_col:    missing.append("ID")
        if not input_col: missing.append("input")
        if not output_col: missing.append("output")

        if missing:
            return None, f"Missing required columns: {', '.join(missing)}", None, None, None

        rename_map = {}
        if id_col:    rename_map[id_col]    = "id"
        if input_col: rename_map[input_col] = "input"
        if output_col: rename_map[output_col] = "output"

        df = df.rename(columns=rename_map)

        if "score" not in df.columns:
            df["score"] = ""

        df = df[[c for c in OUTPUT_COLUMNS_INTERNAL if c in df.columns]]

        start_id = "unknown"
        end_id   = "unknown"
        if "id" in df.columns and not df["id"].empty:
            start_id = str(df["id"].min())
            end_id   = str(df["id"].max())

        return df, f"Loaded {len(df)} rows from {original_filename}", start_id, end_id, original_filename

    except Exception as e:
        return None, f"Error reading file: {str(e)}", None, None, None


def prepare_display_df(internal_df):
    if internal_df is None or internal_df.empty:
        return pd.DataFrame(columns=DISPLAY_COLUMNS)

    df = internal_df.copy()
    rename_map = {
        "id":     "ID",
        "input":  "Input",
        "output": "Output (markdown)",
        "score":  "Score"
    }
    df = df.rename(columns=rename_map)

    for col in DISPLAY_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    return df[DISPLAY_COLUMNS]


def get_current_df_from_table(display_df, internal_df):
    if display_df is None or internal_df is None:
        return internal_df

    updated_df = internal_df.copy()

    display_df = display_df.rename(columns={
        "ID":                "id",
        "Input":             "input",
        "Output (markdown)": "output",
        "Score":             "score"
    })

    if "id" not in display_df.columns or "score" not in display_df.columns:
        return updated_df

    score_dict = {}
    for _, row in display_df.iterrows():
        if pd.notna(row["id"]):
            score_dict[str(row["id"])] = row["score"] if pd.notna(row["score"]) else ""

    updated_df["score"] = updated_df["id"].astype(str).map(score_dict).combine_first(updated_df["score"])
    return updated_df


def sanitize_filename(name: str) -> str:
    """Remove/replace unsafe characters for filenames"""
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = re.sub(r'\s+', '_', name.strip())
    return name


def get_output_path(tester, user, model_name, original_filename):
    tester     = sanitize_filename((tester or "tester").strip() or "tester")
    user       = sanitize_filename((user or "user").strip() or "user")
    model_name = sanitize_filename((model_name or "unknown-model").strip())

    original_filename = sanitize_filename(original_filename)

    # Build folder structure
    base_folder = DRIVE_PATH / tester / user / model_name
    base_folder.mkdir(parents=True, exist_ok=True)

    return base_folder / original_filename


def save_data(internal_df, tester, user, model_name, original_filename):
    if internal_df is None or internal_df.empty:
        return "No data to save", None

    try:
        df_to_save = internal_df[["id", "score"]].copy()
        df_to_save = df_to_save.rename(columns={"id": "ID"})

        output_path = get_output_path(tester, user, model_name, original_filename)

        df_to_save.to_excel(
            output_path,
            index=False,
            engine="openpyxl"
        )

        msg = (
            f"Saved **{output_path.name}**\n"
            f"({len(df_to_save)} rows — ID + score only)\n"
            f"→ {output_path.parent}"
        )
        return msg, str(output_path)

    except Exception as e:
        return f"Save failed: {str(e)}", None


# ────────────────────────────────────────────────
# Gradio Interface
# ────────────────────────────────────────────────
with gr.Blocks(title="Excel Score & Overwrite Tool") as demo:
    gr.Markdown("# Excel Scoring Tool")
    gr.Markdown(
        "Upload .xlsx → edit **Score** column → save **ID + score only**\n\n"
        "Saved to: `tester / user / model / original-filename.xlsx`"
    )

    with gr.Row():
        with gr.Column(scale=1):
            tester_input = gr.Textbox(
                label="Tester / Reviewer",
                placeholder="e.g. alexk, reviewer01",
                max_lines=1
            )
            user_input = gr.Textbox(
                label="User / Subject / Batch",
                placeholder="e.g. userA, studentB, batch2025",
                max_lines=1
            )
            model_input = gr.Textbox(
                label="Model name",
                placeholder="gpt-4o, claude-3.5-sonnet, gemma-2-27b, ...",
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

            status = gr.Textbox(label="Status", interactive=False, lines=4)
            download_file = gr.File(
                label="Download result (ID + score only)",
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
                height=700
            )

    # States – now include original_filename
    df_state           = gr.State(None)
    start_id_state     = gr.State(None)
    end_id_state       = gr.State(None)
    filename_state     = gr.State(None)   # ← new

    # ── Load flow ───────────────────────────────────────
    def load_wrapper(file_obj):
        df, msg, start, end, orig_fn = load_data(file_obj)
        return df, msg, start, end, orig_fn

    load_btn.click(
        fn=load_wrapper,
        inputs=file_input,
        outputs=[df_state, status, start_id_state, end_id_state, filename_state]
    ).then(
        fn=prepare_display_df,
        inputs=df_state,
        outputs=data_table
    )

    # ── Save flow ───────────────────────────────────────
    def save_flow(display_df, internal_df, tester, user, model_name, orig_filename):
        updated_internal = get_current_df_from_table(display_df, internal_df)
        msg, filepath = save_data(updated_internal, tester, user, model_name, orig_filename)
        return (
            updated_internal,
            msg,
            filepath,
            prepare_display_df(updated_internal),
            gr.update(value=filepath, visible=bool(filepath))
        )

    save_btn.click(
        fn=save_flow,
        inputs=[data_table, df_state, tester_input, user_input, model_input, filename_state],
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
        share=False
    )
