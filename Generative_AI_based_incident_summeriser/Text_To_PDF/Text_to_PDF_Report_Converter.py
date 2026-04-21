from fpdf import FPDF
import tkinter as tk
from tkinter import filedialog, messagebox
import os
import re

title = 'Investigation Report'

# These variables store what the user selects in the GUI
# selected_image_files = all chosen image files
# image_map = connects image names in the report to actual image file paths
selected_report_file = None
selected_image_files = []
image_map = {}

#This function cleans special characters that may not display well in the PDF, Example: curly quotes, long dashes, ellipsis, non-breaking spaces
def clean_text(text):
    replacements = {
        '—': '-',
        '–': '-',
        '‘': "'",
        '’': "'",
        '“': '"',
        '”': '"',
        '…': '...',
        '\u00a0': ' '
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text

# This class builds the PDF layout and formatting. It controls titles, section headings, body text, bullets, 5Ws formatting,
# footer page numbers, image insertion, and the main report parsing logic
class PDF(FPDF):

    # Formats the main report title at the top
    def report_title(self, text):
        self.set_font('helvetica', 'B', 18)
        self.set_text_color(0, 0, 0)
        self.cell(0, 10, text, new_x='LMARGIN', new_y='NEXT', align='C')
        self.ln(4)

    # Formats normal section headings
    def section_title(self, text):
        self.set_font('helvetica', 'B', 14)
        self.set_text_color(0, 0, 0)
        self.cell(0, 8, text, new_x='LMARGIN', new_y='NEXT')
        self.ln(2)

    # Adds page numbers at the bottom of each page
    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.set_text_color(169, 169, 169)
        self.cell(0, 10, f'Page {self.page_no()}', align='C')

    # Formats normal paragraph text in the PDF body
    def body_text(self, text):
        text = clean_text(text)
        self.set_font('times', '', 12)
        self.set_text_color(0, 0, 0)
        self.multi_cell(0, 6, text)
        self.ln(2)

    # Formats a normal bullet point line
    def bullet_point(self, text):
        text = clean_text(text)
        self.set_font('times', '', 12)
        self.cell(5, 6, '-', new_x='RIGHT', new_y='TOP')
        self.multi_cell(0, 6, text)
        self.ln(1)

    # Special formatting for 5Ws lines like:
    def five_w_line(self, label, text):
        label = clean_text(label)
        text = clean_text(text)

        self.set_text_color(0, 0, 0)
        self.set_x(self.l_margin)

        self.set_font('times', 'B', 12)
        label_width = self.get_string_width(f'{label}: ') + 1
        self.cell(label_width, 6, f'{label}:', new_x='RIGHT', new_y='TOP')

        self.set_font('times', '', 12)
        self.multi_cell(0, 6, text)
        self.ln(1)

    # Inserts an image into the PDF using the image name found in the report. If the image name does not exist in image_map, it prints a warning line instead
    def insert_image(self, image_name):
        if image_name not in image_map:
            self.set_font('times', 'I', 12)
            self.cell(
                0,
                8,
                f'[Image not found: {image_name}]',
                new_x='LMARGIN',
                new_y='NEXT'
            )
            self.ln(2)
            return

        image_path = image_map[image_name]

        # If the page is getting full, start a new page before adding the image
        if self.get_y() > 180:
            self.add_page()

        self.image(image_path, w=170)
        self.ln(5)

    # This is the main parser for the report text file
    # It reads each line and decides whether it is: A title, a section heading, a bullet point, a 5Ws item, an image placeholder or a normal paragraph
    def print_report(self, report_file):
        with open(report_file, 'r', encoding='utf-8') as fh:
            lines = fh.readlines()

        paragraph_buffer = []

        # This helper joins normal text lines together into one paragraph
        def flush_paragraph():
            nonlocal paragraph_buffer
            if paragraph_buffer:
                joined = ' '.join(paragraph_buffer).strip()
                if joined:
                    self.body_text(joined)
                paragraph_buffer = []

        for raw_line in lines:
            line = raw_line.strip()

            # Blank line means end of paragraph
            if not line:
                flush_paragraph()
                continue

            # Handles image placeholders like:
            # #IMAGE_HERE: figure 1
            elif line.startswith('#IMAGE_HERE:') or line.startswith('##IMAGE_HERE:'):
                flush_paragraph()
                image_name = line.split(':', 1)[1].strip().lower()

                # This maps placeholder names in the text file, to the internal keys stored in image_map
                if image_name == 'background':
                    self.insert_image('background')
                elif image_name == 'figure 1':
                    self.insert_image('figure_1')
                elif image_name == 'figure 2':
                    self.insert_image('figure_2')
                elif image_name == 'figure 3':
                    self.insert_image('figure_3')
                elif image_name == 'figure 4':
                    self.insert_image('figure_4')
                elif image_name == 'figure 5':
                    self.insert_image('figure_5')
                elif image_name == 'figure 6':
                    self.insert_image('figure_6')
                elif image_name == 'figure 7':
                    self.insert_image('figure_7')
                elif image_name == 'figure 8':
                    self.insert_image('figure_8')
                elif image_name == 'figure 9':
                    self.insert_image('figure_9')
                elif image_name == 'figure 10':
                    self.insert_image('figure_10')
                else:
                    self.insert_image(image_name)

            # Handles main heading lines starting with "# "
            elif line.startswith('# '):
                flush_paragraph()
                heading = line[2:].strip()

                if heading.lower() == title.lower():
                    self.report_title(heading)
                else:
                    self.section_title(heading)

            # Handles section headings starting with "## "
            elif line.startswith('## '):
                flush_paragraph()
                self.section_title(line[3:].strip())

            # Detects 5Ws bullet lines in this exact style:
            # - **Who**: removes "**"
            elif re.match(r"^-\s*\*\*(Who|What|When|Where|Why)\*\*:\s*", line, re.IGNORECASE):
                flush_paragraph()
                match = re.match(r"^-\s*\*\*(Who|What|When|Where|Why)\*\*:\s*(.*)$", line, re.IGNORECASE)
                label = match.group(1)
                content = match.group(2)
                self.five_w_line(label, content)

            # Handles normal bullet points
            elif line.startswith('- '):
                flush_paragraph()
                self.bullet_point(line[2:].strip())

            # Any other text is treated as part of a normal paragraph
            else:
                paragraph_buffer.append(line)

        flush_paragraph()

# Lets the user choose the text/markdown report file from the GUI
def import_report_file():
    global selected_report_file

    file_path = filedialog.askopenfilename(
        title="Select report file",
        filetypes=[("Text files", "*.txt *.md"), ("All files", "*.*")]
    )

    if file_path:
        selected_report_file = file_path
        report_label.config(text=os.path.basename(file_path))

# Lets the user choose one or more image files from the GUI. Then builds image_map so report placeholders can match the correct files
def import_image_files():
    global selected_image_files, image_map

    file_paths = filedialog.askopenfilenames(
        title="Select image files",
        filetypes=[("Image files", "*.png *.jpg *.jpeg"), ("All files", "*.*")]
    )

    if file_paths:
        selected_image_files = list(file_paths)
        image_map = {}

        for path in selected_image_files:
            filename = os.path.basename(path).lower()
            name_without_ext = os.path.splitext(filename)[0]

            # This part maps file names to the keys expected in the report parser
            if name_without_ext == 'background':
                image_map['background'] = path
            elif name_without_ext == 'figure 1':
                image_map['figure_1'] = path
            elif name_without_ext == 'figure 2':
                image_map['figure_2'] = path
            elif name_without_ext == 'figure 3':
                image_map['figure_3'] = path
            elif name_without_ext == 'figure 4':
                image_map['figure_4'] = path
            elif name_without_ext == 'figure 5':
                image_map['figure_5'] = path
            elif name_without_ext == 'figure 6':
                image_map['figure_6'] = path
            elif name_without_ext == 'figure 7':
                image_map['figure_7'] = path
            elif name_without_ext == 'figure 8':
                image_map['figure_8'] = path
            elif name_without_ext == 'figure 9':
                image_map['figure_9'] = path
            elif name_without_ext == 'figure 10':
                image_map['figure_10'] = path
            else:
                image_map[name_without_ext] = path

        image_label.config(text=f"{len(selected_image_files)} image(s) selected")

# This function creates the final PDF file. It checks that a report file was chosen, asks where to save the PDF, then builds the PDF using the PDF class above
def generate_pdf():
    if not selected_report_file:
        messagebox.showerror("Error", "Please select a report file first.")
        return

    save_path = filedialog.asksaveasfilename(
        title="Save PDF as",
        defaultextension=".pdf",
        filetypes=[("PDF files", "*.pdf")]
    )

    if not save_path:
        return

    try:
        pdf = PDF('P', 'mm', 'A4')
        pdf.alias_nb_pages()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.print_report(selected_report_file)
        pdf.output(save_path)

        messagebox.showinfo("Success", f"PDF created successfully:\n{save_path}")

    except Exception as e:
        messagebox.showerror("Error", str(e))


# This final section builds the Tkinter window and it creates the title, buttons, labels, and starts the app loop
root = tk.Tk()
root.title("Text to PDF Converter")
root.geometry("500x250")

title_label = tk.Label(root, text="Investigation Report to PDF", font=("Arial", 14, "bold"))
title_label.pack(pady=15)

report_button = tk.Button(root, text="Import Report File", command=import_report_file, width=25)
report_button.pack(pady=10)

report_label = tk.Label(root, text="No report file selected")
report_label.pack()

image_button = tk.Button(root, text="Import Image Files", command=import_image_files, width=25)
image_button.pack(pady=10)

image_label = tk.Label(root, text="No images selected")
image_label.pack()

generate_button = tk.Button(root, text="Generate PDF", command=generate_pdf, width=25)
generate_button.pack(pady=20)

root.mainloop()