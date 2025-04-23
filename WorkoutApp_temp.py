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