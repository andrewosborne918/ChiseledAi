import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import time
import json
import os
import sys
import platform
import google.generativeai as genai
from dotenv import load_dotenv
import subprocess
import logging
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pandas as pd
from typing import Dict, List, Optional
import threading
import re
import random

# Add rounded rectangle method to Canvas class
def create_rounded_rect(self, x1, y1, x2, y2, radius, **kwargs):
    """Create a rounded rectangle on the canvas with smooth corners."""
    # Ensure radius doesn't exceed half the width or height
    radius = min(radius, abs(x2 - x1) / 2, abs(y2 - y1) / 2)

    # Points for the bezier curve to create rounded corners
    points = [
        x1 + radius, y1,                # Top left start
        x2 - radius, y1,                # Top right start
        x2, y1,                         # Top right corner control
        x2, y1 + radius,               # Top right corner end
        x2, y2 - radius,               # Bottom right start
        x2, y2,                        # Bottom right corner control
        x2 - radius, y2,               # Bottom right corner end
        x1 + radius, y2,               # Bottom left start
        x1, y2,                        # Bottom left corner control
        x1, y2 - radius,               # Bottom left corner end
        x1, y1 + radius,               # Top left start
        x1, y1,                        # Top left corner control
        x1 + radius, y1                # Back to start
    ]

    # If width is specified, create two polygons for outline effect
    if 'width' in kwargs and kwargs['width'] > 0:
        width = kwargs.pop('width')
        outline_color = kwargs.pop('outline', 'black')
        fill_color = kwargs.pop('fill', '')
        
        # Create outer shape (outline)
        if outline_color:
            self.create_polygon(points, smooth=True, fill=outline_color, **kwargs)
        
        # Adjust points for inner shape
        if fill_color:
            inner_points = []
            for i in range(0, len(points), 2):
                x, y = points[i], points[i + 1]
                if x == x1:
                    x += width
                elif x == x2:
                    x -= width
                if y == y1:
                    y += width
                elif y == y2:
                    y -= width
                inner_points.extend([x, y])
            
            # Create inner shape (fill)
            self.create_polygon(inner_points, smooth=True, fill=fill_color, outline='', **kwargs)
    else:
        # Create single polygon if no width specified
        return self.create_polygon(points, smooth=True, **kwargs)

    return self.find_all()[-1]

# Add the method to the Canvas class
tk.Canvas.create_rounded_rect = create_rounded_rect

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()

# Configure Google Gemini API
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
if not GOOGLE_API_KEY:
    raise ValueError("Please set GOOGLE_API_KEY in your .env file")

# Configure Gemini API
genai.configure(api_key=GOOGLE_API_KEY)

# Configure YouTube API
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')
if not YOUTUBE_API_KEY:
    raise ValueError("Please set YOUTUBE_API_KEY in your .env file")

# Initialize the models
model = genai.GenerativeModel('gemini-1.5-flash-latest')
youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)



def git_sync(commit_message="Auto-sync: Updated workout plan"):
    """Automatically commit and push changes to GitHub"""
    try:
        # Stage all changes
        subprocess.run(['git', 'add', '.'], check=True)
        logging.info("Staged changes for commit")

        # Commit changes
        subprocess.run(['git', 'commit', '-m', commit_message], check=True)
        logging.info(f"Committed changes with message: {commit_message}")

        # Push changes
        subprocess.run(['git', 'push'], check=True)
        logging.info("Successfully pushed changes to GitHub")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Error during Git sync: {e}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error during Git sync: {e}")
        return False


class WorkoutApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Chiseled AI - Workout Planner")
        self.geometry("800x900")

        # Set window size to full screen size
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        self.geometry(f"{screen_width}x{screen_height}")

        # Set minimum window size (similar to a phone screen)
        self.minsize(360, 640)

        # Set background color to dark gray
        self.configure(bg='#212529')

        # Bind window resize event
        self.bind('<Configure>', self.on_window_resize)

        # Get the appropriate data directory based on platform
        self.data_dir = self.get_data_directory()
        os.makedirs(self.data_dir, exist_ok=True)

        # Create loading screen (no padding or margin except top/bottom)
        self.loading_frame = tk.Frame(self, bg='#212529')
        self.loading_frame.pack(fill="both", expand=True)

        self.loading_container = tk.Frame(self.loading_frame, bg='#212529')
        self.loading_container.pack(expand=True, fill="both", pady=(50, 50))

        # Add title to loading screen (top)
        self.title_label = tk.Label(self.loading_container, text="CHISELED AI",
                                    font=("Impact", 80), bg='#212529', fg='#eb5e28')
        self.title_label.grid(row=0, column=0, sticky="n", pady=0)

        # Load and display logo (middle)
        try:
            logo_image = Image.open("Images/Chiseled_logo.png")
            max_size = (400, 400)
            logo_image.thumbnail(max_size, Image.Resampling.LANCZOS)
            self.logo_image = logo_image
            self.logo_photo = ImageTk.PhotoImage(logo_image)
            self.logo_label = tk.Label(self.loading_container, image=self.logo_photo, bg='#212529')
            self.logo_label.grid(row=1, column=0, sticky="ns", pady=0)
        except Exception as e:
            print(f"Error loading logo: {e}")
            self.subtitle_label = tk.Label(self.loading_container, text="CHISELED AI LOGO",
                                           font=("Helvetica", 16), bg='#212529', fg='white')
            self.subtitle_label.grid(row=1, column=0, sticky="ns", pady=0)

        # Add tagline (bottom)
        self.tagline_label = tk.Label(self.loading_container, text="YOUR PERSONAL WORKOUT PLANNER",
                                      font=("Helvetica", 24), bg='#212529', fg='white')
        self.tagline_label.grid(row=2, column=0, sticky="s", pady=0)

        # Configure row/column weights for vertical distribution
        self.loading_container.grid_rowconfigure(0, weight=1)
        self.loading_container.grid_rowconfigure(1, weight=2)
        self.loading_container.grid_rowconfigure(2, weight=1)
        self.loading_container.grid_columnconfigure(0, weight=1)

        # Check for saved workout plan
        self.saved_plan = self.load_saved_plan()

        # Schedule the main form or saved plan to appear after 3 seconds
        self.after(2000, self.show_initial_screen)

    def get_data_directory(self):
        """Get the appropriate data directory based on the platform."""
        if platform.system() == 'Android':
            # For Android, use the app's internal storage
            return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
        elif platform.system() == 'Darwin':  # iOS
            # For iOS, use the app's documents directory
            return os.path.join(os.path.expanduser('~'), 'Documents', 'ChiseledAI')
        else:
            # For other platforms (Windows, Linux, etc.)
            return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

    def load_saved_plan(self):
        try:
            plan_path = os.path.join(self.data_dir, 'workout_plan.json')
            if os.path.exists(plan_path):
                with open(plan_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading saved plan: {e}")
        return None

    def save_workout_plan(self, plan):
        try:
            plan_path = os.path.join(self.data_dir, 'workout_plan.json')
            with open(plan_path, 'w') as f:
                json.dump(plan, f)

            # Auto-sync after saving workout plan
            git_sync("Auto-sync: Saved new workout plan")

        except Exception as e:
            print(f"Error saving workout plan: {e}")
            # Try alternative save method if the first one fails
            try:
                # Try saving to a different location
                alt_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'workout_plan.json')
                with open(alt_path, 'w') as f:
                    json.dump(plan, f)

                # Auto-sync after alternative save
                git_sync("Auto-sync: Saved workout plan to alternative location")

            except Exception as e2:
                print(f"Alternative save also failed: {e2}")

    def show_initial_screen(self):
        # Remove loading screen
        self.loading_frame.pack_forget()

        if self.saved_plan:
            # Show saved workout plan
            self.workout_plan_page = WorkoutPlanPage(self, self, self.saved_plan)
            self.workout_plan_page.pack(fill="both", expand=True)
            # Skip plan generation since we already have the plan
            self.workout_plan_page.display_workout_plan(self.saved_plan, is_saved_plan=True)
        else:
            # Show main form
            self.show_main_form()

    def on_window_resize(self, event):
        if event.widget == self:
            width = self.winfo_width()
            # Dynamically set wraplength for title and tagline
            wrap = max(200, int(width * 0.9))
            if hasattr(self, 'title_label'):
                self.title_label.config(wraplength=wrap)
            if hasattr(self, 'tagline_label'):
                self.tagline_label.config(wraplength=wrap)
            if hasattr(self, 'main_title_label'):
                self.main_title_label.config(wraplength=wrap)
            if hasattr(self, 'main_subtitle_label'):
                self.main_subtitle_label.config(wraplength=wrap)
            # Update plan page labels if present
            if hasattr(self, 'workout_plan_page'):
                if hasattr(self.workout_plan_page, 'main_title_label'):
                    self.workout_plan_page.main_title_label.config(wraplength=wrap)
                if hasattr(self.workout_plan_page, 'main_subtitle_label'):
                    self.workout_plan_page.main_subtitle_label.config(wraplength=wrap)
                # Responsive plan page buttons
                if hasattr(self.workout_plan_page, 'refresh_canvas') and hasattr(self.workout_plan_page, 'refresh_label'):
                    # Make buttons even smaller on small screens
                    if width < 450:
                        btn_w = 80
                        btn_h = 28
                        btn_font = ("Helvetica", 9, "bold")
                    else:
                        btn_w = 150
                        btn_h = 40
                        btn_font = ("Helvetica", 12, "bold")
                    # Update refresh button
                    self.workout_plan_page.refresh_canvas.config(width=btn_w, height=btn_h)
                    self.workout_plan_page.refresh_canvas.delete("all")
                    self.workout_plan_page.refresh_canvas.create_rounded_rect(0, 0, btn_w, btn_h, 8, fill='#212529', outline='#eb5e28', width=2)
                    self.workout_plan_page.refresh_label.config(font=btn_font)
                    self.workout_plan_page.refresh_label.place(relx=0.5, rely=0.5, anchor="center")
                    # Update new plan button
                    if hasattr(self.workout_plan_page, 'new_plan_canvas') and hasattr(self.workout_plan_page, 'new_plan_label'):
                        self.workout_plan_page.new_plan_canvas.config(width=btn_w, height=btn_h)
                        self.workout_plan_page.new_plan_canvas.delete("all")
                        self.workout_plan_page.new_plan_canvas.create_rounded_rect(0, 0, btn_w, btn_h, 8, fill='#eb5e28', outline='#eb5e28')
                        self.workout_plan_page.new_plan_label.config(font=btn_font)
                        self.workout_plan_page.new_plan_label.place(relx=0.5, rely=0.5, anchor="center")
            # Adjust font size for small screens
            if width < 450:
                if hasattr(self, 'title_label'):
                    self.title_label.config(font=("Impact", 40))
                if hasattr(self, 'tagline_label'):
                    self.tagline_label.config(font=("Helvetica", 14))
                if hasattr(self, 'main_title_label'):
                    self.main_title_label.config(font=("Impact", 30))
                if hasattr(self, 'main_subtitle_label'):
                    self.main_subtitle_label.config(font=("Helvetica", 12))
                if hasattr(self, 'workout_plan_page'):
                    if hasattr(self.workout_plan_page, 'main_title_label'):
                        self.workout_plan_page.main_title_label.config(font=("Impact", 30))
                    if hasattr(self.workout_plan_page, 'main_subtitle_label'):
                        self.workout_plan_page.main_subtitle_label.config(font=("Helvetica", 12))
                # Update all question labels
                if hasattr(self, 'sections'):
                    for section in self.sections:
                        if hasattr(section, 'question_label'):
                            section.question_label.config(font=("Helvetica", 12, "bold"), wraplength=wrap)
            else:
                if hasattr(self, 'title_label'):
                    self.title_label.config(font=("Impact", 80))
                if hasattr(self, 'tagline_label'):
                    self.tagline_label.config(font=("Helvetica", 24))
                if hasattr(self, 'main_title_label'):
                    self.main_title_label.config(font=("Impact", 50))
                if hasattr(self, 'main_subtitle_label'):
                    self.main_subtitle_label.config(font=("Helvetica", 14))
                if hasattr(self, 'workout_plan_page'):
                    if hasattr(self.workout_plan_page, 'main_title_label'):
                        self.workout_plan_page.main_title_label.config(font=("Impact", 50))
                    if hasattr(self.workout_plan_page, 'main_subtitle_label'):
                        self.workout_plan_page.main_subtitle_label.config(font=("Helvetica", 14))
                # Update all question labels
                if hasattr(self, 'sections'):
                    for section in self.sections:
                        if hasattr(section, 'question_label'):
                            section.question_label.config(font=("Helvetica", 16, "bold"), wraplength=wrap)
            # Responsive logo image on load page
            if hasattr(self, 'logo_label') and hasattr(self, 'logo_image'):
                # Set max size based on window width
                max_dim = 200 if width < 450 else 400
                img = self.logo_image.copy()
                img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
                self.logo_photo = ImageTk.PhotoImage(img)
                self.logo_label.config(image=self.logo_photo)
            # Ensure top buttons are responsive (if present)
            if hasattr(self, 'button_container'):
                self.button_container.pack(fill="x")
            if hasattr(self, 'title_frame'):
                self.title_frame.pack(fill="x")
            self.update_idletasks()

    def show_main_form(self):
        # Remove loading screen
        self.loading_frame.pack_forget()

        # Create main container
        self.main_container = tk.Frame(self, padx=40, pady=40, bg='#212529')
        self.main_container.pack(fill="both", expand=True)

        # Create title frame
        self.title_frame = tk.Frame(self.main_container, bg='#212529', padx=10)
        self.title_frame.pack(fill="x", pady=(0, 20))

        self.main_title_label = tk.Label(self.title_frame, text="CHISELED AI",
                                         font=("Impact", 50), bg='#212529', fg='#eb5e28', wraplength=300)
        self.main_title_label.pack()

        self.main_subtitle_label = tk.Label(self.title_frame, text="YOUR PERSONAL WORKOUT PLANNER",
                                            font=("Helvetica", 14), bg='#212529', fg='white', wraplength=300)
        self.main_subtitle_label.pack()

        # Create question container
        self.question_container = tk.Frame(self.main_container, bg='#212529', height=400, padx=10)
        self.question_container.pack(fill="both", expand=True, pady=10)

        # Create navigation frame
        self.nav_frame = tk.Frame(self.main_container, bg='#212529', height=50, padx=10)
        self.nav_frame.pack(fill="x", pady=10)

        # Create navigation buttons
        self.back_button = tk.Label(
            self.nav_frame,
            text="← Back",
            font=("Helvetica", 14, "bold"),
            bg='#212529',
            fg='white',
            cursor="hand2"
        )
        self.back_button.pack(side="left", padx=20)
        self.back_button.bind("<Button-1>", self.show_previous_question)

        self.next_button = tk.Label(
            self.nav_frame,
            text="Next →",
            font=("Helvetica", 14, "bold"),
            bg='#212529',
            fg='white',
            cursor="hand2"
        )
        self.next_button.pack(side="right", padx=20)
        self.next_button.bind("<Button-1>", self.show_next_question)

        # Initialize variables to hold user answers
        self.focus_var = tk.StringVar()
        self.muscle_vars = {}
        self.goal_var = tk.StringVar()
        self.experience_var = tk.StringVar()
        self.equipment_vars = {}
        self.duration_var = tk.StringVar()
        self.location_var = tk.StringVar()
        self.injury_var = tk.StringVar()
        self.style_var = tk.StringVar()

        # Create question frames
        self.focus_section = WorkoutFocus(self.question_container, self)
        self.goal_section = WorkoutGoal(self.question_container, self)
        self.experience_section = ExperienceLevel(self.question_container, self)
        self.equipment_section = EquipmentSelection(self.question_container, self)
        self.duration_section = WorkoutDuration(self.question_container, self)
        self.location_section = WorkoutLocation(self.question_container, self)
        self.injury_section = InjuryRestrictions(self.question_container, self)
        self.style_section = WorkoutStyle(self.question_container, self)

        # Store sections in order
        self.sections = [
            self.focus_section,
            self.goal_section,
            self.experience_section,
            self.equipment_section,
            self.duration_section,
            self.location_section,
            self.injury_section,
            self.style_section
        ]

        # Initialize current section index
        self.current_section_index = 0

        # Show first question
        self.show_current_question()

    def show_current_question(self):
        # Hide all sections
        for section in self.sections:
            section.pack_forget()

        # Show current section
        current_section = self.sections[self.current_section_index]
        current_section.pack(fill="both", expand=True, padx=5, pady=10)

        # Update question numbering based on the current path
        if self.focus_var.get() == "Target muscle group":
            self.goal_section.update_numbering(3)
            self.experience_section.update_numbering(4)
            self.equipment_section.update_numbering(5)
            self.duration_section.update_numbering(6)
            self.location_section.update_numbering(7)
            self.injury_section.update_numbering(8)
            self.style_section.update_numbering(9)
        else:
            self.goal_section.update_numbering(2)
            self.experience_section.update_numbering(3)
            self.equipment_section.update_numbering(4)
            self.duration_section.update_numbering(5)
            self.location_section.update_numbering(6)
            self.injury_section.update_numbering(7)
            self.style_section.update_numbering(8)

        # Update navigation buttons
        self.back_button.pack_forget()
        self.next_button.pack_forget()
        if hasattr(self, 'submit_frame'):
            self.submit_frame.pack_forget()

        if self.current_section_index > 0:
            self.back_button.pack(side="left", padx=20)

        if self.current_section_index < len(self.sections) - 1:
            self.next_button.pack(side="right", padx=20)
        else:
            # Show submit button on last question
            self.submit_frame = tk.Frame(self.nav_frame, bg='#212529', padx=20, pady=10)
            self.submit_frame.pack(side="right", padx=20)

            # Create a canvas for the rounded button
            width = self.winfo_width()
            button_width = 150 if width < 450 else 200
            button_height = 40 if width < 450 else 50
            font_size = 12 if width < 450 else 14

            self.submit_canvas = tk.Canvas(self.submit_frame, bg='#212529', highlightthickness=0,
                                           height=button_height, width=button_width)
            self.submit_canvas.pack(fill='x')

            # Draw rounded rectangle
            self.submit_canvas.create_rounded_rect(0, 0, button_width, button_height, 8,
                                fill='#eb5e28', outline='#eb5e28')

            # Create the label on top of the canvas
            self.submit_label = tk.Label(
                self.submit_canvas,
                text="Workout",
                font=("Helvetica", font_size, "bold"),
                bg='#eb5e28',
                fg='white',
                cursor="hand2"
            )
            self.submit_label.place(relx=0.5, rely=0.5, anchor='center')

            # Bind click events to both canvas and label
            self.submit_canvas.bind("<Button-1>", lambda e: self.collect_responses())
            self.submit_label.bind("<Button-1>", lambda e: self.collect_responses())

            # Add hover effect
            def on_enter(e):
                self.submit_canvas.delete("all")
                self.submit_canvas.create_rounded_rect(0, 0, button_width, button_height, 8,
                                                    fill='#d44e1e', outline='#d44e1e')
                self.submit_label.configure(bg='#d44e1e')

            def on_leave(e):
                self.submit_canvas.delete("all")
                self.submit_canvas.create_rounded_rect(0, 0, button_width, button_height, 8,
                                                    fill='#eb5e28', outline='#eb5e28')
                self.submit_label.configure(bg='#eb5e28')

            # Bind hover events to both canvas and label
            self.submit_canvas.bind("<Enter>", on_enter)
            self.submit_label.bind("<Enter>", on_enter)
            self.submit_canvas.bind("<Leave>", on_leave)
            self.submit_label.bind("<Leave>", on_leave)

    def show_next_question(self, event=None):
        if self.current_section_index < len(self.sections) - 1:
            # Skip muscle section if full body is selected
            if self.current_section_index == 0 and self.focus_var.get() == "Full body":
                self.current_section_index += 2
            else:
                self.current_section_index += 1
            self.show_current_question()
            # Update the window to ensure all elements are properly displayed
            self.update_idletasks()

    def show_previous_question(self, event=None):
        if self.current_section_index > 0:
            # Skip muscle section if full body is selected
            if self.current_section_index == 2 and self.focus_var.get() == "Full body":
                self.current_section_index -= 2
            else:
                self.current_section_index -= 1
            self.show_current_question()
            # Update the window to ensure all elements are properly displayed
            self.update_idletasks()

    def collect_responses(self):
        # Set default values for empty responses
        responses = {
            "Workout Focus": self.focus_var.get() or "Full body",
            "Muscle Groups": [group for group, var in self.muscle_vars.items() if var.get()] if self.focus_var.get() == "Target muscle group" else None,
            "Goal": self.goal_var.get() or "General fitness",
            "Experience": self.experience_var.get() or "Beginner",
            "Equipment": self.equipment_section.collect_equipment_info() or ["Bodyweight only"],
            "Duration": self.duration_var.get() or "60 minutes",
            "Location": self.location_var.get() or "Home",
            "Injuries": self.injury_section.collect_injury_info() or None,
            "Workout Style": self.style_var.get() or "Traditional sets"
        }

        # Save the workout plan
        self.save_workout_plan(responses)

        # Hide the main form
        self.main_container.pack_forget()

        # Create and show the workout plan page
        self.workout_plan_page = WorkoutPlanPage(self, self, responses)
        self.workout_plan_page.pack(fill="both", expand=True)

    def show_next(self, current_section):
        # This method is now handled by the navigation buttons
        pass

    def update_button_layout(self):
        """Update the layout of the buttons based on the window width."""
        width = self.winfo_width()
        
        # Clear previous packing
        for widget in self.button_container.winfo_children():
            widget.pack_forget()

        if width <= 500:
            # Stack buttons vertically
            self.refresh_canvas.pack(side="top", fill="x", pady=(0, 5))
            self.new_plan_canvas.pack(side="top", fill="x")
        else:
            # Pack buttons side by side
            self.refresh_canvas.pack(side="left", padx=10)
            self.new_plan_canvas.pack(side="left", padx=10)


