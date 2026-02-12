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
OUTPUT_COLUMNS_INTERNAL = ["id", "input", "output", "score"]
DISPLAY_COLUMNS = ["ID", "Input", "Output (markdown)", "Score"]
SAVE_PATH = Path("evaluation_score")
SAVE_PATH.mkdir(exist_ok=True)
# ────────────────────────────────────────────────
# Helper functions
# ────────────────────────────────────────────────
def find_column(df: pd.DataFrame, possible_names: list[str]) -> str | None:
    cols_lower = {c.lower(): c for c in df.columns}
    for name in possible_names:
        if name.lower() in cols_lower:
            return cols_lower[name.lower()]
    return None
def load_data(file_obj, tester, user, model_name, save_dir):
    if file_obj is None:
        return None, "Please upload a file", None, None, None
    try:
        filepath = file_obj.name
        original_filename = os.path.basename(filepath)
        df = pd.read_excel(filepath, engine="openpyxl")
        id_col    = find_column(df, INPUT_COLUMNS["id"])
        input_col  = find_column(df, INPUT_COLUMNS["input"])
        output_col = find_column(df, INPUT_COLUMNS["output"])
        missing = [n for n, c in [("ID", id_col), ("input", input_col), ("output", output_col)] if not c]
        if missing:
            return None, f"Missing required columns: {', '.join(missing)}", None, None, None
        rename_map = {}
        if id_col:    rename_map[id_col]    = "id"
        if input_col:  rename_map[input_col]  = "input"
        if output_col: rename_map[output_col] = "output"
        df = df.rename(columns=rename_map)
        if "score" not in df.columns:
            df["score"] = pd.NA
        df = df[[c for c in OUTPUT_COLUMNS_INTERNAL if c in df.columns]]
        start_id = str(df["id"].min()) if "id" in df.columns and not df["id"].empty else "unknown"
        end_id   = str(df["id"].max()) if "id" in df.columns and not df["id"].empty else "unknown"
        # Merge previous scores if exist
        output_path = get_output_path(tester, user, model_name, original_filename, save_dir)
        if output_path.exists():
            try:
                score_df = pd.read_excel(output_path, engine="openpyxl")
                if "ID" in score_df.columns and "score" in score_df.columns:
                    score_df = score_df.rename(columns={"ID": "id"})
                    df = df.merge(score_df[["id", "score"]], on="id", how="left", suffixes=("", "_old"))
                    df["score"] = df["score_old"].combine_first(df["score"])
                    df.drop(columns=["score_old"], errors="ignore", inplace=True)
            except:
                pass
        return df, f"Loaded {len(df)} rows from {original_filename}", start_id, end_id, original_filename
    except Exception as e:
        return None, f"Error reading file: {str(e)}", None, None, None
def prepare_display_df(internal_df):
    if internal_df is None or internal_df.empty:
        return pd.DataFrame(columns=DISPLAY_COLUMNS)
    df = internal_df.rename(columns={
        "id": "ID",
        "input": "Input",
        "output": "Output (markdown)",
        "score": "Score"
    }).reindex(columns=DISPLAY_COLUMNS, fill_value="")
    return df
def get_current_df_from_table(display_df, internal_df):
    if display_df is None or internal_df is None:
        return internal_df
    updated = internal_df.copy()
    score_map = dict(zip(display_df["ID"].astype(str), display_df["Score"].astype(str).replace({"nan": "", "<NA>": ""})))
    updated["score"] = updated["id"].astype(str).map(score_map).combine_first(updated["score"])
    return updated
