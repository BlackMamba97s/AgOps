def read_text_file(file_name):
    try:
        with open(file_name, 'r') as file:
            data = file.read()
        return data
    except FileNotFoundError:
        return "File not found."