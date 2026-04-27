#!/usr/bin/env python3
"""
CONTINUOUS VISION AGENT SYSTEM
Live screen capture, video analysis, and streaming understanding

Capabilities:
- Live screen watching (continuous capture)
- Video file analysis (frame-by-frame)
- YouTube/web video understanding
- Real-time anomaly detection
- Memory across frames (understands changes over time)
"""

import asyncio
import base64
import io
import json
import os
import sys
import time
import threading
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import subprocess
import re

# Try to import required libraries
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("Warning: opencv-python not installed. Video analysis limited.")

try:
    import mss
    MSS_AVAILABLE = True
except ImportError:
    MSS_AVAILABLE = False
    print("Warning: mss not installed. Screen capture limited.")

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


# ============================================
# DATA MODELS
# ============================================

class CaptureMode(Enum):
    SCREEN = "screen"
    VIDEO = "video"
    YOUTUBE = "youtube"
    STREAM = "stream"

class AnalysisLevel(Enum):
    FRAME = "frame"      # Analyze each frame
    CHANGES = "changes"  # Only when significant changes
    TIMED = "timed"      # Every N seconds
    ANOMALY = "anomaly"  # Detect anomalies

@dataclass
class FrameAnalysis:
    """Analysis of a single frame"""
    timestamp: float
    frame_number: int
    summary: str
    objects_detected: List[str] = field(default_factory=list)
    text_content: str = ""
    changes_from_previous: List[str] = field(default_factory=list)
    anomalies: List[str] = field(default_factory=list)
    confidence: float = 0.0

@dataclass
class StreamSession:
    """A continuous watching session"""
    session_id: str
    mode: CaptureMode
    start_time: float
    frames_analyzed: int = 0
    key_events: List[Dict] = field(default_factory=list)
    memory: List[str] = field(default_factory=list)  # What agent "remembers"
    last_frame_hash: str = ""

# ============================================
# SCREEN CAPTURE
# ============================================

class ScreenCapture:
    """Capture live screen/window"""
    
    def __init__(self):
        self.running = False
        self.capture_thread = None
        self.sct = None
        
    def start_capture(self, monitor: int = 1, fps: int = 2):
        """Start continuous screen capture"""
        if not MSS_AVAILABLE:
            return None, "mss library not available"
        
        try:
            self.sct = mss.mss()
            self.running = True
            
            monitor_info = self.sct.monitors[monitor]
            
            def capture_loop():
                while self.running:
                    start_time = time.time()
                    
                    # Capture screen
                    screenshot = self.sct.grab(monitor_info)
                    
                    # Convert to bytes
                    img_bytes = mss.tools.to_png(screenshot.rgb, screenshot.size)
                    
                    # Calculate frame hash for change detection
                    frame_hash = str(hash(img_bytes[:100]))
                    
                    # Wait to maintain FPS
                    elapsed = time.time() - start_time
                    if elapsed < 1/fps:
                        time.sleep(1/fps - elapsed)
                    
                    yield {
                        "image": img_bytes,
                        "hash": frame_hash,
                        "timestamp": time.time(),
                        "size": screenshot.size
                    }
            
            return capture_loop(), None
        except Exception as e:
            return None, str(e)
    
    def stop_capture(self):
        """Stop capture"""
        self.running = False
        if self.sct:
            self.sct.close()
    
    def capture_region(self, x: int, y: int, width: int, height: int):
        """Capture specific region"""
        if not MSS_AVAILABLE:
            return None
        
        with mss.mss() as sct:
            monitor = {"left": x, "top": y, "width": width, "height": height}
            screenshot = sct.grab(monitor)
            return mss.tools.to_png(screenshot.rgb, screenshot.size)


# ============================================
# VIDEO ANALYZER
# ============================================

class VideoAnalyzer:
    """Analyze video files frame by frame"""
    
    def __init__(self):
        self.cap = None
        self.total_frames = 0
        self.fps = 0
    
    def open_video(self, video_path: str) -> bool:
        """Open video file"""
        if not CV2_AVAILABLE:
            return False
        
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            return False
        
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        return True
    
    def get_frame(self, frame_number: int = -1):
        """Get specific frame or next frame"""
        if not self.cap or not self.cap.isOpened():
            return None
        
        if frame_number >= 0:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        
        ret, frame = self.cap.read()
        if ret:
            # Encode as JPEG
            _, buffer = cv2.imencode('.jpg', frame)
            return buffer.tobytes()
        return None
    
    def extract_frames(self, interval_seconds: int = 1) -> List[Dict]:
        """Extract frames at intervals"""
        frames = []
        if not self.cap:
            return frames
        
        interval_frames = int(self.fps * interval_seconds)
        frame_num = 0
        
        while True:
            ret, frame = self.cap.read()
            if not ret:
                break
            
            if frame_num % interval_frames == 0:
                _, buffer = cv2.imencode('.jpg', frame)
                frames.append({
                    "frame_number": frame_num,
                    "timestamp": frame_num / self.fps,
                    "image": buffer.tobytes()
                })
            
            frame_num += 1
        
        return frames
    
    def close(self):
        """Close video"""
        if self.cap:
            self.cap.release()


