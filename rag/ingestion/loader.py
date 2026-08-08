from pathlib import Path

import frontmatter


def load_markdown(file_path)-> tuple[str, dict]:
    """
    Load a markdown file and return its content and metadata.

    Args:
        file_path (str): The path to the markdown file.

    Returns:
        tuple: A tuple containing the content (str) and metadata (dict) of the markdown file.
    """
    with open(file_path, 'r') as f:
        content = f.read()

    # Parse the frontmatter
    parsed = frontmatter.parse(content)
    return parsed[1], parsed[0]

if __name__ == "__main__":
    # Example usage
    file_path = (
        Path(__file__).resolve().parent.parent
        / "documents" / "engineering-standards" / "engineering-standard-pressure-and-flow-margins.md"
    )
    content, metadata = load_markdown(file_path)
    print("Content:")
    print(content)
    print("\nMetadata:")
    print(metadata)