def sanitize_filename(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', '_', name or "unnamed")
    name = re.sub(r'\s+', '_', name.strip())
    return name
def get_output_path(tester, user, model_name, original_filename, save_dir):
    parts = [tester or "tester", user or "user", model_name or "model"]
    folder = Path(save_dir) / "/".join(sanitize_filename(p) for p in parts)
    folder.mkdir(parents=True, exist_ok=True)
    return folder / sanitize_filename(original_filename)
def save_data(internal_df, tester, user, model_name, original_filename, save_dir):
    if internal_df is None or internal_df.empty:
        return "No data to save", None
    try:
        df_save = internal_df[["id", "score"]].rename(columns={"id": "ID"})
        path = get_output_path(tester, user, model_name, original_filename, save_dir)
        df_save.to_excel(path, index=False, engine="openpyxl")
        msg = f"Saved **{path.name}** ({len(df_save)} rows)\n→ {path.parent}"
        return msg, str(path)
    except Exception as e:
        return f"Save failed: {str(e)}", None
# ────────────────────────────────────────────────
# Gradio UI
# ────────────────────────────────────────────────
custom_css = """
#save-btn {
    background-color: #f97316 !important;
    color: green !important;
    border: 1px solid #ea580c !important;
    font-weight: 600 !important;
}
#save-btn:hover {
    background-color: #ea580c !important;
}
#main-table {
    height: 82vh !important;
    min-height: 600px !important;
    max-height: 92vh !important;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    overflow: hidden;
}
.gradio-container {
    max-width: 98% !important;
}
"""
with gr.Blocks(title="Excel Scoring Tool", css=custom_css) as demo:
    gr.Markdown("# Excel Scoring Tool")
    gr.Markdown("Fill in Tester, User/Batch and Model → then upload .xlsx file → edit scores → save")
    with gr.Row():
        with gr.Column(scale=1):
            tester_input = gr.Textbox(label="Tester / Reviewer", placeholder="e.g. alexk, reviewer01", max_lines=1)
            user_input   = gr.Textbox(label="User / Subject / Batch", placeholder="e.g. userA, batch2025", max_lines=1)
            model_input  = gr.Textbox(label="Model name", placeholder="gpt-4o, claude-3.5-sonnet, ...", max_lines=1)
            save_dir_input = gr.Textbox(label="Save Directory", value="/content/drive/MyDrive/OSAS/osas_chat_bot/manual_test", max_lines=1)
            file_input = gr.File(
                label="Upload your .xlsx file",
                file_types=[".xlsx"],
                type="filepath",
                interactive=False   # disabled until fields are filled
            )
            save_btn = gr.Button("Save", elem_id="save-btn")
            status = gr.Textbox(label="Status", interactive=False, lines=4)
            download_file = gr.File(label="Download result (ID + score)", interactive=False, visible=False)
        with gr.Column(scale=7):
            data_table = gr.Dataframe(
                label="Data (Output rendered as Markdown)",
                headers=DISPLAY_COLUMNS,
                datatype=["str", "str", "markdown", "str"],
                interactive=True,
                wrap=True,
                elem_id="main-table",
            )
    # ─── States ────────────────────────────────────────────────
    df_state       = gr.State(None)
    filename_state = gr.State(None)
    # ─── Enable/disable upload when fields change ──────────────
    def update_file_interactive(t, u, m):
        all_filled = bool(t and t.strip() and u and u.strip() and m and m.strip())
        return gr.update(interactive=all_filled)
    for comp in [tester_input, user_input, model_input]:
        comp.change(
            update_file_interactive,
            inputs=[tester_input, user_input, model_input],
            outputs=file_input
        )
    # ─── Load file ─────────────────────────────────────────────
    def load_wrapper(file_obj, tester, user, model, save_dir):
        if not all(x and str(x).strip() for x in [tester, user, model]):
            return None, "Please fill Tester, User/Batch and Model first", None
        df, msg, start, end, fname = load_data(file_obj, tester, user, model, save_dir)
        return df, msg, fname
    file_input.change(
        load_wrapper,
        inputs=[file_input, tester_input, user_input, model_input, save_dir_input],
        outputs=[df_state, status, filename_state]
    ).then(
        prepare_display_df,
        inputs=df_state,
        outputs=data_table
    )
    # ─── Save ──────────────────────────────────────────────────
    def on_save(display_df, internal_df, tester, user, model, fname, save_dir):
        if internal_df is None:
            return None, "No data loaded", None, None, gr.skip()
        updated = get_current_df_from_table(display_df, internal_df)
        msg, path = save_data(updated, tester, user, model, fname, save_dir)
        return (
            updated,
            msg,
            path,
            prepare_display_df(updated),
            gr.update(value=path, visible=bool(path))
        )
    save_btn.click(
        on_save,
        inputs=[data_table, df_state, tester_input, user_input, model_input, filename_state, save_dir_input],
        outputs=[df_state, status, download_file, data_table, download_file]
    )
    # Ctrl+S support
    demo.load(None, js="""
    () => {
        window.addEventListener('keydown', e => {
            if (e.ctrlKey && e.key === 's') {
                e.preventDefault();
                document.querySelector('#save-btn')?.click();
            }
        });
    }
    """)
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--share", action="store_true",
                        help="Launch with public share link (Gradio)")
    
    args = parser.parse_args()

    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        debug=True,
        share=args.share     # ← will be True only if --share was passed
    )