# Each question section as a class

class WorkoutFocus(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg='#212529')
        self.app = app
        self.center_frame = tk.Frame(self, bg='#212529', padx=5)
        self.center_frame.pack(expand=True, fill="both", padx=5, pady=10)
        tk.Label(self.center_frame, text="1. What kind of workout would you like to do?", font=("Helvetica", 16, "bold"), bg='#212529', fg='white', wraplength=500).pack(anchor="w", pady=5)
        self.dropdown = ttk.Combobox(self.center_frame, textvariable=app.focus_var, values=["Full body", "Target muscle group"])
        self.dropdown.pack(fill="x", pady=5)
        self.dropdown.bind("<<ComboboxSelected>>", self.on_focus_change)
        self.dropdown.bind("<Button-1>", lambda e: self.dropdown.focus_set() or self.dropdown.event_generate('<Down>'))
        body_parts = {
            "Upper Body": ["Chest", "Back", "Shoulders", "Biceps", "Triceps", "Forearms"],
            "Lower Body": ["Glutes", "Quads", "Hamstrings", "Calves", "Hip Flexors"],
            "Core / Midsection": ["Upper Abs", "Lower Abs", "Obliques", "Lower Back", "Transverse Abdominis"]
        }
        self.muscle_frame = tk.Frame(self.center_frame, bg='#212529')
        self.muscle_label = tk.Label(self.muscle_frame, text="Which muscle groups?", font=("Helvetica", 14, "bold"), bg='#212529', fg='white', wraplength=400)
        self.muscle_label.pack(anchor="w", pady=5)
        self.muscle_row = tk.Frame(self.muscle_frame, bg='#212529')
        self.muscle_row.pack(fill="x", pady=5)
        for col, (group_name, muscles) in enumerate(body_parts.items()):
            col_frame = tk.Frame(self.muscle_row, bg='#212529')
            col_frame.grid(row=0, column=col, padx=10, sticky="n")
            group_label = tk.Label(col_frame, text=group_name, font=("Helvetica", 13, "bold"), bg='#212529', fg='#eb5e28', wraplength=150)
            group_label.pack(anchor="w", pady=(0, 2))
            for muscle in muscles:
                var = tk.BooleanVar()
                self.app.muscle_vars[muscle] = var
                CustomCheckbox(col_frame, text=muscle, variable=var, command=lambda: None, bg='#212529', fg='white', selectcolor='#eb5e28').pack(anchor="w", pady=2)

    def on_focus_change(self, event=None):
        if self.app.focus_var.get() == "Target muscle group":
            self.muscle_frame.pack(fill="x", pady=10)
        else:
            self.muscle_frame.pack_forget()


class WorkoutGoal(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg='#212529')
        self.app = app

        # Create centered container
        self.center_frame = tk.Frame(self, bg='#212529', padx=5)
        self.center_frame.pack(expand=True, fill="both", padx=5, pady=10)

        self.question_label = tk.Label(self.center_frame, font=("Helvetica", 16, "bold"), bg='#212529', fg='white',
                                       wraplength=300)
        self.question_label.pack(anchor="w", pady=5)
        dropdown = ttk.Combobox(self.center_frame, textvariable=app.goal_var,
                                values=["Build muscle", "Lose fat", "Increase endurance",
                                        "Improve flexibility/mobility", "General fitness"])
        dropdown.pack(fill="x", pady=5)
        # Remove automatic advancement
        dropdown.bind("<<ComboboxSelected>>", lambda e: None)
        # Make entire dropdown clickable to show list
        dropdown.bind("<Button-1>", lambda e: dropdown.focus_set() or dropdown.event_generate('<Down>'))

    def update_numbering(self, number):
        self.question_label.config(text=f"{number}. What is your primary goal?")


class CustomCheckbox(tk.Frame):
    def __init__(self, parent, text, variable, command=None, bg='#212529', fg='white', selectcolor='#eb5e28', **kwargs):
        super().__init__(parent, bg=bg)
        self.variable = variable
        self.command = command
        self.bg = bg
        self.fg = fg
        self.selectcolor = selectcolor
        self.canvas = tk.Canvas(self, width=28, height=28, bg=bg, highlightthickness=0)
        self.canvas.pack(side="left", padx=(0, 8))
        self.label = tk.Label(self, text=text, font=("Helvetica", 12), bg=bg, fg=fg)
        self.label.pack(side="left")
        self.canvas.bind("<Button-1>", self.on_click)
        self.label.bind("<Button-1>", self.on_click)
        self.variable.trace_add('write', self.update_state)
        self.draw()

    def draw(self):
        self.canvas.delete("all")
        # Outer square
        self.canvas.create_rectangle(4, 4, 24, 24, outline="white", width=2, fill=self.bg)
        # Fill and checkmark if selected
        if self.variable.get():
            self.canvas.create_rectangle(6, 6, 22, 22, outline="white", width=0, fill=self.selectcolor)
            # Draw checkmark
            self.canvas.create_line(9, 15, 14, 20, 20, 10, fill="white", width=3, capstyle=tk.ROUND, joinstyle=tk.ROUND)

    def on_click(self, event=None):
        self.variable.set(not self.variable.get())
        if self.command:
            self.command()
        self.draw()

    def update_state(self, *args):
        self.draw()

