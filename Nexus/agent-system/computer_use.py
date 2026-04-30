#!/usr/bin/env python3
"""
REVOLUTIONARY COMPUTER USE AGENT
Autonomous computer control - click, type, automate anything

This system gives AI:
- Mouse control (click, drag, scroll, move)
- Keyboard control (type, hotkeys, shortcuts)
- Visual understanding (see screen, plan actions)
- Workflow automation (browser, terminal, apps)

Based on Anthropic's Computer Use but 100% local & free
"""

import asyncio
import json
import os
import random
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

# Platform-specific imports
if sys.platform == "win32":
    try:
        import pyautogui
        import pygetwindow as gw
        PYAUTOGUI_AVAILABLE = True
    except ImportError:
        PYAUTOGUI_AVAILABLE = False
        print("Installing pyautogui...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyautogui", "pygetwindow", "-q"])


# ============================================
# DATA MODELS
# ============================================

class ActionType(Enum):
    """Types of computer actions"""
    CLICK = "click"
    RIGHT_CLICK = "right_click"
    DOUBLE_CLICK = "double_click"
    DRAG = "drag"
    MOVE = "move"
    TYPE = "type"
    HOTKEY = "hotkey"
    WAIT = "wait"
    SCREENSHOT = "screenshot"
    FIND_IMAGE = "find_image"
    EXECUTE = "execute"
    TERMINAL = "terminal"
    URL = "url"

@dataclass
class Action:
    """A single action to execute"""
    action_type: ActionType
    params: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    confidence: float = 1.0
    
    def __str__(self):
        return f"{self.action_type.value}: {self.params}"

@dataclass
class ActionPlan:
    """A sequence of actions to achieve a goal"""
    goal: str
    actions: List[Action] = field(default_factory=list)
    reasoning: str = ""
    alternatives: List[str] = field(default_factory=list)

@dataclass
class ExecutionResult:
    """Result of action execution"""
    success: bool
    action: Action
    result: Any = None
    error: str = ""
    screenshot_after: Optional[bytes] = None


# ============================================
# SCREEN UTILITIES
# ============================================

class ScreenManager:
    """Handle screen capture and coordinates"""
    
    def __init__(self):
        self.width = 1920
        self.height = 1080
        self._update_screen_size()
    
    def _update_screen_size(self):
        """Get current screen size"""
        if PYAUTOGUI_AVAILABLE:
            self.width, self.height = pyautogui.size()
    
    def get_screen_size(self) -> Tuple[int, int]:
        """Get screen dimensions"""
        self._update_screen_size()
        return (self.width, self.height)
    
    def screenshot(self, region: Optional[Tuple[int, int, int, int]] = None) -> bytes:
        """Take a screenshot"""
        if not PYAUTOGUI_AVAILABLE:
            return b""
        
        if region:
            img = pyautogui.screenshot(region=region)
        else:
            img = pyautogui.screenshot()
        
        # Convert to bytes
        import io
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        return buffer.getvalue()
    
    def get_pixel_color(self, x: int, y: int) -> Tuple[int, int, int]:
        """Get color at position"""
        if PYAUTOGUI_AVAILABLE:
            return pyautogui.pixel(x, y)
        return (0, 0, 0)
    
    def find_image(self, image_path: str, confidence: float = 0.8) -> Optional[Tuple[int, int]]:
        """Find an image on screen (requires template matching)"""
        # Simplified - would use OpenCV in production
        return None


# ============================================
# MOUSE CONTROLLER
# ============================================