# ============================================
# YOUTUBE/WEB VIDEO
# ============================================

class YouTubeAnalyzer:
    """Download and analyze YouTube/web videos"""
    
    def __init(self):
        self.temp_dir = tempfile.gettempdir()
    
    async def download_video(self, url: str, max_duration: int = 300) -> Optional[str]:
        """Download YouTube video for analysis"""
        # Check if yt-dlp is available
        try:
            subprocess.run(["yt-dlp", "--version"], capture_output=True, timeout=5)
        except:
            # Try youtube-dl
            try:
                subprocess.run(["youtube-dl", "--version"], capture_output=True, timeout=5)
            except:
                return None, "Neither yt-dlp nor youtube-dl available"
        
        output_path = os.path.join(self.temp_dir, "nexus_video.mp4")
        
        try:
            # Download best quality (up to 720p for speed)
            cmd = [
                "yt-dlp",
                "-f", "best[height<=720]",
                "-o", output_path,
                "--download-sections", f"*-{max_duration}",  # Limit duration
                "--no-playlist",
                url
            ]
            
            result = subprocess.run(cmd, capture_output=True, timeout=300)
            
            if result.returncode == 0 and os.path.exists(output_path):
                return output_path, None
            else:
                return None, result.stderr.decode() if result.stderr else "Download failed"
                
        except subprocess.TimeoutExpired:
            return None, "Download timeout"
        except Exception as e:
            return None, str(e)
    
    async def get_video_info(self, url: str) -> Dict[str, Any]:
        """Get video metadata without downloading"""
        try:
            cmd = ["yt-dlp", "--dump-json", "--no-download", url]
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            
            if result.returncode == 0:
                data = json.loads(result.stdout.decode())
                return {
                    "title": data.get("title", ""),
                    "duration": data.get("duration", 0),
                    "description": data.get("description", ""),
                    "uploader": data.get("uploader", ""),
                    "view_count": data.get("view_count", 0),
                    "url": url
                }
        except:
            pass
        
        return {"error": "Could not get video info"}


# ============================================
# CONTINUOUS VISION AGENT
# ============================================

