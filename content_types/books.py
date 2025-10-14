import subprocess
from pathlib import Path
from typing import Union


def convert_to_text(file_path: Union[str, Path]) -> str:
    """Convert an .epub or .mobi file to a text file using Calibre's ebook-convert tool.

    Args:
        file_path (str): The path to the .epub or .mobi file.

    Returns:
        str: The path to the converted text file.
    """
    path = Path(file_path)
    text_file_path = path.with_suffix(".txt")
    subprocess.run(["ebook-convert", str(path), str(text_file_path)], check=True)
    return str(text_file_path)


def process_book_attachment(file_path: Union[str, Path]) -> str:
    """Process a book attachment by converting it to text and reading the content.

    Args:
        file_path (str): The path to the book file.

    Returns:
        str: The content of the book as plain text.
    """
    text_file_path = convert_to_text(file_path)
    with open(text_file_path, "r") as file:
        content = file.read()
    return content