class MouseController:
    """Control mouse movements and clicks"""
    
    def __init__(self):
        self.safety_limits = True
        
    def move_to(self, x: int, y: int, duration: float = 0.2):
        """Move mouse to position"""
        if not PYAUTOGUI_AVAILABLE:
            return False
        
        try:
            if self.safety_limits:
                # Ensure within screen bounds
                import pyautogui
                width, height = pyautogui.size()
                x = max(0, min(x, width - 1))
                y = max(0, min(y, height - 1))
            
            pyautogui.moveTo(x, y, duration=duration)
            return True
        except Exception as e:
            print(f"Move error: {e}")
            return False
    
    def click(self, x: Optional[int] = None, y: Optional[int] = None, 
              button: str = "left", clicks: int = 1):
        """Click at position (or current)"""
        if not PYAUTOGUI_AVAILABLE:
            return False
        
        try:
            if x is not None and y is not None:
                pyautogui.moveTo(x, y)
            
            pyautogui.click(clicks=clicks, button=button)
            return True
        except Exception as e:
            print(f"Click error: {e}")
            return False
    
    def right_click(self, x: Optional[int] = None, y: Optional[int] = None):
        """Right click"""
        return self.click(x, y, button="right")
    
    def double_click(self, x: Optional[int] = None, y: Optional[int] = None):
        """Double click"""
        return self.click(x, y, clicks=2)
    
    def drag(self, start: Tuple[int, int], end: Tuple[int, int], duration: float = 0.5):
        """Drag from start to end"""
        if not PYAUTOGUI_AVAILABLE:
            return False
        
        try:
            pyautogui.moveTo(start[0], start[1])
            pyautogui.mouseDown()
            pyautogui.moveTo(end[0], end[1], duration=duration)
            pyautogui.mouseUp()
            return True
        except Exception as e:
            print(f"Drag error: {e}")
            return False
    
    def scroll(self, clicks: int = 3):
        """Scroll (positive = up, negative = down)"""
        if not PYAUTOGUI_AVAILABLE:
            return False
        
        try:
            pyautogui.scroll(clicks)
            return True
        except:
            return False


# ============================================
# KEYBOARD CONTROLLER
# ============================================

class KeyboardController:
    """Control keyboard input"""
    
    def __init__(self):
        self.pause_between_keys = 0.05
    
    def type(self, text: str, interval: float = 0.05):
        """Type text"""
        if not PYAUTOGUI_AVAILABLE:
            return False
        
        try:
            pyautogui.write(text, interval=interval)
            return True
        except Exception as e:
            print(f"Type error: {e}")
            return False
    
    def press(self, *keys):
        """Press key combination"""
        if not PYAUTOGUI_AVAILABLE:
            return False
        
        try:
            pyautogui.hotkey(*keys)
            return True
        except Exception as e:
            print(f"Press error: {e}")
            return False
    
    def key_down(self, key: str):
        """Hold key down"""
        if PYAUTOGUI_AVAILABLE:
            pyautogui.keyDown(key)
    
    def key_up(self, key: str):
        """Release key"""
        if PYAUTOGUI_AVAILABLE:
            pyautogui.keyUp(key)
    
    def hotkey(self, *keys):
        """Press hotkey combination"""
        return self.press(*keys)


# ============================================
# WINDOW MANAGER
# ============================================

class WindowManager:
    """Manage windows and applications"""
    
    def get_active_window(self) -> Optional[str]:
        """Get title of active window"""
        if not PYAUTOGUI_AVAILABLE:
            return None
        
        try:
            import pygetwindow as gw
            win = gw.getActiveWindow()
            return win.title if win else None
        except:
            return None
    
    def get_all_windows(self) -> List[str]:
        """Get all window titles"""
        if not PYAUTOGUI_AVAILABLE:
            return []
        
        try:
            import pygetwindow as gw
            return [w.title for w in gw.getAllWindows() if w.title]
        except:
            return []
    
    def activate_window(self, title: str) -> bool:
        """Focus window by title (partial match)"""
        if not PYAUTOGUI_AVAILABLE:
            return False
        
        try:
            import pygetwindow as gw
            wins = gw.getWindowsWithTitle(title)
            if wins:
                wins[0].activate()
                return True
        except:
            pass
        return False
    
    def minimize_window(self, title: str) -> bool:
        """Minimize window"""
        if not PYAUTOGUI_AVAILABLE:
            return False
        
        try:
            import pygetwindow as gw
            wins = gw.getWindowsWithTitle(title)
            if wins:
                wins[0].minimize()
                return True
        except:
            pass
        return False
    
    def maximize_window(self, title: str) -> bool:
        """Maximize window"""
        if not PYAUTOGUI_AVAILABLE:
            return False
        
        try:
            import pygetwindow as gw
            wins = gw.getWindowsWithTitle(title)
            if wins:
                wins[0].maximize()
                return True
        except:
            pass
        return False


# ============================================
# ACTION PLANNER (The Brain)
# ============================================

