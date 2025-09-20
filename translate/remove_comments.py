# remove_comments.py
"""
Removes comments and unnecessary newlines from Python code.
"""

import re
import ast
from typing import List, Optional
from pathlib import Path


class CommentRemover(ast.NodeTransformer):
    """AST NodeTransformer to remove comments and docstrings."""
    
    def __init__(self, remove_docstrings: bool = True, remove_comments: bool = True):
        self.remove_docstrings = remove_docstrings
        self.remove_comments = remove_comments
    
    def visit_Expr(self, node):
        """Remove expression statements that are just strings (docstrings)."""
        if (self.remove_docstrings and 
            isinstance(node.value, ast.Constant) and 
            isinstance(node.value.value, str)):
            return None
        return node
    
    def visit_FunctionDef(self, node):
        """Remove docstrings from function definitions."""
        node = self.generic_visit(node)
        
        if (self.remove_docstrings and 
            node.body and 
            isinstance(node.body[0], ast.Expr) and 
            isinstance(node.body[0].value, ast.Constant) and 
            isinstance(node.body[0].value.value, str)):
            node.body = node.body[1:]
        
        return node
    
    def visit_ClassDef(self, node):
        """Remove docstrings from class definitions."""
        node = self.generic_visit(node)
        
        if (self.remove_docstrings and 
            node.body and 
            isinstance(node.body[0], ast.Expr) and 
            isinstance(node.body[0].value, ast.Constant) and 
            isinstance(node.body[0].value.value, str)):
            node.body = node.body[1:]
        
        return node
    
    def visit_Module(self, node):
        """Remove docstrings from module."""
        node = self.generic_visit(node)
        
        if (self.remove_docstrings and 
            node.body and 
            isinstance(node.body[0], ast.Expr) and 
            isinstance(node.body[0].value, ast.Constant) and 
            isinstance(node.body[0].value.value, str)):
            node.body = node.body[1:]
        
        return node


def remove_comments_and_docstrings(code: str, remove_docstrings: bool = True, 
                                 remove_comments: bool = True) -> str:
    """
    Remove comments and docstrings from Python code.
    
    Args:
        code: Python code as string
        remove_docstrings: Whether to remove docstrings
        remove_comments: Whether to remove comments
        
    Returns:
        Code with comments and/or docstrings removed
    """
    try:
        # Parse the code into an AST
        tree = ast.parse(code)
        
        # Transform the AST to remove comments and docstrings
        transformer = CommentRemover(remove_docstrings, remove_comments)
        tree = transformer.visit(tree)
        
        # Convert the AST back to code
        cleaned_code = ast.unparse(tree)
        
        # Remove any remaining comments (inline comments)
        if remove_comments:
            # Remove inline comments
            cleaned_code = re.sub(r'#.*$', '', cleaned_code, flags=re.MULTILINE)
            
            # Remove empty lines (optional)
            cleaned_code = re.sub(r'\n\s*\n', '\n', cleaned_code)
        
        return cleaned_code
    
    except SyntaxError as e:
        print(f"Syntax error in code: {e}")
        return code  # Return original code if parsing fails


def remove_comments_from_file(file_path: Path, output_path: Optional[Path] = None, 
                           remove_docstrings: bool = True, remove_comments: bool = True) -> bool:
    """
    Remove comments and docstrings from a Python file.
    
    Args:
        file_path: Path to the input file
        output_path: Path to the output file (if None, overwrites input)
        remove_docstrings: Whether to remove docstrings
        remove_comments: Whether to remove comments
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Read the file
        with open(file_path, 'r', encoding='utf-8') as f:
            code = f.read()
        
        # Remove comments and docstrings
        cleaned_code = remove_comments_and_docstrings(code, remove_docstrings, remove_comments)
        
        # Determine output path
        if output_path is None:
            output_path = file_path
        
        # Write the cleaned code
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(cleaned_code)
        
        return True
    
    except Exception as e:
        print(f"Error processing file {file_path}: {e}")
        return False


def remove_comments_from_directory(directory: Path, output_directory: Optional[Path] = None,
                                remove_docstrings: bool = True, remove_comments: bool = True,
                                recursive: bool = True) -> List[bool]:
    """
    Remove comments and docstrings from all Python files in a directory.
    
    Args:
        directory: Path to the input directory
        output_directory: Path to the output directory (if None, overwrites input files)
        remove_docstrings: Whether to remove docstrings
        remove_comments: Whether to remove comments
        recursive: Whether to process subdirectories recursively
        
    Returns:
        List of success statuses for each file
    """
    results = []
    
    # Create output directory if specified and doesn't exist
    if output_directory and not output_directory.exists():
        output_directory.mkdir(parents=True, exist_ok=True)
    
    # Get all Python files
    python_files = []
    if recursive:
        python_files = list(directory.rglob('*.py'))
    else:
        python_files = list(directory.glob('*.py'))
    
    # Process each file
    for file_path in python_files:
        # Determine relative path for output directory structure
        if output_directory:
            rel_path = file_path.relative_to(directory)
            out_path = output_directory / rel_path
            
            # Create parent directories if needed
            out_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            out_path = None
        
        # Process the file
        result = remove_comments_from_file(file_path, out_path, remove_docstrings, remove_comments)
        results.append(result)
    
    return results


# Example usage
if __name__ == "__main__":
    # Example code with comments and docstrings
    example_code = '''
"""
This is a module docstring.
It will be removed.
"""

def example_function(param1, param2):
    """
    This is a function docstring.
    It will be removed.
    """
    # This is a comment that will be removed
    result = param1 + param2  # Inline comment
    return result

class ExampleClass:
    """Class docstring that will be removed."""
    
    def method(self):
        # Method comment
        pass
'''
    
    # Remove comments and docstrings
    cleaned = remove_comments_and_docstrings(example_code)
    print("Original code:")
    print(example_code)
    print("\nCleaned code:")
    print(cleaned)
    
    # Example with file
    test_file = Path("test_file.py")
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write(example_code)
    
    # Remove comments from file
    success = remove_comments_from_file(test_file)
    print(f"\nFile processing {'successful' if success else 'failed'}")
    
    # Show cleaned file content
    with open(test_file, 'r', encoding='utf-8') as f:
        print(f.read())
    
    # Clean up
    test_file.unlink()