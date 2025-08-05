import json
import os
import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
import cv2


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
        self.classes = ["object"]  # Default class
        self.current_class = 0
        self.scale_factor = 1.0

        # Create control panel window
        self.setup_control_panel()

    def setup_control_panel(self):
        self.control_panel = tk.Tk()
        self.control_panel.title("Annotation Controls")
        self.control_panel.geometry("300x400")

        # Buttons
        tk.Button(self.control_panel, text="Open Folder", command=self.select_folder).pack(fill=tk.X, padx=10, pady=5)
        tk.Button(self.control_panel, text="Open Image", command=self.select_single_image).pack(fill=tk.X, padx=10, pady=5)
        tk.Button(self.control_panel, text="Previous Image", command=self.prev_image).pack(fill=tk.X, padx=10, pady=5)
        tk.Button(self.control_panel, text="Next Image", command=self.next_image).pack(fill=tk.X, padx=10, pady=5)
        tk.Button(self.control_panel, text="Save Annotations", command=self.save_annotations).pack(fill=tk.X, padx=10, pady=5)
        tk.Button(self.control_panel, text="Delete Last Box", command=self.delete_last_box).pack(fill=tk.X, padx=10, pady=5)

        # Class selection
        tk.Label(self.control_panel, text="Current Class:").pack(anchor=tk.W, padx=10, pady=(10, 0))
        self.class_var = tk.StringVar(value=self.classes[self.current_class])
        self.class_dropdown = tk.OptionMenu(self.control_panel, self.class_var, *self.classes, command=self.change_class)
        self.class_dropdown.pack(fill=tk.X, padx=10, pady=5)

        tk.Button(self.control_panel, text="Add New Class", command=self.add_new_class).pack(fill=tk.X, padx=10, pady=5)

        # Export options
        tk.Label(self.control_panel, text="Export:").pack(anchor=tk.W, padx=10, pady=(10, 0))
        tk.Button(self.control_panel, text="Export to YOLO", command=self.export_to_yolo).pack(fill=tk.X, padx=10, pady=5)
        tk.Button(self.control_panel, text="Export to COCO", command=self.export_to_coco).pack(fill=tk.X, padx=10, pady=5)

        # Status display
        tk.Label(self.control_panel, text="Status:").pack(anchor=tk.W, padx=10, pady=(10, 0))
        self.status_var = tk.StringVar(value="Ready")
        tk.Label(self.control_panel, textvariable=self.status_var, wraplength=280).pack(fill=tk.X, padx=10, pady=5)

        # Image info
        self.image_info_var = tk.StringVar(value="No image loaded")
        tk.Label(self.control_panel, textvariable=self.image_info_var, wraplength=280).pack(fill=tk.X, padx=10, pady=5)

        # Close button
        tk.Button(self.control_panel, text="Quit", command=self.quit).pack(fill=tk.X, padx=10, pady=10)

    def select_folder(self):
        folder_path = filedialog.askdirectory(title="Select folder with images")
        if not folder_path:
            return False

        self.folder_path = folder_path
        self.image_files = [f for f in os.listdir(folder_path)
                            if f.lower().endswith(('.png', '.jpg', '.jpeg'))]

        if not self.image_files:
            self.status_var.set("No image files found in the selected folder")
            return False

        self.current_image_index = 0
        self.load_current_image()
        return True

    def select_single_image(self):
        image_path = filedialog.askopenfilename(
            title="Select image file",
            filetypes=[("Image files", "*.jpg *.jpeg *.png")]
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
            self.status_var.set(f"Could not open {self.image_path}")
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
        cv2.imshow("Annotator", self.image)

        # Try to load existing annotations if they exist
        self.load_annotations()

        return True

    def load_annotations(self):
        annotation_path = os.path.splitext(self.image_path)[0] + "_annotations.json"
        if os.path.exists(annotation_path):
            try:
                with open(annotation_path, 'r') as f:
                    data = json.load(f)

                if "boxes" in data:
                    for box_data in data["boxes"]:
                        class_name = box_data.get("class", "object")
                        if class_name not in self.classes:
                            self.classes.append(class_name)
                            self.update_class_dropdown()

                        # Convert back to display coordinates
                        x1 = int(box_data["x1"] * self.scale_factor)
                        y1 = int(box_data["y1"] * self.scale_factor)
                        x2 = int(box_data["x2"] * self.scale_factor)
                        y2 = int(box_data["y2"] * self.scale_factor)

                        self.boxes.append({
                            "box": [(x1, y1), (x2, y2)],
                            "class": class_name
                        })

                    self.draw_boxes()
                    self.status_var.set(f"Loaded {len(self.boxes)} annotations")
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

    def change_class(self, selected_class):
        if selected_class in self.classes:
            self.current_class = self.classes.index(selected_class)

    def add_new_class(self):
        new_class = simpledialog.askstring("Add Class", "Enter new class name:", parent=self.control_panel)
        if new_class and new_class not in self.classes:
            self.classes.append(new_class)
            self.current_class = len(self.classes) - 1
            self.class_var.set(new_class)
            self.update_class_dropdown()
            self.status_var.set(f"Added new class: {new_class}")

    def delete_last_box(self):
        if self.boxes:
            self.boxes.pop()
            self.draw_boxes()
            self.status_var.set(f"Deleted last box. {len(self.boxes)} boxes remaining.")

    def mouse_callback(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self.drawing = True
            self.current_box = [(x, y)]
        elif event == cv2.EVENT_MOUSEMOVE and self.drawing:
            img_copy = self.image.copy()
            cv2.rectangle(img_copy, self.current_box[0], (x, y), (0, 255, 0), 2)
            self.draw_boxes(img_copy)
        elif event == cv2.EVENT_LBUTTONUP and self.drawing:
            self.drawing = False
            self.current_box.append((x, y))
            # Use current selected class
            current_class = self.class_var.get()
            self.boxes.append({
                "box": self.current_box,
                "class": current_class
            })
            self.draw_boxes()
            self.status_var.set(f"Added box with class '{current_class}'. Total: {len(self.boxes)} boxes.")

    def draw_boxes(self, img_copy=None):
        if img_copy is None:
            img_copy = self.image.copy()

        for box in self.boxes:
            cv2.rectangle(img_copy, box["box"][0], box["box"][1], (0, 255, 0), 2)
            label = box["class"]
            cv2.putText(img_copy, label, (box["box"][0][0], box["box"][0][1] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        cv2.imshow("Annotator", img_copy)

    def save_annotations(self):
        if not self.boxes:
            self.status_var.set("No annotations to save")
            return

        # Convert annotations back to original image coordinates
        annotations = {
            "image": os.path.basename(self.image_path),
            "boxes": [
                {
                    "class": box["class"],
                    "x1": int(box["box"][0][0] / self.scale_factor),
                    "y1": int(box["box"][0][1] / self.scale_factor),
                    "x2": int(box["box"][1][0] / self.scale_factor),
                    "y2": int(box["box"][1][1] / self.scale_factor)
                }
                for box in self.boxes
            ]
        }

        save_path = os.path.splitext(self.image_path)[0] + "_annotations.json"
        with open(save_path, 'w') as f:
            json.dump(annotations, f, indent=2)
        self.status_var.set(f"Saved {len(self.boxes)} annotations to {save_path}")

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
        self.control_panel.quit()

    def run(self):
        cv2.namedWindow("Annotator")
        cv2.setMouseCallback("Annotator", self.mouse_callback)

        if not self.image_files:
            self.status_var.set("Please select a folder or image to start")

        # Start the GUI event loop
        self.control_panel.mainloop()


if __name__ == "__main__":
    annotator = SimpleAnnotator()
    annotator.run()