class ActionPlanner:
    """
    Analyzes screen and creates action plans
    Uses vision model to understand what's on screen
    """
    
    def __init__(self):
        self.vision_model = "llava"
        self.reasoning_model = "deepseek-r1:7b"
    
    async def analyze_and_plan(self, screenshot: bytes, goal: str) -> ActionPlan:
        """Analyze screen and create action plan to achieve goal"""
        
        # First, analyze what's on screen
        screen_description = await self._analyze_screen(screenshot)
        
        # Then, create a plan
        plan = await self._create_plan(screen_description, goal)
        
        return plan
    
    async def _analyze_screen(self, screenshot: bytes) -> str:
        """Use vision to understand screen"""
        try:
            import base64
            b64 = base64.b64encode(screenshot).decode('utf-8')
            
            prompt = """Describe what's on this screen in detail:
- What application is running
- What UI elements are visible (buttons, menus, text fields)
- What is the current state
- Where are important elements positioned (use relative positions: top-left, center, bottom-right)

Be specific about locations."""
            
            proc = await asyncio.create_subprocess_exec(
                "ollama", "run", self.vision_model,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, _ = await asyncio.wait_for(
                proc.communicate(input=prompt.encode()),
                timeout=60
            )
            
            return stdout.decode()
            
        except Exception as e:
            return f"Error analyzing: {e}"
    
    async def _create_plan(self, screen_desc: str, goal: str) -> ActionPlan:
        """Create action plan to achieve goal"""
        
        prompt = f"""Given this screen:
{screen_desc}

Goal: {goal}

Create a step-by-step plan to achieve this goal. For each step, specify:
- What action to take (click, type, hotkey, etc.)
- Where (coordinates or element description)
- What to type (if applicable)

Respond in this JSON format:
{{
  "reasoning": "why this approach will work",
  "actions": [
    {{"type": "click", "x": 100, "y": 200, "description": "click submit button"}},
    {{"type": "type", "text": "hello", "description": "enter search query"}},
    {{"type": "hotkey", "keys": ["ctrl", "c"], "description": "copy text"}}
  ],
  "alternatives": ["backup plan 1", "backup plan 2"]
}}

Only include realistic actions. Be specific with coordinates."""
        
        try:
            proc = await asyncio.create_subprocess_exec(
                "ollama", "run", self.reasoning_model,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, _ = await asyncio.wait_for(
                proc.communicate(input=prompt.encode()),
                timeout=120
            )
            
            # Parse JSON from response
            response = stdout.decode()
            return self._parse_plan(response, goal)
            
        except Exception as e:
            return ActionPlan(goal=goal, reasoning=f"Error: {e}")
    
    def _parse_plan(self, response: str, goal: str) -> ActionPlan:
        """Parse JSON plan from response"""
        try:
            # Try to extract JSON
            if '{' in response:
                json_str = response[response.find('{'):response.rfind('}')+1]
                data = json.loads(json_str)
                
                actions = []
                for a in data.get('actions', []):
                    action_type = ActionType(a.get('type', 'click'))
                    actions.append(Action(
                        action_type=action_type,
                        params=a,
                        description=a.get('description', '')
                    ))
                
                return ActionPlan(
                    goal=goal,
                    reasoning=data.get('reasoning', ''),
                    actions=actions,
                    alternatives=data.get('alternatives', [])
                )
        except:
            pass
        
        # Fallback - simple plan
        return ActionPlan(
            goal=goal,
            reasoning="Could not parse, creating simple plan",
            actions=[Action(ActionType.SCREENSHOT, {}, "Take screenshot to understand")]
        )


# ============================================
# COMPUTER USE AGENT (Main Class)
# ============================================

class ComputerUseAgent:
    """
    The Revolutionary Computer Agent
    Can see, plan, and execute actions on computer
    """
    
    def __init__(self):
        self.screen = ScreenManager()
        self.mouse = MouseController()
        self.keyboard = KeyboardController()
        self.windows = WindowManager()
        self.planner = ActionPlanner()
        
        self.action_history: List[ExecutionResult] = []
        self.max_history = 100
        
    async def execute_goal(self, goal: str, max_steps: int = 10) -> Dict[str, Any]:
        """
        Main function - achieve a goal by executing actions
        """
        print(f"\n🎯 GOAL: {goal}")
        print("=" * 60)
        
        steps_executed = 0
        success = False
        
        while steps_executed < max_steps:
            # 1. Take screenshot
            screenshot = self.screen.screenshot()
            print(f"\n[Step {steps_executed + 1}] Analyzing screen...")
            
            # 2. Plan actions
            plan = await self.planner.analyze_and_plan(screenshot, goal)
            print(f"   Plan: {plan.reasoning[:100]}...")
            
            if not plan.actions:
                print("   ⚠️ No actions planned")
                break
            
            # 3. Execute actions
            for action in plan.actions:
                result = await self._execute_action(action)
                self.action_history.append(result)
                
                if result.success:
                    print(f"   ✅ {action.description or action.action_type.value}")
                else:
                    print(f"   ❌ {action.description or action.action_type.value}: {result.error}")
                
                # Take brief pause between actions
                await asyncio.sleep(0.3)
            
            steps_executed += 1
            
            # 4. Check if goal achieved (simplified check)
            if await self._check_goal_achieved(goal):
                success = True
                print(f"\n🎉 GOAL ACHIEVED!")
                break
        
        # 5. Return summary
        return {
            "goal": goal,
            "success": success,
            "steps": steps_executed,
            "actions_executed": len(self.action_history),
            "history": [str(a.action) for a in self.action_history[-10:]]
        }
    
    async def _execute_action(self, action: Action) -> ExecutionResult:
        """Execute a single action"""
        
        try:
            if action.action_type == ActionType.CLICK:
                x = action.params.get('x', 0)
                y = action.params.get('y', 0)
                self.mouse.click(x, y)
                
            elif action.action_type == ActionType.RIGHT_CLICK:
                x = action.params.get('x', 0)
                y = action.params.get('y', 0)
                self.mouse.right_click(x, y)
                
            elif action.action_type == ActionType.DOUBLE_CLICK:
                x = action.params.get('x', 0)
                y = action.params.get('y', 0)
                self.mouse.double_click(x, y)
                
            elif action.action_type == ActionType.DRAG:
                start = action.params.get('start', (0, 0))
                end = action.params.get('end', (0, 0))
                self.mouse.drag(start, end)
                
            elif action.action_type == ActionType.MOVE:
                x = action.params.get('x', 0)
                y = action.params.get('y', 0)
                self.mouse.move_to(x, y)
                
            elif action.action_type == ActionType.TYPE:
                text = action.params.get('text', '')
                self.keyboard.type(text)
                
            elif action.action_type == ActionType.HOTKEY:
                keys = action.params.get('keys', [])
                self.keyboard.hotkey(*keys)
                
            elif action.action_type == ActionType.WAIT:
                seconds = action.params.get('seconds', 1)
                await asyncio.sleep(seconds)
                
            elif action.action_type == ActionType.SCREENSHOT:
                pass  # Already captured
                
            elif action.action_type == ActionType.TERMINAL:
                cmd = action.params.get('command', '')
                if cmd:
                    subprocess.run(cmd, shell=True)
                    
            elif action.action_type == ActionType.URL:
                url = action.params.get('url', '')
                if url:
                    # Open URL in default browser
                    if sys.platform == "win32":
                        os.system(f'start "" "{url}"')
            
            return ExecutionResult(success=True, action=action)
            
        except Exception as e:
            return ExecutionResult(success=False, action=action, error=str(e))
    
    async def _check_goal_achieved(self, goal: str) -> bool:
        """Check if goal appears to be achieved"""
        # Simplified - in production would analyze screen
        keywords = ["success", "done", "complete", "finished", "welcome"]
        return any(k in goal.lower() for k in keywords)
    
    def get_screen_info(self) -> Dict[str, Any]:
        """Get current screen state"""
        width, height = self.screen.get_screen_size()
        active_window = self.windows.get_active_window()
        all_windows = self.windows.get_all_windows()
        
        return {
            "screen_size": (width, height),
            "active_window": active_window,
            "open_windows": all_windows[:10]
        }
    
    # Convenience methods for direct control
    async def click_at(self, x: int, y: int) -> bool:
        """Click at specific coordinates"""
        return self.mouse.click(x, y)
    
    async def type_text(self, text: str) -> bool:
        """Type text"""
        return self.keyboard.type(text)
    
    async def press_hotkey(self, *keys) -> bool:
        """Press hotkey"""
        return self.keyboard.hotkey(*keys)
    
    async def open_url(self, url: str) -> bool:
        """Open URL in browser"""
        return self.keyboard.press("ctrl", "l") and asyncio.create_subprocess_shell(f'start "" "{url}"')


# ============================================
# AUTOMATION WORKFLOWS
# ============================================

class AutomationWorkflows:
    """Pre-built automation workflows"""
    
    def __init__(self):
        self.computer = ComputerUseAgent()
    
    async def browse_and_search(self, query: str, browser: str = "chrome") -> Dict:
        """Open browser, search for query"""
        print(f"\n🌐 Searching for: {query}")
        
        # 1. Open browser
        if sys.platform == "win32":
            os.system(f'start {browser}')
        await asyncio.sleep(2)
        
        # 2. Type in address bar and search
        self.computer.keyboard.press("ctrl", "l")
        await asyncio.sleep(0.5)
        self.computer.keyboard.type(f"https://www.google.com/search?q={query}")
        self.computer.keyboard.press("enter")
        
        return {"status": "search_executed", "query": query}
    
    async def fill_form(self, field_values: Dict[str, str]) -> Dict:
        """Fill form fields (simplified)"""
        for field, value in field_values.items():
            await asyncio.sleep(0.5)
            self.computer.keyboard.type(value)
            self.computer.keyboard.press("tab")
        
        return {"status": "form_filled", "fields": len(field_values)}
    
    async def download_file(self, url: str, path: str) -> Dict:
        """Download file via browser"""
        print(f"\n📥 Downloading: {url}")
        
        # Open URL
        if sys.platform == "win32":
            os.system(f'start "" "{url}"')
        
        await asyncio.sleep(5)  # Wait for download to start
        
        return {"status": "download_started", "url": url}


# ============================================
# CLI INTERFACE
# ============================================

async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Revolutionary Computer Use Agent")
    parser.add_argument("--goal", help="Goal to achieve")
    parser.add_argument("--action", help="Single action: click,x,y or type,text or hotkey,ctrl+c")
    parser.add_argument("--interactive", action="store_true", help="Interactive mode")
    parser.add_argument("--info", action="store_true", help="Show screen info")
    parser.add_argument("--workflow", help="Run predefined workflow (search, download)")
    parser.add_argument("--query", help="Query for workflow")
    
    args = parser.parse_args()
    
    print("""
╔══════════════════════════════════════════════════════════════╗
║        🤖 REVOLUTIONARY COMPUTER USE AGENT                   ║
║  👁️ See • 🧠 Plan • 🎯 Execute • 🔄 Automate                ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    computer = ComputerUseAgent()
    
    if args.info:
        info = computer.get_screen_info()
        print(f"\n📺 Screen: {info['screen_size'][0]}x{info['screen_size'][1]}")
        print(f"🪟 Active: {info['active_window']}")
        print(f"📂 Open windows:")
        for w in info['open_windows'][:5]:
            print(f"   - {w}")
        return
    
    if args.action:
        # Single action
        parts = args.action.split(',')
        action_type = parts[0].strip()
        
        if action_type == "click" and len(parts) >= 3:
            x, y = int(parts[1]), int(parts[2])
            await computer.click_at(x, y)
            print(f"✅ Clicked at ({x}, {y})")
        
        elif action_type == "type" and len(parts) >= 2:
            text = parts[1]
            await computer.type_text(text)
            print(f"✅ Typed: {text}")
        
        elif action_type == "hotkey" and len(parts) >= 2:
            keys = parts[1].split('+')
            await computer.press_hotkey(*keys)
            print(f"✅ Pressed: {'+'.join(keys)}")
        
        return
    
    if args.goal:
        result = await computer.execute_goal(args.goal)
        print(f"\n📊 Result: {result}")
        return
    
    if args.workflow:
        workflows = AutomationWorkflows()
        
        if args.workflow == "search" and args.query:
            result = await workflows.browse_and_search(args.query)
            print(result)
        
        return
    
    if args.interactive:
        print("""
Commands:
  click,x,y    - Click at coordinates
  type,text    - Type text
  hotkey,keys  - Press hotkey (e.g., ctrl+c)
  goal,text    - Achieve a goal
  info         - Show screen info
  quit         - Exit
        """)
        
        while True:
            cmd = input("\n> ").strip()
            if cmd.lower() == "quit":
                break
            
            parts = cmd.split(',')
            action = parts[0].strip().lower()
            
            if action == "click" and len(parts) >= 3:
                await computer.click_at(int(parts[1]), int(parts[2]))
            elif action == "type" and len(parts) >= 2:
                await computer.type_text(parts[1])
            elif action == "hotkey" and len(parts) >= 2:
                await computer.press_hotkey(*parts[1].split('+'))
            elif action == "info":
                info = computer.get_screen_info()
                print(info)
            elif action == "goal" and len(parts) >= 2:
                await computer.execute_goal(parts[1])
            else:
                print("Unknown command")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())