import typer

app = typer.Typer(help="Release Gate 評比工具：用同一組任務與評分表比較 AI 助手。")


@app.callback()
def main() -> None:
    pass
