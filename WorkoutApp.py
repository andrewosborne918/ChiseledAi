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

class ExerciseDatabase:
    def __init__(self, excel_path: str):
        """Initialize the exercise database from an Excel file"""
        try:
            self.df = pd.read_excel(excel_path)
            logging.info(f"Successfully loaded exercise database from {excel_path}")
            self._validate_database()
        except Exception as e:
            logging.error(f"Error loading exercise database: {e}")
            raise

    def _validate_database(self):
        """Validate that the database has the required columns"""
        required_columns = ['exercise_name', 'difficulty', 'muscle_group', 'video_url']
        missing_columns = [col for col in required_columns if col not in self.df.columns]
        if missing_columns:
            logging.warning(f"Missing columns in exercise database: {missing_columns}")
            # Add missing columns with default values
            for col in missing_columns:
                if col == 'video_url':
                    self.df[col] = None
                else:
                    self.df[col] = 'Unknown'
            logging.info("Added default values for missing columns")

    def get_exercises_by_muscle_group(self, muscle_group: str) -> List[Dict]:
        """Get all exercises for a specific muscle group"""
        return self.df[self.df['muscle_group'] == muscle_group].to_dict('records')

    def get_exercises_by_difficulty(self, difficulty: str) -> List[Dict]:
        """Get all exercises of a specific difficulty level"""
        return self.df[self.df['difficulty'] == difficulty].to_dict('records')

    def get_exercises_by_equipment(self, equipment: str) -> List[Dict]:
        """Get all exercises that can be done with specific equipment"""
        if 'equipment' in self.df.columns:
            return self.df[self.df['equipment'] == equipment].to_dict('records')
        else:
            logging.warning("Equipment column not found, returning all exercises")
            return self.df.to_dict('records')

    def get_exercise(self, exercise_name: str) -> Optional[Dict]:
        """Get a specific exercise by name"""
        exercise = self.df[self.df['exercise_name'] == exercise_name]
        return exercise.to_dict('records')[0] if not exercise.empty else None

    def get_random_exercises(self, count: int = 1, **filters) -> List[Dict]:
        """Get random exercises with optional filters"""
        filtered_df = self.df
        for key, value in filters.items():
            if key in self.df.columns:
                filtered_df = filtered_df[filtered_df[key] == value]
        return filtered_df.sample(min(count, len(filtered_df))).to_dict('records')

    def get_exercises_by_filters(self, muscle_group: Optional[str] = None, 
                               difficulty: Optional[str] = None,
                               equipment: Optional[str] = None) -> List[Dict]:
        """Get exercises matching multiple criteria"""
        filtered_df = self.df
        if muscle_group:
            filtered_df = filtered_df[filtered_df['muscle_group'] == muscle_group]
        if difficulty:
            filtered_df = filtered_df[filtered_df['difficulty'] == difficulty]
        if equipment and 'equipment' in self.df.columns:
            filtered_df = filtered_df[filtered_df['equipment'] == equipment]
        return filtered_df.to_dict('records')

# Initialize the exercise database
try:
    EXERCISE_DB = ExerciseDatabase('Exercise_Database.xlsx')  # Updated to match the correct filename
except Exception as e:
    logging.error(f"Failed to initialize exercise database: {e}")
    EXERCISE_DB = None