class CustomRadioButton(tk.Frame):
    def __init__(self, parent, text, variable, value, command=None, bg='#212529', fg='white', selectcolor='#eb5e28', **kwargs):
        super().__init__(parent, bg=bg)
        self.variable = variable
        self.value = value
        self.command = command
        self.bg = bg
        self.fg = fg
        self.selectcolor = selectcolor
        self.canvas = tk.Canvas(self, width=28, height=28, bg=bg, highlightthickness=0)
        self.canvas.pack(side="left", padx=(0, 8))
        self.label = tk.Label(self, text=text, font=("Helvetica", 12), bg=bg, fg=fg)
        self.label.pack(side="left")
        self.canvas.bind("<Button-1>", self.on_click)
        self.label.bind("<Button-1>", self.on_click)
        self.variable.trace_add('write', self.update_state)
        self.draw()

    def draw(self):
        self.canvas.delete("all")
        # Outer circle
        self.canvas.create_oval(4, 4, 24, 24, outline="white", width=2, fill=self.bg)
        # Fill if selected
        if self.variable.get() == self.value:
            self.canvas.create_oval(8, 8, 20, 20, outline="white", width=0, fill=self.selectcolor)

    def on_click(self, event=None):
        self.variable.set(self.value)
        if self.command:
            self.command()
        self.draw()

    def update_state(self, *args):
        self.draw()

class ExperienceLevel(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg='#212529')
        self.app = app
        self.center_frame = tk.Frame(self, bg='#212529', padx=5)
        self.center_frame.pack(expand=True, fill="both", padx=5, pady=10)
        self.question_label = tk.Label(self.center_frame, font=("Helvetica", 16, "bold"), bg='#212529', fg='white', wraplength=300)
        self.question_label.pack(anchor="w", pady=5)
        # Only set the value, do not reassign the variable
        app.experience_var.set("")
        for level in ["Beginner", "Intermediate", "Advanced"]:
            CustomRadioButton(self.center_frame, text=level, variable=app.experience_var, value=level, bg='#212529', fg='white', selectcolor='#eb5e28').pack(anchor="w", pady=2)
    def update_numbering(self, number):
        self.question_label.config(text=f"{number}. What is your fitness level?")


class EquipmentSelection(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg='#212529')
        self.app = app
        self.center_frame = tk.Frame(self, bg='#212529', padx=5)
        self.center_frame.pack(expand=True, fill="both", padx=5, pady=10)
        self.question_label = tk.Label(self.center_frame, font=("Helvetica", 16, "bold"), bg='#212529', fg='white', wraplength=300)
        self.question_label.pack(anchor="w", pady=5)
        equipment_list = ["Bodyweight only", "Dumbbells", "Barbells", "Resistance bands", "Kettlebells", "Machines", "Other"]
        self.checkbox_frame = tk.Frame(self.center_frame, bg='#212529')
        self.checkbox_frame.pack(fill="x", pady=5)
        for eq in equipment_list:
            var = tk.BooleanVar()
            app.equipment_vars[eq] = var
            CustomCheckbox(self.checkbox_frame, text=eq, variable=var, command=lambda eq=eq: self.on_checkbox_change(eq), bg='#212529', fg='white', selectcolor='#eb5e28').pack(anchor="w", pady=2)
        # Always create the text_frame and its children
        self.text_frame = tk.Frame(self.center_frame, bg='#212529')
        self.text_label = tk.Label(self.text_frame, text="Please describe your other equipment:", font=("Helvetica", 12), bg='#212529', fg='white')
        self.text_label.pack(anchor="w", pady=(20, 5))
        self.text_widget = tk.Text(self.text_frame, height=4, font=("Helvetica", 12), bg='#212529', fg='white')
        self.text_widget.pack(fill="x", pady=5)
        text_scrollbar = ttk.Scrollbar(self.text_frame, orient="vertical", command=self.text_widget.yview)
        text_scrollbar.pack(side="right", fill="y")
        self.text_widget.configure(yscrollcommand=text_scrollbar.set)
        # Do not pack text_frame initially

    def on_checkbox_change(self, equipment):
        if equipment == "Other":
            if self.app.equipment_vars["Other"].get():
                self.text_frame.pack(fill="x", pady=10)
            else:
                self.text_frame.pack_forget()

    def update_numbering(self, number):
        self.question_label.config(text=f"{number}. Available equipment:")

    def collect_equipment_info(self):
        equipment = [eq for eq, var in self.app.equipment_vars.items() if var.get()]
        if "Other" in equipment:
            other_equipment = self.text_widget.get("1.0", "end-1c").strip()
            if other_equipment:
                equipment.remove("Other")
                equipment.append(f"Other: {other_equipment}")
        return equipment


class WorkoutDuration(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg='#212529')
        self.app = app

        # Create centered container
        self.center_frame = tk.Frame(self, bg='#212529', padx=5)
        self.center_frame.pack(expand=True, fill="both", padx=5, pady=10)

        self.question_label = tk.Label(self.center_frame, font=("Helvetica", 16, "bold"), bg='#212529', fg='white',
                                       wraplength=300)
        self.question_label.pack(anchor="w", pady=5)

        # Add a scale (slider) for duration selection
        self.duration_var = tk.IntVar(value=60)
        self.scale = tk.Scale(self.center_frame, from_=15, to=180, orient="horizontal", resolution=5,
                              variable=self.duration_var, bg='#212529', fg='white', troughcolor='#2b3035',
                              highlightthickness=0, showvalue=0, length=300, sliderrelief='flat',
                              activebackground='#eb5e28')
        self.scale.pack(fill="x", pady=10)

        # Label to show the selected duration
        self.value_label = tk.Label(self.center_frame, text="60 minutes", font=("Helvetica", 14), bg='#212529', fg='#eb5e28')
        self.value_label.pack(anchor="center", pady=(0, 5))

        # Update label in real time
        self.scale.bind("<B1-Motion>", self.update_value_label)
        self.scale.bind("<ButtonRelease-1>", self.update_value_label)
        self.update_value_label()

        # Link to app.duration_var
        app.duration_var = self.duration_var

    def update_value_label(self, event=None):
        value = self.duration_var.get()
        if value < 60:
            label = f"{value}m"
        else:
            hours = value // 60
            minutes = value % 60
            label = f"{hours}h {minutes:02d}m"
        self.value_label.config(text=label)

    def update_numbering(self, number):
        self.question_label.config(text=f"{number}. Workout duration?")


class WorkoutLocation(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg='#212529')
        self.app = app

        # Create centered container
        self.center_frame = tk.Frame(self, bg='#212529', padx=5)
        self.center_frame.pack(expand=True, fill="both", padx=5, pady=10)

        self.question_label = tk.Label(self.center_frame, font=("Helvetica", 16, "bold"), bg='#212529', fg='white',
                                       wraplength=300)
        self.question_label.pack(anchor="w", pady=5)
        dropdown = ttk.Combobox(self.center_frame, textvariable=app.location_var,
                                values=["Gym", "Home", "Outdoors"])
        dropdown.pack(fill="x", pady=5)
        # Remove automatic advancement
        dropdown.bind("<<ComboboxSelected>>", lambda e: None)
        # Make entire dropdown clickable to show list
        dropdown.bind("<Button-1>", lambda e: dropdown.focus_set() or dropdown.event_generate('<Down>'))

    def update_numbering(self, number):
        self.question_label.config(text=f"{number}. Where will you work out?")


class InjuryRestrictions(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg='#212529')
        self.app = app
        self.center_frame = tk.Frame(self, bg='#212529', padx=5)
        self.center_frame.pack(expand=True, fill="both", padx=5, pady=10)
        self.question_label = tk.Label(self.center_frame, font=("Helvetica", 16, "bold"), bg='#212529', fg='white', wraplength=300)
        self.question_label.pack(anchor="w", pady=5)
        # Only set the value, do not reassign the variable
        app.injury_var.set("")
        self.radio_frame = tk.Frame(self.center_frame, bg='#212529')
        self.radio_frame.pack(fill="x", pady=10)
        for option in ["No", "Yes"]:
            CustomRadioButton(self.radio_frame, text=option, variable=app.injury_var, value=option, command=self.on_injury_selection, bg='#212529', fg='white', selectcolor='#eb5e28').pack(anchor="w", pady=2)
        # Always create the text_frame and its children
        self.text_frame = tk.Frame(self.center_frame, bg='#212529')
        self.text_label = tk.Label(self.text_frame, text="Please describe your injuries/restrictions:", font=("Helvetica", 12), bg='#212529', fg='white')
        self.text_label.pack(anchor="w", pady=(20, 5))
        self.text_widget = tk.Text(self.text_frame, height=4, font=("Helvetica", 12), bg='#212529', fg='white')
        self.text_widget.pack(fill="x", pady=5)
        text_scrollbar = ttk.Scrollbar(self.text_frame, orient="vertical", command=self.text_widget.yview)
        text_scrollbar.pack(side="right", fill="y")
        self.text_widget.configure(yscrollcommand=text_scrollbar.set)
        # Do not pack text_frame initially

    def on_injury_selection(self):
        """Handle injury selection changes"""
        if self.app.injury_var.get() == "Yes":
            self.text_frame.pack(fill="x", pady=10)
        else:
            self.text_frame.pack_forget()

    def update_numbering(self, number):
        self.question_label.config(text=f"{number}. Any injuries/restrictions?")

    def collect_injury_info(self):
        """Return the user's injury information if 'Yes' is selected, else None."""
        if self.app.injury_var.get() == "Yes":
            return self.text_widget.get("1.0", "end-1c").strip() or None
        return None