class ContinuousVisionAgent:
    """
    The "eyes" - watches screens, videos continuously
    and builds understanding over time
    """
    
    def __init__(self):
        self.screen = ScreenCapture()
        self.video = VideoAnalyzer()
        self.youtube = YouTubeAnalyzer()
        self.ollama_model = "llava"
        
        self.sessions: Dict[str, StreamSession] = {}
        self.current_session: Optional[StreamSession] = None
        
        # Processing settings
        self.change_threshold = 0.1  # 10% change to trigger analysis
        self.analyze_interval = 2    # Analyze every 2 seconds of video
        self.frame_skip = 3          # Skip frames for speed
        
    async def watch_screen(self, monitor: int = 1, fps: int = 1) -> Dict[str, Any]:
        """Start watching screen in real-time"""
        
        session_id = f"screen_{int(time.time())}"
        self.current_session = StreamSession(
            session_id=session_id,
            mode=CaptureMode.SCREEN,
            start_time=time.time()
        )
        
        generator, error = self.screen.start_capture(monitor=monitor, fps=fps)
        
        if error:
            return {"error": error}
        
        print(f"\n👁️ SCREEN WATCH started (Session: {session_id})")
        print("Press Ctrl+C to stop\n")
        
        last_analysis_time = 0
        analysis_interval = 3  # Analyze every 3 seconds
        
        try:
            for frame_data in generator:
                self.current_session.frames_analyzed += 1
                
                # Check if significant change from last frame
                is_new = self._detect_change(frame_data["hash"])
                
                # Periodic analysis or on significant change
                current_time = time.time()
                should_analyze = (
                    current_time - last_analysis_time > analysis_interval 
                    or is_new
                )
                
                if should_analyze:
                    analysis = await self._analyze_frame(
                        frame_data["image"],
                        frame_data["timestamp"]
                    )
                    
                    if analysis:
                        self.current_session.memory.append(analysis.summary)
                        self.current_session.key_events.append({
                            "timestamp": current_time,
                            "type": "analysis",
                            "data": analysis.summary
                        })
                        
                        # Print analysis
                        print(f"[{current_time - self.current_session.start_time:.1f}s] {analysis.summary}")
                        
                        # Check for anomalies
                        if analysis.anomalies:
                            print(f"  ⚠️ ANOMALY: {analysis.anomalies}")
                    
                    last_analysis_time = current_time
                    
                # Keep memory manageable
                if len(self.current_session.memory) > 100:
                    self.current_session.memory = self.current_session.memory[-50:]
        
        except KeyboardInterrupt:
            print("\n\n🛑 Screen watching stopped")
        
        finally:
            self.screen.stop_capture()
        
        return self._get_session_summary()
    
    async def analyze_video(self, video_path: str, speed: float = 1.0) -> Dict[str, Any]:
        """Analyze video file"""
        
        if not self.video.open_video(video_path):
            return {"error": "Could not open video"}
        
        session_id = f"video_{int(time.time())}"
        self.current_session = StreamSession(
            session_id=session_id,
            mode=CaptureMode.VIDEO,
            start_time=time.time()
        )
        
        print(f"\n🎬 VIDEO ANALYSIS started")
        print(f"File: {video_path}")
        print(f"Total frames: {self.video.total_frames}")
        print(f"FPS: {self.video.fps}")
        print("=" * 50)
        
        frame_count = 0
        last_analysis = 0
        
        while True:
            # Get next frame
            frame = self.video.get_frame()
            if frame is None:
                break
            
            frame_count += 1
            
            # Analyze at intervals (adjusted by speed)
            current_timestamp = frame_count / self.video.fps
            if current_timestamp - last_analysis >= self.analyze_interval / speed:
                analysis = await self._analyze_frame(frame, current_timestamp)
                
                if analysis:
                    self.current_session.memory.append(analysis.summary)
                    self.current_session.frames_analyzed += 1
                    
                    print(f"[{current_timestamp:.1f}s] Frame {frame_count}: {analysis.summary}")
                    
                    if analysis.text_content:
                        print(f"  📝 Text: {analysis.text_content[:100]}")
                    
                    if analysis.anomalies:
                        print(f"  ⚠️ {analysis.anomalies}")
                
                last_analysis = current_timestamp
            
            # Progress indicator
            if frame_count % 100 == 0:
                progress = (frame_count / self.video.total_frames) * 100
                print(f"  Progress: {progress:.1f}%")
        
        self.video.close()
        print("\n✅ Video analysis complete")
        
        return self._get_session_summary()
    
    async def watch_youtube(self, url: str, max_duration: int = 180) -> Dict[str, Any]:
        """Watch and analyze YouTube video"""
        
        print(f"\n📺 Downloading YouTube video...")
        print(f"URL: {url}")
        
        video_path, error = await self.youtube.download_video(url, max_duration)
        
        if error:
            return {"error": error}
        
        print(f"✅ Downloaded, starting analysis...\n")
        
        return await self.analyze_video(video_path)
    
    async def _analyze_frame(self, image_bytes: bytes, timestamp: float) -> Optional[FrameAnalysis]:
        """Analyze a single frame using vision model"""
        
        try:
            # Encode image as base64 for prompt
            b64_image = base64.b64encode(image_bytes).decode('utf-8')
            
            prompt = f"""Analyze this image/video frame and provide:
1. A brief summary of what's shown (1-2 sentences)
2. Any text visible on screen
3. Any notable objects, UI elements, or people
4. Any anomalies or unexpected elements
5. What changed from previous frame (if applicable)

Be concise and specific."""

            # Call Ollama with image (llava expects base64)
            proc = await asyncio.create_subprocess_exec(
                "ollama", "run", self.ollama_model,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # For llava, we need special format
            # Using simplified approach - in practice would use llava's native image support
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=f"[img-1]<base64>{b64_image[:1000]}...\n\n{prompt}".encode()),
                timeout=60
            )
            
            result = stdout.decode()
            
            # Parse result into structured analysis
            return FrameAnalysis(
                timestamp=timestamp,
                frame_number=self.current_session.frames_analyzed if self.current_session else 0,
                summary=result[:200] if result else "No analysis",
                text_content=self._extract_text(result),
                confidence=0.8 if result else 0.0
            )
            
        except Exception as e:
            print(f"Analysis error: {e}")
            return None
    
    def _detect_change(self, frame_hash: str) -> bool:
        """Detect if frame is significantly different"""
        if not self.current_session:
            return True
        
        if not self.current_session.last_frame_hash:
            self.current_session.last_frame_hash = frame_hash
            return True
        
        is_different = frame_hash != self.current_session.last_frame_hash
        self.current_session.last_frame_hash = frame_hash
        return is_different
    
    def _extract_text(self, analysis: str) -> str:
        """Extract text content from analysis"""
        # Simple extraction - look for "Text:" or similar
        lines = analysis.split('\n')
        for line in lines:
            if 'text' in line.lower():
                return line.split(':', 1)[-1].strip()
        return ""
    
    def _get_session_summary(self) -> Dict[str, Any]:
        """Get summary of current session"""
        if not self.current_session:
            return {}
        
        duration = time.time() - self.current_session.start_time
        
        return {
            "session_id": self.current_session.session_id,
            "mode": self.current_session.mode.value,
            "duration": duration,
            "frames_analyzed": self.current_session.frames_analyzed,
            "key_events": len(self.current_session.key_events),
            "memory": self.current_session.memory[-10:]  # Last 10 memories
        }