def get_youtube_video(exercise_name):
    """Return a YouTube search URL for the exercise"""
    try:
        if EXERCISE_DB:
            exercise = EXERCISE_DB.get_exercise(exercise_name)
            if exercise and exercise.get('video_url'):
                logging.info(f"Found video URL in database for {exercise_name}: {exercise['video_url']}")
                return exercise['video_url'], "Exercise Database"
            else:
                logging.info(f"No video URL found in database for {exercise_name}")
        
        # Fallback to YouTube search if no database match
        search_query = f"{exercise_name} exercise tutorial proper form"
        search_url = f"https://www.youtube.com/results?search_query={search_query.replace(' ', '+')}"
        logging.info(f"Using YouTube search URL for {exercise_name}: {search_url}")
        return search_url, "YouTube Search"
    except Exception as e:
        logging.error(f"Error getting video URL for {exercise_name}: {e}")
        return None, None

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
        
        # Set minimum window size (similar to a phone screen)
        self.minsize(360, 640)
        
        # Set background color to dark gray
        self.configure(bg='#212529')
        
        # Bind window resize event
        self.bind('<Configure>', self.on_window_resize)
        
        # Get the appropriate data directory based on platform
        self.data_dir = self.get_data_directory()
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Create loading screen
        self.loading_frame = tk.Frame(self, bg='#212529')
        self.loading_frame.pack(fill="both", expand=True)
        
        # Create a container for vertical distribution
        self.loading_container = tk.Frame(self.loading_frame, bg='#212529', padx=40)
        self.loading_container.pack(expand=True, fill="both", pady=50)
        
        # Add title to loading screen
        self.title_label = tk.Label(self.loading_container, text="CHISELED AI", 
                             font=("Impact", 80), bg='#212529', fg='#eb5e28')
        self.title_label.pack(pady=20)
        
        # Load and display logo
        try:
            logo_image = Image.open("Images/Chiseled_logo.png")
            max_size = (400, 400)
            logo_image.thumbnail(max_size, Image.Resampling.LANCZOS)
            self.logo_photo = ImageTk.PhotoImage(logo_image)
            self.logo_label = tk.Label(self.loading_container, image=self.logo_photo, bg='#212529')
            self.logo_label.pack(pady=20)
        except Exception as e:
            print(f"Error loading logo: {e}")
            self.subtitle_label = tk.Label(self.loading_container, text="CHISELED AI LOGO", 
                                    font=("Helvetica", 16), bg='#212529', fg='white')
            self.subtitle_label.pack(pady=20)
        
        # Add tagline
        self.tagline_label = tk.Label(self.loading_container, text="YOUR PERSONAL WORKOUT PLANNER", 
                               font=("Helvetica", 24), bg='#212529', fg='white')
        self.tagline_label.pack(pady=20)
        
        # Check for saved workout plan
        self.saved_plan = self.load_saved_plan()
        
        # Schedule the main form or saved plan to appear after 3 seconds
        self.after(3000, self.show_initial_screen)
    
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
            print(f"Window width: {width}")  # Debug logging
            
            if width < 450:
                print("Applying small screen font sizes")  # Debug logging
                # Small screen font sizes
                if hasattr(self, 'title_label'):
                    self.title_label.config(font=("Impact", 40))
                if hasattr(self, 'subtitle_label'):
                    self.subtitle_label.config(font=("Helvetica", 12))
                if hasattr(self, 'tagline_label'):
                    self.tagline_label.config(font=("Helvetica", 16))
                if hasattr(self, 'main_title_label'):
                    self.main_title_label.config(font=("Impact", 30))
                if hasattr(self, 'main_subtitle_label'):
                    self.main_subtitle_label.config(font=("Helvetica", 12))
                
                # Update loading screen image size
                if hasattr(self, 'logo_image'):
                    max_size = (200, 200)  # Smaller size for small screens
                    self.logo_image.thumbnail(max_size, Image.Resampling.LANCZOS)
                    self.logo_photo = ImageTk.PhotoImage(self.logo_image)
                    if hasattr(self, 'logo_label'):
                        self.logo_label.config(image=self.logo_photo)
                
                # Update question fonts
                if hasattr(self, 'sections'):
                    print("Updating question fonts to small size")  # Debug logging
                    for section in self.sections:
                        # Update question label
                        if hasattr(section, 'question_label'):
                            section.question_label.config(font=("Helvetica", 12, "bold"), wraplength=300)
                            print(f"Updated question label in {section.__class__.__name__}")  # Debug logging
                        
                        # Update all labels in the section
                        for widget in section.winfo_children():
                            if isinstance(widget, tk.Label):
                                widget.config(font=("Helvetica", 12), wraplength=300)
                            elif isinstance(widget, tk.Checkbutton) or isinstance(widget, tk.Radiobutton):
                                widget.config(font=("Helvetica", 10), wraplength=300)
                            elif isinstance(widget, tk.Frame):
                                # Check widgets in nested frames
                                for child in widget.winfo_children():
                                    if isinstance(child, tk.Label):
                                        child.config(font=("Helvetica", 12), wraplength=300)
                                    elif isinstance(child, tk.Checkbutton) or isinstance(child, tk.Radiobutton):
                                        child.config(font=("Helvetica", 10), wraplength=300)
                
                # Auto-sync after significant UI changes
                git_sync("Auto-sync: Updated UI for small screen")
            else:
                print("Applying normal screen font sizes")  # Debug logging
                # Normal screen font sizes
                if hasattr(self, 'title_label'):
                    self.title_label.config(font=("Impact", 80))
                if hasattr(self, 'subtitle_label'):
                    self.subtitle_label.config(font=("Helvetica", 16))
                if hasattr(self, 'tagline_label'):
                    self.tagline_label.config(font=("Helvetica", 24))
                if hasattr(self, 'main_title_label'):
                    self.main_title_label.config(font=("Impact", 50))
                if hasattr(self, 'main_subtitle_label'):
                    self.main_subtitle_label.config(font=("Helvetica", 14))
                
                # Update loading screen image size
                if hasattr(self, 'logo_image'):
                    max_size = (400, 400)  # Normal size for larger screens
                    self.logo_image.thumbnail(max_size, Image.Resampling.LANCZOS)
                    self.logo_photo = ImageTk.PhotoImage(self.logo_image)
                    if hasattr(self, 'logo_label'):
                        self.logo_label.config(image=self.logo_photo)
                
                # Update question fonts
                if hasattr(self, 'sections'):
                    print("Updating question fonts to normal size")  # Debug logging
                    for section in self.sections:
                        # Update question label
                        if hasattr(section, 'question_label'):
                            section.question_label.config(font=("Helvetica", 16, "bold"), wraplength=400)
                            print(f"Updated question label in {section.__class__.__name__}")  # Debug logging
                        
                        # Update all labels in the section
                        for widget in section.winfo_children():
                            if isinstance(widget, tk.Label):
                                widget.config(font=("Helvetica", 16), wraplength=400)
                            elif isinstance(widget, tk.Checkbutton) or isinstance(widget, tk.Radiobutton):
                                widget.config(font=("Helvetica", 12), wraplength=400)
                            elif isinstance(widget, tk.Frame):
                                # Check widgets in nested frames
                                for child in widget.winfo_children():
                                    if isinstance(child, tk.Label):
                                        child.config(font=("Helvetica", 16), wraplength=400)
                                    elif isinstance(child, tk.Checkbutton) or isinstance(child, tk.Radiobutton):
                                        child.config(font=("Helvetica", 12), wraplength=400)
                
                # Auto-sync after significant UI changes
                git_sync("Auto-sync: Updated UI for normal screen")
            
            # Force update of all widgets
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
        self.muscle_section = MuscleGroup(self.question_container, self)
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
            self.muscle_section,
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
            # Update numbering for target muscle group path
            self.goal_section.update_numbering(3)
            self.experience_section.update_numbering(4)
            self.equipment_section.update_numbering(5)
            self.duration_section.update_numbering(6)
            self.location_section.update_numbering(7)
            self.injury_section.update_numbering(8)
            self.style_section.update_numbering(9)
        else:
            # Update numbering for full body path
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
            def create_rounded_rect(canvas, x1, y1, x2, y2, radius, **kwargs):
                points = [
                    x1+radius, y1,
                    x2-radius, y1,
                    x2, y1,
                    x2, y1+radius,
                    x2, y2-radius,
                    x2, y2,
                    x2-radius, y2,
                    x1+radius, y2,
                    x1, y2,
                    x1, y2-radius,
                    x1, y1+radius,
                    x1, y1,
                ]
                return canvas.create_polygon(points, smooth=True, **kwargs)
            
            # Create the rounded rectangle background
            radius = 10 if width < 450 else 15
            create_rounded_rect(self.submit_canvas, 0, 0, button_width, button_height, radius, 
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
            self.submit_label.bind("<Button-1>", lambda e: self.collect_responses())

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
        responses = {
            "Workout Focus": self.focus_var.get(),
            "Muscle Groups": [group for group, var in self.muscle_vars.items() if var.get()] if self.focus_var.get() == "Target muscle group" else None,
            "Goal": self.goal_var.get(),
            "Experience": self.experience_var.get(),
            "Equipment": self.equipment_section.collect_equipment_info(),
            "Duration": self.duration_var.get(),
            "Location": self.location_var.get(),
            "Injuries": self.injury_section.collect_injury_info(),
            "Workout Style": self.style_var.get(),
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

# Each question section as a class

class WorkoutFocus(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg='#212529')
        self.app = app
        
        # Create centered container
        self.center_frame = tk.Frame(self, bg='#212529', padx=5)
        self.center_frame.pack(expand=True, fill="both", padx=5, pady=10)
        
        tk.Label(self.center_frame, text="1. What kind of workout would you like to do?", 
                 font=("Helvetica", 16, "bold"), bg='#212529', fg='white', wraplength=500).pack(anchor="w", pady=5)
        dropdown = ttk.Combobox(self.center_frame, textvariable=app.focus_var, 
                              values=["Full body", "Target muscle group"])
        dropdown.pack(fill="x", pady=5)
        # Remove automatic advancement
        dropdown.bind("<<ComboboxSelected>>", lambda e: None)
        # Make entire dropdown clickable to show list
        dropdown.bind("<Button-1>", lambda e: dropdown.focus_set() or dropdown.event_generate('<Down>'))

class MuscleGroup(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg='#212529')
        self.app = app
        self.muscle_groups = ["Chest", "Back", "Legs", "Arms", "Shoulders", "Core", "Glutes"]
        
        # Create centered container
        self.center_frame = tk.Frame(self, bg='#212529', padx=5)
        self.center_frame.pack(expand=True, fill="both", padx=5, pady=10)
        
        tk.Label(self.center_frame, text="2. Which muscle groups?", 
                 font=("Helvetica", 16, "bold"), bg='#212529', fg='white', wraplength=300).pack(anchor="w", pady=5)
        
        # Create a frame to hold the checkboxes
        self.checkbox_frame = tk.Frame(self.center_frame, bg='#212529')
        self.checkbox_frame.pack(fill="x", pady=5)
        
        # Create checkboxes for each muscle group
        for group in self.muscle_groups:
            var = tk.BooleanVar()
            self.app.muscle_vars[group] = var
            tk.Checkbutton(self.checkbox_frame, text=group, variable=var,
                          command=lambda: None, font=("Helvetica", 12),
                          bg='#212529', fg='white', wraplength=300).pack(anchor="w", pady=2)
    
    def on_checkbox_change(self):
        # Check if at least one muscle group is selected
        if any(var.get() for var in self.app.muscle_vars.values()):
            self.app.show_next_question()

class WorkoutGoal(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg='#212529')
        self.app = app
        
        # Create centered container
        self.center_frame = tk.Frame(self, bg='#212529', padx=5)
        self.center_frame.pack(expand=True, fill="both", padx=5, pady=10)
        
        self.question_label = tk.Label(self.center_frame, font=("Helvetica", 16, "bold"), bg='#212529', fg='white', wraplength=300)
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

class ExperienceLevel(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg='#212529')
        self.app = app
        
        # Create centered container
        self.center_frame = tk.Frame(self, bg='#212529', padx=5)
        self.center_frame.pack(expand=True, fill="both", padx=5, pady=10)
        
        self.question_label = tk.Label(self.center_frame, font=("Helvetica", 16, "bold"), bg='#212529', fg='white', wraplength=300)
        self.question_label.pack(anchor="w", pady=5)
        for level in ["Beginner", "Intermediate", "Advanced"]:
            tk.Radiobutton(self.center_frame, text=level, variable=app.experience_var, value=level,
                          command=lambda: None, font=("Helvetica", 12),
                          bg='#212529', fg='white', wraplength=300).pack(anchor="w", pady=2)
    
    def update_numbering(self, number):
        self.question_label.config(text=f"{number}. What is your fitness level?")

class EquipmentSelection(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg='#212529')
        self.app = app
        
        # Create centered container
        self.center_frame = tk.Frame(self, bg='#212529', padx=5)
        self.center_frame.pack(expand=True, fill="both", padx=5, pady=10)
        
        self.question_label = tk.Label(self.center_frame, font=("Helvetica", 16, "bold"), bg='#212529', fg='white', wraplength=300)
        self.question_label.pack(anchor="w", pady=5)
        equipment_list = ["Bodyweight only", "Dumbbells", "Barbells", "Resistance bands", "Kettlebells", "Machines", "Other"]
        
        # Create a frame for checkboxes
        self.checkbox_frame = tk.Frame(self.center_frame, bg='#212529')
        self.checkbox_frame.pack(fill="x", pady=5)
        
        # Create checkboxes for each equipment type
        for eq in equipment_list:
            var = tk.BooleanVar()
            app.equipment_vars[eq] = var
            tk.Checkbutton(self.checkbox_frame, text=eq, variable=var,
                          command=lambda eq=eq: self.on_checkbox_change(eq),
                          font=("Helvetica", 12), bg='#212529', fg='white', wraplength=300).pack(anchor="w", pady=2)
        
        # Create text entry frame (initially hidden)
        self.text_frame = tk.Frame(self.center_frame, bg='#212529')
        self.text_label = tk.Label(self.text_frame, text="Please describe your other equipment:", 
                                  font=("Helvetica", 12), bg='#212529', fg='white')
        self.text_label.pack(anchor="w", pady=(20, 5))
        
        # Create text widget for multi-line input
        self.text_widget = tk.Text(self.text_frame, height=4, font=("Helvetica", 12), bg='#212529', fg='white')
        self.text_widget.pack(fill="x", pady=5)
        
        # Add scrollbar to text widget
        text_scrollbar = ttk.Scrollbar(self.text_frame, orient="vertical", command=self.text_widget.yview)
        text_scrollbar.pack(side="right", fill="y")
        self.text_widget.configure(yscrollcommand=text_scrollbar.set)
    
    def on_checkbox_change(self, equipment):
        if equipment == "Other":
            if self.app.equipment_vars["Other"].get():
                self.text_frame.pack(fill="x", pady=10)
            else:
                self.text_frame.pack_forget()
        # Remove automatic advancement
        # Just update the UI without advancing to next question
    
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
        
        self.question_label = tk.Label(self.center_frame, font=("Helvetica", 16, "bold"), bg='#212529', fg='white', wraplength=300)
        self.question_label.pack(anchor="w", pady=5)
        dropdown = ttk.Combobox(self.center_frame, textvariable=app.duration_var, 
                              values=["15 minutes", "30 minutes", "45 minutes", "60 minutes"])
        dropdown.pack(fill="x", pady=5)
        # Remove automatic advancement
        dropdown.bind("<<ComboboxSelected>>", lambda e: None)
        # Make entire dropdown clickable to show list
        dropdown.bind("<Button-1>", lambda e: dropdown.focus_set() or dropdown.event_generate('<Down>'))
    
    def update_numbering(self, number):
        self.question_label.config(text=f"{number}. Workout duration?")

class WorkoutLocation(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg='#212529')
        self.app = app
        
        # Create centered container
        self.center_frame = tk.Frame(self, bg='#212529', padx=5)
        self.center_frame.pack(expand=True, fill="both", padx=5, pady=10)
        
        self.question_label = tk.Label(self.center_frame, font=("Helvetica", 16, "bold"), bg='#212529', fg='white', wraplength=300)
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
        
        # Create centered container
        self.center_frame = tk.Frame(self, bg='#212529', padx=5)
        self.center_frame.pack(expand=True, fill="both", padx=5, pady=10)
        
        self.question_label = tk.Label(self.center_frame, font=("Helvetica", 16, "bold"), bg='#212529', fg='white', wraplength=300)
        self.question_label.pack(anchor="w", pady=5)
        
        # Create a frame for radio buttons
        self.radio_frame = tk.Frame(self.center_frame, bg='#212529')
        self.radio_frame.pack(fill="x", pady=5)
        
        # Create radio buttons with custom appearance
        for option in ["No", "Yes"]:
            # Create a frame for each radio button to control spacing
            radio_container = tk.Frame(self.radio_frame, bg='#212529')
            radio_container.pack(side="left", padx=10)
            
            # Create the radio button with custom indicator
            radio = tk.Radiobutton(
                radio_container,
                text=option,
                variable=app.injury_var,
                value=option,
                command=self.on_injury_selection,
                font=("Helvetica", 12),
                bg='#212529',
                fg='white',
                wraplength=300,
                indicatoron=0,  # Remove default indicator
                selectcolor='#eb5e28',  # Color when selected
                width=8,  # Fixed width for consistent appearance
                height=1,  # Fixed height
                bd=0,  # No border
                highlightthickness=0  # No highlight
            )
            radio.pack(side="left")
        
        # Create text entry frame (initially hidden)
        self.text_frame = tk.Frame(self.center_frame, bg='#212529')
        self.text_label = tk.Label(self.text_frame, text="Please describe your injuries/restrictions:", 
                                  font=("Helvetica", 12), bg='#212529', fg='white')
        self.text_label.pack(anchor="w", pady=(20, 5))
        
        # Create text widget for multi-line input
        self.text_widget = tk.Text(self.text_frame, height=4, font=("Helvetica", 12), bg='#212529', fg='white')
        self.text_widget.pack(fill="x", pady=5)
        
        # Add scrollbar to text widget
        text_scrollbar = ttk.Scrollbar(self.text_frame, orient="vertical", command=self.text_widget.yview)
        text_scrollbar.pack(side="right", fill="y")
        self.text_widget.configure(yscrollcommand=text_scrollbar.set)
    
    def on_injury_selection(self):
        # Only show/hide the text input frame without advancing
        if self.app.injury_var.get() == "Yes":
            self.text_frame.pack(fill="x", pady=10)
        else:
            self.text_frame.pack_forget()
    
    def update_numbering(self, number):
        self.question_label.config(text=f"{number}. Any injuries/restrictions?")

    def collect_injury_info(self):
        if self.app.injury_var.get() == "Yes":
            return self.text_widget.get("1.0", "end-1c").strip()
        return None

class WorkoutStyle(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg='#212529')
        self.app = app
        
        # Create centered container
        self.center_frame = tk.Frame(self, bg='#212529', padx=5)
        self.center_frame.pack(expand=True, fill="both", padx=5, pady=10)
        
        self.question_label = tk.Label(self.center_frame, font=("Helvetica", 16, "bold"), bg='#212529', fg='white', wraplength=300)
        self.question_label.pack(anchor="w", pady=5)
        dropdown = ttk.Combobox(self.center_frame, textvariable=app.style_var,
                              values=["Circuit", "Supersets", "Traditional sets", "HIIT", "Yoga/Pilates", "Stretching/Mobility"])
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
            # Show loading frame only for new plans
            self.loading_frame = tk.Frame(self.plan_container, bg='#212529')
            self.loading_frame.pack(fill="both", expand=True)
            
            self.loading_label = tk.Label(
                self.loading_frame,
                text="Generating your personalized workout plan...",
                font=("Helvetica", 16),
                bg='#212529',
                fg='white'
            )
            self.loading_label.pack(pady=20)
            
            self.loading_dots = tk.Label(
                self.loading_frame,
                text="",
                font=("Helvetica", 24),
                bg='#212529',
                fg='#eb5e28'
            )
            self.loading_dots.pack()
            
            self.dots_count = 0
            self.animate_loading()
            
            # Start plan generation in a separate thread
            self.after(100, lambda: self.generate_and_display_plan(responses))
        else:
            # Display saved plan immediately
            self.display_workout_plan(responses, is_saved_plan=True)
    
    def animate_loading(self):
        """Animate the loading dots"""
        if hasattr(self, 'loading_dots') and self.loading_dots.winfo_exists():
            dots = "." * (self.dots_count % 4)
            self.loading_dots.config(text=dots)
            self.dots_count += 1
            self.after(500, self.animate_loading)
    
    def generate_and_display_plan(self, responses):
        """Generate the plan and update the display"""
        # Remove loading frame if it exists
        if hasattr(self, 'loading_frame'):
            self.loading_frame.pack_forget()
        
        # Generate new plan
        plan = self.generate_workout_plan(responses)
        
        # Save the generated plan
        responses['plan_text'] = plan
        from datetime import datetime
        current_time = datetime.now()
        responses['timestamp'] = current_time.strftime("%B %d, %Y | %I:%M%p").replace("AM", "am").replace("PM", "pm")
        self.app.save_workout_plan(responses)
        
        # Display the workout plan
        self.display_workout_plan(responses, is_saved_plan=True)
    
    def display_workout_plan(self, responses, is_saved_plan=False):
        # Clear any existing plan display
        for widget in self.plan_container.winfo_children():
            widget.destroy()
        
        # Create a text widget for the workout plan
        self.plan_text = tk.Text(self.plan_container, wrap=tk.WORD, bg='#212529', fg='white',
                               font=("Helvetica", 14), padx=10, pady=10)
        self.plan_text.pack(fill="both", expand=True)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(self.plan_container, orient="vertical", command=self.plan_text.yview)
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
        
        # Get the plan text
        if is_saved_plan and 'plan_text' in responses:
            plan = responses['plan_text']
        else:
            plan = self.generate_workout_plan(responses)
            responses['plan_text'] = plan
        
        # Process and insert the plan with formatting
        lines = plan.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                self.plan_text.insert("end", "\n")
                continue
            
            if line.startswith('#'):
                # Header
                header_text = line.lstrip('#').strip()
                self.plan_text.insert("end", header_text + "\n", "header")
            elif line.startswith('##'):
                # Subheader
                subheader_text = line.lstrip('#').strip()
                self.plan_text.insert("end", subheader_text + "\n", "subheader")
            elif line.startswith('[') and '](' in line and ')' in line:
                # Exercise link
                exercise_name = line[line.find('[')+1:line.find(']')]
                url = line[line.find('(')+1:line.find(')')]
                
                # Insert the exercise name as a clickable link
                self.plan_text.insert("end", exercise_name, "exercise_link")
                self.plan_text.insert("end", "\n")
                
                # Store the URL in the tag
                self.plan_text.tag_bind("exercise_link", "<Button-1>", lambda e, url=url: self.open_url(url))
            elif line.startswith('-'):
                # Bullet point
                bullet_text = line.lstrip('-').strip()
                # Check for bold text within bullet points
                if '**' in bullet_text:
                    parts = bullet_text.split('**')
                    self.plan_text.insert("end", "• ", "bullet")
                    for i, part in enumerate(parts):
                        if i % 2 == 0:
                            self.plan_text.insert("end", part, "normal")
                        else:
                            self.plan_text.insert("end", part, "h3")
                    self.plan_text.insert("end", "\n")
                else:
                    self.plan_text.insert("end", "• " + bullet_text + "\n", "bullet")
            else:
                # Normal text
                if '**' in line:
                    parts = line.split('**')
                    for i, part in enumerate(parts):
                        if i % 2 == 0:
                            self.plan_text.insert("end", part, "normal")
                        else:
                            self.plan_text.insert("end", part, "h3")
                    self.plan_text.insert("end", "\n")
                else:
                    self.plan_text.insert("end", line + "\n", "normal")
        
        # Make it read-only
        self.plan_text.config(state="disabled")
        
        # Add some spacing at the end
        self.plan_text.insert("end", "\n\n")
        
        # Create button container
        self.button_container = tk.Frame(self.main_container, bg='#212529', padx=20, pady=10)
        self.button_container.pack(side="bottom", pady=20)
        
        # Create refresh plan button
        width = self.app.winfo_width()
        button_width = 150 if width < 450 else 200
        button_height = 40 if width < 450 else 50
        font_size = 12 if width < 450 else 14
        
        self.refresh_canvas = tk.Canvas(self.button_container, bg='#212529', highlightthickness=0, 
                                     height=button_height, width=button_width)
        self.refresh_canvas.pack(side="left", padx=10)
        
        # Draw rounded rectangle with orange outline
        radius = 10 if width < 450 else 15
        self.create_rounded_rect(self.refresh_canvas, 0, 0, button_width, button_height, radius, 
                              fill='#212529', outline='#eb5e28', width=2)
        
        # Create the label on top of the canvas
        self.refresh_label = tk.Label(
            self.refresh_canvas,
            text="Refresh Plan",
            font=("Helvetica", font_size, "bold"),
            bg='#212529',
            fg='white',
            cursor="hand2"
        )
        self.refresh_label.place(relx=0.5, rely=0.5, anchor='center')
        self.refresh_label.bind("<Button-1>", lambda e: self.refresh_plan(responses))

    def create_rounded_rect(self, canvas, x1, y1, x2, y2, radius, **kwargs):
        """Create a rounded rectangle on the canvas"""
        points = [
            x1+radius, y1,
            x2-radius, y1,
            x2, y1,
            x2, y1+radius,
            x2, y2-radius,
            x2, y2,
            x2-radius, y2,
            x1+radius, y2,
            x1, y2,
            x1, y2-radius,
            x1, y1+radius,
            x1, y1,
        ]
        return canvas.create_polygon(points, smooth=True, **kwargs)

    def refresh_plan(self, responses):
        """Generate a new workout plan with the same preferences"""
        # Remove the current plan display
        for widget in self.plan_container.winfo_children():
            widget.destroy()
        
        # Generate and display a new plan
        self.display_workout_plan(responses, is_saved_plan=False)

    def open_url(self, url):
        """Open the URL in the default web browser"""
        import webbrowser
        webbrowser.open(url)
    
    def generate_workout_plan(self, responses):
        # Create a prompt for Gemini based on user responses
        available_exercises = []
        if EXERCISE_DB:
            # Get exercises based on user's equipment
            for equipment in responses['Equipment']:
                exercises = EXERCISE_DB.get_exercises_by_equipment(equipment)
                available_exercises.extend(exercises)
                logging.info(f"Found {len(exercises)} exercises for equipment: {equipment}")
            
            # If no exercises found for specific equipment, get all exercises
            if not available_exercises:
                available_exercises = EXERCISE_DB.get_random_exercises(20)
                logging.info("No exercises found for specific equipment, using random exercises")
            
            # Get unique exercise names
            exercise_names = list(set(ex['exercise_name'] for ex in available_exercises))
            logging.info(f"Available exercises: {exercise_names}")
            
            # Create a prompt that explicitly lists the exercises
            exercise_list = "\n".join([f"- {name}" for name in exercise_names])
        else:
            exercise_names = []
            exercise_list = ""
            logging.warning("Exercise database not available")

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

Available Exercises:
{exercise_list}

Please provide a comprehensive workout plan that includes:
1. A warm-up routine
2. Main workout exercises with sets, reps, and rest periods
3. A cool-down routine
4. Any specific notes or modifications based on the user's preferences and restrictions

Formatting Guidelines:
1. If there is any information that is sexual or violent, please ignore it
2. Use markup to format the workouts
3. Make the title of the workout an H1 (use #)
4. Make the different workout block headers an H2 (use ##)
5. For each exercise:
   - Use ONLY the exact exercise names from the list above
   - Do not modify or combine exercise names
   - Include sets, reps, rest time, and important notes
6. Use clear spacing between sections and exercises

Format the plan in a clear, easy-to-follow structure. Use the following format:

# [Workout Title]

[Introduction text]

## Warm-up ([duration])
[Workout description]

[Exercise Name]
- Sets: [number]
- Reps: [number]
- Rest: [time]
- Notes: [any important notes]

[Exercise Name]
- Sets: [number]
- Reps: [number]
- Rest: [time]
- Notes: [any important notes]

...

## Main Workout ([duration])
[Workout description]

[Exercise Name]
- Sets: [number]
- Reps: [number]
- Rest: [time]
- Notes: [any important notes]

[Exercise Name]
- Sets: [number]
- Reps: [number]
- Rest: [time]
- Notes: [any important notes]

...

## Cool-down ([duration])
[Workout description]

[Exercise Name]
- Sets: [number]
- Reps: [number]
- Rest: [time]
- Notes: [any important notes]

[Exercise Name]
- Sets: [number]
- Reps: [number]
- Rest: [time]
- Notes: [any important notes]

...

## Specific Notes and Modifications
[Notes text]

[Closing text]"""

        try:
            # Generate the workout plan using Gemini
            logging.info("Generating workout plan with Gemini API...")
            response = model.generate_content(prompt)
            
            if not response or not response.text:
                logging.error("Empty response from Gemini API")
                raise ValueError("Empty response from Gemini API")
                
            plan_text = response.text
            logging.info("Successfully generated workout plan")
            
            # Process the plan to add video links
            lines = plan_text.split('\n')
            processed_lines = []
            
            for line in lines:
                line = line.strip()
                # Check if the line is an exercise name (not a header, bullet point, or already linked)
                if (line and 
                    not line.startswith(('#', '-', '[')) and 
                    ']' not in line):
                    # Try to find a matching exercise name
                    matching_exercise = None
                    for exercise in exercise_names:
                        if exercise.lower() == line.lower():
                            matching_exercise = exercise
                            logging.info(f"Found exact match for exercise: {exercise}")
                            break
                    
                    if matching_exercise:
                        logging.info(f"Getting video for exercise: {matching_exercise}")
                        video_url, source = get_youtube_video(matching_exercise)
                        if video_url:
                            processed_lines.append(f"[{matching_exercise}]({video_url}) - {source}")
                            logging.info(f"Added video link for {matching_exercise}: {video_url}")
                        else:
                            processed_lines.append(matching_exercise)
                            logging.warning(f"No video found for {matching_exercise}")
                    else:
                        processed_lines.append(line)
                        logging.debug(f"No match found for line: {line}")
                else:
                    processed_lines.append(line)
            
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

if __name__ == "__main__":
    app = WorkoutApp()
    app.mainloop()
