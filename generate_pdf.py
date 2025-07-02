from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import os

def create_chapter_pdf(text_file_path, output_pdf_path, title):
    doc = SimpleDocTemplate(output_pdf_path, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # Add title to the PDF
    story.append(Paragraph(title, styles['h1']))
    story.append(Spacer(1, 0.2 * 100)) # Add some space after title

    with open(text_file_path, 'r') as f:
        content = f.read()
        # Split content into paragraphs and add them
        paragraphs = content.split('\n\n') # Assuming double newline separates paragraphs
        for para in paragraphs:
            if para.strip(): # Ensure paragraph is not empty
                story.append(Paragraph(para.strip(), styles['Normal']))
                story.append(Spacer(1, 0.1 * 100)) # Add space between paragraphs

    doc.build(story)
    print(f"PDF '{output_pdf_path}' created successfully.")

def create_multi_page_pdf(chapter_files_and_titles, output_pdf_path):
    doc = SimpleDocTemplate(output_pdf_path, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    for i, (text_file_path, title) in enumerate(chapter_files_and_titles):
        # Add chapter title
        story.append(Paragraph(title, styles['h1']))
        story.append(Spacer(1, 0.2 * 100)) # Add some space after title

        with open(text_file_path, 'r') as f:
            content = f.read()
            paragraphs = content.split('\n\n')
            for para in paragraphs:
                if para.strip():
                    story.append(Paragraph(para.strip(), styles['Normal']))
                    story.append(Spacer(1, 0.1 * 100))

        # Add a page break after each chapter, except the last one
        if i < len(chapter_files_and_titles) - 1:
            story.append(Paragraph("<pageBreak/>", styles['Normal']))

    doc.build(story)
    print(f"Multi-page PDF '{output_pdf_path}' created successfully.")

if __name__ == "__main__":
    # This block is for testing or direct execution, not for the bot's primary use.
    # Ensure the output directory exists
    output_dir = "story_pdfs"
    os.makedirs(output_dir, exist_ok=True)

    # Example of creating a single chapter PDF
    # create_chapter_pdf("story_content/chapter_1_the_awakening.txt", "story_pdfs/chapter_1_test.pdf", "Test Chapter 1")

    # Example of creating a multi-page PDF (if needed for testing)
    # chapter_data = [
    #     ("story_content/chapter_1_the_awakening.txt", "Chapter 1: The Awakening"),
    #     ("story_content/chapter_2_the_search.txt", "Chapter 2: The Search")
    # ]
    # create_multi_page_pdf(chapter_data, "story_pdfs/full_story_test.pdf")