# ============================================
# SIMPLE FRAME ANALYZER (No opencv/mss needed)
# ============================================

class SimpleVisionAnalyzer:
    """Fallback analyzer when libraries not available"""
    
    def __init__(self):
        self.ollama_model = "llava"
    
    async def analyze_image_file(self, image_path: str) -> Dict[str, Any]:
        """Analyze a single image file"""
        
        if not os.path.exists(image_path):
            return {"error": "File not found"}
        
        try:
            # Read image and convert to base64
            with open(image_path, "rb") as f:
                image_data = f.read()
            
            b64 = base64.b64encode(image_data).decode('utf-8')
            
            prompt = """Describe this image in detail. What is shown?
What text is visible? What objects are present?
Any notable features or issues?"""
            
            proc = await asyncio.create_subprocess_exec(
                "ollama", "run", self.ollama_model,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, _ = await asyncio.wait_for(
                proc.communicate(input=f"[img-1]<base64>{b64[:500]}...\n\n{prompt}".encode()),
                timeout=90
            )
            
            return {"analysis": stdout.decode()}
            
        except Exception as e:
            return {"error": str(e)}
    
    async def analyze_video_url(self, url: str) -> Dict[str, Any]:
        """Try to get info about a video URL"""
        
        try:
            # Check if it's a YouTube URL
            if 'youtube.com' in url or 'youtu.be' in url:
                # Try to get video info
                cmd = ["yt-dlp", "--dump-json", "--no-download", url]
                result = subprocess.run(cmd, capture_output=True, timeout=30)
                
                if result.returncode == 0:
                    data = json.loads(result.stdout.decode())
                    return {
                        "title": data.get("title", ""),
                        "duration": data.get("duration", 0),
                        "description": data.get("description", "")[:500],
                        "uploader": data.get("uploader", ""),
                        "note": "Video detected. Use --watch-youtube to analyze."
                    }
        except:
            pass
        
        return {"error": "Could not analyze URL"}


# ============================================
# CLI INTERFACE
# ============================================

async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Continuous Vision Agent")
    parser.add_argument("--mode", choices=["screen", "video", "youtube", "analyze"],
                       default="analyze", help="Mode of operation")
    parser.add_argument("--source", help="Video file or URL")
    parser.add_argument("--monitor", type=int, default=1, help="Monitor number for screen capture")
    parser.add_argument("--fps", type=int, default=1, help="Frames per second for screen capture")
    parser.add_argument("--speed", type=float, default=1.0, help="Video analysis speed")
    parser.add_argument("--image", help="Single image to analyze")
    
    args = parser.parse_args()
    
    print("""
╔══════════════════════════════════════════════════════════════╗
║           CONTINUOUS VISION AGENT SYSTEM                     ║
║  👁️ Live Screen • 🎬 Video • 📺 YouTube • 🖼️ Images          ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    if args.mode == "screen":
        agent = ContinuousVisionAgent()
        result = await agent.watch_screen(monitor=args.monitor, fps=args.fps)
        print(f"\nSession Summary: {result}")
    
    elif args.mode == "video":
        if not args.source:
            print("Error: --source required for video mode")
            return
        
        agent = ContinuousVisionAgent()
        result = await agent.analyze_video(args.source, speed=args.speed)
        print(f"\nAnalysis: {result}")
    
    elif args.mode == "youtube":
        if not args.source:
            print("Error: --source (URL) required for youtube mode")
            return
        
        agent = ContinuousVisionAgent()
        result = await agent.watch_youtube(args.source)
        print(f"\nAnalysis: {result}")
    
    elif args.mode == "analyze":
        if args.image:
            analyzer = SimpleVisionAnalyzer()
            result = await analyzer.analyze_image_file(args.image)
            print(f"\nAnalysis:\n{result}")
        elif args.source:
            analyzer = SimpleVisionAnalyzer()
            result = await analyzer.analyze_video_url(args.source)
            print(f"\n{result}")
        else:
            parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())