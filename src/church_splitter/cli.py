import sys
import os
import argparse
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
from church_splitter.splitter import ChurchAudioSplitter, format_timestamp
from church_splitter.config import (
    DEFAULT_MODEL_SIZE,
    DEFAULT_WINDOW_SECONDS,
    DEFAULT_MIN_SERMON_MINUTES,
    DEFAULT_SPEECH_DENSITY_THRESHOLD,
    DEFAULT_GAP_TOLERANCE_SECONDS,
    DEFAULT_PADDING_SECONDS,
    find_ffmpeg
)

console = Console()

def cli_main():
    parser = argparse.ArgumentParser(
        description="Church Audio Splitter - Lossless Worship & Sermon Extractor powered by Whisper & FFmpeg"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Command: split
    split_parser = subparsers.add_parser("split", help="Analyze and split church service audio losslessly")
    split_parser.add_argument("-i", "--input", required=True, help="Path to raw service audio (.mp3 or .wav)")
    split_parser.add_argument("-o", "--output-dir", default=None, help="Directory to save split audio files (defaults to input folder / splits)")
    split_parser.add_argument("-m", "--model", default=DEFAULT_MODEL_SIZE, choices=["tiny", "base", "small", "medium"], help="Whisper model size")
    split_parser.add_argument("--min-sermon-min", type=float, default=DEFAULT_MIN_SERMON_MINUTES, help="Minimum sermon duration in minutes (default: 10)")
    split_parser.add_argument("--density-threshold", type=float, default=DEFAULT_SPEECH_DENSITY_THRESHOLD, help="Speech density threshold (default: 0.55)")
    split_parser.add_argument("--gap-tolerance", type=float, default=DEFAULT_GAP_TOLERANCE_SECONDS, help="Gap tolerance in seconds (default: 45)")
    split_parser.add_argument("--combine-worship", action="store_true", help="Also generate a combined worship file joining opening & closing worship")
    split_parser.add_argument("--export-transcript", action="store_true", default=True, help="Export sermon text transcript")

    # Command: analyze
    analyze_parser = subparsers.add_parser("analyze", help="Detect sermon timestamps and print speech density profile without cutting")
    analyze_parser.add_argument("-i", "--input", required=True, help="Path to raw service audio (.mp3 or .wav)")
    analyze_parser.add_argument("-m", "--model", default=DEFAULT_MODEL_SIZE, choices=["tiny", "base", "small", "medium"], help="Whisper model size")
    analyze_parser.add_argument("--min-sermon-min", type=float, default=DEFAULT_MIN_SERMON_MINUTES, help="Minimum sermon duration in minutes")

    # Command: ui
    ui_parser = subparsers.add_parser("ui", help="Launch the local interactive Web UI")
    ui_parser.add_argument("-p", "--port", type=int, default=8000, help="Port to run web server on (default: 8000)")
    ui_parser.add_argument("--host", default="127.0.0.1", help="Host interface (default: 127.0.0.1)")

    # Default to UI if no arguments passed
    if len(sys.argv) == 1:
        parser.print_help()
        print("\nTip: Run 'church-split ui' to start the interactive web interface, or 'church-split split -i audio.mp3'")
        return

    args = parser.parse_args()

    if args.command == "ui":
        import uvicorn
        from church_splitter.server import app
        console.print(Panel(f"[bold green]Starting Church Audio Splitter Web UI[/bold green]\nOpen [cyan]http://{args.host}:{args.port}[/cyan] in your browser.", title="Church Audio Splitter"))
        uvicorn.run(app, host=args.host, port=args.port)
        return

    elif args.command in ["split", "analyze"]:
        input_path = Path(args.input)
        if not input_path.exists():
            console.print(f"[bold red]Error: Input file not found:[/bold red] {input_path}")
            sys.exit(1)

        output_dir = Path(args.output_dir) if getattr(args, "output_dir", None) else input_path.parent / f"{input_path.stem}_splits"

        console.print(Panel(
            f"[bold cyan]Input File:[/bold cyan] {input_path.name}\n"
            f"[bold cyan]Whisper Model:[/bold cyan] {args.model}\n"
            f"[bold cyan]FFmpeg:[/bold cyan] {find_ffmpeg()}",
            title="⛪ Church Service Audio Splitter"
        ))

        splitter = ChurchAudioSplitter(model_size=args.model)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=console
        ) as progress:
            task = progress.add_task("[yellow]Initializing analysis...", total=100)

            def progress_cb(pct: float, desc: str):
                progress.update(task, completed=int(pct * 100), description=f"[yellow]{desc}")

            result = splitter.analyze_service(
                audio_path=input_path,
                min_sermon_minutes=getattr(args, "min_sermon_min", DEFAULT_MIN_SERMON_MINUTES),
                density_threshold=getattr(args, "density_threshold", DEFAULT_SPEECH_DENSITY_THRESHOLD),
                gap_tolerance=getattr(args, "gap_tolerance", DEFAULT_GAP_TOLERANCE_SECONDS),
                progress_callback=progress_cb
            )

        # Print detection results table
        table = Table(title="Detected Service Segments", show_header=True, header_style="bold magenta")
        table.add_column("Segment", style="cyan")
        table.add_column("Start Time", style="green")
        table.add_column("End Time", style="green")
        table.add_column("Duration", style="yellow")

        for w in result.worship_segments:
            table.add_row(
                f"🎵 {w['name']}",
                format_timestamp(w['start']),
                format_timestamp(w['end']),
                format_timestamp(w['end'] - w['start'])
            )

        table.add_row(
            "📖 Sermon (Spoken Message)",
            format_timestamp(result.sermon_start),
            format_timestamp(result.sermon_end),
            format_timestamp(result.sermon_duration)
        )
        console.print(table)
        console.print(f"[bold green]Confidence Score:[/bold green] {result.confidence * 100:.1f}%\n")

        if args.command == "split":
            console.print("[bold yellow]Executing lossless FFmpeg stream copy (-c copy)...[/bold yellow]")
            summary = splitter.export_splits(
                input_audio_path=input_path,
                output_dir=output_dir,
                sermon_start=result.sermon_start,
                sermon_end=result.sermon_end,
                combine_worship=args.combine_worship,
                export_transcript=args.export_transcript,
                sermon_transcript=result.sermon_transcript
            )

            console.print(Panel(
                f"[bold green]✓ Lossless split completed successfully![/bold green]\n"
                f"Files saved to: [cyan]{output_dir}[/cyan]\n\n" +
                "\n".join([f" • [bold]{f['label']}[/bold]: {f['filename']}" for f in summary['files']]),
                title="Export Results"
            ))

if __name__ == "__main__":
    cli_main()