class WorkoutStyle(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg='#212529')
        self.app = app

        # Create centered container
        self.center_frame = tk.Frame(self, bg='#212529', padx=5)
        self.center_frame.pack(expand=True, fill="both", padx=5, pady=10)

        self.question_label = tk.Label(self.center_frame, font=("Helvetica", 16, "bold"), bg='#212529', fg='white',
                                       wraplength=300)
        self.question_label.pack(anchor="w", pady=5)
        dropdown = ttk.Combobox(self.center_frame, textvariable=app.style_var,
                                values=["Traditional sets", "Supersets", "Circuit", "HIIT", "Yoga/Pilates",
                                        "Stretching/Mobility"])
        dropdown.pack(fill="x", pady=5)
        # Remove automatic advancement
        dropdown.bind("<<ComboboxSelected>>", lambda e: None)
        # Make entire dropdown clickable to show list
        dropdown.bind("<Button-1>", lambda e: dropdown.focus_set() or dropdown.event_generate('<Down>'))

    def update_numbering(self, number):
        self.question_label.config(text=f"{number}. Preferred workout style?")


class WorkoutPlanPage(tk.Frame):
    def __init__(self, parent, app, responses):
        super().__init__(parent, bg='#212529')
        self.app = app
        self.responses = responses  # Store the responses
        self.progress_value = 0
        self.is_generating = False

        # Define loading_sentences and related attributes FIRST
        self.loading_sentences = [
            "Mentally spotting you while the plan loads…",
            "Consulting the workout oracle…",
            "Resisting the urge to make you do burpees…",
            "Counting imaginary kettlebells…",
            "Updating your sweat forecast…",
            "Telling your muscles what's about to happen… they're nervous.",
            "Bribing the gym gods for a good session...",
            "Whispering motivational quotes to your quads...",
            "Plotting the shortest route to soreness.",
            "Adding an extra rep just because we can.",
            "Trying to remember where we left the dumbbells...",
            "Slapping chalk on the keyboard for max effort.",
            "Spying on your fridge for post-workout snack ideas...",
            "Downloading just the right amount of pain.",
            "Warming up your excuses—so we can destroy them.",
            "Adjusting gravity to make push-ups harder (you're welcome).",
            "Converting coffee into programming power…",
            "Simulating slow-motion montages with epic music…",
            "Applying motivational beard oil to the algorithm.",
            "Arguing with your muscles about what they can handle.",
            "Warning: Side effects may include confidence and soreness.",
            "Just doing a few warm-up stretches… for the code.",
            "Persuading the burpees to be nice today.",
            "Measuring your willpower… it's above average!",
            "Trying to make leg day sound fun… it's not working.",
            "Convincing your abs to come out of hiding...",
            "Running with scissors... safely. Almost done!",
            "Trying to spell 'calisthenics' correctly. Still trying.",
            "Summoning gym spirits with protein powder and WiFi.",
            "Arguing with the server about how many reps you should do.",
            "Poking your glutes to see if they're awake.",
            "Unpacking your digital dumbbells...",
            "Negotiating a truce between cardio and strength training.",
            "Locating the motivation you lost last weekend.",
            "Giving your goals a motivational pep talk.",
            "Sifting through thousands of burpees to find the perfect one for you...",
            "Politely asking your muscles to rise and shine.",
            "Debating whether or not to include mountain climbers.",
            "Disabling the 'skip leg day' button. For your own good.",
            "Translating sweat into results...",
            "Slapping high-fives to imaginary gym buddies.",
            "Fetching water bottles and good intentions…",
            "Making your workout slightly more painful than yesterday.",
            "We asked your abs to show up. They ghosted us.",
            "Injecting just enough pain to make you proud later.",
            "Warning: Your glutes are about to file a complaint.",
            "Your personal trainer is buffering…",
            "Teaching your biceps the meaning of life.",
            "Running with dumbbells… slowly… virtually.",
            "Bringing the heat. Also the sweat.",
            "Building a better body—one loading bar at a time.",
            "Programming soreness into your future.",
            "Scouting the internet for motivational quotes… and snacks.",
            "Looking for lost gains… please wait.",
            "Putting the 'ow' in 'workout.'",
            "Downloading gym grunts and beast mode.",
            "Powerlifting your routine into existence.",
            "Calculating the precise moment you'll start questioning your life choices.",
            "Just one more second… and then another rep.",
            "Your future self is cheering. We're just stalling for dramatic effect."
        ]
        self.loading_sentence_indices = []
        self.loading_sentence_label = None

        # Create main container
        self.main_container = tk.Frame(self, padx=40, pady=40, bg='#212529')
        self.main_container.pack(fill="both", expand=True)

        # Create title frame
        self.title_frame = tk.Frame(self.main_container, bg='#212529', padx=10)
        self.title_frame.pack(fill="x", pady=(0, 20))

        self.main_title_label = tk.Label(self.title_frame, text="CHISELED AI",
                                         font=("Impact", 50), bg='#212529', fg='#eb5e28', wraplength=300)
        self.main_title_label.pack()

        self.main_subtitle_label = tk.Label(self.title_frame, text="YOUR PERSONAL WORKOUT PLANNER",
                                            font=("Helvetica", 14), bg='#212529', fg='white', wraplength=300)
        self.main_subtitle_label.pack()

        # Create plan container
        self.plan_container = tk.Frame(self.main_container, bg='#212529', padx=10)
        self.plan_container.pack(fill="both", expand=True, pady=20)

        # Check if this is a saved plan
        is_saved_plan = 'plan_text' in responses and 'timestamp' in responses

        if not is_saved_plan:
            self.show_loading_screen()
            # Start plan generation in a background thread
            self.after(100, lambda: self.start_plan_generation(responses))
        else:
            # Display saved plan immediately
            self.display_workout_plan(responses, is_saved_plan=True)

    def show_loading_screen(self):
        """Show the loading screen with progress bar and motivational sentences, responsive for small screens."""
        # Show loading frame only for new plans
        self.loading_frame = tk.Frame(self.plan_container, bg='#212529')
        self.loading_frame.pack(fill="both", expand=True)

        # Define font and wraplength variables for loading screen
        width = self.app.winfo_width() if hasattr(self.app, 'winfo_width') else 800
        is_small = width < 500
        title_font = ("Impact", 32) if is_small else ("Impact", 50)
        wraplength = 220 if is_small else 400

        # Use pack with fill and expand for all containers
        center_container = tk.Frame(self.loading_frame, bg='#212529')
        center_container.pack(fill="both", expand=True)

        # Title
        self.loading_title_label = tk.Label(center_container, text="CHISELED AI", font=title_font, bg='#212529', fg='#eb5e28', wraplength=wraplength, justify="left", anchor="w")
        self.loading_title_label.pack(fill="x")
        self.loading_label = tk.Label(
            center_container,
            text="Generating your personalized workout plan...",
            font=("Helvetica", 16),
            bg='#212529',
            fg='white',
            justify="left",
            anchor="w"
        )
        self.loading_label.pack(fill="x")

        # Create progress bar container
        progress_container = tk.Frame(center_container, bg='#212529')
        progress_container.pack(fill="x")

        # Create progress bar using Canvas, dynamic width
        progress_width = center_container.winfo_width() if center_container.winfo_width() > 0 else 300
        self.progress_canvas = tk.Canvas(
            progress_container,
            height=20,
            bg='#212529',
            highlightthickness=0
        )
        self.progress_canvas.pack(fill="x")

        def update_progress_bar_width(event=None):
            width = progress_container.winfo_width()
            if width < 100:
                width = 100
            self.progress_canvas.config(width=width)
            self.progress_canvas.delete("all")
            self.progress_canvas.create_rounded_rect(
                0, 0, width, 20, 10,
                fill='#2b3035',
                outline='#eb5e28',
                width=2
            )
        progress_container.bind("<Configure>", update_progress_bar_width)
        update_progress_bar_width()

        # Initialize progress variables
        self.progress_value = 0
        self.start_time = time.time()
        self.is_generating = True

        # Start updating progress immediately
        self.update_progress_bar()

        # Add the sentence label below the progress bar
        self.loading_sentence_label = tk.Label(center_container, text="", font=("Helvetica", 13, "italic"), bg='#212529', fg='#eb5e28', wraplength=400, justify="left", anchor="w")
        self.loading_sentence_label.pack(fill="x")

        def update_sentence_wrap(event=None):
            width = center_container.winfo_width()
            if width > 40:
                self.loading_sentence_label.config(wraplength=width - 40)
            else:
                self.loading_sentence_label.config(wraplength=width)
        center_container.bind("<Configure>", update_sentence_wrap)
        update_sentence_wrap()

        # Prepare a shuffled list of indices for random, non-repeating order
        self.loading_sentence_indices = list(range(len(self.loading_sentences)))
        random.shuffle(self.loading_sentence_indices)
        self.loading_sentence_pointer = 0
        self.loading_sentence_active = True
        self.update_loading_sentence()

    def update_progress_bar(self):
        """Update the progress bar continuously"""
        if not self.is_generating:
            return

        # Calculate elapsed time and progress
        elapsed = time.time() - self.start_time
        self.progress_value = min(95, (elapsed / 65.0) * 95)  # 12 seconds to reach 95%
        
        # Calculate width of progress fill
        width = (self.progress_value / 100) * 296

        # Update progress bar fill
        self.progress_canvas.delete('progress_fill')
        self.progress_fill = self.progress_canvas.create_rounded_rect(
            2, 2, width + 2, 18, 9,
            fill='#eb5e28',
            outline='',
            tags='progress_fill'
        )

        # Continue updating if not at 95%
        if self.progress_value < 95:
            self.after(16, self.update_progress_bar)  # Update at ~60 FPS

    def start_plan_generation(self, responses):
        threading.Thread(target=self.generate_and_display_plan, args=(responses,), daemon=True).start()

    def generate_and_display_plan(self, responses):
        """Generate the plan and update the display with progress bar"""
        try:
            # Generate the prompt and start the plan generation
            prompt = f"""Create a detailed, personalized workout plan based on the following user preferences:

Workout Focus: {responses['Workout Focus']}
{"Targeted Muscles: " + ", ".join(responses['Muscle Groups']) if responses['Muscle Groups'] else ""}
Goal: {responses['Goal']}
Experience Level: {responses['Experience']}
Equipment: {", ".join(responses['Equipment'])}
Duration: {responses['Duration']}
Location: {responses['Location']}
{"Injuries/Restrictions: " + responses['Injuries'] if responses['Injuries'] else ""}
Workout Style: {responses['Workout Style']}

Please provide a comprehensive workout plan that includes:
1. A warm-up routine
2. Main workout exercises with sets, reps, and rest periods
3. A cool-down routine
4. Any specific notes or modifications based on the user's preferences and restrictions

Important Guidelines:
1. Only suggest exercises that can be done with the available equipment
2. Ensure exercises are appropriate for the user's experience level
3. Account for any injuries or restrictions in the exercise selection
4. Match the workout duration to the user's preference
5. Consider the workout location in exercise selection

Formatting Guidelines:
1. Use markup to format the workouts
2. Make the title of the workout an H1 (use #)
3. Make the different workout block headers an H2 (use ##)
4. For each exercise:
   - Put the exercise name in square brackets [Exercise Name]
   - Include sets, reps, rest time, and important notes after the exercise name
   - Use bullet points (-) for sets, reps, and notes
5. Use clear spacing between sections and exercises"""

            # Generate initial response
            response = model.generate_content(prompt)
            if not response or not response.text:
                raise ValueError("Empty response from Gemini API")

            plan_text = response.text
            
            # Process the plan to identify exercises
            lines = plan_text.split('\n')
            processed_lines = []
            exercise_instructions = {}
            
            for line in lines:
                line = line.strip()
                if not line:
                    processed_lines.append(line)
                    continue

                # Check for exercise names in square brackets
                if '[' in line and ']' in line:
                    start = line.find('[')
                    end = line.find(']')
                    if start < end:
                        exercise_name = line[start + 1:end]
                        
                        # Generate instructions for this exercise
                        instruction_prompt = f"""Provide detailed instructions for the exercise: {exercise_name}

Please include:
1. Starting position
2. Movement execution
3. Breathing pattern
4. Common mistakes to avoid
5. Form cues
6. Safety tips

Keep the instructions clear and concise, focusing on proper form and safety."""

                        try:
                            instruction_response = model.generate_content(instruction_prompt)
                            if instruction_response and instruction_response.text:
                                exercise_instructions[exercise_name] = instruction_response.text.strip()
                            else:
                                exercise_instructions[exercise_name] = "Instructions not available."
                        except Exception as e:
                            exercise_instructions[exercise_name] = "Instructions not available."

                # Add the line as is
                processed_lines.append(line)

            # Store the exercise instructions in the responses dictionary
            responses['exercise_instructions'] = exercise_instructions

            # Save the generated plan
            plan = '\n'.join(processed_lines)
            responses['plan_text'] = plan
            from datetime import datetime
            current_time = datetime.now()
            responses['timestamp'] = current_time.strftime("%B %d, %Y | %I:%M%p").replace("AM", "am").replace("PM", "pm")
            self.app.save_workout_plan(responses)

            # When plan is ready, complete the progress bar
            self.progress_value = 100
            width = 296  # Full width
            self.progress_canvas.delete(self.progress_fill)
            self.progress_fill = self.progress_canvas.create_rounded_rect(
                2, 2, width + 2, 18, 9,
                fill='#eb5e28',
                outline=''
            )
            
            # Stop progress animation and display the plan
            self.is_generating = False
            self.loading_sentence_active = False
            self.after(500, lambda: self.display_workout_plan(responses, is_saved_plan=True))

        except Exception as e:
            self.is_generating = False
            self.loading_sentence_active = False
            error_label = tk.Label(
                self.loading_frame,
                text=f"Error generating plan: {str(e)}\nPlease try again.",
                font=("Helvetica", 12),
                bg='#212529',
                fg='red',
                wraplength=400
            )
            error_label.pack(pady=20)

    def display_workout_plan(self, responses, is_saved_plan=False):
        """Display the workout plan with proper formatting and styling."""
        # Clear any existing plan display and buttons
        for widget in self.plan_container.winfo_children():
            widget.destroy()

        # Create a main content frame that will hold both the text and buttons
        content_frame = tk.Frame(self.plan_container, bg='#212529')
        content_frame.pack(fill="both", expand=True)

        # Create button container at the top
        self.button_container = tk.Frame(content_frame, bg='#212529', padx=20, pady=10)
        self.button_container.pack(fill="x", pady=(0, 20))

        # Create buttons
        self.create_buttons()

        # Create a container for the text area that will expand
        text_container = tk.Frame(content_frame, bg='#212529')
        text_container.pack(fill="both", expand=True)

        # Create a frame to hold the text widget and scrollbar
        text_frame = tk.Frame(text_container, bg='#212529')
        text_frame.pack(fill="both", expand=True)

        # Create a text widget for the workout plan
        self.plan_text = tk.Text(text_frame, wrap=tk.WORD, bg='#212529', fg='white',
                                 font=("Helvetica", 14), padx=10, pady=10,
                                 spacing1=5, spacing2=2, spacing3=5,
                                 highlightthickness=0, borderwidth=0)
        self.plan_text.pack(side="left", fill="both", expand=True)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.plan_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.plan_text.configure(yscrollcommand=scrollbar.set)

        # Configure tags for different text styles
        self.plan_text.tag_configure("header", font=("Helvetica", 18, "bold"), foreground="#eb5e28")
        self.plan_text.tag_configure("subheader", font=("Helvetica", 16, "bold"), foreground="#eb5e28")
        self.plan_text.tag_configure("h3", font=("Helvetica", 15, "bold"), foreground="#eb5e28")
        self.plan_text.tag_configure("exercise_link", font=("Helvetica", 14, "bold"), foreground="#4dabf7", underline=1)
        self.plan_text.tag_configure("bullet", lmargin1=20, lmargin2=40)
        self.plan_text.tag_configure("normal", font=("Helvetica", 14))
        self.plan_text.tag_configure("timestamp", font=("Helvetica", 12), foreground="#eb5e28")

        # Add timestamp at the top
        if is_saved_plan and 'timestamp' in responses:
            timestamp = responses['timestamp']
        else:
            current_time = datetime.now()
            timestamp = current_time.strftime("%B %d, %Y | %I:%M%p").replace("AM", "am").replace("PM", "pm")
            responses['timestamp'] = timestamp

        self.plan_text.insert("end", timestamp + "\n\n", "timestamp")

        # Get the plan text and instructions
        if is_saved_plan and 'plan_text' in responses:
            plan = responses['plan_text']
        else:
            plan = self.generate_workout_plan(responses)
            responses['plan_text'] = plan

        # Store exercise instructions for later use
        self.exercise_instructions = responses.get('exercise_instructions', {})

        # Process and insert the plan with formatting
        lines = plan.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                self.plan_text.insert("end", "\n")
                continue

            # Remove any remaining asterisks from the line
            line = line.replace('*', '')

            if line.startswith('#') and not line.startswith('##'):
                # Header
                header_text = line.lstrip('#').strip()
                self.plan_text.insert("end", header_text + "\n", "header")
            elif line.startswith('##'):
                # Subheader
                subheader_text = line.lstrip('#').strip()
                self.plan_text.insert("end", subheader_text + "\n", "subheader")
            elif '[' in line and ']' in line:
                # Line contains exercise name(s) in brackets
                current_pos = 0
                while '[' in line[current_pos:] and ']' in line[current_pos:]:
                    # Find the next exercise
                    start = line.find('[', current_pos)
                    end = line.find(']', start)
                    
                    if start > current_pos:
                        # Insert any text before the exercise name
                        self.plan_text.insert("end", line[current_pos:start])
                    
                    # Extract and insert the exercise name
                    exercise_name = line[start + 1:end]
                    
                    # Create a unique tag for this exercise
                    tag_name = f"link_{len(self.exercise_instructions)}_{exercise_name}"
                    self.plan_text.tag_configure(tag_name, font=("Helvetica", 14, "bold"), 
                                               foreground="#4dabf7", underline=1)
                    
                    # Insert the exercise name and get indices for tagging
                    start_index = self.plan_text.index("end-1c")
                    self.plan_text.insert("end", exercise_name)
                    end_index = self.plan_text.index("end-1c")
                    
                    # Apply the tag
                    self.plan_text.tag_add(tag_name, start_index, end_index)
                    
                    # Create click handler for this exercise
                    def make_click_handler(name):
                        def handler(event):
                            instructions = self.exercise_instructions.get(name, "Instructions not available.")
                            ExerciseInstructionPopup(self, name, instructions)
                        return handler
                    
                    # Bind click event
                    self.plan_text.tag_bind(tag_name, "<Button-1>", make_click_handler(exercise_name))
                    self.plan_text.tag_bind(tag_name, "<Enter>", 
                        lambda e: self.plan_text.config(cursor="hand2"))
                    self.plan_text.tag_bind(tag_name, "<Leave>", 
                        lambda e: self.plan_text.config(cursor=""))
                    
                    current_pos = end + 1
                
                # Add any remaining text after the last exercise
                if current_pos < len(line):
                    self.plan_text.insert("end", line[current_pos:])
                self.plan_text.insert("end", "\n")
            elif line.startswith('-'):
                # Bullet point
                bullet_text = line.lstrip('-').strip()
                self.plan_text.insert("end", "• " + bullet_text + "\n", "bullet")
            else:
                # Normal text
                self.plan_text.insert("end", line + "\n", "normal")

        # Make it read-only
        self.plan_text.config(state="disabled")

        # Force update of all widgets
        self.update_idletasks()

    def create_buttons(self):
        """Create the refresh and new plan buttons."""
        # Create a frame to hold buttons side by side
        button_frame = tk.Frame(self.button_container, bg='#212529')
        button_frame.pack(expand=True)

        # Create refresh button (clear with orange outline)
        self.refresh_canvas = tk.Canvas(button_frame, width=150, height=40,
                                      bg='#212529', highlightthickness=0)
        self.refresh_canvas.pack(side="left", padx=10)
        self.refresh_canvas.create_rounded_rect(0, 0, 150, 40, 8,
                                              fill='#212529', outline='#eb5e28', width=2)
        self.refresh_label = tk.Label(self.refresh_canvas, text="Refresh Plan", 
                                    font=("Helvetica", 12, "bold"),
                                    bg='#212529', fg='white')
        self.refresh_label.place(relx=0.5, rely=0.5, anchor="center")

        # Bind both canvas and label for better click handling
        self.refresh_canvas.bind("<Button-1>", lambda e: self.refresh_plan())
        self.refresh_label.bind("<Button-1>", lambda e: self.refresh_plan())

        # Add hover effect for refresh button
        def on_refresh_enter(e):
            self.refresh_canvas.delete("all")
            self.refresh_canvas.create_rounded_rect(0, 0, 150, 40, 8,
                                                 fill='#2b3035', outline='#eb5e28', width=2)
            self.refresh_label.configure(bg='#2b3035')

        def on_refresh_leave(e):
            self.refresh_canvas.delete("all")
            self.refresh_canvas.create_rounded_rect(0, 0, 150, 40, 8,
                                                 fill='#212529', outline='#eb5e28', width=2)
            self.refresh_label.configure(bg='#212529')

        self.refresh_canvas.bind("<Enter>", on_refresh_enter)
        self.refresh_label.bind("<Enter>", on_refresh_enter)
        self.refresh_canvas.bind("<Leave>", on_refresh_leave)
        self.refresh_label.bind("<Leave>", on_refresh_leave)

        # Create new plan button (full orange)
        self.new_plan_canvas = tk.Canvas(button_frame, width=150, height=40,
                                       bg='#212529', highlightthickness=0)
        self.new_plan_canvas.pack(side="left", padx=10)
        self.new_plan_canvas.create_rounded_rect(0, 0, 150, 40, 8,
                                               fill='#eb5e28', outline='#eb5e28')
        self.new_plan_label = tk.Label(self.new_plan_canvas, text="New Plan",
                                     font=("Helvetica", 12, "bold"),
                                     bg='#eb5e28', fg='white')
        self.new_plan_label.place(relx=0.5, rely=0.5, anchor="center")

        # Add hover effect for new plan button
        def on_new_plan_enter(e):
            self.new_plan_canvas.delete("all")
            self.new_plan_canvas.create_rounded_rect(0, 0, 150, 40, 8,
                                                   fill='#d44e1e', outline='#d44e1e')
            self.new_plan_label.configure(bg='#d44e1e')

        def on_new_plan_leave(e):
            self.new_plan_canvas.delete("all")
            self.new_plan_canvas.create_rounded_rect(0, 0, 150, 40, 8,
                                                   fill='#eb5e28', outline='#eb5e28')
            self.new_plan_label.configure(bg='#eb5e28')

        # Bind both canvas and label for better click handling
        self.new_plan_canvas.bind("<Button-1>", lambda e: self.start_new_plan())
        self.new_plan_label.bind("<Button-1>", lambda e: self.start_new_plan())
        self.new_plan_canvas.bind("<Enter>", on_new_plan_enter)
        self.new_plan_label.bind("<Enter>", on_new_plan_enter)
        self.new_plan_canvas.bind("<Leave>", on_new_plan_leave)
        self.new_plan_label.bind("<Leave>", on_new_plan_leave)

    def start_new_plan(self):
        """Start a new workout plan by showing the main form"""
        # Destroy the current workout plan page
        self.destroy()

        # Show the main form
        self.app.show_main_form()

    def open_url(self, url):
        """Open the URL in the default web browser"""
        import webbrowser
        webbrowser.open(url)

    def generate_workout_plan(self, responses):
        # Create a prompt for Gemini based on user responses
        prompt = f"""Create a detailed, personalized workout plan based on the following user preferences:

Workout Focus: {responses['Workout Focus']}
{"Targeted Muscles: " + ", ".join(responses['Muscle Groups']) if responses['Muscle Groups'] else ""}
Goal: {responses['Goal']}
Experience Level: {responses['Experience']}
Equipment: {", ".join(responses['Equipment'])}
Duration: {responses['Duration']}
Location: {responses['Location']}
{"Injuries/Restrictions: " + responses['Injuries'] if responses['Injuries'] else ""}
Workout Style: {responses['Workout Style']}

Please provide a comprehensive workout plan that includes:
1. A warm-up routine
2. Main workout exercises with sets, reps, and rest periods
3. A cool-down routine
4. Any specific notes or modifications based on the user's preferences and restrictions

Important Guidelines:
1. Only suggest exercises that can be done with the available equipment
2. Ensure exercises are appropriate for the user's experience level
3. Account for any injuries or restrictions in the exercise selection
4. Match the workout duration to the user's preference
5. Consider the workout location in exercise selection

Formatting Guidelines:
1. Use markup to format the workouts
2. Make the title of the workout an H1 (use #)
3. Make the different workout block headers an H2 (use ##)
4. For each exercise:
   - Put the exercise name in square brackets [Exercise Name]
   - Include sets, reps, rest time, and important notes after the exercise name
   - Use bullet points (-) for sets, reps, and notes
5. Use clear spacing between sections and exercises

Format the plan in a clear, easy-to-follow structure with each exercise name in [brackets]."""

        try:
            # Generate the workout plan using Gemini
            logging.info("Generating workout plan with Gemini API...")
            response = model.generate_content(prompt)

            if not response or not response.text:
                logging.error("Empty response from Gemini API")
                raise ValueError("Empty response from Gemini API")

            plan_text = response.text
            logging.info("Successfully generated workout plan")

            # Process the plan to identify exercises and get their instructions
            lines = plan_text.split('\n')
            processed_lines = []
            exercise_instructions = {}

            for line in lines:
                line = line.strip()
                
                # Skip empty lines
                if not line:
                    processed_lines.append(line)
                    continue

                # Check for exercise names in square brackets
                if '[' in line and ']' in line:
                    start = line.find('[')
                    end = line.find(']')
                    if start < end:
                        exercise_name = line[start + 1:end]
                        
                        # Generate instructions for this exercise
                        instruction_prompt = f"""Provide detailed instructions for the exercise: {exercise_name}

Please include:
1. Starting position
2. Movement execution
3. Breathing pattern
4. Common mistakes to avoid
5. Form cues
6. Safety tips

Keep the instructions clear and concise, focusing on proper form and safety. Put this in markdown format"""

                        try:
                            instruction_response = model.generate_content(instruction_prompt)
                            if instruction_response and instruction_response.text:
                                exercise_instructions[exercise_name] = instruction_response.text.strip()
                                logging.info(f"Generated instructions for {exercise_name}")
                            else:
                                exercise_instructions[exercise_name] = "Instructions not available."
                                logging.warning(f"No instructions generated for {exercise_name}")
                        except Exception as e:
                            exercise_instructions[exercise_name] = "Instructions not available."
                            logging.error(f"Error generating instructions for {exercise_name}: {e}")

                # Add the line as is
                processed_lines.append(line)

            # Store the exercise instructions in the responses dictionary
            responses['exercise_instructions'] = exercise_instructions

            return '\n'.join(processed_lines)

        except Exception as e:
            logging.error(f"Error generating workout plan: {str(e)}")
            logging.error(f"Error type: {type(e).__name__}")
            if hasattr(e, 'response'):
                logging.error(f"API Response: {e.response}")
            # Fallback plan if Gemini fails
            return f"""# YOUR PERSONALIZED WORKOUT PLAN

Workout Focus: {responses['Workout Focus']}
{"Targeted Muscles: " + ", ".join(responses['Muscle Groups']) if responses['Muscle Groups'] else ""}
Goal: {responses['Goal']}
Experience Level: {responses['Experience']}
Equipment: {", ".join(responses['Equipment'])}
Duration: {responses['Duration']}
Location: {responses['Location']}
{"Injuries/Restrictions: " + responses['Injuries'] if responses['Injuries'] else ""}
Workout Style: {responses['Workout Style']}

Note: We encountered an error while generating your workout plan. Please try again later or contact support if the issue persists.
Error details: {str(e)}"""

    def refresh_plan(self):
        """Generate a new workout plan with the same preferences"""
        # Clear the current plan display
        for widget in self.plan_container.winfo_children():
            widget.destroy()

        # Show loading screen with progress bar
        self.show_loading_screen()

        # Start new plan generation
        self.after(100, lambda: self.start_plan_generation(self.responses))

    def update_loading_sentence(self):
        """Show a new random, non-repeating sentence every 5 seconds while loading."""
        if not getattr(self, 'loading_sentence_active', True):
            return
        if self.loading_sentence_pointer >= len(self.loading_sentence_indices):
            # If we run out, reshuffle and start over (shouldn't happen in normal loading)
            import random
            self.loading_sentence_indices = list(range(len(self.loading_sentences)))
            random.shuffle(self.loading_sentence_indices)
            self.loading_sentence_pointer = 0
        idx = self.loading_sentence_indices[self.loading_sentence_pointer]
        self.loading_sentence_label.config(text=self.loading_sentences[idx])
        self.loading_sentence_pointer += 1
        # Only update if still generating
        if getattr(self, 'is_generating', False):
            self.after(5000, self.update_loading_sentence)
        else:
            self.loading_sentence_active = False


