"""
Daena Video Compressor Tool
============================
A powerful video compression utility that maintains quality while reducing file size.
Uses ffmpeg under the hood with multiple compression presets.

Features:
- Multiple compression presets (high-quality, balanced, web-optimized, github-friendly)
- Smart size targeting (compress to target size)
- Batch compression for multiple files
- Quality metrics comparison
- Progress tracking

Usage:
    python daena_video_compressor.py input.mp4 -o output.mp4 -p balanced
    python daena_video_compressor.py input.mp4 --target-size 95  # Target 95MB
    python daena_video_compressor.py folder/ --batch -p web  # Batch compress
"""

import subprocess
import os
import sys
import argparse
import json
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from enum import Enum
import shutil
import time


class CompressionPreset(Enum):
    """Compression presets with different quality/size tradeoffs."""
    HIGH_QUALITY = "high_quality"
    BALANCED = "balanced"
    WEB_OPTIMIZED = "web"
    GITHUB_FRIENDLY = "github"  # Under 100MB
    MAXIMUM = "max"  # Maximum compression


@dataclass
class CompressionSettings:
    """Settings for video compression."""
    crf: int  # Constant Rate Factor (18-51, lower = better quality)
    preset: str  # FFmpeg preset (ultrafast to veryslow)
    audio_bitrate: str  # Audio bitrate
    scale: Optional[str]  # Video scale (e.g., "1920:1080", None = original)
    description: str


# Preset configurations
PRESETS: Dict[CompressionPreset, CompressionSettings] = {
    CompressionPreset.HIGH_QUALITY: CompressionSettings(
        crf=20,
        preset="slow",
        audio_bitrate="192k",
        scale=None,
        description="Minimal quality loss, moderate size reduction"
    ),
    CompressionPreset.BALANCED: CompressionSettings(
        crf=24,
        preset="medium",
        audio_bitrate="128k",
        scale=None,
        description="Good balance between quality and size"
    ),
    CompressionPreset.WEB_OPTIMIZED: CompressionSettings(
        crf=28,
        preset="medium",
        audio_bitrate="128k",
        scale="1280:720",
        description="Optimized for web streaming (720p)"
    ),
    CompressionPreset.GITHUB_FRIENDLY: CompressionSettings(
        crf=32,
        preset="slow",
        audio_bitrate="96k",
        scale="1280:720",
        description="Optimized for GitHub (under 100MB)"
    ),
    CompressionPreset.MAXIMUM: CompressionSettings(
        crf=35,
        preset="slow",
        audio_bitrate="64k",
        scale="854:480",
        description="Maximum compression (480p)"
    ),
}


