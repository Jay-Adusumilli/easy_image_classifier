import json
import os
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox, colorchooser
import cv2
from PIL import Image, ImageTk


class SimpleAnnotator:
    def __init__(self):
        self.image = None
        self.image_path = None
        self.folder_path = None
        self.image_files = []
        self.current_image_index = 0
        self.original_image = None
        self.boxes = []
        self.current_box = []
        self.drawing = False
        self.classes = ["Object"]  # Default class
        self.class_colors = {}  # Store per-class colors
        self.current_class = 0
        # Neon starting colors
        self.neon_colors = [
            "#39ff14", "#ff073a", "#00f0ff", "#fffb00", "#ff00fb", "#ff9900", "#00ff99", "#ff00a6", "#00fffb"
        ]
        # Assign neon colors to initial classes
        for idx, cls in enumerate(self.classes):
            self.class_colors[cls] = self.neon_colors[idx % len(self.neon_colors)]
        # --- Add these lines to initialize pan offsets ---
        self.offset_x = 0
        self.offset_y = 0

        # Create main window
        self.root = tk.Tk()
        self.root.title("Image Annotation Tool")
        self.root.geometry("1500x900")
        self.root.lift()
        self.root.focus_force()

        # --- Move these lines here, after root is created ---
        self.total_classes_var = tk.StringVar(value="")
        self.total_classes_label = None
        # --- End move ---

        # Layout frames
        self.left_frame = tk.Frame(self.root, width=300, height=900)
        self.left_frame.pack(side=tk.LEFT, fill=tk.Y)
        self.right_frame = tk.Frame(self.root, width=1200, height=900)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.setup_control_panel(self.left_frame)
        self.setup_image_canvas(self.right_frame)

        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.root.mainloop()

    def setup_control_panel(self, parent):
        tk.Button(parent, text="Open Folder", command=self.select_folder).pack(fill=tk.X, padx=10, pady=5)
        tk.Button(parent, text="Open Image", command=self.select_single_image).pack(fill=tk.X, padx=10, pady=5)
        tk.Button(parent, text="Previous Image", command=self.prev_image).pack(fill=tk.X, padx=10, pady=5)
        tk.Button(parent, text="Next Image", command=self.next_image).pack(fill=tk.X, padx=10, pady=5)
        tk.Button(parent, text="Save Annotations", command=self.save_annotations).pack(fill=tk.X, padx=10, pady=5)
        # Remove Delete Last Box button
        # Add Delete Selected Annotation button (disabled by default)
        self.delete_selected_btn = tk.Button(parent, text="Delete Selected Annotation", command=self.delete_selected_annotation, state=tk.DISABLED)
        self.delete_selected_btn.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(parent, text="Current Class:").pack(anchor=tk.W, padx=10, pady=(10, 0))
        self.class_var = tk.StringVar(value=self.classes[self.current_class])
        self.class_dropdown = tk.OptionMenu(parent, self.class_var, *self.classes, command=self.change_class)
        self.class_dropdown.pack(fill=tk.X, padx=10, pady=5)
        tk.Button(parent, text="Add New Class", command=self.add_new_class).pack(fill=tk.X, padx=10, pady=5)
        # --- Move annotation mode radio buttons here ---
        self.annotation_mode = tk.StringVar(value="rectangle")
        tk.Label(parent, text="Annotation Mode:").pack(anchor=tk.W, padx=10, pady=(10, 0))
        mode_frame = tk.Frame(parent)
        mode_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Radiobutton(mode_frame, text="Rectangle", variable=self.annotation_mode, value="rectangle").pack(side=tk.LEFT)
        tk.Radiobutton(mode_frame, text="Circle", variable=self.annotation_mode, value="circle").pack(side=tk.LEFT)
        # --- End move ---
        tk.Label(parent, text="Status:").pack(anchor=tk.W, padx=10, pady=(10, 0))
        self.status_var = tk.StringVar(value="Ready")
        self.status_label = tk.Label(parent, textvariable=self.status_var, wraplength=280, anchor="w", justify="left", width=40)
        self.status_label.pack(fill=tk.X, padx=10, pady=5)
        self.image_info_var = tk.StringVar(value="No image loaded")
        tk.Label(parent, textvariable=self.image_info_var, wraplength=280).pack(fill=tk.X, padx=10, pady=5)
        self.legend_frame = tk.Frame(parent)
        self.legend_frame.pack(fill=tk.X, padx=10, pady=5)
        self.update_legend()
        # --- Only create the label here, don't re-create the StringVar ---
        self.total_classes_label = tk.Label(parent, textvariable=self.total_classes_var, font=("Arial", 10, "italic"))
        self.total_classes_label.pack(fill=tk.X, padx=10, pady=(0, 10))
        tk.Button(parent, text="Quit", command=self.save_and_quit).pack(fill=tk.X, padx=10, pady=10)

    def update_legend(self):
        for widget in self.legend_frame.winfo_children():
            widget.destroy()
        tk.Label(self.legend_frame, text="Legend:", font=("Arial", 10, "bold")).pack(anchor=tk.W)
        # --- Count annotations per class ---
        class_counts = {cls: 0 for cls in self.classes}
        for box in self.boxes:
            if box["class"] in class_counts:
                class_counts[box["class"]] += 1
        if hasattr(self, "circles"):
            for circle in self.circles:
                if circle["class"] in class_counts:
                    class_counts[circle["class"]] += 1
        # --- Show legend with counts ---
        for idx, cls in enumerate(self.classes):
            color = self.class_colors.get(cls, self.neon_colors[idx % len(self.neon_colors)])
            legend_item = tk.Frame(self.legend_frame)
            legend_item.pack(anchor=tk.W, fill=tk.X)
            color_box = tk.Canvas(legend_item, width=20, height=20)
            color_box.create_rectangle(0, 0, 20, 20, fill=color, outline=color)
            color_box.pack(side=tk.LEFT)
            tk.Label(legend_item, text=f"{cls} ({class_counts.get(cls,0)})", font=("Arial", 10)).pack(side=tk.LEFT, padx=5)
            edit_btn = tk.Button(legend_item, text="Edit Color", command=lambda c=cls: self.edit_class_color(c), width=8)
            edit_btn.pack(side=tk.LEFT, padx=2)
        # --- Show total classes below legend ---
        self.total_classes_var.set(f"Total classes: {len(self.classes)}")

    def edit_class_color(self, cls):
        initial_color = self.class_colors.get(cls, "#39ff14")
        color_code = colorchooser.askcolor(title=f"Choose color for '{cls}'", initialcolor=initial_color)
        if color_code and color_code[1]:
            self.class_colors[cls] = color_code[1]
            self.update_legend()
            self.display_image()

    def get_class_color(self, cls):
        # Use user-set color if available, else neon, else fallback
        if cls in self.class_colors:
            return self.class_colors[cls]
        idx = self.classes.index(cls) if cls in self.classes else 0
        return self.neon_colors[idx % len(self.neon_colors)]

    def save_and_quit(self):
        self.save_annotations()
        self.root.destroy()

    def setup_image_canvas(self, parent):
        self.canvas = tk.Canvas(parent, width=1200, height=900, bg='black')
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind('<MouseWheel>', self.on_zoom)
        # Left click for selection and panning
        self.canvas.bind('<ButtonPress-1>', self.on_canvas_click)
        self.canvas.bind('<B1-Motion>', self.on_pan_move)
        self.canvas.bind('<ButtonRelease-1>', self.on_pan_end)
        # Right click for box drawing
        self.canvas.bind('<ButtonPress-3>', self.on_draw_start)
        self.canvas.bind('<B3-Motion>', self.on_draw_move)
        self.canvas.bind('<ButtonRelease-3>', self.on_draw_end)
        # Shift+Right click for circle drawing
        self.canvas.bind('<Shift-ButtonPress-3>', self.on_circle_start)
        self.canvas.bind('<Shift-B3-Motion>', self.on_circle_move)
        self.canvas.bind('<Shift-ButtonRelease-3>', self.on_circle_end)

    def on_zoom(self, event):
        # Zoom in/out with mouse wheel, clamp scale
        prev_scale = self.scale_factor
        factor = 1.1 if event.delta > 0 else 0.9
        self.scale_factor = max(0.1, min(5.0, self.scale_factor * factor))
        if abs(self.scale_factor - prev_scale) > 0.01:
            self.update_resized_image()
            self.display_image()

    def on_pan_start(self, event):
        self.drag_start = (event.x, event.y)
        self.last_offset_x = self.offset_x
        self.last_offset_y = self.offset_y

    def on_pan_move(self, event):
        if self.drag_start:
            dx = event.x - self.drag_start[0]
            dy = event.y - self.drag_start[1]
            self.offset_x = self.last_offset_x + dx
            self.offset_y = self.last_offset_y + dy
            self.display_image()

    def on_pan_end(self, event):
        self.drag_start = None
        self.display_image()

    def on_draw_start(self, event):
        if self.annotation_mode.get() == "rectangle":
            self.drawing = True
            # Always record in original image space
            self.current_box = [(int((event.x - self.offset_x) / self.scale_factor), int((event.y - self.offset_y) / self.scale_factor))]
        elif self.annotation_mode.get() == "circle":
            self.drawing = True
            self.current_circle = [(int((event.x - self.offset_x) / self.scale_factor), int((event.y - self.offset_y) / self.scale_factor))]

    def on_draw_move(self, event):
        if not self.drawing:
            return
        if self.annotation_mode.get() == "rectangle":
            x1, y1 = self.current_box[0]
            x2 = int((event.x - self.offset_x) / self.scale_factor)
            y2 = int((event.y - self.offset_y) / self.scale_factor)
            self.display_image(temp_box=[(x1, y1), (x2, y2)])
        elif self.annotation_mode.get() == "circle":
            x1, y1 = self.current_circle[0]
            x2 = int((event.x - self.offset_x) / self.scale_factor)
            y2 = int((event.y - self.offset_y) / self.scale_factor)
            self.display_image(temp_circle=[(x1, y1), (x2, y2)])

    def on_draw_end(self, event):
        if not self.drawing:
            return
        self.drawing = False
        if self.annotation_mode.get() == "rectangle":
            x1, y1 = self.current_box[0]
            x2 = int((event.x - self.offset_x) / self.scale_factor)
            y2 = int((event.y - self.offset_y) / self.scale_factor)
            self.boxes.append({
                "box": [(x1, y1), (x2, y2)],
                "class": self.class_var.get()
            })
            self.display_image()
            self.update_legend()  # <-- update counts
            self.status_var.set(f"Added box with class '{self.class_var.get()}'. Total: {len(self.boxes)} boxes.")
        elif self.annotation_mode.get() == "circle":
            x1, y1 = self.current_circle[0]
            x2 = int((event.x - self.offset_x) / self.scale_factor)
            y2 = int((event.y - self.offset_y) / self.scale_factor)
            if not hasattr(self, 'circles'):
                self.circles = []
            self.circles.append({
                "circle": [(x1, y1), (x2, y2)],
                "class": self.class_var.get()
            })
            self.display_image()
            self.update_legend()  # <-- update counts
            self.status_var.set(f"Added circle with class '{self.class_var.get()}'. Total: {len(self.circles)} circles.")

    # --- Circle annotation handlers ---
    def on_circle_start(self, event):
        self.drawing = True
        self.current_circle = [(int((event.x - self.offset_x) / self.scale_factor), int((event.y - self.offset_y) / self.scale_factor))]

    def on_circle_move(self, event):
        if not self.drawing:
            return
        x1, y1 = self.current_circle[0]
        x2 = int((event.x - self.offset_x) / self.scale_factor)
        y2 = int((event.y - self.offset_y) / self.scale_factor)
        self.display_image(temp_circle=[(x1, y1), (x2, y2)])

    def on_circle_end(self, event):
        if not self.drawing:
            return
        self.drawing = False
        x1, y1 = self.current_circle[0]
        x2 = int((event.x - self.offset_x) / self.scale_factor)
        y2 = int((event.y - self.offset_y) / self.scale_factor)
        if not hasattr(self, 'circles'):
            self.circles = []
        self.circles.append({
            "circle": [(x1, y1), (x2, y2)],
            "class": self.class_var.get()
        })
        self.display_image()
        self.update_legend()  # <-- update counts
        self.status_var.set(f"Added circle with class '{self.class_var.get()}'. Total: {len(self.circles)} circles.")

    # Update display_image to render circles
    def display_image(self, temp_box=None, temp_circle=None):
        if self.resized_img is None:
            return
        self.tk_img = ImageTk.PhotoImage(self.resized_img)
        self.canvas.delete("all")
        self.canvas_image_id = self.canvas.create_image(self.offset_x, self.offset_y, anchor=tk.NW, image=self.tk_img)
        # Draw boxes
        for box in self.boxes:
            (x1, y1), (x2, y2) = box["box"]
            color = self.get_class_color(box["class"])
            # Convert from original image space to display space
            x1_disp = int(x1 * self.scale_factor) + self.offset_x
            y1_disp = int(y1 * self.scale_factor) + self.offset_y
            x2_disp = int(x2 * self.scale_factor) + self.offset_x
            y2_disp = int(y2 * self.scale_factor) + self.offset_y
            self.canvas.create_rectangle(x1_disp, y1_disp, x2_disp, y2_disp, outline=color, width=2)
        # Draw circles
        if hasattr(self, 'circles'):
            for circle in self.circles:
                (x1, y1), (x2, y2) = circle["circle"]
                color = self.get_class_color(circle["class"])
                x1_disp = int(x1 * self.scale_factor) + self.offset_x
                y1_disp = int(y1 * self.scale_factor) + self.offset_y
                x2_disp = int(x2 * self.scale_factor) + self.offset_x
                y2_disp = int(y2 * self.scale_factor) + self.offset_y
                r = int(((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5 * self.scale_factor)
                self.canvas.create_oval(x1_disp - r, y1_disp - r, x1_disp + r, y1_disp + r, outline=color, width=2)
        # Draw temp box
        if temp_box:
            (x1, y1), (x2, y2) = temp_box
            color = self.get_class_color(self.class_var.get())
            x1_disp = int(x1 * self.scale_factor) + self.offset_x
            y1_disp = int(y1 * self.scale_factor) + self.offset_y
            x2_disp = int(x2 * self.scale_factor) + self.offset_x
            y2_disp = int(y2 * self.scale_factor) + self.offset_y
            self.canvas.create_rectangle(x1_disp, y1_disp, x2_disp, y2_disp, outline=color, width=2, dash=(4, 2))
        # Draw temp circle
        if temp_circle:
            (x1, y1), (x2, y2) = temp_circle
            color = self.get_class_color(self.class_var.get())
            x1_disp = int(x1 * self.scale_factor) + self.offset_x
            y1_disp = int(y1 * self.scale_factor) + self.offset_y
            x2_disp = int(x2 * self.scale_factor) + self.offset_x
            y2_disp = int(y2 * self.scale_factor) + self.offset_y
            r = int(((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5 * self.scale_factor)
            self.canvas.create_oval(x1_disp - r, y1_disp - r, x1_disp + r, y1_disp + r, outline=color, width=2, dash=(4, 2))

    def select_folder(self):
        folder_path = filedialog.askdirectory(title="Select folder with images")
        if not folder_path:
            return False
        self.folder_path = folder_path
        self.image_files = [f for f in os.listdir(folder_path)
                            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.tif', '.tiff'))]
        if not self.image_files:
            self.status_var.set("No image files found in the selected folder")
            return False
        self.current_image_index = 0
        self.load_current_image()
        return True

    def select_single_image(self):
        image_path = filedialog.askopenfilename(
            title="Select image file",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.tif *.tiff")]
        )
        if not image_path:
            return False

        self.folder_path = os.path.dirname(image_path)
        self.image_path = image_path
        self.image_files = [os.path.basename(image_path)]
        self.current_image_index = 0
        self.load_current_image()
        return True

    def load_current_image(self):
        if not self.image_files or self.current_image_index >= len(self.image_files):
            self.status_var.set("No image to load")
            return False

        # Clear previous annotations
        self.boxes = []

        # Load current image
        current_file = self.image_files[self.current_image_index]
        self.image_path = os.path.join(self.folder_path, current_file)
        self.original_image = cv2.imread(self.image_path)

        if self.original_image is None:
            self.status_var.set("Failed to load image")
            return False

        # Resize image to a reasonable size for display
        h, w = self.original_image.shape[:2]
        max_dimension = 1200  # Maximum dimension for display

        if max(h, w) > max_dimension:
            self.scale_factor = max_dimension / max(h, w)
            new_w = int(w * self.scale_factor)
            new_h = int(h * self.scale_factor)
            self.image = cv2.resize(self.original_image, (new_w, new_h))
        else:
            self.scale_factor = 1.0
            self.image = self.original_image.copy()

        # Update image info
        self.image_info_var.set(f"Image: {current_file} ({self.current_image_index + 1}/{len(self.image_files)})\n"
                                f"Dimensions: {w}x{h}\nScale: {self.scale_factor:.2f}")

        # Display image
        self.update_resized_image()
        self.display_image()

        # Try to load existing annotations if they exist
        self.load_annotations()
        self.display_image()  # <-- Ensure annotations are shown after loading

        # Reset pan offset so annotations are visible
        self.offset_x = 0
        self.offset_y = 0

        return True

    def load_annotations(self):
        annotation_path = os.path.join(self.folder_path, "all_annotations.json")
        self.boxes = []
        self.circles = []
        if not os.path.exists(annotation_path):
            return
        try:
            with open(annotation_path, 'r') as f:
                data = json.load(f)
            # Load classes and colors
            if "classes" in data:
                self.classes = data["classes"]
                self.update_class_dropdown()
            if "colors" in data:
                self.class_colors = data["colors"]
            # Load current image annotations
            img_name = os.path.basename(self.image_path)
            img_ann = data.get("images", {}).get(img_name, {})
            for cls, ann in img_ann.items():
                for box in ann.get("boxes", []):
                    x1, y1, x2, y2 = box
                    # Store in original image space
                    self.boxes.append({
                        "box": [(x1, y1), (x2, y2)],
                        "class": cls
                    })
                for circle in ann.get("circles", []):
                    x1, y1, x2, y2 = circle
                    self.circles.append({
                        "circle": [(x1, y1), (x2, y2)],
                        "class": cls
                    })
            self.status_var.set(f"Loaded annotations for {img_name}")
            self.update_legend()  # <-- update counts
        except Exception as e:
            self.status_var.set(f"Error loading annotations: {e}")

    def next_image(self):
        if not self.image_files:
            return

        if self.current_image_index < len(self.image_files) - 1:
            self.current_image_index += 1
            self.load_current_image()
        else:
            self.status_var.set("Already at the last image")

    def prev_image(self):
        if not self.image_files:
            return

        if self.current_image_index > 0:
            self.current_image_index -= 1
            self.load_current_image()
        else:
            self.status_var.set("Already at the first image")

    def update_class_dropdown(self):
        menu = self.class_dropdown["menu"]
        menu.delete(0, "end")
        for cls in self.classes:
            menu.add_command(label=cls, command=lambda value=cls: self.class_var.set(value))
        self.update_legend()

    def change_class(self, selected_class):
        if selected_class in self.classes:
            self.current_class = self.classes.index(selected_class)

    def add_new_class(self):
        new_class = simpledialog.askstring("Add Class", "Enter new class name:", parent=self.root)
        if new_class and new_class not in self.classes:
            self.classes.append(new_class)
            # Assign next neon color
            self.class_colors[new_class] = self.neon_colors[len(self.classes)-1 % len(self.neon_colors)]
            self.current_class = len(self.classes) - 1
            self.class_var.set(new_class)
            self.update_class_dropdown()
            self.status_var.set(f"Added new class: {new_class}")

    def delete_selected_annotation(self):
        if not self.selected_annotation:
            return
        typ, idx = self.selected_annotation
        if typ == "box":
            del self.boxes[idx]
        elif typ == "circle" and hasattr(self, "circles"):
            del self.circles[idx]
        self.selected_annotation = None
        self.delete_selected_btn.config(state=tk.DISABLED)
        self.display_image()
        self.update_legend()  # <-- update counts
        self.status_var.set("Annotation deleted.")

    def mouse_callback(self, event, x, y, flags, param):
        # Right mouse button for drawing boxes
        if event == cv2.EVENT_RBUTTONDOWN:
            self.drawing = True
            self.current_box = [(x, y)]
        elif event == cv2.EVENT_MOUSEMOVE and self.drawing and flags & cv2.EVENT_FLAG_RBUTTON:
            img_copy = self.image.copy()
            cv2.rectangle(img_copy, self.current_box[0], (x, y), (0, 255, 0), 2)
            self.draw_boxes(img_copy)
        elif event == cv2.EVENT_RBUTTONUP and self.drawing:
            self.drawing = False
            self.current_box.append((x, y))
            current_class = self.class_var.get()
            self.boxes.append({
                "box": self.current_box,
                "class": current_class
            })
            self.draw_boxes()
            self.status_var.set(f"Added box with class '{current_class}'. Total: {len(self.boxes)} boxes.")

        # Left mouse button for panning (dragging)
        elif event == cv2.EVENT_LBUTTONDOWN:
            self.drag_start = (x, y)
        elif event == cv2.EVENT_MOUSEMOVE and self.drag_start is not None and flags & cv2.EVENT_FLAG_LBUTTON:
            dx = x - self.drag_start[0]
            dy = y - self.drag_start[1]
            self.offset_x += dx
            self.offset_y += dy
            self.drag_start = (x, y)
            self.display_image()
        elif event == cv2.EVENT_LBUTTONUP:
            self.drag_start = None

    def draw_boxes(self, img_copy=None):
        # This function is now a no-op, as all drawing is handled by Tkinter canvas
        pass

    def save_annotations(self):
        annotation_path = os.path.join(self.folder_path, "all_annotations.json")
        data = {}
        if os.path.exists(annotation_path):
            try:
                with open(annotation_path, 'r') as f:
                    data = json.load(f)
            except Exception:
                data = {}
        data["classes"] = self.classes
        data["colors"] = self.class_colors
        if "images" not in data:
            data["images"] = {}
        img_name = os.path.basename(self.image_path)
        img_ann = {}
        for cls in self.classes:
            img_ann[cls] = {"boxes": [], "circles": []}
        for box in self.boxes:
            cls = box["class"]
            # Save coordinates in original image space
            img_ann[cls]["boxes"].append([
                int(box["box"][0][0]),
                int(box["box"][0][1]),
                int(box["box"][1][0]),
                int(box["box"][1][1])
            ])
        if hasattr(self, "circles"):
            for circle in self.circles:
                cls = circle["class"]
                img_ann[cls]["circles"].append([
                    int(circle["circle"][0][0]),
                    int(circle["circle"][0][1]),
                    int(circle["circle"][1][0]),
                    int(circle["circle"][1][1])
                ])
        data["images"][img_name] = img_ann
        with open(annotation_path, 'w') as f:
            json.dump(data, f, indent=2)
        self.status_var.set(f"Saved annotations for {img_name} to {annotation_path}")

    def export_to_yolo(self):
        if not self.folder_path:
            self.status_var.set("No folder selected")
            return

        # Create output directory in the same folder as images
        output_dir = os.path.join(self.folder_path, "yolo_export")
        os.makedirs(output_dir, exist_ok=True)

        # Create classes.txt file
        classes_file = os.path.join(output_dir, "classes.txt")
        with open(classes_file, 'w') as f:
            f.write("\n".join(self.classes))

        # Create directories
        images_dir = os.path.join(output_dir, "images")
        labels_dir = os.path.join(output_dir, "labels")
        os.makedirs(images_dir, exist_ok=True)
        os.makedirs(labels_dir, exist_ok=True)

        # Import shutil once
        import shutil

        # Process all images
        count = 0
        for img_file in self.image_files:
            base_name = os.path.splitext(img_file)[0]
            json_path = os.path.join(self.folder_path, f"{base_name}_annotations.json")

            if not os.path.exists(json_path):
                continue

            # Copy the image file
            src_img = os.path.join(self.folder_path, img_file)
            dst_img = os.path.join(images_dir, img_file)
            if os.path.exists(src_img):
                shutil.copy2(src_img, dst_img)

            # Read image dimensions
            img = cv2.imread(src_img)
            if img is None:
                continue

            img_h, img_w = img.shape[:2]

            # Create YOLO annotation
            yolo_file = os.path.join(labels_dir, f"{base_name}.txt")

            try:
                with open(json_path, 'r') as f:
                    data = json.load(f)

                if "boxes" not in data:
                    continue

                with open(yolo_file, 'w') as f:
                    for box in data["boxes"]:
                        if "class" not in box or not all(k in box for k in ["x1", "y1", "x2", "y2"]):
                            continue

                        class_id = self.classes.index(box["class"])
                        x1, y1, x2, y2 = box["x1"], box["y1"], box["x2"], box["y2"]

                        # Normalize coordinates (YOLO format)
                        x_center = ((x1 + x2) / 2) / img_w
                        y_center = ((y1 + y2) / 2) / img_h
                        width = (x2 - x1) / img_w
                        height = (y2 - y1) / img_h

                        f.write(f"{class_id} {x_center} {y_center} {width} {height}\n")
                count += 1
            except Exception as e:
                self.status_var.set(f"Error processing {json_path}: {e}")
                continue

        # Create dataset.yaml for easy use with YOLOv5/v8
        yaml_path = os.path.join(output_dir, "dataset.yaml")
        with open(yaml_path, 'w') as f:
            f.write(f"path: {output_dir}\n")
            f.write("train: images\n")
            f.write("val: images\n\n")
            f.write(f"nc: {len(self.classes)}\n")
            f.write(f"names: {self.classes}\n")

        self.status_var.set(f"Exported {count} annotations to YOLO format in {output_dir}")

    def export_to_coco(self):
        if not self.folder_path:
            self.status_var.set("No folder selected")
            return

        # Create output directory
        output_dir = os.path.join(self.folder_path, "coco_export")
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, "annotations.json")

        coco_data = {
            "images": [],
            "annotations": [],
            "categories": []
        }

        # Create categories
        for idx, class_name in enumerate(self.classes):
            coco_data["categories"].append({
                "id": idx + 1,
                "name": class_name,
                "supercategory": "none"
            })

        # Import shutil once
        import shutil

        # Process all images
        annotation_id = 1
        for img_id, img_file in enumerate(self.image_files):
            base_name = os.path.splitext(img_file)[0]
            json_path = os.path.join(self.folder_path, f"{base_name}_annotations.json")

            if not os.path.exists(json_path):
                continue

            # Copy the image file to output directory
            src_img = os.path.join(self.folder_path, img_file)
            dst_img = os.path.join(output_dir, img_file)
            if os.path.exists(src_img):
                shutil.copy2(src_img, dst_img)

            # Read image dimensions
            img = cv2.imread(src_img)
            if img is None:
                continue

            h, w = img.shape[:2]

            # Add image to COCO format
            coco_data["images"].append({
                "id": img_id + 1,
                "width": w,
                "height": h,
                "file_name": img_file
            })

            try:
                with open(json_path, 'r') as f:
                    data = json.load(f)

                if "boxes" not in data:
                    continue

                for box in data["boxes"]:
                    if "class" not in box or not all(k in box for k in ["x1", "y1", "x2", "y2"]):
                        continue

                    x1, y1, x2, y2 = box["x1"], box["y1"], box["x2"], box["y2"]
                    width = x2 - x1
                    height = y2 - y1

                    coco_data["annotations"].append({
                        "id": annotation_id,
                        "image_id": img_id + 1,
                        "category_id": self.classes.index(box["class"]) + 1,
                        "bbox": [x1, y1, width, height],
                        "area": width * height,
                        "segmentation": [],
                        "iscrowd": 0
                    })
                    annotation_id += 1
            except Exception as e:
                self.status_var.set(f"Error processing {json_path}: {e}")
                continue

        with open(output_file, 'w') as f:
            json.dump(coco_data, f, indent=2)

        self.status_var.set(f"Exported annotations to COCO format in {output_dir}")

    def quit(self):
        cv2.destroyAllWindows()
        self.root.destroy()

    def run(self):
        pass  # Remove all code from run to prevent extra window

    def update_resized_image(self):
        if self.original_image is None:
            self.resized_img = None
            return
        h, w = self.original_image.shape[:2]
        new_w = int(w * self.scale_factor)
        new_h = int(h * self.scale_factor)
        img = Image.fromarray(cv2.cvtColor(self.original_image, cv2.COLOR_BGR2RGB))
        # Use correct resampling constant for Pillow
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        self.resized_img = img

    def on_canvas_click(self, event):
        # Check if click is inside any box or circle
        x = int((event.x - self.offset_x) / self.scale_factor)
        y = int((event.y - self.offset_y) / self.scale_factor)
        found = None
        # Check boxes
        for idx, box in enumerate(self.boxes):
            (x1, y1), (x2, y2) = box["box"]
            if min(x1, x2) <= x <= max(x1, x2) and min(y1, y2) <= y <= max(y1, y2):
                found = ("box", idx)
                break
        # Check circles
        if not found and hasattr(self, "circles"):
            for idx, circle in enumerate(self.circles):
                (cx1, cy1), (cx2, cy2) = circle["circle"]
                r = int(((cx2-cx1)**2 + (cy2-cy1)**2)**0.5)
                if ((x - cx1)**2 + (y - cy1)**2) <= r**2:
                    found = ("circle", idx)
                    break
        self.selected_annotation = found
        if found:
            self.delete_selected_btn.config(state=tk.NORMAL)
            self.status_var.set("Annotation selected. Click delete to remove.")
        else:
            self.delete_selected_btn.config(state=tk.DISABLED)
            self.status_var.set("No annotation selected.")
        # Start panning
        self.on_pan_start(event)

if __name__ == "__main__":
    annotator = SimpleAnnotator()
    annotator.run()