class ExerciseInstructionPopup(tk.Toplevel):
    def __init__(self, parent, exercise_name, instructions):
        super().__init__(parent)
        self.title(f"{exercise_name} Instructions")
        
        # Set window properties
        self.geometry("400x600")
        self.configure(bg='#212529')
        self.transient(parent)  # Set to be on top of the main window
        self.grab_set()  # Make the popup modal
        
        # Store for dynamic resizing
        self.exercise_name = exercise_name
        self.header_label = None
        self.header_font_large = ("Impact", 24)
        self.header_font_small = ("Impact", 16)
        self.header_min_font = ("Impact", 12)
        self.header_padding = 40  # 20px left/right

        # Create main container
        main_container = tk.Frame(self, bg='#212529', padx=20, pady=20)
        main_container.pack(fill="both", expand=True)
        
        # Add exercise name as header (will be updated responsively)
        self.header_label = tk.Label(main_container, text=exercise_name,
                                    font=self.header_font_large, bg='#212529', fg='#eb5e28',
                                    wraplength=340, justify="center")
        self.header_label.pack(pady=(0, 20))

        # Bind resize event for responsive header
        self.bind("<Configure>", self._on_resize_header)

        # Create text frame
        text_frame = tk.Frame(main_container, bg='#212529')
        text_frame.pack(fill="both", expand=True)
        
        # Create text widget for instructions
        self.text_widget = tk.Text(text_frame, wrap=tk.WORD,
                                 bg='#212529', fg='white',
                                 font=("Helvetica", 14),
                                 padx=10, pady=10,
                                 highlightthickness=0,
                                 borderwidth=0)
        self.text_widget.pack(side="left", fill="both", expand=True)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical",
                                command=self.text_widget.yview)
        scrollbar.pack(side="right", fill="y")
        self.text_widget.configure(yscrollcommand=scrollbar.set)

        # Configure text tags for formatting
        self.text_widget.tag_configure("header", 
                                     font=("Helvetica", 16, "bold"), 
                                     foreground="#eb5e28",
                                     spacing1=10,
                                     spacing3=10)
        self.text_widget.tag_configure("normal", 
                                     font=("Helvetica", 14),
                                     foreground="white",
                                     spacing1=0,
                                     spacing2=0,
                                     spacing3=0,
                                     lmargin1=0,
                                     lmargin2=0,
                                     justify="left")
        self.text_widget.tag_configure("bullet", 
                                     font=("Helvetica", 14),
                                     foreground="white",
                                     spacing1=0,
                                     spacing2=0,
                                     spacing3=0,
                                     lmargin1=10,
                                     lmargin2=25,
                                     justify="left")

        # --- Improved Formatting logic ---
        import re
        sections = [re.sub(r'[\*#]+', '', s).strip() for s in instructions.split('\n') if s.strip()]
        numbered_heading = re.compile(r'^(\d+)\.\s*([A-Za-z ]{1,40}?)(:|\.)$')
        intro_lines = []
        outro_lines = []
        headings = []
        heading_indices = []
        # Find all heading indices
        for idx, section in enumerate(sections):
            if numbered_heading.match(section):
                headings.append(section)
                heading_indices.append(idx)
        # Find intro (before first heading)
        first_heading_idx = heading_indices[0] if heading_indices else None
        last_heading_idx = heading_indices[-1] if heading_indices else None
        # Collect intro lines
        if first_heading_idx is not None:
            intro_lines = sections[:first_heading_idx]
        else:
            intro_lines = sections[:]
        # Collect outro lines (after last heading's bullets)
        if last_heading_idx is not None:
            # Find where the last heading's bullets end
            idx = last_heading_idx + 1
            while idx < len(sections):
                # If it's a heading, break
                if numbered_heading.match(sections[idx]):
                    break
                idx += 1
            outro_lines = sections[idx:]
        # Insert intro as normal paragraph
        if intro_lines:
            self.text_widget.insert("end", " ".join(intro_lines) + "\n\n", "normal")
        # Insert headings and their bullets
        idx = first_heading_idx if first_heading_idx is not None else len(sections)
        while idx < len(sections):
            section = sections[idx]
            if numbered_heading.match(section):
                self.text_widget.insert("end", section + "\n", "header")
                idx += 1
                # Insert bullets under this heading
                while idx < len(sections) and not numbered_heading.match(sections[idx]):
                    bullet = sections[idx]
                    # Only treat as bullet if not empty and not duplicate of heading
                    if bullet and bullet != section:
                        self.text_widget.insert("end", "• " + bullet + "\n", "bullet")
                    idx += 1
            else:
                idx += 1
        # Insert outro as normal paragraph
        if outro_lines:
            self.text_widget.insert("end", "\n" + " ".join(outro_lines) + "\n", "normal")

        # Make text widget read-only
        self.text_widget.config(state="disabled")
        
        # Create button frame
        button_frame = tk.Frame(main_container, bg='#212529', pady=20)
        button_frame.pack()

        # Create canvas for the rounded button
        button_canvas = tk.Canvas(button_frame, width=150, height=40,
                                bg='#212529', highlightthickness=0)
        button_canvas.pack()

        # Create rounded rectangle button
        button_canvas.create_rounded_rect(0, 0, 150, 40, 8,
                                        fill='#eb5e28', outline='#eb5e28')

        # Add button label
        button_label = tk.Label(button_canvas, text="Close",
                              font=("Helvetica", 12, "bold"),
                              bg='#eb5e28', fg='white',
                              cursor="hand2")
        button_label.place(relx=0.5, rely=0.5, anchor='center')

        # Add hover effect
        def on_enter(e):
            button_canvas.delete("all")
            button_canvas.create_rounded_rect(0, 0, 150, 40, 8,
                                           fill='#d44e1e', outline='#d44e1e')
            button_label.configure(bg='#d44e1e')

        def on_leave(e):
            button_canvas.delete("all")
            button_canvas.create_rounded_rect(0, 0, 150, 40, 8,
                                           fill='#eb5e28', outline='#eb5e28')
            button_label.configure(bg='#eb5e28')

        # Bind events
        button_canvas.bind("<Button-1>", lambda e: self.destroy())
        button_label.bind("<Button-1>", lambda e: self.destroy())
        button_canvas.bind("<Enter>", on_enter)
        button_label.bind("<Enter>", on_enter)
        button_canvas.bind("<Leave>", on_leave)
        button_label.bind("<Leave>", on_leave)
        
        # Center the window on the screen
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _on_resize_header(self, event=None):
        # Responsive wraplength and font size for header
        width = self.winfo_width()
        wrap = max(100, width - self.header_padding)
        text_len = len(self.exercise_name)
        # Heuristic: normal font unless text would wrap to more than 2 lines
        avg_char_width = 13  # rough px width for Impact 24
        max_chars_per_line = wrap // avg_char_width
        if text_len > max_chars_per_line * 2:
            font = self.header_font_small
        else:
            font = self.header_font_large
        self.header_label.config(wraplength=wrap, font=font)


if __name__ == "__main__":
    app = WorkoutApp()
    app.mainloop()