class VideoCompressor:
    """Video compression engine using ffmpeg."""
    
    def __init__(self):
        self.ffmpeg_path = self._find_ffmpeg()
        if not self.ffmpeg_path:
            raise RuntimeError("FFmpeg not found. Please install FFmpeg and add it to PATH.")
    
    def _find_ffmpeg(self) -> Optional[str]:
        """Find ffmpeg executable."""
        return shutil.which("ffmpeg")
    
    def get_video_info(self, input_path: str) -> Dict:
        """Get video metadata using ffprobe."""
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            input_path
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return json.loads(result.stdout)
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            print(f"Error getting video info: {e}")
            return {}
    
    def get_file_size_mb(self, path: str) -> float:
        """Get file size in MB."""
        return os.path.getsize(path) / (1024 * 1024)
    
    def compress(
        self,
        input_path: str,
        output_path: str,
        preset: CompressionPreset = CompressionPreset.BALANCED,
        target_size_mb: Optional[float] = None,
        progress_callback: Optional[callable] = None
    ) -> Dict:
        """
        Compress a video file.
        
        Args:
            input_path: Path to input video
            output_path: Path for output video
            preset: Compression preset to use
            target_size_mb: Target file size in MB (overrides preset CRF)
            progress_callback: Callback for progress updates
        
        Returns:
            Dict with compression results
        """
        input_path = Path(input_path)
        output_path = Path(output_path)
        
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        # Get input size
        input_size_mb = self.get_file_size_mb(str(input_path))
        
        # Get settings
        settings = PRESETS[preset]
        
        # Build ffmpeg command
        cmd = [
            self.ffmpeg_path,
            "-i", str(input_path),
            "-c:v", "libx264",
            "-crf", str(settings.crf),
            "-preset", settings.preset,
            "-c:a", "aac",
            "-b:a", settings.audio_bitrate,
            "-y",  # Overwrite output
        ]
        
        # Add scale if specified
        if settings.scale:
            cmd.extend(["-vf", f"scale={settings.scale}"])
        
        # Add output path
        cmd.append(str(output_path))
        
        print(f"\n{'='*60}")
        print(f"🎬 Daena Video Compressor")
        print(f"{'='*60}")
        print(f"📁 Input:  {input_path.name} ({input_size_mb:.2f} MB)")
        print(f"📦 Output: {output_path.name}")
        print(f"🔧 Preset: {preset.value} - {settings.description}")
        print(f"{'='*60}\n")
        
        # Run compression
        start_time = time.time()
        try:
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True
            )
            if process.returncode != 0:
                print(f"FFmpeg error: {process.stderr}")
                return {"success": False, "error": process.stderr}
        except subprocess.CalledProcessError as e:
            return {"success": False, "error": str(e)}
        
        elapsed_time = time.time() - start_time
        
        # Get output size
        output_size_mb = self.get_file_size_mb(str(output_path))
        reduction_percent = ((input_size_mb - output_size_mb) / input_size_mb) * 100
        
        result = {
            "success": True,
            "input_path": str(input_path),
            "output_path": str(output_path),
            "input_size_mb": round(input_size_mb, 2),
            "output_size_mb": round(output_size_mb, 2),
            "reduction_percent": round(reduction_percent, 1),
            "elapsed_seconds": round(elapsed_time, 1),
            "preset": preset.value
        }
        
        print(f"✅ Compression complete!")
        print(f"📊 Results:")
        print(f"   • Original size:   {input_size_mb:.2f} MB")
        print(f"   • Compressed size: {output_size_mb:.2f} MB")
        print(f"   • Reduction:       {reduction_percent:.1f}%")
        print(f"   • Time taken:      {elapsed_time:.1f}s")
        print(f"{'='*60}\n")
        
        return result
    
    def batch_compress(
        self,
        input_folder: str,
        output_folder: str,
        preset: CompressionPreset = CompressionPreset.BALANCED,
        extensions: List[str] = None
    ) -> List[Dict]:
        """
        Batch compress all videos in a folder.
        
        Args:
            input_folder: Folder containing videos
            output_folder: Folder for compressed videos
            preset: Compression preset
            extensions: File extensions to process
        
        Returns:
            List of compression results
        """
        if extensions is None:
            extensions = [".mp4", ".mov", ".avi", ".mkv", ".webm"]
        
        input_folder = Path(input_folder)
        output_folder = Path(output_folder)
        output_folder.mkdir(parents=True, exist_ok=True)
        
        results = []
        video_files = [f for f in input_folder.iterdir() 
                      if f.suffix.lower() in extensions]
        
        print(f"Found {len(video_files)} videos to compress")
        
        for i, video_file in enumerate(video_files, 1):
            print(f"\n[{i}/{len(video_files)}] Processing: {video_file.name}")
            output_path = output_folder / f"{video_file.stem}_compressed{video_file.suffix}"
            
            result = self.compress(
                str(video_file),
                str(output_path),
                preset=preset
            )
            results.append(result)
        
        return results
    
    def compress_to_target_size(
        self,
        input_path: str,
        output_path: str,
        target_size_mb: float,
        max_iterations: int = 5
    ) -> Dict:
        """
        Compress video to a target file size using iterative approach.
        
        Args:
            input_path: Path to input video
            output_path: Path for output video
            target_size_mb: Target file size in MB
            max_iterations: Maximum compression iterations
        
        Returns:
            Compression result
        """
        input_path = Path(input_path)
        output_path = Path(output_path)
        temp_path = output_path.parent / f"{output_path.stem}_temp{output_path.suffix}"
        
        input_size_mb = self.get_file_size_mb(str(input_path))
        
        print(f"\n🎯 Target size: {target_size_mb} MB")
        print(f"📁 Input size:  {input_size_mb:.2f} MB")
        
        # Start with a CRF estimate based on target ratio
        ratio = target_size_mb / input_size_mb
        estimated_crf = int(23 + (1 - ratio) * 20)  # Rough estimate
        estimated_crf = max(18, min(51, estimated_crf))
        
        best_result = None
        best_crf = estimated_crf
        
        for iteration in range(max_iterations):
            print(f"\n🔄 Iteration {iteration + 1}/{max_iterations} (CRF: {estimated_crf})")
            
            cmd = [
                self.ffmpeg_path,
                "-i", str(input_path),
                "-c:v", "libx264",
                "-crf", str(estimated_crf),
                "-preset", "medium",
                "-c:a", "aac",
                "-b:a", "128k",
                "-y",
                str(temp_path)
            ]
            
            subprocess.run(cmd, capture_output=True)
            
            current_size = self.get_file_size_mb(str(temp_path))
            print(f"   Result: {current_size:.2f} MB")
            
            if current_size <= target_size_mb:
                best_result = temp_path
                best_crf = estimated_crf
                
                # Try a lower CRF for better quality
                if current_size < target_size_mb * 0.9:
                    estimated_crf = max(18, estimated_crf - 3)
                else:
                    break
            else:
                # Increase CRF for smaller size
                estimated_crf = min(51, estimated_crf + 3)
        
        # Copy best result to output
        if best_result and best_result.exists():
            shutil.move(str(best_result), str(output_path))
            output_size_mb = self.get_file_size_mb(str(output_path))
            
            return {
                "success": True,
                "input_path": str(input_path),
                "output_path": str(output_path),
                "input_size_mb": round(input_size_mb, 2),
                "output_size_mb": round(output_size_mb, 2),
                "target_size_mb": target_size_mb,
                "final_crf": best_crf
            }
        
        return {"success": False, "error": "Could not achieve target size"}


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Daena Video Compressor - Compress videos while maintaining quality",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s video.mp4 -o compressed.mp4 -p balanced
  %(prog)s video.mp4 --target-size 95
  %(prog)s videos/ --batch -p web -o output/
  %(prog)s --list-presets
        """
    )
    
    parser.add_argument("input", nargs="?", help="Input video file or folder (for batch)")
    parser.add_argument("-o", "--output", help="Output file or folder")
    parser.add_argument("-p", "--preset", 
                       choices=["high_quality", "balanced", "web", "github", "max"],
                       default="balanced",
                       help="Compression preset (default: balanced)")
    parser.add_argument("--target-size", type=float, 
                       help="Target file size in MB (overrides preset)")
    parser.add_argument("--batch", action="store_true",
                       help="Batch process all videos in input folder")
    parser.add_argument("--list-presets", action="store_true",
                       help="List available compression presets")
    
    args = parser.parse_args()
    
    # List presets
    if args.list_presets:
        print("\n📋 Available Compression Presets:\n")
        for preset, settings in PRESETS.items():
            print(f"  {preset.value:<15} CRF:{settings.crf:<3} Scale:{settings.scale or 'original':<12} - {settings.description}")
        print()
        return
    
    if not args.input:
        parser.print_help()
        return
    
    # Initialize compressor
    try:
        compressor = VideoCompressor()
    except RuntimeError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    
    # Map preset string to enum
    preset_map = {
        "high_quality": CompressionPreset.HIGH_QUALITY,
        "balanced": CompressionPreset.BALANCED,
        "web": CompressionPreset.WEB_OPTIMIZED,
        "github": CompressionPreset.GITHUB_FRIENDLY,
        "max": CompressionPreset.MAXIMUM,
    }
    preset = preset_map[args.preset]
    
    # Batch mode
    if args.batch:
        output_folder = args.output or str(Path(args.input) / "compressed")
        results = compressor.batch_compress(args.input, output_folder, preset)
        
        # Summary
        print(f"\n{'='*60}")
        print(f"📊 Batch Compression Summary")
        print(f"{'='*60}")
        total_input = sum(r.get("input_size_mb", 0) for r in results if r.get("success"))
        total_output = sum(r.get("output_size_mb", 0) for r in results if r.get("success"))
        print(f"   • Videos processed: {len(results)}")
        print(f"   • Total input:      {total_input:.2f} MB")
        print(f"   • Total output:     {total_output:.2f} MB")
        print(f"   • Total saved:      {total_input - total_output:.2f} MB")
        print(f"{'='*60}\n")
    
    # Target size mode
    elif args.target_size:
        output_path = args.output or str(Path(args.input).stem) + "_compressed.mp4"
        result = compressor.compress_to_target_size(
            args.input, output_path, args.target_size
        )
        if not result.get("success"):
            print(f"❌ Error: {result.get('error')}")
            sys.exit(1)
    
    # Single file mode
    else:
        output_path = args.output or str(Path(args.input).stem) + "_compressed.mp4"
        result = compressor.compress(args.input, output_path, preset)
        if not result.get("success"):
            print(f"❌ Error: {result.get('error')}")
            sys.exit(1)


if __name__ == "__main__":
    main()
